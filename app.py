import streamlit as st
import requests
import pandas as pd
import numpy as np
import time

# הגדרות תצוגה
st.set_page_config(page_title="Protocol 402 - Turbo Finnhub", layout="centered")

st.title("Dashboard 🕵️‍♂️")
st.write("🚀 **פרוטוקול 402 - סריקה מהירה (מצב קבוצות + Finnhub API)**")

# הגדרת מפתח ה-API שלך כברירת מחדל (ניתן לשינוי במידת הצורך בבר הצדדי)
FINNHUB_API_KEY = st.sidebar.text_input("Finnhub API Key:", value="d99ri6pr01qh9urlc1ug", type="password")

# --- הגדרת הקבוצות שלך ---
stock_groups = {
    "קבוצה 1 (Tech Giants)": ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX"],
    "קבוצה 2 (Semi & Finance)": ["AMD", "INTC", "ADBE", "PYPL", "CMCSA", "PEP", "AVGO", "COST"],
    "קבוצה 3 (Consumer/BlueChip)": ["DIS", "BA", "KO", "MCD", "JPM", "BAC", "V", "WMT"],
    "קבוצה 4 (Retail/Software)": ["TGT", "PG", "NKE", "IBM", "ORCL", "CSCO", "QCOM", "GS"],
    "קבוצה 5 (Industrial/Health)": ["AXP", "MMM", "CAT", "HON", "INTU", "TXN", "AMGN", "SBUX"]
}

# --- בחירת הקבוצה מהממשק ---
selected_group = st.selectbox("בחר קבוצת מניות לסריקה:", list(stock_groups.keys()))
tickers_to_scan = stock_groups[selected_group]

# --- פונקציית משיכת נתונים מ-Finnhub ---
def fetch_finnhub_candles(symbol, resolution, days_back):
    """
    מביאה נתוני נרות מ-Finnhub ומחזירה DataFrame מותאם
     resolutions נתמכים: 1, 5, 15, 30, 60, D, W, M
    """
    to_time = int(time.time())
    from_time = to_time - (days_back * 24 * 60 * 60)
    
    url = "https://finnhub.io/api/v1/stock/candle"
    params = {
        "symbol": symbol,
        "resolution": resolution,
        "from": from_time,
        "to": to_time,
        "token": FINNHUB_API_KEY
    }
    
    try:
        response = requests.get(url, params=params)
        if response.status_code == 200:
            data = response.json()
            if data.get("s") == "ok":
                df = pd.DataFrame({
                    "Open": data["o"],
                    "High": data["h"],
                    "Low": data["l"],
                    "Close": data["c"],
                    "Volume": data["v"]
                }, index=pd.to_datetime(data["t"], unit="s"))
                return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- פונקציות חישוב ---
def calculate_indicators(df):
    if df.empty or len(df) < 50: return None
    df = df.copy()
    high_low = df['High'] - df['Low']
    high_cp = np.abs(df['High'] - df['Close'].shift())
    low_cp = np.abs(df['Low'] - df['Close'].shift())
    tr = pd.concat([high_low, high_cp, low_cp], axis=1).max(axis=1)
    df['ATR'] = tr.rolling(14).mean()
    df['Vol_SMA20'] = df['Volume'].rolling(20).mean()
    df['H20_Prev'] = df['High'].rolling(20).max().shift(1)
    df['L20'] = df['Low'].rolling(20).min()
    df['EMA50'] = df['Close'].ewm(span=50, adjust=False).mean()
    return df

def evaluate_tf_confluence(df, resample_4h=False):
    try:
        if df.empty: return False
        df = df.dropna()
        if df.empty: return False
        if resample_4h:
            df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        df = calculate_indicators(df)
        if df is None or df.empty: return False
        row = df.iloc[-1]
        return bool((row['Close'] >= row['Open']) and not ((row['Close'] >= row['H20_Prev'] * 0.98) and (row['Volume'] < row['Vol_SMA20'] * 0.8)))
    except: 
        return False

