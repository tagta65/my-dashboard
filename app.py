import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרות תצוגה
st.set_page_config(page_title="Protocol 402 - Turbo", layout="centered")

st.title("Dashboard 🕵️‍♂️")
st.write("🚀 **פרוטוקול 402 - סריקה מהירה (מצב קבוצות)**")

# --- הגדרת הקבוצות שלך ---
# אתה יכול לערוך את הרשימות האלו כאן בקלות
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

# --- פונקציות חישוב (נשאר זהה) ---
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

def evaluate_tf_confluence_from_bulk(df_raw, resample_4h=False):
    try:
        df = df_raw.dropna()
        if df.empty: return False
        if resample_4h:
            df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        df = calculate_indicators(df)
        if df is None or df.empty: return False
        row = df.iloc[-1]
        return bool((row['Close'] >= row['Open']) and not ((row['Close'] >= row['H20_Prev'] * 0.98) and (row['Volume'] < row['Vol_SMA20'] * 0.8)))
    except: return False

# --- ממשק משתמש ---
timeframe_options = {"15 דקות": "15m", "שעה אחת": "1h", "4 שעות": "4h", "יומי": "1d", "שבועי": "1wk"}
selected_tf_label = st.selectbox("בחר ציר זמן:", list(timeframe_options.keys()), index=3)
main_tf = timeframe_options[selected_tf_label]

# --- משיכת נתונים ממוקדת לקבוצה בלבד ---
with st.spinner(f'🚀 טוען נתונים עבור {selected_group}...'):
    try:
        # עכשיו אנחנו מורידים נתונים רק ל-8 המניות שבקבוצה!
        bulk_wk = yf.download(tickers_to_scan, period="max", interval="1wk", group_by='ticker', progress=False)
        bulk_d = yf.download(tickers_to_scan, period="max", interval="1d", group_by='ticker', progress=False)
        bulk_h1 = yf.download(tickers_to_scan, period="60d", interval="1h", group_by='ticker', progress=False)
        bulk_main = yf.download(tickers_to_scan, period="60d", interval="15m", group_by='ticker', progress=False) if main_tf == "15m" else None
    except Exception as e:
        st.error(f"שגיאה במשיכת הנתונים: {e}")
        st.stop()

# --- עיבוד והצגה ---
rows_data = []
for t in tickers_to_scan:
    try:
        if t not in bulk_wk.columns: continue
        
        if main_tf == "1wk": df = bulk_wk[t]
        elif main_tf == "1d": df = bulk_d[t]
        elif main_tf == "1h": df = bulk_h1[t]
        elif main_tf == "4h":
            df = bulk_h1[t].dropna().resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        elif main_tf == "15m" and bulk_main is not None:
            df = bulk_main[t]
        else: continue
            
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
        
        w_ok = evaluate_tf_confluence_from_bulk(bulk_wk[t])
        d_ok = evaluate_tf_confluence_from_bulk(bulk_d[t])
        h4_ok = evaluate_tf_confluence_from_bulk(bulk_h1[t], resample_4h=True)
        h1_ok = evaluate_tf_confluence_from_bulk(bulk_h1[t])
        
        mtf_text = "🚀" if sum([w_ok, d_ok, h4_ok, h1_ok]) == 4 else "".join([f"{k} " for k, v in zip(["W", "D", "H", "M"], [w_ok, d_ok, h4_ok, h1_ok]) if v]) or "—"
        
        rows_data.append({
            "Ticker": t, "Price / %": f"{c:.2f} ({chg:+.2f}%)", "Signal": signal,
            "ATR": f"{atr_target:.2f}", "Fib": f"{fib_target:.1f}", "Conf": mtf_text, "score": score
        })
    except: continue

if rows_data:
    grid_data = pd.DataFrame(rows_data).sort_values(by="score", ascending=False).drop(columns=["score"])
    st.dataframe(grid_data, use_container_width=True, hide_index=True)
else:
    st.warning("לא נמצאו מספיק נתונים לקבוצה זו.")
