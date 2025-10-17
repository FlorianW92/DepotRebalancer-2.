import streamlit as st
import pandas as pd
import yfinance as yf
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode
import pandas_market_calendars as mcal
from datetime import datetime, timedelta
import os

# ---------------- Pfade ----------------
DATA_PATH = "depot_data.csv"

# ---------------- CSV laden ----------------
if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)
else:
    st.error("CSV-Datei nicht gefunden!")

# ---------------- USD->EUR ----------------
try:
    eurusd = yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
except:
    eurusd = 1.08

# ---------------- Kurse abrufen ----------------
def get_price(ticker, currency):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        price = float(data["Close"].iloc[-1])
        if currency=="USD":
            price /= eurusd
        return round(price,2)
    except:
        return None

# ---------------- Kurse aktualisieren ----------------
if "Price" not in df.columns or st.button("📊 Kurse aktualisieren"):
    df["Price"] = [get_price(t,c) for t,c in zip(df["Ticker"], df["Currency"])]

# ---------------- Marktwert berechnen ----------------
df["MarketValue"] = (df["Shares"] * df["Price"]).round(2)

# ---------------- Sparplan Datum ----------------
start_date = datetime(2025,11,6)
nyse = mcal.get_calendar('XNYS')
today = pd.Timestamp.today()
def next_trading_day(d):
    schedule = nyse.schedule(start_date=d, end_date=d+timedelta(days=7))
    if d in schedule.index:
        return d
    else:
        return schedule.index[0]
plan_day = next_trading_day(start_date)

# ---------------- AgGrid Editierbar ----------------
st.title("💼 Dein optimiertes Depot")
gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_column("Shares", editable=True)
grid_options = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    height=400,
    fit_columns_on_grid_load=True
)

# ---------------- CSV speichern ----------------
updated_df = grid_response['data']
df['Shares'] = updated_df['Shares']
df["MarketValue"] = (df["Shares"] * df["Price"]).round(2)
df.to_csv(DATA_PATH, index=False)

# ---------------- Pie Charts ----------------
sector_summary = df[df["Sector"]!="Bestand"].groupby("Sector")["MarketValue"].sum().reset_index()
fig, ax = plt.subplots()
ax.pie(sector_summary["MarketValue"], labels=sector_summary["Sector"], autopct="%1.1f%%")
st.pyplot(fig)

# ---------------- Rebalancing Hinweise ----------------
st.subheader("🔄 Umschichtungsplan")
for sector in df["Sector"].unique():
    if sector=="Bestand":
        continue
    sector_df = df[df["Sector"]==sector]
    total_mv = sector_df["MarketValue"].sum()
    for idx, row in sector_df.iterrows():
        target_pct = row["MonthlyAmount"] / sector_df["MonthlyAmount"].sum()
        actual_pct = row["MarketValue"] / total_mv if total_mv>0 else 0
        if actual_pct < target_pct*0.95:
            st.write(f"{row['Name']} ({sector}): aktuell {actual_pct:.1%}, Ziel {target_pct:.1%} → **aufstocken**")
        elif actual_pct > target_pct*1.05:
            # Vorschlag wohin umschichten
            others = sector_df[sector_df["Name"]!=row["Name"]]
            if not others.empty:
                target = others.iloc[0]["Name"]
                st.write(f"{row['Name']} ({sector}): aktuell {actual_pct:.1%}, Ziel {target_pct:.1%} → **in {target} umschichten**")