# --- ממשק משתמש לבחירת Timeframe ---
timeframe_options = {"15 דקות": "15", "שעה אחת": "60", "4 שעות": "4h", "יומי": "D", "שבועי": "W"}
selected_tf_label = st.selectbox("בחר ציר זמן ראשי:", list(timeframe_options.keys()), index=3)
main_tf = timeframe_options[selected_tf_label]

# --- עיבוד והצגה בזמן אמת ---
rows_data = []

with st.spinner(f'🚀 סורק נתונים מ-Finnhub עבור {selected_group}...'):
    for t in tickers_to_scan:
        try:
            # משיכת נתוני בסיס הנדרשים לחישוב הקונפלואנס (Confluence)
            df_wk = fetch_finnhub_candles(t, "W", days_back=700)   # ~100 שבועות לטובת EMA50
            df_d = fetch_finnhub_candles(t, "D", days_back=200)    # ~200 ימים לטובת EMA50
            df_h1 = fetch_finnhub_candles(t, "60", days_back=60)   # 60 יום עבור 1H ו-4H
            
            # קביעת ה-DataFrame הראשי לפי בחירת המשתמש
            if main_tf == "W": 
                df = df_wk
            elif main_tf == "D": 
                df = df_d
            elif main_tf == "60": 
                df = df_h1
            elif main_tf == "4h":
                if not df_h1.empty:
                    df = df_h1.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
                else:
                    df = pd.DataFrame()
            elif main_tf == "15":
                df = fetch_finnhub_candles(t, "15", days_back=30) # 30 יום עבור 15 דקות
            else:
                continue

            # הרצת אינדיקטורים על הציור הנבחר
            df = calculate_indicators(df)
            if df is None or df.empty: continue
                
            row = df.iloc[-1]
            c, o, v, vm, h, e, l20, atr = float(row['Close']), float(row['Open']), float(row['Volume']), float(row['Vol_SMA20']), float(row['H20_Prev']), float(row['EMA50']), float(row['L20']), float(row['ATR'])
            
            chg = ((c - o) / o) * 100
            is_breakout = (c > h) and (v > vm * 2.5)
            macro_up = c > e
            is_exhaustion = (c >= h * 0.98) and (v < vm * 0.8)
            
            sig_weight = 4000 if (is_breakout and macro_up) else 3000 if is_breakout else 2000 if macro_up else 1000
            score = sig_weight + chg
            
            signal = "⚡ CONFIRMED" if (is_breakout and macro_up) else "🔥 BREAKOUT" if is_breakout else "📈 BULLISH" if macro_up else "📉 BEARISH"
            
            fib_target = c - (abs(c - l20) * 1.618) if (is_exhaustion or chg < 0) else c + (abs(c - l20) * 1.618)
            atr_target = c + (atr * 1.618)
            
            # חישוב קונפלואנס רב-ממדי (Multi-Timeframe Confluence)
            w_ok = evaluate_tf_confluence(df_wk)
            d_ok = evaluate_tf_confluence(df_d)
            h4_ok = evaluate_tf_confluence(df_h1, resample_4h=True)
            h1_ok = evaluate_tf_confluence(df_h1)
            
            mtf_text = "🚀" if sum([w_ok, d_ok, h4_ok, h1_ok]) == 4 else "".join([f"{k} " for k, v in zip(["W", "D", "H", "M"], [w_ok, d_ok, h4_ok, h1_ok]) if v]) or "—"
            
            rows_data.append({
                "Ticker": t, "Price / %": f"{c:.2f} ({chg:+.2f}%)", "Signal": signal,
                "ATR": f"{atr_target:.2f}", "Fib": f"{fib_target:.1f}", "Conf": mtf_text, "score": score
            })
            
            # מניעת עומס קל על ה-API (Finnhub מאפשר עד 60 בקשות בדקה בחינם)
            time.sleep(0.05)
        except: 
            continue

# --- הצגת הטבלה הסופית ---
if rows_data:
    grid_data = pd.DataFrame(rows_data).sort_values(by="score", ascending=False).drop(columns=["score"])
    st.dataframe(grid_data, use_container_width=True, hide_index=True)
else:
    st.warning("לא נמצאו מספיק נתונים לקבוצה זו. ודא שמפתח ה-API תקין ופעיל.")
