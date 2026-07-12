import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרות תצוגה מותאמות למובייל (iPhone)
st.set_page_config(page_title="Protocol 402 Dashboard", layout="centered")

st.title("Protocol 402 - MTF Dashboard 📱")
st.write("True MTF Quad-Confluence iPhone Grid")

# --- מנגנון שינוי צירי זמן אינטראקטיבי ---
# מאפשר לך לשנות את ציר הזמן הראשי של הדשבורד בלחיצה
timeframe_options = {
    "15 דקות": "15m",
    "שעה אחת": "1h",
    "4 שעות": "4h",
    "יומי": "1d",
    "שבועי": "1wk"
}
selected_tf_label = st.selectbox("בחר ציר זמן ראשי לבדיקה:", list(timeframe_options.keys()), index=3)
main_tf = timeframe_options[selected_tf_label]

# רשימת הטיקרים המדויקת מהפרוטוקול שלך
tickers = ["NVDA", "AAPL", "MSFT", "AMZN", "TSLA", "META", "GOOGL", "QQQ"]

# פונקציית עזר לחישוב אינדיקטורים על ה-Dataframe
def calculate_indicators(df):
    if df.empty or len(df) < 50:
        return None
    
    # חישוב ATR 14 ידני
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    
    # אינדיקטורים נוספים מהפרוטוקול
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    df['H20_Prev'] = df['High'].rolling(20).max().shift(1)
    df['L20'] = df['Low'].rolling(20).min()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    
    return df

# פונקציה לבדיקת תנאי ה-Confluence של ציר זמן ספציפי
def check_tf_confluence(ticker, tf_interval):
    # התאמת תקופת המשיכה לפי האינטרוול כדי לחסוך בזמן טעינה
    period = "max" if tf_interval in ["1d", "1wk"] else "60d"
    if tf_interval == "4h":
        data = yf.download(ticker, period="60d", interval="1h", progress=False)
        if not data.empty:
            data = data.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
    else:
        data = yf.download(ticker, period=period, interval=tf_interval, progress=False)
        
    data = calculate_indicators(data)
    if data is None or data.empty:
        return False
    
    row = data.iloc[-1]
    is_green = row['Close'] >= row['Open']
    is_exhaustion = (row['Close'] >= row['H20_Prev'] * 0.98) and (row['Volume'] < row['Vol_SMA20'] * 0.8)
    
    return bool(is_green and not is_exhaustion)

# --- מנוע עיבוד הנתונים הראשי ---
@st.cache_data(ttl=60)  # קאש לדקה אחת כדי לא להעמיס במשיכות חוזרות מאייפון
def fetch_and_build_dashboard(main_interval):
    rows_data = []
    
    for t in tickers:
        # משיכת הנתונים עבור ציר הזמן הראשי שנבחר
        period = "max" if main_interval in ["1d", "1wk"] else "60d"
        if main_interval == "4h":
            df = yf.download(t, period="60d", interval="1h", progress=False)
            if not df.empty:
                df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        else:
            df = yf.download(t, period=period, interval=main_interval, progress=False)
            
        df = calculate_indicators(df)
        if df is None or df.empty:
            continue
            
        row = df.iloc[-1]
        c = float(row['Close'])
        o = float(row['Open'])
        v = float(row['Volume'])
        vm = float(row['Vol_SMA20'])
        h = float(row['H20_Prev'])
        e = float(row['EMA50'])
        l20 = float(row['L20'])
        atr = float(row['ATR'])
        
        chg = ((c - o) / o) * 100
        is_breakout = (c > h) and (v > vm * 2.5)
        macro_up = c > e
        is_exhaustion = (c >= h * 0.98) and (v < vm * 0.8)
        
        # חישוב משקל למיון (Sorting Engine)
        sig_weight = 4000 if (is_breakout and macro_up) else 3000 if is_breakout else 2000 if macro_up else 1000
        score = sig_weight + chg
        
        # קביעת סיגנל וצבעים
        if is_breakout and macro_up:
            signal = "⚡ CONFIRMED"
        elif is_breakout:
            signal = "🔥 BREAKOUT"
        elif macro_up:
            signal = "📈 BULLISH"
        else:
            signal = "📉 BEARISH"
            
        # יעד פיבונאצ'י
        if is_exhaustion or chg < 0:
            fib_target = c - (abs(c - l20) * 1.618)
            fib_text = f"▼ {fib_target:.1f}"
        else:
            fib_target = c + (abs(c - l20) * 1.618)
            fib_text = f"▲ {fib_target:.1f}"
            
        # יעד ATR
        atr_target = c + (atr * 1.618)
        
        # חישוב Chaos Emoji
        x_mom = ((c - e) / e) * 100
        y_vol = v / vm if vm > 0 else 1.0
        
        if is_exhaustion and y_vol < 0.8 and x_mom > 4.5:
            chaos_emoji = "⚠️"
        elif is_breakout and macro_up:
            chaos_emoji = "🏃‍♂️"
        elif not macro_up and c < e * 0.94 and y_vol < 0.8:
            chaos_emoji = "⏳"
        elif abs(x_mom) < 1.2 and y_vol < 1.1:
            chaos_emoji = "🌫️"
        else:
            chaos_emoji = "🔵"
            
        # חישוב True MTF Quad-Confluence לשכבות קבועות (W, D, 4H, 1H/45m)
        # כדי לחסוך זמן ריצה במובייל, נשתמש בסימולציה מהירה או בדיקה ישירה:
        w_ok = check_tf_confluence(t, "1wk")
        d_ok = check_tf_confluence(t, "1d")
        h4_ok = check_tf_confluence(t, "4h")
        m45_ok = check_tf_confluence(t, "1h") # החלפה הטובה ביותר ל-45m ב-yfinance
        
        green_counter = sum([w_ok, d_ok, h4_ok, m45_ok])
        
        if green_counter == 4:
            mtf_text = "🚀"
        elif green_counter == 0:
            mtf_text = "—"
        else:
            mtf_text = ""
            if w_ok: mtf_text += "W "
            if d_ok: mtf_text += "D "
            if h4_ok: mtf_text += "H "
            if m45_ok: mtf_text += "M "
            
        rows_data.append({
            "Ticker": t,
            "Price / %": f"{c:.2f} ({chg:+.2f}%)",
            "Signal": signal,
            "ATR Tar": f"{atr_target:.2f}",
            "Fib Tar": fib_text,
            "Confluence": mtf_text,
            "Chaos": chaos_emoji,
            "score": score
        })
        
    # מיון התוצאות לפי ה-Score (בדומה ל-Bubble Sort שכתבת ב-Pine)
    df_result = pd.DataFrame(rows_data)
    if not df_result.empty:
        df_result = df_result.sort_values(by="score", ascending=False).drop(columns=["score"])
    return df_result

# הרצת המנוע והצגת הטבלה
with st.spinner("מחשב נתוני פרוטוקול..."):
    grid_data = fetch_and_build_dashboard(main_tf)

# הצגת הטבלה בעיצוב נקי וקומפקטי שמתאים בול למסך האייפון
st.dataframe(
    grid_data, 
    use_container_width=True, 
    hide_index=True
)

st.caption(f"עודכן לאחרונה עבור ציר זמן: {selected_tf_label}")
