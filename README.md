
# Crypto Signals App - نسخة تجريبية

تطبيق ويب بسيط يجيب بيانات الأسعار من CoinGecko، يحسب مؤشر RSI، ويعطي توصية شراء/بيع.

## محتوى المشروع
- `main.py` - تطبيق Streamlit
- `requirements.txt` - المكتبات المطلوبة

## كيف تشغله محلياً
1. ثبت Python (3.8+)
2. ثبت المكتبات:
   ```
   pip install -r requirements.txt
   ```
3. شغل التطبيق:
   ```
   streamlit run main.py
   ```

## نشر على Streamlit Community Cloud
1. ارفع هذا المشروع على GitHub (repository جديد).
2. سجل دخول على https://share.streamlit.io باستخدام GitHub.
3. اختر الريبو واضغط Deploy.
4. افتح الرابط من موبايلك.

## ملاحظات
- التطبيق يستخدم CoinGecko API مجانياً. أحياناً قد يكون هناك حد للطلبات أو تأخر في البيانات.
- هذه نسخة تجريبية: نقدر نضيف مؤشرات ثانية، تحليل إخباري، أو ربط بتنبيهات فيما بعد.
