import streamlit as st
import requests
import pandas as pd

st.title("NASDAQ Full Market Screener 🕵️‍♂️")

# פונקציה למשיכת כל השוק בבקשה אחת בודדת
@st.cache_data(ttl=300) # שמירת נתונים ל-5 דקות כדי לחסוך טעינות
def get_all_nasdaq_stocks():
    # הכתובת הסודית של הדשבורד הרשמי של נאסד"ק
    url = "https://api.nasdaq.com/api/screener/stocks?tablewithcharts=true&download=true"
    
    # הגדרת דפדפן פיקטיבי כדי שהשרת יענה לנו מיד
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 16_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.5 Mobile/15E148 Safari/604.1",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=15)
        json_data = response.json()
        
        # חילוץ השורות מתוך המבנה של נאסד"ק
        rows = json_data['data']['rows']
        df = pd.DataFrame(rows)
        
        # ניקוי וסינון ראשוני: נשמור רק מניות של בורסת NASDAQ
        # (ה-API הזה לפעמים מחזיר גם את NYSE, אז נסנן שיהיה רק נאסד"ק נקי)
        if 'exchange' in df.columns:
            df = df[df['exchange'].str.upper() == 'NASDAQ']
            
        return df
    except Exception as e:
        st.error(f"שגיאה במשיכת הנתונים: {e}")
        return pd.DataFrame()

# הרצת המשיכה
with st.spinner("שואב את כל 3,000 מניות הנאסד"ק במכה אחת..."):
    all_stocks_df = get_all_nasdaq_stocks()

if not all_stocks_df.empty:
    # הצגת המניות באייפון בצורה נקייה
    # נבחר להציג רק עמודות מעניינות כדי שלא יראה עמוס במובייל
    columns_to_show = ['symbol', 'name', 'lastsale', 'netchange', 'pctchange', 'volume']
    
    st.write(f"נמצאו {len(all_stocks_df)} מניות בנאסד\"ק:")
    st.dataframe(all_stocks_df[columns_to_show], use_container_width=True, hide_index=True)
else:
    st.warning("לא הצלחתי לטעון את רשימת המניות.")
