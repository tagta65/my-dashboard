import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרות תצוגה מותאמות למובייל (iPhone)
st.set_page_config(page_title="Protocol 402 - Unified Dashboard", layout="centered")

st.title("Dashboard 🕵️‍♂️")
st.write("פרוטוקול 402 - מסך סריקה וחישוב מאוחד")

# --- מנוע משיכת כל מניות הנאסד"ק מה-API הרשמי ---
@st.cache_data(ttl=300)
def get_all_nasdaq_market():
    url = "https://api.nasdaq.com/api/screener/stocks?tablewithcharts=true&download=true"
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9"
    }
    try:
        response = requests.get(url, headers=headers, timeout=15)
        json_data = response.json()
        rows = json_data['data']['rows']
        df = pd.DataFrame(rows)
        
        if 'exchange' in df.columns:
            df = df[df['exchange'].str.upper() == 'NASDAQ']
            
        # ניקוי נתונים
        df['pctchange'] = df['pctchange'].str.replace('%', '', regex=False).str.strip()
        df['pctchange'] = pd.to_numeric(df['pctchange'], errors='coerce').fillna(0)
        df['volume'] = pd.to_numeric(df['volume'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"שגיאה במשיכת הנתונים מנאס드\"ק: {e}")
        return pd.DataFrame()

# פונקציות עזר לחישובים (פרוטוקול 402)
def calculate_indicators(df):
    if df.empty or len(df) < 50:
        return None
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

def check_tf_confluence(ticker, tf_interval):
    period = "max" if tf_interval in ["1d", "1wk"] else "60d"
    try:
        if tf_interval == "4h":
            data = yf.download(ticker, period="60d", interval="1h", progress=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            if not data.empty:
                data = data.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        else:
            data = yf.download(ticker, period=period, interval=tf_interval, progress=False)
            if isinstance(data.columns, pd.MultiIndex): data.columns = data.columns.get_level_values(0)
            
        data = calculate_indicators(data)
        if data is None or data.empty: return False
        row = data.iloc[-1]
        return bool((row['Close'] >= row['Open']) and not ((row['Close'] >= row['H20_Prev'] * 0.98) and (row['Volume'] < row['Vol_SMA20'] * 0.8)))
    except:
        return False

# שאיבת הנתונים הגולמיים של השוק
with st.spinner('מתחבר לשרתי נאסד"ק ומסנכרן נתונים...'):
    nasdaq_raw = get_all_nasdaq_market()

# --- ממשק משתמש אחוד ---
timeframe_options = {"15 דקות": "15m", "שעה אחת": "1h", "4 שעות": "4h", "יומי": "1d", "שבועי": "1wk"}
selected_tf_label = st.selectbox("בחר ציר זמן ראשי לבדיקה:", list(timeframe_options.keys()), index=3)
main_tf = timeframe_options[selected_tf_label]

# תיבת הזרקה דינמית - מאפשרת להביא כל מניה מתוך ה-3,000 ישירות לחישוב
custom_ticker = st.text_input("🔍 הוסף מניה ספציפית לחישוב (למשל: AAPL, TSLA, MSFT):", "").upper().strip()

if not nasdaq_raw.empty:
    # בחירת 30 המניות הכי פעילות בשוק (לפי Volume) כבסיס קבוע
    top_active = nasdaq_raw.sort_values(by="volume", ascending=False).head(30)
    tickers_to_scan = top_active['symbol'].tolist()
    
    # אם המשתמש הזין מניה ידנית, נדחף אותה לראש הרשימה כדי שתחושב מיד
    if custom_ticker and custom_ticker not in tickers_to_scan:
        tickers_to_scan.insert(0, custom_ticker)
    
    rows_data = []
    with st.spinner(f"מריץ את פרוטוקול 402 על {len(tickers_to_scan)} המניות המובילות..."):
        for t in tickers_to_scan:
            try:
                period = "max" if main_tf in ["1d", "1wk"] else "60d"
                if main_tf == "4h":
                    df = yf.download(t, period="60d", interval="1h", progress=False)
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                    if not df.empty:
                        df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
                else:
                    df = yf.download(t, period=period, interval=main_tf, progress=False)
                    if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)
                
                df = calculate_indicators(df)
                if df is None or df.empty: continue
                    
                row = df.iloc[-1]
                c, o, v, vm, h, e, l20, atr = float(row['Close']), float(row['Open']), float(row['Volume']), float(row['Vol_SMA20']), float(row['H20_Prev']), float(row['EMA50']), float(row['L20']), float(row['ATR'])
                
                chg = ((c - o) / o) * 100
                is_breakout = (c > h) and (v > vm * 2.5)
                macro_up = c > e
                is_exhaustion = (c >= h * 0.98) and (v < vm * 0.8)
                
                # חישוב משקל למיון הטבלה
                sig_weight = 4000 if (is_breakout and macro_up) else 3000 if is_breakout else 2000 if macro_up else 1000
                score = sig_weight + chg
                
                if is_breakout and macro_up: signal = "⚡ CONFIRMED"
                elif is_breakout: signal = "🔥 BREAKOUT"
                elif macro_up: signal = "📈 BULLISH"
                else: signal = "📉 BEARISH"
                    
                fib_target = c - (abs(c - l20) * 1.618) if (is_exhaustion or chg < 0) else c + (abs(c - l20) * 1.618)
                fib_text = f"▼ {fib_target:.1f}" if (is_exhaustion or chg < 0) else f"▲ {fib_target:.1f}"
                atr_target = c + (atr * 1.618)
                
                x_mom = ((c - e) / e) * 100
                chaos_emoji = "⚠️" if (is_exhaustion and v/vm < 0.8 and x_mom > 4.5) else "🏃‍♂️" if (is_breakout and macro_up) else "🔵"
                    
                w_ok, d_ok, h4_ok, h1_ok = check_tf_confluence(t, "1wk"), check_tf_confluence(t, "1d"), check_tf_confluence(t, "4h"), check_tf_confluence(t, "1h")
                green_counter = sum([w_ok, d_ok, h4_ok, h1_ok])
                mtf_text = "🚀" if green_counter == 4 else "".join([f"{k} " for k, v in zip(["W", "D", "H", "M"], [w_ok, d_ok, h4_ok, h1_ok]) if v]) or "—"
                
                rows_data.append({
                    "Ticker": t, "Price / %": f"{c:.2f} ({chg:+.2f}%)", "Signal": signal,
                    "ATR Tar": f"{atr_target:.2f}", "Fib Tar": fib_text, "Confluence": mtf_text, "Chaos": chaos_emoji, "score": score
                })
            except: continue
    
    # הצגת הטבלה המאוחדת
    if rows_data:
        grid_data = pd.DataFrame(rows_data).sort_values(by="score", ascending=False).drop(columns=["score"])
        st.write("📊 **טבלת איתותי כניסה וניהול סיכונים מאוחדת:**")
        st.dataframe(grid_data, use_container_width=True, hide_index=True)
    else:
        st.warning("לא נמצאו מספיק נתונים לחישוב האינדיקטורים כרגע.")
        
    st.caption(f"עודכן לאחרונה עבור ציר זמן: {selected_tf_label}")
else:
    st.error("נכשלה טעינת נתוני השוק משרתי נאסד\"ק.")
