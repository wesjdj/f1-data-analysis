import os
import tempfile

import fastf1
import fastf1.plotting
import matplotlib.pyplot as plt
import seaborn as sns
import streamlit as st

CACHE_DIR = os.environ.get("FASTF1_CACHE", os.path.join(tempfile.gettempdir(), "fastf1-cache"))
os.makedirs(CACHE_DIR, exist_ok=True)
fastf1.Cache.enable_cache(CACHE_DIR)

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
}
LAP_COLORS = ["#66B2FF", "#3399FF", "#0066CC", "#004C99", "#003366", "#001F3F"]

st.set_page_config(page_title="F1 Data Analysis", layout="wide")


@st.cache_data(show_spinner=False)
def event_names(year):
    schedule = fastf1.get_event_schedule(year, include_testing=False)
    return schedule["EventName"].tolist()


@st.cache_resource(show_spinner=False)
def load_session(year, event, kind, telemetry):
    session = fastf1.get_session(year, event, kind)
    session.load(telemetry=telemetry, weather=False, messages=False)
    return session


def pick_event(key, default_year, default_event):
    col1, col2 = st.columns([1, 3])
    year = col1.number_input("Season", 2018, 2026, default_year, key=f"{key}-year")
    names = event_names(int(year))
    index = names.index(default_event) if default_event in names else 0
    event = col2.selectbox("Grand Prix", names, index=index, key=f"{key}-event")
    return int(year), event


def brake_traces_tab():
    st.subheader("Brake traces")
    year, event = pick_event("brake", 2025, "British Grand Prix")
    with st.spinner("Loading session telemetry..."):
        session = load_session(year, event, "R", True)

    drivers = sorted(session.laps["Driver"].dropna().unique())
    col1, col2 = st.columns([1, 3])
    driver = col1.selectbox("Driver", drivers, index=drivers.index("PIA") if "PIA" in drivers else 0)
    driver_laps = session.laps.pick_drivers(driver)
    lap_numbers = sorted(int(n) for n in driver_laps["LapNumber"].dropna())
    default_laps = [n for n in [18, 19, 20, 21, 22] if n in lap_numbers] or lap_numbers[:3]
    laps = col2.multiselect("Laps (max 6)", lap_numbers, default=default_laps, max_selections=6)

    circuit = session.get_circuit_info()
    max_distance = int(circuit.corners["Distance"].max()) + 500
    zoom = st.slider("Distance range (m)", 0, max_distance, (min(4000, max_distance), min(5200, max_distance)), step=50)

    if not laps:
        st.info("Select one or more laps.")
        return

    offset = 0.3
    fig, ax = plt.subplots(figsize=(16, 7), facecolor="white")
    ax.set_facecolor("white")
    for i, lap_number in enumerate(laps):
        lap = driver_laps[driver_laps["LapNumber"] == lap_number].iloc[0]
        telemetry = lap.get_telemetry()
        ax.plot(telemetry["Distance"], telemetry["Brake"] + i * offset,
                label=f"Lap {lap_number}", linewidth=2.5, color=LAP_COLORS[i], alpha=0.85)

    y_max = len(laps) * offset + 1.1
    for _, corner in circuit.corners.iterrows():
        if not zoom[0] <= corner["Distance"] <= zoom[1]:
            continue
        ax.axvline(x=corner["Distance"], color="#CCCCCC", linestyle="--", alpha=0.5, linewidth=1.2)
        label = f"{corner['Number']}{corner['Letter']}" if corner["Letter"] else str(corner["Number"])
        ax.text(corner["Distance"], y_max + 0.05, label, ha="center", fontsize=9, alpha=0.7, fontweight="bold")

    ax.set_xlim(*zoom)
    ax.set_xlabel("Distance (m)", fontsize=12, fontweight="bold")
    ax.set_ylabel("Brake Application (Stacked)", fontsize=12, fontweight="bold")
    ax.set_title(f"{driver} - Brake Traces (Distance: {zoom[0]}-{zoom[1]} m)\n{year} {event}",
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
    year, event = pick_event("pace", 2026, "Australian Grand Prix")
    with st.spinner("Loading session laps..."):
        session = load_session(year, event, "R", False)

    laps = session.laps.pick_quicklaps().copy()
    laps["LapTime (s)"] = laps["LapTime"].dt.total_seconds()
    order = laps.groupby("Team")["LapTime (s)"].median().sort_values().index
    palette = {team: TEAM_PALETTE.get(team, "#888888") for team in order}

    with plt.style.context("dark_background"):
        fig, ax = plt.subplots(figsize=(15, 9))
        sns.boxplot(
            data=laps, x="Team", y="LapTime (s)", hue="Team", order=order, palette=palette,
            whiskerprops=dict(color="white"), boxprops=dict(edgecolor="white"),
            medianprops=dict(color="grey"), capprops=dict(color="white"), ax=ax,
        )
        ax.set_title(f"{year} {event}")
        ax.set(xlabel=None)
        ax.grid(visible=False)
        plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        fig.tight_layout()
        st.pyplot(fig)
        plt.close(fig)


st.title("F1 Data Analysis")
st.caption("Data from the FastF1 library. The first load of a session can take up to a minute.")
brake_tab, pace_tab = st.tabs(["Brake traces", "Team pace"])
with brake_tab:
    brake_traces_tab()
with pace_tab:
    team_pace_tab()
