import os
import pandas as pd
import yfinance as yf
import streamlit as st
from datetime import datetime
from pytz import timezone
import matplotlib.pyplot as plt
import pandas_market_calendars as mcal

st.set_page_config(page_title="Depot Rebalancer", layout="wide")

# --------------------------------------------------------
# 📁 Pfad zur CSV im selben Ordner
# --------------------------------------------------------
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE_DIR, "depot_data.csv")

# --------------------------------------------------------
# 📂 CSV laden oder erstellen
# --------------------------------------------------------
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

# --------------------------------------------------------
# 💱 USD→EUR Kurs
# --------------------------------------------------------
try:
    eurusd = yf.Ticker("EURUSD=X").history(period="1d")["Close"].iloc[-1]
except:
    eurusd = 1.08

# --------------------------------------------------------
# 📆 XETRA-Kalender
# --------------------------------------------------------
xetra = mcal.get_calendar("XETR")
def next_trading_day(date):
    schedule = xetra.schedule(start_date=date, end_date=date + pd.Timedelta(days=30))
    for day in schedule.index:
        if day.date() >= date.date():
            return pd.Timestamp(day)
    return pd.Timestamp(date)

# --------------------------------------------------------
# 📈 Kursabruf
# --------------------------------------------------------
def get_price(ticker, currency):
    try:
        data = yf.Ticker(ticker).history(period="1d")
        if data.empty:
            return None
        price = float(data["Close"].iloc[-1])
        if currency == "USD":
            price /= eurusd
        return round(price, 2)
    except Exception:
        return None

# --------------------------------------------------------
# ⚙️ Kursaktualisierung
# --------------------------------------------------------
st.sidebar.title("⚙️ Einstellungen")
if st.sidebar.button("📊 Kurse aktualisieren"):
    st.toast("Lade aktuelle Kurse ...")
    df["Price"] = [get_price(t, c) for t, c in zip(df["Ticker"], df["Currency"])]
    df.to_csv(DATA_PATH, index=False)
else:
    if "Price" not in df.columns:
        df["Price"] = [get_price(t, c) for t, c in zip(df["Ticker"], df["Currency"])]

# --------------------------------------------------------
# 💰 Marktwerte
# --------------------------------------------------------
df["MarketValue"] = (df["Price"] * df["Shares"]).fillna(0).round(2)

# --------------------------------------------------------
# 📆 Sparplan ab 6.11.2025
# --------------------------------------------------------
today = pd.Timestamp(datetime.now(timezone("Europe/Berlin")).date())
plan_day = next_trading_day(pd.Timestamp(2025, 11, 6))

if today >= plan_day:
    for idx, row in df.iterrows():
        if row["Sector"] == "Bestand":  # VW ausschließen
            continue
        price = row["Price"] or get_price(row["Ticker"], row["Currency"])
        if price and price > 0:
            new_shares = row["MonthlyAmount"] / price
            df.at[idx, "Shares"] += new_shares
    st.success(f"Sparplan automatisch ausgeführt am {plan_day.date()} ✅")
    df.to_csv(DATA_PATH, index=False)

# --------------------------------------------------------
# 🧮 Darstellung & Analyse
# --------------------------------------------------------
st.title("💼 Dein persönlicher Depot Rebalancer")

df_display = df.copy()
total_value = df_display.loc[df_display["Sector"] != "Bestand", "MarketValue"].sum()

sector_summary = (
    df_display[df_display["Sector"] != "Bestand"]
    .groupby("Sector")["MarketValue"]
    .sum()
    .reset_index()
)
sector_summary["Percent"] = (sector_summary["MarketValue"] / total_value * 100).round(2)

# --------------------------------------------------------
# 🥧 Pie Chart mit Fehlerprüfung
# --------------------------------------------------------
st.subheader("📊 Sektoraufteilung (ohne VW)")
if not sector_summary.empty and sector_summary["MarketValue"].sum() > 0:
    fig, ax = plt.subplots()
    ax.pie(
        sector_summary["MarketValue"],
        labels=sector_summary["Sector"],
        autopct="%1.1f%%",
        startangle=90
    )
    ax.axis("equal")
    st.pyplot(fig)
else:
    st.info("Keine Kursdaten vorhanden. Bitte zuerst '📊 Kurse aktualisieren' klicken.")

# --------------------------------------------------------
# 🔄 Umschichtungsvorschläge
# --------------------------------------------------------
st.subheader("💡 Umschichtungsvorschläge")
sector_targets = {
    "Technologie & KI": 200,
    "Cybersecurity / Cloud": 50,
    "Erneuerbare Energien & Infra": 100,
    "Zukunft / Disruption": 100,
    "Gesundheit / Stabilität": 50,
    "Konsum & Industrie": 50,
}

for sector, target in sector_targets.items():
    current = df_display[df_display["Sector"] == sector]["MarketValue"].sum()
    diff = current - target
    if abs(diff) > 10:
        if diff > 0:
            suggestion = df_display[df_display["Sector"] == sector].sort_values("MarketValue", ascending=False).iloc[0]["Name"]
            st.warning(f"📉 {sector}: {round(diff, 2)} € zu viel – verkaufe ggf. **{suggestion}** und schichte in untergewichtete Sektoren um.")
        else:
            st.info(f"📈 {sector}: {round(abs(diff), 2)} € zu wenig – erhöhe Anteil durch Nachkauf.")

# --------------------------------------------------------
# 📋 Tabelle
# --------------------------------------------------------
st.subheader("📋 Aktuelles Depot")
st.dataframe(df_display[["Name", "Ticker", "Sector", "Shares", "Price", "MarketValue"]])
