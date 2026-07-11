import streamlit as st
import yfinance as yf

st.title("Protocol Dashboard 🚀")
st.write("הדשבורד שלך באוויר ישירות מה-iPhone!")

# בדיקה מהירה של משיכת נתונים
ticker = st.text_input("הכנס סימול מניה לבדיקה:", "NVDA")
if ticker:
    stock_data = yf.Ticker(ticker).history(period="1d")
    if not stock_data.empty:
        last_price = stock_data['Close'].iloc[-1]
        st.metric(label=f"מחיר Spot נוכחי של {ticker}", value=f"${last_price:.2f}")
    else:
        st.error("לא נמצאו נתונים עבור הסימול הזה.")
