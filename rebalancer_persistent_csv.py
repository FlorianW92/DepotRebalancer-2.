import os
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime, timedelta
from pytz import timezone
import matplotlib.pyplot as plt
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode

st.set_page_config(page_title="Depot Rebalancer", layout="wide")

# ---------------- CSV-Datei Pfad ----------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "depot_data.csv")

# ---------------- CSV laden oder erstellen ----------------
if os.path.exists(DATA_PATH):
    df = pd.read_csv(DATA_PATH)
else:
    initial_data = [
        ["NVIDIA","NVDA","Technologie & KI",75,0,"USD"],
        ["Microsoft","MSFT","Technologie & KI",50,0,"USD"],
        ["Alphabet","GOOGL","Technologie & KI",50,0,"USD"],
        ["ASML","ASML","Technologie & KI",25,0,"EUR"],
        ["CrowdStrike","CRWD","Cybersecurity / Cloud",25,0,"USD"],
        ["ServiceNow","NOW","Cybersecurity / Cloud",25,0,"USD"],
        ["First Solar","FSLR","Erneuerbare Energien & Infra",50,0,"USD"],
        ["NextEra Energy","NEE","Erneuerbare Energien & Infra",25,0,"USD"],
        ["Brookfield Renewable","BEPC","Erneuerbare Energien & Infra",25,0,"USD"],
        ["Tesla","TSLA","Zukunft / Disruption",37.5,0,"USD"],
        ["Palantir","PLTR","Zukunft / Disruption",25,0,"USD"],
        ["Super Micro Computer","SMCI","Zukunft / Disruption",12.5,0,"USD"],
        ["Johnson & Johnson","JNJ","Gesundheit / Stabilität",25,0,"USD"],
        ["Novo Nordisk","NVO","Gesundheit / Stabilität",25,0,"USD"],
        ["Apple","AAPL","Konsum & Industrie",25,0,"USD"],
        ["Volkswagen","VOW3.DE","Bestand",0,57.213,"EUR"],
    ]
    df = pd.DataFrame(initial_data, columns=["Name","Ticker","Sector","MonthlyAmount","Shares","Currency"])
    df.to_csv(DATA_PATH, index=False)

# ---------------- USD->EUR ----------------
try:
    eurusd = yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
except:
    eurusd = 1.08

# ---------------- Kursabruf ----------------
def get_price(ticker, currency):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if data.empty:
            return None
        price = float(data["Close"].iloc[-1])
        if currency == "USD":
            price /= eurusd
        return round(price, 2)
    except:
        return None

# ---------------- Kursaktualisierung ----------------
if "Price" not in df.columns or st.button("📊 Kurse aktualisieren"):
    df["Price"] = [get_price(t, c) for t, c in zip(df["Ticker"], df["Currency"])]
    df.to_csv(DATA_PATH, index=False)

# ---------------- Marktwerte ----------------
df["MarketValue"] = (df["Shares"] * df["Price"]).fillna(0).round(2)

# ---------------- Editierbare Shares mit AgGrid ----------------
st.title("💼 Depot & Shares Editierbar")

gb = GridOptionsBuilder.from_dataframe(df)
gb.configure_default_column(editable=True)
gb.configure_column("Shares", editable=True)
gb.configure_selection(selection_mode="single", use_checkbox=True)
grid_options = gb.build()

grid_response = AgGrid(
    df,
    gridOptions=grid_options,
    update_mode=GridUpdateMode.MODEL_CHANGED,
    height=400,
    fit_columns_on_grid_load=True,
    enable_enterprise_modules=False
)

updated_df = grid_response['data']
# Speichern in CSV
updated_df.to_csv(DATA_PATH, index=False)
df = updated_df.copy()
df["MarketValue"] = (df["Shares"] * df["Price"]).round(2)

# ---------------- Pie Chart ----------------
st.subheader("📊 Sektoraufteilung (ohne VW)")
display_df = df[df["Sector"] != "Bestand"]
total_value = display_df["MarketValue"].sum()
if total_value > 0:
    sector_summary = display_df.groupby("Sector")["MarketValue"].sum().reset_index()
    sector_summary["Percent"] = (sector_summary["MarketValue"]/total_value*100).round(2)
    fig, ax = plt.subplots()
    ax.pie(sector_summary["MarketValue"], labels=sector_summary["Sector"], autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    st.pyplot(fig)
else:
    st.info("Keine Daten für Pie Chart vorhanden.")

# ---------------- Umschichtungsvorschläge ----------------
st.subheader("💡 Umschichtungsvorschläge")
sector_targets = {
    "Technologie & KI":200,
    "Cybersecurity / Cloud":50,
    "Erneuerbare Energien & Infra":100,
    "Zukunft / Disruption":100,
    "Gesundheit / Stabilität":50,
    "Konsum & Industrie":50,
}

for sector, target in sector_targets.items():
    sector_df = display_df[display_df["Sector"]==sector]
    current = sector_df["MarketValue"].sum()
    diff = current - target
    if abs(diff) > 10:
        if diff > 0:  # Übergewicht
            sell_candidate = sector_df.sort_values("MarketValue", ascending=False).iloc[0]["Name"]
            buy_sector = [s for s in sector_targets if s != sector]
            buy_sector_values = {s: display_df[display_df["Sector"]==s]["MarketValue"].sum() for s in buy_sector}
            under_sector = min(buy_sector_values, key=buy_sector_values.get)
            st.warning(f"📉 {sector}: {round(diff,2)} € zu viel – verkaufe ggf. **{sell_candidate}** und schichte in **{under_sector}** um.")
        else:  # Untergewicht
            buy_candidate = sector_df.sort_values("MarketValue").iloc[0]["Name"]
            st.info(f"📈 {sector}: {round(abs(diff),2)} € zu wenig – erhöhe Anteil durch **{buy_candidate}** oder in untergewichtete Sektoren umschichten.")

