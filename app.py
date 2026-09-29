from pathlib import Path

import pandas as pd
import streamlit as st

import charts

DATA_DIR = Path(__file__).parent / "data"

st.set_page_config(page_title="F1 Race Explorer", page_icon="🏁", layout="wide")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Titillium+Web:ital,wght@0,400;0,600;0,700;0,900;1,900&display=swap');
html, body, [class*="st-"], .stMarkdown, button, input { font-family: 'Titillium Web', 'Segoe UI', sans-serif; }
.block-container { padding-top: 2rem; max-width: 1400px; }
h2, h3 { font-weight: 700; letter-spacing: .01em; }
.hero {
  position: relative; overflow: hidden; border-radius: 14px; padding: 24px 28px; margin-bottom: 14px;
  background: linear-gradient(115deg, #1B1B24 0%, #15151E 55%, rgba(225, 6, 0, .28) 100%);
  border-top: 3px solid #E10600;
}
.hero::after {
  content: ""; position: absolute; top: 0; right: 0; bottom: 0; width: 220px; opacity: .10;
  background-image: conic-gradient(#fff 25%, transparent 0 50%, #fff 0 75%, transparent 0);
  background-size: 18px 18px;
  -webkit-mask-image: linear-gradient(to left, #000, transparent); mask-image: linear-gradient(to left, #000, transparent);
}
.hero .kicker { color: #E10600; font-weight: 700; letter-spacing: .22em; font-size: .78rem; text-transform: uppercase; }
.hero h1 { font-weight: 900; font-style: italic; text-transform: uppercase; font-size: 2.5rem; line-height: 1.1; margin: 4px 0 6px; padding: 0; }
.hero .meta { color: #9A9AAB; font-size: .95rem; }
.kpis { display: grid; grid-template-columns: repeat(auto-fit, minmax(150px, 1fr)); gap: 12px; margin: 4px 0 18px; }
.kpi { background: #1B1B24; border-radius: 10px; padding: 14px 16px; border-left: 4px solid var(--c, #E10600); }
.kpi .label { font-size: .72rem; letter-spacing: .14em; text-transform: uppercase; color: #9A9AAB; }
.kpi .value { font-size: 1.5rem; font-weight: 700; line-height: 1.25; color: #EDEDF2; }
.kpi .sub { font-size: .85rem; color: #9A9AAB; }
.insights { display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; margin: 6px 0 14px; }
.insight { background: rgba(225, 6, 0, .07); border: 1px solid rgba(225, 6, 0, .25); border-radius: 10px; padding: 10px 14px; font-size: .95rem; }
.insight b { color: #EDEDF2; }
.stTabs [data-baseweb="tab-list"] { gap: 6px; }
.stTabs [data-baseweb="tab"] { font-weight: 600; letter-spacing: .03em; padding: 8px 14px; }
</style>
""", unsafe_allow_html=True)


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


def kpi(label, value, sub="", color=charts.ACCENT):
    return (f'<div class="kpi" style="--c:{color}"><div class="label">{label}</div>'
            f'<div class="value">{value}</div><div class="sub">{sub}</div></div>')


def insights(*items):
    st.markdown('<div class="insights">' + "".join(f'<div class="insight">{i}</div>' for i in items if i) + "</div>",
                unsafe_allow_html=True)


def plural(n, word):
    return f"{n} {word}" if n == 1 else f"{n} {word}s"


def show(fig):
    st.plotly_chart(fig, width="stretch", config={"displaylogo": False})


with st.sidebar:
    st.markdown("### 🏁 F1 Race Explorer")
    names = list(races())
    race_label = st.selectbox("Race", names, index=len(names) - 1)
    st.caption("Data: FastF1 timing and telemetry, exported with `prepare_data.py`.")

race = races()[race_label]
info = load(race, "race").iloc[0]
laps = load(race, "laps")
results = load(race, "results")
corners = load(race, "corners")
telemetry = load(race, "telemetry")
periods = charts.track_status_periods(laps)
styles = charts.driver_styles(results)
order = charts.finishing_order(results)

st.markdown(f"""
<div class="hero">
  <div class="kicker">Round report · {info['Year']}</div>
  <h1>{info['Event']}</h1>
  <div class="meta">{info['Circuit']}, {info['Country']} · {info['Date']} · {info['TotalLaps']} laps</div>
</div>
""", unsafe_allow_html=True)

winner = results.sort_values("Position").iloc[0]
fastest = laps.loc[laps["LapTime (s)"].idxmin()]
classified = results.dropna(subset=["Position"])
starters = classified[classified["GridPosition"] > 0].assign(Gain=lambda r: r["GridPosition"] - r["Position"])
gainer = starters.sort_values("Gain", ascending=False).iloc[0]
pit_stops = int((laps["PitIn"] & (laps["LapNumber"] < info["TotalLaps"])).sum())
neutral_laps = sum(end - start + 1 for kind, start, end in periods if kind in ("SC", "VSC"))
finishers = results["ClassifiedPosition"].str.isnumeric().sum()
kinds = pd.Series([kind for kind, _, _ in periods]).value_counts()
period_summary = " · ".join(f"{n}× {charts.STATUS_BANDS[k][0]}" for k, n in kinds.items())

st.markdown('<div class="kpis">' + "".join([
    kpi("Winner", winner["FullName"], winner["Team"], winner["TeamColor"]),
    kpi("Fastest lap", charts.fmt_laptime(fastest["LapTime (s)"]), f"{fastest['Driver']} · lap {fastest['LapNumber']}",
        styles.get(fastest["Driver"], ("#888888",))[0]),
    kpi("Biggest climb", f"+{int(gainer['Gain'])} places", f"{gainer['Driver']} · P{int(gainer['GridPosition'])} → "
        f"P{int(gainer['Position'])}", gainer["TeamColor"]),
    kpi("Pit stops", pit_stops, f"{pit_stops / max(len(results), 1):.1f} per driver"),
    kpi("Neutralised laps", neutral_laps, period_summary or "green all race", "#FFD12E"),
    kpi("Finishers", f"{finishers} / {len(results)}", "classified"),
]) + "</div>", unsafe_allow_html=True)

story_tab, strategy_tab, pace_tab, h2h_tab, brake_tab = st.tabs(
    ["📈 Race story", "🛞 Strategy", "⏱️ Pace", "⚔️ Head to head", "🦶 Brake consistency"])

with story_tab:
    changes = laps.dropna(subset=["Position"]).sort_values("LapNumber").groupby("Driver", observed=True)["Position"]
    swaps = int(changes.diff().abs().fillna(0).sum() // 2)
    leaders = laps[laps["Position"] == 1]["Driver"].astype(str)
    lead_changes = int((leaders.reset_index(drop=True) != leaders.reset_index(drop=True).shift()).sum() - 1)
    most_laps_led = leaders.value_counts()
    insights(
        f"<b>{winner['Driver']}</b> won from P{int(winner['GridPosition'])} on the grid.",
        f"<b>{most_laps_led.index[0]}</b> led the most laps ({most_laps_led.iloc[0]} of {info['TotalLaps']}); "
        f"the lead changed hands <b>{max(lead_changes, 0)}</b> times.",
        f"About <b>{swaps}</b> position swaps over the race, pit stops included.",
    )
    st.markdown("#### Lap-by-lap positions")
    st.caption("Team colours; the second driver of each team is dotted. Shaded bands are safety-car periods.")
    show(charts.position_chart(laps, results, periods))

    st.markdown("#### Classification")
    table = results.sort_values("Position").assign(
        Gained=lambda r: (r["GridPosition"] - r["Position"]).where(
            (r["GridPosition"] > 0) & r["ClassifiedPosition"].str.isnumeric()).map(
            lambda g: "–" if pd.isna(g) else f"{g:+.0f}"),
    )[["ClassifiedPosition", "Driver", "FullName", "Team", "GridPosition", "Gained", "Status", "Points", "TeamColor"]]
    styled = table.style.apply(
        lambda row: [f"border-left: 6px solid {row['TeamColor']}" if col == "ClassifiedPosition" else ""
                     for col in row.index], axis=1)
    st.dataframe(
        styled, hide_index=True, width="stretch", height=35 * len(table) + 38,
        column_order=["ClassifiedPosition", "Driver", "FullName", "Team", "GridPosition", "Gained", "Status", "Points"],
        column_config={
            "ClassifiedPosition": st.column_config.TextColumn("Pos"),
            "FullName": st.column_config.TextColumn("Name"),
            "GridPosition": st.column_config.NumberColumn("Grid", format="%d"),
            "Gained": st.column_config.TextColumn("+/-"),
            "Points": st.column_config.NumberColumn("Pts", format="%d"),
        },
    )

with strategy_tab:
    stints = charts.stints(laps)
    finisher_ids = results.loc[results["ClassifiedPosition"].str.isnumeric(), "Driver"]
    stops = stints.groupby("Driver", observed=True)["Stint"].count().sub(1).reindex(finisher_ids).dropna().astype(int)
    winner_plan = " → ".join(stints[stints["Driver"] == winner["Driver"]]["Compound"].str.title())
    degradation_fig, fits = charts.degradation(laps)
    worst = max(fits, key=fits.get) if fits else None
    if worst and fits[worst] > 0:
        tyre_note = f"Steepest tyre drop-off: <b>{worst.title()}</b> at {fits[worst]:+.3f} s per lap of tyre age."
    elif worst:
        tyre_note = ("Lap times <b>fell</b> as tyres aged on every compound: track evolution and fuel burn "
                     "outweighed tyre wear.")
    else:
        tyre_note = ""
    insights(
        f"Winning strategy: <b>{winner_plan}</b> ({plural(stops.get(winner['Driver'], 0), 'stop')}).",
        f"Among finishers, <b>{stops.idxmax()}</b> stopped the most ({plural(stops.max(), 'stop')}); "
        + (f"<b>{stops.idxmin()}</b> stopped the least ({plural(stops.min(), 'stop')})."
           if (stops == stops.min()).sum() == 1 else
           f"<b>{(stops == stops.min()).sum()}</b> drivers made only {plural(stops.min(), 'stop')}."),
        tyre_note,
    )
    st.markdown("#### Tyre stints")
    st.caption("Ordered by finishing position. The number in each bar is the stint length in laps.")
    show(charts.strategy_chart(laps, results))
    st.markdown("#### Tyre degradation")
    st.caption("Clean green-flag laps only. Fuel burn makes the car faster each lap, so real degradation is a "
               "little higher than these trends show.")
    show(degradation_fig)

with pace_tab:
    medians = laps[laps["IsQuick"]].groupby("Team", observed=True)["LapTime (s)"].median().sort_values()
    ideal = charts.ideal_laps(laps, results[results["ClassifiedPosition"].str.isnumeric()])
    most_left = ideal.sort_values("Time left on table", ascending=False).iloc[0]
    insights(
        f"Fastest team on race pace: <b>{medians.index[0]}</b>, {medians.iloc[1] - medians.iloc[0]:.3f} s per lap "
        f"ahead of {medians.index[1]}.",
        f"Spread from fastest to slowest team: <b>{medians.iloc[-1] - medians.iloc[0]:.2f} s</b> per lap.",
        f"<b>{most_left['Driver']}</b> left the most time on the table: their best sectors add up to a lap "
        f"{most_left['Time left on table']:.3f} s faster than their fastest lap.",
    )
    left, right = st.columns([3, 2])
    with left:
        st.markdown("#### Team race pace")
        st.caption("Distribution of quick laps (within 107 % of the fastest), fastest team first.")
        show(charts.team_pace_chart(laps, results))
    with right:
        st.markdown("#### Driver median pace")
        st.caption("Gap of each driver's median quick lap to the fastest.")
        show(charts.driver_gap_chart(laps, results))

    st.markdown("#### Lap times through the race")
    picked = st.multiselect("Drivers", order, default=order[:3], max_selections=6, key=f"pace-drivers-{race}")
    if picked:
        show(charts.lap_time_chart(laps, picked, results, periods))

    st.markdown("#### Fastest vs ideal lap")
    st.caption("Ideal lap = the sum of a driver's best three sectors.")
    st.dataframe(
        ideal[["Driver", "Team", "Fastest", "Ideal", "Time left on table", "Best S1", "Best S2", "Best S3"]],
        hide_index=True, width="stretch",
        column_config={
            "Fastest": st.column_config.NumberColumn(format="%.3f s"),
            "Ideal": st.column_config.NumberColumn(format="%.3f s"),
            "Time left on table": st.column_config.ProgressColumn(
                format="%.3f s", min_value=0.0, max_value=float(max(ideal["Time left on table"].max(), 0.001))),
            "Best S1": st.column_config.NumberColumn(format="%.3f"),
            "Best S2": st.column_config.NumberColumn(format="%.3f"),
            "Best S3": st.column_config.NumberColumn(format="%.3f"),
        },
    )


def fastest_lap_number(driver):
    rows = laps[(laps["Driver"] == driver) & laps["LapTime (s)"].notna()]
    return int(rows.loc[rows["LapTime (s)"].idxmin(), "LapNumber"])


def lap_picker(column, driver, key):
    lap_numbers = sorted(telemetry.loc[telemetry["Driver"] == driver, "LapNumber"].unique().tolist())
    fastest_lap = fastest_lap_number(driver)
    return column.selectbox(f"{driver} lap", lap_numbers, index=lap_numbers.index(fastest_lap)
                            if fastest_lap in lap_numbers else 0, key=f"{key}-{race}-{driver}", help="Defaults to the fastest lap.")


with h2h_tab:
    with_telemetry = [d for d in order if d in set(telemetry["Driver"])]
    c1, c2, c3, c4 = st.columns(4)
    driver_a = c1.selectbox("Driver A", with_telemetry, index=0, key=f"h2h-a-{race}")
    driver_b = c3.selectbox("Driver B", [d for d in with_telemetry if d != driver_a], index=0,
                            key=f"h2h-b-{race}-{driver_a}")
    lap_a = lap_picker(c2, driver_a, "lap-a")
    lap_b = lap_picker(c4, driver_b, "lap-b")
    tel_a = telemetry[(telemetry["Driver"] == driver_a) & (telemetry["LapNumber"] == lap_a)].sort_values("Distance")
    tel_b = telemetry[(telemetry["Driver"] == driver_b) & (telemetry["LapNumber"] == lap_b)].sort_values("Distance")
    color_a = styles[driver_a][0]
    color_b = styles[driver_b][0] if styles[driver_b][0] != color_a else charts.INK

    h2h_fig, delta = charts.head_to_head_chart(tel_a, tel_b, driver_a, driver_b, color_a, color_b, corners)
    track_fig, sectors_a, sector_count = charts.track_dominance_chart(
        tel_a, tel_b, driver_a, driver_b, color_a, color_b, corners, info["Rotation"])
    apex_fig, apex_gap = charts.apex_speed_chart(tel_a, tel_b, driver_a, driver_b, color_a, color_b, corners)
    final_gap = delta[-1]
    ahead, behind = (driver_a, driver_b) if final_gap >= 0 else (driver_b, driver_a)
    insights(
        f"<b>{ahead}</b> is {abs(final_gap):.3f} s quicker over these laps.",
        f"Top speed: <b>{driver_a}</b> {tel_a['Speed'].max()} km/h vs <b>{driver_b}</b> {tel_b['Speed'].max()} km/h.",
        f"<b>{driver_a}</b> was faster in {sectors_a} of {sector_count} mini-sectors, <b>{driver_b}</b> in "
        f"{sector_count - sectors_a}.",
        f"Time at full throttle: <b>{driver_a}</b> {(tel_a['Throttle'] >= 98).mean():.0%} · "
        f"<b>{driver_b}</b> {(tel_b['Throttle'] >= 98).mean():.0%}.",
    )
    left, right = st.columns(2)
    with left:
        st.markdown("#### Track dominance")
        st.caption("Each mini-sector shows the driver with the higher average speed.")
        show(track_fig)
    with right:
        st.markdown("#### Corner minimum speeds")
        st.caption(f"Biggest corner advantage: {driver_a if apex_gap.max() >= -apex_gap.min() else driver_b} by "
                   f"{max(apex_gap.max(), -apex_gap.min()):.0f} km/h at "
                   f"{apex_gap.idxmax() if apex_gap.max() >= -apex_gap.min() else apex_gap.idxmin()}.")
        show(apex_fig)
    st.markdown("#### Telemetry overlay")
    show(h2h_fig)

with brake_tab:
    st.caption("Stacked brake traces for one driver over several laps, and where each lap starts to brake for each "
               "corner. A tight cluster of dots means a consistent braking point.")
    with_telemetry = [d for d in order if d in set(telemetry["Driver"])]
    c1, c2 = st.columns([1, 3])
    default_driver = "PIA" if "PIA" in with_telemetry and race.startswith("2025-british") else with_telemetry[0]
    driver = c1.selectbox("Driver", with_telemetry, index=with_telemetry.index(default_driver), key=f"brake-driver-{race}")
    driver_tel = telemetry[telemetry["Driver"] == driver].sort_values(["LapNumber", "Distance"])
    green = charts.clean_laps(laps[laps["Driver"] == driver])["LapNumber"].astype(int).tolist()
    lap_numbers = sorted(driver_tel["LapNumber"].unique().tolist())
    notebook_laps = [18, 19, 20, 21, 22]
    default_laps = notebook_laps if driver == "PIA" and race.startswith("2025-british") else green[len(green) // 2:][:5]
    picked_laps = c2.multiselect("Laps (max 6)", lap_numbers, default=[n for n in default_laps if n in lap_numbers],
                                 max_selections=6, key=f"brake-laps-{race}-{driver}")
    max_distance = int(driver_tel["Distance"].max())
    default_zoom = (4000, 5200) if race.startswith("2025-british") else (0, max_distance)
    zoom = st.slider("Distance range (m)", 0, max_distance, default_zoom, step=50, key=f"brake-zoom-{race}-{driver}")

    if not picked_laps:
        st.info("Select one or more laps.")
    else:
        show(charts.brake_trace_chart(driver_tel, picked_laps, corners, zoom))
        points = charts.braking_points(driver_tel, picked_laps, corners)
        if len(picked_laps) > 1 and not points.empty:
            spread = points.groupby("Corner", sort=False)["Before corner (m)"].agg(lambda s: s.max() - s.min())
            insights(
                f"Most consistent braking: <b>{spread.idxmin()}</b>, all laps within {spread.min():.0f} m.",
                f"Least consistent: <b>{spread.idxmax()}</b>, a spread of {spread.max():.0f} m between laps.",
                f"Average spread over {len(spread)} braking zones: <b>{spread.mean():.0f} m</b>.",
            )
            st.markdown("#### Braking points by corner")
            show(charts.braking_point_chart(points, picked_laps))
