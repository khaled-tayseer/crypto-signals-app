import streamlit as st
import requests
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from datetime import datetime

st.set_page_config(page_title="Crypto Signals", layout="centered")
st.title("🔎 Crypto Signals - تجربة")
st.write("تطبيق بسيط يحسب RSI ويعطي توصية شراء/بيع. البيانات من CoinGecko.")

COINS = {
    "Bitcoin (BTC)": "bitcoin",
    "Ethereum (ETH)": "ethereum",
    "Binance Coin (BNB)": "binancecoin",
    "Solana (SOL)": "solana",
    "Ripple (XRP)": "ripple"
}

col1, col2 = st.columns([2,1])

with col1:
    coin_label = st.selectbox("اختر العملة", list(COINS.keys()), index=0)
    coin = COINS[coin_label]
    days = st.selectbox("مدة البيانات (أيام)", [1,3,7,14,30], index=2)
    interval = st.selectbox("الفاصل الزمني", ["hourly","daily"], index=0)

with col2:
    st.write("إعدادات مخاطرة")
    tp_pct = st.number_input("Take Profit (%)", value=5.0, step=0.5, format="%.2f")
    sl_pct = st.number_input("Stop Loss (%)", value=2.0, step=0.5, format="%.2f")
    rsi_lower = st.slider("RSI - منطقة تشبع بيعي (Buy <)", 5, 50, 30)
    rsi_upper = st.slider("RSI - منطقة تشبع شرائي (Sell >)", 50, 95, 70)

if st.button("احصل على التوصية الآن"):
    status = st.empty()
    status.info("جارٍ جلب البيانات من CoinGecko...")
    try:
        url = f"https://api.coingecko.com/api/v3/coins/{coin}/market_chart"
        params = {"vs_currency":"usd", "days": days, "interval": interval}
        r = requests.get(url, params=params, timeout=15)
        data = r.json()
        if "prices" not in data or len(data["prices"]) == 0:
            st.error("مش لاقي بيانات أسعار من CoinGecko حالياً. جرب تاني بعد شوية.")
        else:
            prices = [p[1] for p in data["prices"]]
            times = [p[0] for p in data["prices"]]
            df = pd.DataFrame({"timestamp": times, "price": prices})
            df["dt"] = pd.to_datetime(df["timestamp"], unit="ms")
            df = df.set_index("dt")

            # RSI implementation
            window = 14
            delta = df['price'].diff()
            up = delta.clip(lower=0)
            down = -1 * delta.clip(upper=0)
            ma_up = up.ewm(com=(window-1), adjust=False).mean()
            ma_down = down.ewm(com=(window-1), adjust=False).mean()
            rs = ma_up / ma_down
            df['rsi'] = 100 - (100 / (1 + rs))
            latest_rsi = df['rsi'].iloc[-1]
            latest_price = df['price'].iloc[-1]

            # Recommendation logic
            if latest_rsi < rsi_lower:
                reco = "✅ اشتري - السوق في منطقة تشبع بيعي"
                action = "BUY"
            elif latest_rsi > rsi_upper:
                reco = "⚠️ سوق مش مناسب للشراء - منطقة تشبع شرائي (فكر في البيع)"
                action = "SELL"
            else:
                reco = "⏳ انتظر - السوق محايد"
                action = "HOLD"

            status.success("تم التحليل")
            st.subheader(f"{coin_label} — السعر الآن: ${latest_price:,.2f}")
            st.markdown(f"**RSI الحالي:** {latest_rsi:.2f}")
            st.markdown(f"**توصية:** {reco}")
            st.markdown(f"**Take Profit:** {tp_pct:.2f}% — **Stop Loss:** {sl_pct:.2f}%")

            # Simple suggested TP/SL price levels
            if action == "BUY":
                tp_price = latest_price * (1 + tp_pct/100)
                sl_price = latest_price * (1 - sl_pct/100)
                st.markdown(f"**سعر الاستهداف (TP):** ${tp_price:,.2f}")
                st.markdown(f"**سعر وقف الخسارة (SL):** ${sl_price:,.2f}")
            elif action == "SELL":
                tp_price = latest_price * (1 - tp_pct/100)
                sl_price = latest_price * (1 + sl_pct/100)
                st.markdown(f"**سعر الاستهداف عند البيع (TP):** ${tp_price:,.2f}")
                st.markdown(f"**سعر وقف الخسارة (SL):** ${sl_price:,.2f}")

            # Plot price and RSI using matplotlib
            fig, ax = plt.subplots(2, 1, figsize=(8,6), sharex=True)
            ax[0].plot(df.index, df['price'])
            ax[0].set_ylabel("Price (USD)")
            ax[0].set_title(f"السعر — {coin_label}")
            ax[1].plot(df.index, df['rsi'])
            ax[1].axhline(rsi_lower, linestyle='--')
            ax[1].axhline(rsi_upper, linestyle='--')
            ax[1].set_ylabel("RSI")
            ax[1].set_ylim(0,100)
            plt.tight_layout()
            st.pyplot(fig)
    except Exception as e:
        st.error(f"حصل خطأ أثناء التنفيذ: {e}")