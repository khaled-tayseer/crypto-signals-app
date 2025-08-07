# main.py - Crypto Advisor with fallback and Telegram alerts
import streamlit as st
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from time import sleep
import os
from datetime import datetime

st.set_page_config(page_title="Crypto Advisor - متقدم", layout="centered")
st.title("🔎 Crypto Advisor - توصيات و تنبيهات")

COINS = {
    "Bitcoin (BTC)": {"cg":"bitcoin","cc":"bitcoin"},
    "Ethereum (ETH)": {"cg":"ethereum","cc":"ethereum"},
    "Binance Coin (BNB)": {"cg":"binancecoin","cc":"binance-coin"},
    "Solana (SOL)": {"cg":"solana","cc":"solana"},
    "Ripple (XRP)": {"cg":"ripple","cc":"ripple"}
}

col1, col2 = st.columns([2,1])

with col1:
    coin_label = st.selectbox("اختر العملة", list(COINS.keys()), index=0)
    coin_cg = COINS[coin_label]["cg"]
    coin_cc = COINS[coin_label]["cc"]
    days = st.selectbox("مدة البيانات (أيام)", [1,3,7,14,30], index=2)
    interval = st.selectbox("الفاصل الزمني", ["hourly","daily"], index=0)

with col2:
    st.write("إعدادات (تلقائية — تقدر تعدل الأوزان)")
    auto_tp_sl = st.checkbox("اقتراح TP/SL تلقائي", value=True)
    weight_rsi = st.slider("وزن RSI", 0.0, 2.0, 1.0, 0.1)
    weight_macd = st.slider("وزن MACD", 0.0, 2.0, 1.0, 0.1)
    weight_ema = st.slider("وزن EMA", 0.0, 2.0, 0.8, 0.1)
    alert_threshold = st.slider("عتبة اشعار (score >= )", 0.5, 3.0, 1.5, 0.1)
    st.markdown("**ملحوظة:** لو درجة الثقة أعلى من العتبة هيبعت اشعار تلقائيًا لبوت التليجرام (لو مفعل).")

# Telegram config from environment (add these in Streamlit Cloud)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

def fetch_coingecko(coin, days, interval, tries=3):
    url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
    params = {"vs_currency":"usd", "days": days, "interval": interval}
    for attempt in range(tries):
        try:
            r = requests.get(url, params=params, timeout=12)
            data = r.json()
            if isinstance(data, dict) and "prices" in data and len(data["prices"])>0:
                return {"source":"coingecko", "data": data}
            sleep(1)
        except Exception:
            sleep(1)
    return None

def fetch_coincap(coin_cc, days, interval):
    # CoinCap history endpoint: /assets/{id}/history?interval=d1
    # We'll fetch daily history if interval == 'daily', otherwise use hourly-ish fallback via market price endpoint.
    try:
        if interval == "daily":
            url = f"https://api.coincap.io/v2/assets/{coin_cc}/history"
            params = {"interval":"d1", "start": 0, "end": int(pd.Timestamp.utcnow().timestamp()*1000)}
            r = requests.get(url, params=params, timeout=12)
            j = r.json()
            # CoinCap returns data list of {priceUsd, time, date}
            if "data" in j and len(j["data"])>0:
                prices = []
                times = []
                for item in j["data"][-(days*24):]:
                    prices.append(float(item.get("priceUsd", 0)))
                    times.append(int(pd.to_datetime(item.get("date")).timestamp()*1000))
                return {"source":"coincap", "data": {"prices": list(zip(times, prices))}}
        # fallback: use the single current price repeatedly (less ideal)
        url2 = f"https://api.coincap.io/v2/assets/{coin_cc}"
        r2 = requests.get(url2, timeout=10)
        j2 = r2.json()
        if "data" in j2:
            price = float(j2["data"].get("priceUsd", 0))
            now_ms = int(pd.Timestamp.utcnow().timestamp()*1000)
            prices = [(now_ms - i*3600000, price) for i in range( max(1, hours_from_days(days)) )][::-1]
            return {"source":"coincap", "data": {"prices": prices}}
    except Exception:
        return None
    return None

def hours_from_days(d):
    return max(1, int(d*24))

