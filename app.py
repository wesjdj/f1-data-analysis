from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
import streamlit as st

DATA_DIR = Path(__file__).parent / "data"

TEAM_PALETTE = {
    "Audi": "#00e700",
    "Alpine": "#ff87bc",
    "Mercedes": "#27f4d2",
    "Racing Bulls": "#fcd700",
    "Red Bull Racing": "#0600ef",
    "Williams": "#00a0dd",
    "Ferrari": "#e80020",
    "Aston Martin": "#00665f",
    "McLaren": "#ff8000",
    "Haas F1 Team": "#b6babd",
    "Cadillac": "#AAAADD",
    "Kick Sauber": "#52e252",
}
LAP_COLORS = ["#66B2FF", "#3399FF", "#0066CC", "#004C99", "#003366", "#001F3F"]

st.set_page_config(page_title="F1 Data Analysis", layout="wide")


@st.cache_data(show_spinner=False)
def races():
    found = {}
    for race_dir in sorted(DATA_DIR.iterdir()):
        info = pd.read_parquet(race_dir / "race.parquet").iloc[0]
        found[f"{info['Year']} {info['Event']}"] = race_dir.name
    return found


@st.cache_data(show_spinner=False)
def load(race, table):
    return pd.read_parquet(DATA_DIR / race / f"{table}.parquet")


def pick_race(key, default):
    names = list(races())
    index = names.index(default) if default in names else 0
    label = st.selectbox("Race", names, index=index, key=f"{key}-race")
    return label, races()[label]


def brake_traces_tab():
    st.subheader("Brake traces")
    label, race = pick_race("brake", "2025 British Grand Prix")
    telemetry = load(race, "telemetry")
    corners = load(race, "corners")

    drivers = sorted(telemetry["Driver"].unique())
    col1, col2 = st.columns([1, 3])
    driver = col1.selectbox("Driver", drivers, index=drivers.index("PIA") if "PIA" in drivers else 0)
    driver_telemetry = telemetry[telemetry["Driver"] == driver]
    lap_numbers = sorted(driver_telemetry["LapNumber"].unique().tolist())
    default_laps = [n for n in [18, 19, 20, 21, 22] if n in lap_numbers] or lap_numbers[:3]
    laps = col2.multiselect("Laps (max 6)", lap_numbers, default=default_laps, max_selections=6)

    max_distance = int(driver_telemetry["Distance"].max())
    zoom = st.slider("Distance range (m)", 0, max_distance,
                     (min(4000, max_distance), min(5200, max_distance)), step=50)

    if not laps:
        st.info("Select one or more laps.")
        return

    offset = 0.3
    fig, ax = plt.subplots(figsize=(16, 7), facecolor="white")
    ax.set_facecolor("white")
    for i, lap_number in enumerate(laps):
        lap = driver_telemetry[driver_telemetry["LapNumber"] == lap_number]
        ax.plot(lap["Distance"], lap["Brake"].astype(float) + i * offset,
                label=f"Lap {lap_number}", linewidth=2.5, color=LAP_COLORS[i], alpha=0.85)

    y_max = len(laps) * offset + 1.1
    for _, corner in corners.iterrows():
        if not zoom[0] <= corner["Distance"] <= zoom[1]:
            continue
        ax.axvline(x=corner["Distance"], color="#CCCCCC", linestyle="--", alpha=0.5, linewidth=1.2)
        text = f"{corner['Number']}{corner['Letter']}" if corner["Letter"] else str(corner["Number"])
        ax.text(corner["Distance"], y_max + 0.05, text, ha="center", fontsize=9, alpha=0.7, fontweight="bold")

    ax.set_xlim(*zoom)
    ax.set_xlabel("Distance (m)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Brake Application (Stacked)", fontsize=12, fontweight="bold")
    ax.set_title(f"{driver} - Brake Traces (Distance: {zoom[0]}-{zoom[1]} m)\n{label}",
                 fontsize=14, fontweight="bold", pad=20)
    ax.legend(loc="upper right", fontsize=11, framealpha=0.95)
    ax.grid(True, alpha=0.25, linewidth=0.5, axis="x")
    ax.set_ylim(-0.1, y_max + 0.2)
    ax.set_yticks([])
    fig.tight_layout()
    st.pyplot(fig)
    plt.close(fig)


def team_pace_tab():
    st.subheader("Team race pace")
    label, race = pick_race("pace", "2026 Australian Grand Prix")
    laps = load(race, "laps")
    laps = laps[laps["IsQuick"]].astype({"Team": str})
    order = laps.groupby("Team")["LapTime (s)"].median().sort_values().index
    palette = {team: TEAM_PALETTE.get(team, "#888888") for team in order}

    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=(15, 9))
        sns.boxplot(
            data=laps, x="Team", y="LapTime (s)", hue="Team", order=order, palette=palette,
            whiskerprops=dict(color="white"), boxprops=dict(edgecolor="white"),
            medianprops=dict(color="grey"), capprops=dict(color="white"), ax=ax,
        )
        ax.set_title(label)
        ax.set(xlabel=None)
        ax.grid(visible=False)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)


st.title("F1 Data Analysis")
st.caption("Data from the FastF1 library, exported with prepare_data.py.")
brake_tab, pace_tab = st.tabs(["Brake traces", "Team pace"])
with brake_tab:
    brake_traces_tab()
with pace_tab:
    team_pace_tab()
