import streamlit as st
import requests
import yfinance as yf
import pandas as pd
import numpy as np

# הגדרות תצוגה מותאמות למובייל (iPhone)
st.set_page_config(page_title="Protocol 402 - Full Nasdaq", layout="centered")

st.title("Protocol 402 - Full NASDAQ Scanner 🕵️‍♂️")
st.write("סורק את כל השוק ומריץ קונפלוונס על המניות החמות ביותר")

# --- מנגנון שינוי צירי זמן אינטראקטיבי ---
timeframe_options = {
    "15 דקות": "15m",
    "שעה אחת": "1h",
    "4 שעות": "4h",
    "יומי": "1d",
    "שבועי": "1wk"
}
selected_tf_label = st.selectbox("בחר ציר זמן ראשי לבדיקה:", list(timeframe_options.keys()), index=3)
main_tf = timeframe_options[selected_tf_label]

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
    period = "max" if tf_interval in ["1d", "1wk"] else "60d"
    try:
        if tf_interval == "4h":
            data = yf.download(ticker, period="60d", interval="1h", progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            if not data.empty:
                data = data.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
        else:
            data = yf.download(ticker, period=period, interval=tf_interval, progress=False)
            if isinstance(data.columns, pd.MultiIndex):
                data.columns = data.columns.get_level_values(0)
            
        data = calculate_indicators(data)
        if data is None or data.empty:
            return False
        
        row = data.iloc[-1]
        is_green = row['Close'] >= row['Open']
        is_exhaustion = (row['Close'] >= row['H20_Prev'] * 0.98) and (row['Volume'] < row['Vol_SMA20'] * 0.8)
        return bool(is_green and not is_exhaustion)
    except:
        return False

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
            
        # ניקוי נתונים פנימי כדי שנוכל למיין לפי אחוזים
        df['pctchange'] = df['pctchange'].str.replace('%', '', regex=False).str.strip()
        df['pctchange'] = pd.to_numeric(df['pctchange'], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"שגיאה במשיכת הנתונים מנאסד\"ק: {e}")
        return pd.DataFrame()

# 1. שאיבת כל השוק בבקשה אחת (כאן תוקנה השגיאה!)
with st.spinner('שואב את כל 3,000 מניות הנאסד"ק במכה אחת...'):
    nasdaq_raw = get_all_nasdaq_market()

if not nasdaq_raw.empty:
    # 2. סינון מהיר של הטופ 15 מניות עם השינוי הכי גבוה (הכי חמות בשוק)
    top_gainers = nasdaq_raw.sort_values(by="pctchange", ascending=False).head(15)
    tickers_to_scan = top_gainers['symbol'].tolist()
    
    st.success(f"השוק נסרק בהצלחה! מריץ פרוטוקול קונפלוונס על 15 המובילות...")
    
    # 3. הרצת פרוטוקול 402 הריבועי על המניות המסוננות
    rows_data = []
    
    with st.spinner("מחשב אינדיקטורים, יעדי ATR, פיבונאצ'י ו-Chaos..."):
        for t in tickers_to_scan:
            period = "max" if main_tf in ["1d", "1wk"] else "60d"
            try:
                if main_tf == "4h":
                    df = yf.download(t, period="60d", interval="1h", progress=False)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                    if not df.empty:
                        df = df.resample('4h').agg({'Open': 'first', 'High': 'max', 'Low': 'min', 'Close': 'last', 'Volume': 'sum'})
                else:
                    df = yf.download(t, period=period, interval=main_tf, progress=False)
                    if isinstance(df.columns, pd.MultiIndex):
                        df.columns = df.columns.get_level_values(0)
                
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
                
                # חישוב משקל למיון
                sig_weight = 4000 if (is_breakout and macro_up) else 3000 if is_breakout else 2000 if macro_up else 1000
                score = sig_weight + chg
                
                if is_breakout and macro_up: signal = "⚡ CONFIRMED"
                elif is_breakout: signal = "🔥 BREAKOUT"
                elif macro_up: signal = "📈 BULLISH"
                else: signal = "📉 BEARISH"
                    
                if is_exhaustion or chg < 0:
                    fib_target = c - (abs(c - l20) * 1.618)
                    fib_text = f"▼ {fib_target:.1f}"
                else:
                    fib_target = c + (abs(c - l20) * 1.618)
                    fib_text = f"▲ {fib_target:.1f}"
                    
                atr_target = c + (atr * 1.618)
                
                # Chaos Emoji
                x_mom = ((c - e) / e) * 100
                y_vol = v / vm if vm > 0 else 1.0
                
                if is_exhaustion and y_vol < 0.8 and x_mom > 4.5: chaos_emoji = "⚠️"
                elif is_breakout and macro_up: chaos_emoji = "🏃‍♂️"
                elif not macro_up and c < e * 0.94 and y_vol < 0.8: chaos_emoji = "⏳"
                elif abs(x_mom) < 1.2 and y_vol < 1.1: chaos_emoji = "🌫️"
                else: chaos_emoji = "🔵"
                    
                # True MTF Confluence (W, D, 4H, 1H)
                w_ok = check_tf_confluence(t, "1wk")
                d_ok = check_tf_confluence(t, "1d")
                h4_ok = check_tf_confluence(t, "4h")
                m45_ok = check_tf_confluence(t, "1h")
                
                green_counter = sum([w_ok, d_ok, h4_ok, m45_ok])
                if green_counter == 4: mtf_text = "🚀"
                elif green_counter == 0: mtf_text = "—"
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
            except:
                continue

    # 4. מיון סופי והצגה על מסך האייפון
    if rows_data:
        grid_data = pd.DataFrame(rows_data)
        grid_data = grid_data.sort_values(by="score", ascending=False).drop(columns=["score"])
        
        st.dataframe(grid_data, use_container_width=True, hide_index=True)
    else:
        st.warning("לא נמצאו מספיק נתונים להרצת הפרוטוקול על הטיקרים שנבחרו.")
        
    st.caption(f"עודכן לאחרונה עבור ציר זמן: {selected_tf_label}")
else:
    st.error("נכשלה טעינת בורסת נאסד\"ק.")