def compute_indicators(df):
    df = df.copy()
    window = 14
    delta = df['price'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ma_up = up.ewm(com=(window-1), adjust=False).mean()
    ma_down = down.ewm(com=(window-1), adjust=False).mean()
    rs = ma_up / ma_down
    df['rsi'] = 100 - (100 / (1 + rs))
    df['ema_short'] = df['price'].ewm(span=12, adjust=False).mean()
    df['ema_long'] = df['price'].ewm(span=26, adjust=False).mean()
    df['macd'] = df['ema_short'] - df['ema_long']
    df['macd_signal'] = df['macd'].ewm(span=9, adjust=False).mean()
    roll = df['price'].rolling(window=20)
    df['bb_mid'] = roll.mean()
    df['bb_std'] = roll.std()
    df['bb_upper'] = df['bb_mid'] + (2 * df['bb_std'])
    df['bb_lower'] = df['bb_mid'] - (2 * df['bb_std'])
    df['ret'] = np.log(df['price'] / df['price'].shift(1))
    vol = df['ret'].std() * np.sqrt(365) if df['ret'].dropna().shape[0] > 5 else 0.02
    return df, vol

def signal_from_indicators(latest, weights):
    score = 0.0
    # RSI
    if latest['rsi'] < 30:
        score += 1.0 * weights['rsi']
    elif latest['rsi'] > 70:
        score -= 1.0 * weights['rsi']
    # MACD
    if latest['macd'] > latest['macd_signal']:
        score += 1.0 * weights['macd']
    else:
        score -= 0.8 * weights['macd']
    # EMA trend
    if latest['ema_short'] > latest['ema_long']:
        score += 0.6 * weights['ema']
    else:
        score -= 0.6 * weights['ema']
    # Bollinger
    if not np.isnan(latest.get('bb_lower', np.nan)):
        if latest['price'] < latest['bb_lower']:
            score += 0.5
        elif latest['price'] > latest['bb_upper']:
            score -= 0.5
    if score >= 1.0:
        reco = "BUY"
    elif score <= -1.0:
        reco = "SELL"
    else:
        reco = "HOLD"
    return reco, score

def suggest_tp_sl(price, vol, reco):
    daily_vol = vol / np.sqrt(252) if vol>0 else 0.02
    price_std = price * daily_vol
    if reco == "BUY":
        sl = max(price - price_std*1.0, 0.0)
        tp = price + price_std*2.0
    elif reco == "SELL":
        sl = price + price_std*1.0
        tp = max(price - price_std*2.0, 0.0)
    else:
        sl = price - price_std*1.0
        tp = price + price_std*1.0
    sl_pct = (price - sl)/price * 100 if price>0 else 0
    tp_pct = (tp - price)/price * 100 if price>0 else 0
    return tp, sl, tp_pct, sl_pct

def send_telegram_message(token, chat_id, text):
    try:
        if not token or not chat_id:
            return False, "Telegram token/chat not configured"
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {"chat_id": chat_id, "text": text, "parse_mode":"HTML"}
        r = requests.post(url, json=payload, timeout=10)
        j = r.json()
        return j.get("ok", False), j
    except Exception as e:
        return False, str(e)

def prepare_df_from_api(result):
    data = result["data"]
    prices = [p[1] for p in data["prices"]]
    times = [p[0] for p in data["prices"]]
    df = pd.DataFrame({"ts": times, "price": prices})
    df["dt"] = pd.to_datetime(df["ts"], unit="ms")
    df = df.set_index("dt")
    return df

if st.button("احصل على التوصية الآن"):
    st.info("جاري جلب البيانات وتحليل المؤشرات...")
    res = fetch_coingecko(coin_cg, days, interval)
    used_source = None
    if res is None:
        st.warning("CoinGecko فشل — أحاول مصدر بديل (CoinCap)...")
        res2 = fetch_coincap(coin_cc, days, interval)
        if res2 is None:
            st.error("فشل تحميل البيانات من كلا المصدرين الآن. جرب بعد شوية أو غيّر إعدادات الأيام/الفاصل.")
            st.stop()
        else:
            used_source = res2["source"]
            df = prepare_df_from_api(res2)
    else:
        used_source = res["source"]
        df = prepare_df_from_api(res)

    df, vol = compute_indicators(df)
    latest = df.iloc[-1]
    weights = {"rsi": weight_rsi, "macd": weight_macd, "ema": weight_ema}
    reco, score = signal_from_indicators(latest, weights)
    latest_price = latest['price']
    st.subheader(f"{coin_label} — السعر الآن: ${latest_price:,.2f}  (من {used_source})")
    st.markdown(f"**درجة الثقة (score):** {score:.2f}")

    if reco == "BUY":
        st.success("توصية: **اشتري الآن** ✅")
    elif reco == "SELL":
        st.warning("توصية: **فكر في البيع/جني الأرباح** ⚠️")
    else:
        st.info("توصية: **انتظر / سوق محايد** ⏳")

    if auto_tp_sl:
        tp, sl, tp_pct, sl_pct = suggest_tp_sl(latest_price, vol, reco)
        st.markdown(f"**اقتراح TP:** ${tp:,.2f} (~{tp_pct:.2f}%)")
        st.markdown(f"**اقتراح SL:** ${sl:,.2f} (~{sl_pct:.2f}%)")

    with st.expander("عرض مؤشرات (آخر 10 نقاط)"):
        st.write(df.tail(10)[['price','rsi','ema_short','ema_long','macd','macd_signal','bb_upper','bb_lower']])

    fig, ax = plt.subplots(2,1, figsize=(8,5), sharex=True)
    ax[0].plot(df.index, df['price'], label='price')
    ax[0].plot(df.index, df['ema_short'], label='EMA12', alpha=0.7)
    ax[0].plot(df.index, df['ema_long'], label='EMA26', alpha=0.7)
    if not df['bb_upper'].isna().all():
        ax[0].plot(df.index, df['bb_upper'], linestyle='--', alpha=0.5)
        ax[0].plot(df.index, df['bb_lower'], linestyle='--', alpha=0.5)
    ax[0].legend(); ax[0].set_title("Price & EMAs")
    ax[1].plot(df.index, df['rsi'], label='RSI')
    ax[1].axhline(30, linestyle='--', alpha=0.5)
    ax[1].axhline(70, linestyle='--', alpha=0.5)
    ax[1].set_ylim(0,100); ax[1].set_title("RSI")
    plt.tight_layout()
    st.pyplot(fig)

    # Send Telegram alert if strong signal
    if abs(score) >= alert_threshold:
        token = TELEGRAM_TOKEN
        chat = TELEGRAM_CHAT_ID
        now = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
        text = f"<b>Crypto Advisor</b>\n{coin_label}\nالتوصية: {reco}\nالسعر الآن: ${latest_price:,.2f}\nدرجة الثقة: {score:.2f}\nTP~ {tp:.2f} ({tp_pct:.2f}%) | SL~ {sl:.2f} ({sl_pct:.2f}%)\nمصدر البيانات: {used_source}\nوقت: {now}"
        ok, resp = send_telegram_message(token, chat, text)
        if ok:
            st.success("تم إرسال إشعار لتليجرام (Push).")
        else:
            st.error(f"فشل إرسال إشعار لتليجرام: {resp}")
