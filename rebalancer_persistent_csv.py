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

# ---------------- Session State für Shares ----------------
if "shares_dict" not in st.session_state:
    st.session_state.shares_dict = dict(zip(df["Ticker"], df["Shares"]))

# ---------------- USD->EUR ----------------
try:
    eurusd = yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
except:
    eurusd = 1.08  # fallback

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

# ---------------- Kurs-Aktualisierung ----------------
if "Price" not in df.columns or st.button("📊 Kurse aktualisieren"):
    df["Price"] = [get_price(t,c) for t,c in zip(df["Ticker"], df["Currency"])]

# ---------------- MarketValue berechnen ----------------
df["Shares"] = df["Ticker"].map(st.session_state.shares_dict)
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
    update_mode=GridUpdateMode.VALUE_CHANGED,
    height=400,
    fit_columns_on_grid_load=True
)

# Werte in Session State übernehmen
updated_df = grid_response['data']
for i, t in enumerate(df["Ticker"]):
    st.session_state.shares_dict[t] = updated_df[i]['Shares']

# MarketValue neu berechnen und CSV speichern
df["Shares"] = df["Ticker"].map(st.session_state.shares_dict)
df["MarketValue"] = (df["Shares"] * df["Price"]).round(2)
df.to_csv(DATA_PATH, index=False)

# ---------------- Pie Charts ----------------
sector_summary = df[df["Sector"]!="Bestand"].groupby("Sector")["MarketValue"].sum().reset_index()
fig, ax = plt.subplots()
ax.pie(sector_summary["MarketValue"], labels=sector_summary["Sector"], autopct="%1.1f%%")
st.pyplot(fig)

# ---------------- Rebalancing Hinweise ----------------
st.subheader("🔄 Umschichtungsplan (inkl. Ziel 1 Mio. €)")
target_total = 1_000_000
for sector in df["Sector"].unique():
    if sector=="Bestand": continue
    sec_df = df[df["Sector"]==sector].copy()
    total_mv = sec_df["MarketValue"].sum()
    for idx, row in sec_df.iterrows():
        target_pct = row["MonthlyAmount"]/sec_df["MonthlyAmount"].sum()
        actual_pct = row["MarketValue"]/total_mv if total_mv>0 else 0
        target_value = target_pct * target_total
        if row["MarketValue"] < target_value*0.95:
            st.write(f"{row['Name']} ({sector}) unter Ziel ({row['MarketValue']:.0f}€ vs. {target_value:.0f}€) → **aufstocken**")
        elif row["MarketValue"] > target_value*1.05:
            # Vorschlag wohin umschichten
            others = sec_df[sec_df["Name"]!=row["Name"]]
            underweight = others[others["MarketValue"]/total_mv < (others["MonthlyAmount"]/sec_df["MonthlyAmount"].sum())]
            if not underweight.empty:
                target = underweight.iloc[0]["Name"]
                st.write(f"{row['Name']} ({sector}) über Ziel ({row['MarketValue']:.0f}€) → in {target} umschichten oder Teilverkauf erwägen")
