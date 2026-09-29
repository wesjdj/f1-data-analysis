"""Plotly figures and race analysis helpers for app.py."""

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

INK = "#EDEDF2"
MUTED = "#9A9AAB"
GRID = "#2A2A36"
SURFACE = "#0F0F14"
PANEL = "#1B1B24"
ACCENT = "#E10600"
FONT = "Titillium Web, Segoe UI, sans-serif"

COMPOUND_COLORS = {
    "SOFT": "#DA291C",
    "MEDIUM": "#FFD12E",
    "HARD": "#F0F0EC",
    "INTERMEDIATE": "#43B02A",
    "WET": "#0067AD",
}
DARK_TEXT_COMPOUNDS = {"MEDIUM", "HARD"}
STATUS_BANDS = {
    "SC": ("SC", "rgba(255, 209, 46, 0.16)"),
    "VSC": ("VSC", "rgba(255, 209, 46, 0.08)"),
    "RED": ("RED FLAG", "rgba(225, 6, 0, 0.20)"),
}
LAP_COLORS = ["#9CCBFF", "#66B2FF", "#3399FF", "#0066CC", "#004C99", "#003366"]


def style(fig, height=460, **layout):
    fig.update_layout(
        template="plotly_dark",
        height=height,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family=FONT, color=INK, size=13),
        margin=dict(l=10, r=10, t=40, b=10),
        hoverlabel=dict(font_family=FONT, bgcolor=PANEL, bordercolor=GRID),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0, bgcolor="rgba(0,0,0,0)"),
        **layout,
    )
    fig.update_xaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    fig.update_yaxes(gridcolor=GRID, zeroline=False, linecolor=GRID)
    return fig


def fmt_laptime(seconds):
    if pd.isna(seconds):
        return "–"
    minutes = int(seconds // 60)
    return f"{minutes}:{seconds - 60 * minutes:06.3f}"


def rgba(hex_color, alpha):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"


def driver_styles(results):
    styles = {}
    seen = set()
    for _, row in results.sort_values("Position").iterrows():
        styles[row["Driver"]] = (row["TeamColor"], "dot" if row["Team"] in seen else "solid")
        seen.add(row["Team"])
    return styles


def team_colors(results):
    return results.drop_duplicates("Team").set_index("Team")["TeamColor"].to_dict()


def finishing_order(results):
    return results.sort_values("Position")["Driver"].tolist()


def track_status_periods(laps):
    flags = laps.groupby("LapNumber")["TrackStatus"].agg("".join)
    periods = []
    for lap, codes in flags.items():
        kind = "RED" if "5" in codes else "SC" if "4" in codes else "VSC" if ("6" in codes or "7" in codes) else None
        if kind is None:
            continue
        if periods and periods[-1][0] == kind and periods[-1][2] == lap - 1:
            periods[-1][2] = lap
        else:
            periods.append([kind, lap, lap])
    return periods


def add_status_bands(fig, periods):
    for kind, start, end in periods:
        label, color = STATUS_BANDS[kind]
        fig.add_vrect(
            x0=start - 0.5, x1=end + 0.5, fillcolor=color, line_width=0, layer="below",
            annotation_text=label, annotation_position="top left",
            annotation_font=dict(color=MUTED, size=11),
        )


def position_chart(laps, results, periods):
    styles = driver_styles(results)
    fig = go.Figure()
    last_lap = int(laps["LapNumber"].max())
    for driver in finishing_order(results):
        data = laps[laps["Driver"] == driver].dropna(subset=["Position"])
        if data.empty:
            continue
        color, dash = styles[driver]
        fig.add_trace(go.Scatter(
            x=data["LapNumber"], y=data["Position"], mode="lines", name=driver,
            line=dict(color=color, width=2.2, dash=dash),
            customdata=data[["Compound"]].astype(str),
            hovertemplate="<b>%{fullData.name}</b> · Lap %{x}<br>P%{y} · %{customdata[0]}<extra></extra>",
        ))
        end = data.iloc[-1]
        fig.add_annotation(
            x=end["LapNumber"], y=end["Position"], text=driver, showarrow=False,
            xanchor="left", xshift=6, font=dict(size=11, color=INK if end["LapNumber"] == last_lap else MUTED),
        )
    add_status_bands(fig, periods)
    style(fig, height=620, showlegend=False, hovermode="closest")
    fig.update_yaxes(range=[len(results) + 0.5, 0.5], dtick=1, title="Position")
    fig.update_xaxes(title="Lap", range=[0.5, last_lap + 3])
    return fig


def stints(laps):
    return (
        laps.dropna(subset=["Stint"])
        .groupby(["Driver", "Stint"], observed=True)
        .agg(Compound=("Compound", "first"), Start=("LapNumber", "min"), End=("LapNumber", "max"))
        .reset_index()
        .assign(Laps=lambda s: s["End"] - s["Start"] + 1, Compound=lambda s: s["Compound"].astype(str))
    )


def strategy_chart(laps, results):
    order = [d for d in finishing_order(results) if d in set(laps["Driver"])]
    data = stints(laps)
    data = data[data["Driver"].isin(order)]
    fig = go.Figure()
    for compound in [c for c in COMPOUND_COLORS if c in set(data["Compound"])] + \
            sorted(set(data["Compound"]) - set(COMPOUND_COLORS)):
        rows = data[data["Compound"] == compound]
        fig.add_trace(go.Bar(
            y=rows["Driver"], x=rows["Laps"], base=rows["Start"] - 1, orientation="h", name=compound.title(),
            marker=dict(color=COMPOUND_COLORS.get(compound, "#888888"), line=dict(color=SURFACE, width=2)),
            text=rows["Laps"], textposition="inside", insidetextanchor="middle", textangle=0,
            textfont=dict(color=SURFACE if compound in DARK_TEXT_COMPOUNDS else INK, size=11),
            customdata=rows[["Start", "End"]],
            hovertemplate="<b>%{y}</b> · " + compound.title() +
                          "<br>Laps %{customdata[0]}–%{customdata[1]} (%{x} laps)<extra></extra>",
        ))
    style(fig, height=26 * len(order) + 110, barmode="overlay", bargap=0.25, barcornerradius=4)
    fig.update_yaxes(categoryorder="array", categoryarray=order, autorange="reversed", showgrid=False)
    fig.update_xaxes(title="Lap")
    return fig


def clean_laps(laps):
    return laps[
        laps["IsQuick"] & ~laps["PitIn"] & ~laps["PitOut"]
        & (laps["TrackStatus"] == "1") & laps["LapTime (s)"].notna()
    ]


def degradation(laps):
    data = clean_laps(laps).dropna(subset=["TyreLife"])
    fits = {}
    fig = go.Figure()
    for compound, rows in data.groupby(data["Compound"].astype(str)):
        if len(rows) < 12:
            continue
        color = COMPOUND_COLORS.get(compound, "#888888")
        fig.add_trace(go.Scatter(
            x=rows["TyreLife"], y=rows["LapTime (s)"], mode="markers", name=compound.title(),
            legendgroup=compound, marker=dict(color=color, size=8, opacity=0.35, line=dict(width=0)),
            customdata=rows[["Driver", "LapNumber"]],
            hovertemplate="%{customdata[0]} · Lap %{customdata[1]}<br>Tyre age %{x} · %{y:.3f} s<extra></extra>",
        ))
        slope, intercept = np.polyfit(rows["TyreLife"], rows["LapTime (s)"], 1)
        fits[compound] = slope
        x = np.array([rows["TyreLife"].min(), rows["TyreLife"].max()])
        fig.add_trace(go.Scatter(
            x=x, y=slope * x + intercept, mode="lines", legendgroup=compound, showlegend=False,
            line=dict(color=color, width=3), hovertemplate=f"{compound.title()} trend: {slope:+.3f} s/lap<extra></extra>",
        ))
    style(fig, height=440)
    fig.update_xaxes(title="Tyre age (laps)")
    fig.update_yaxes(title="Lap time (s)")
    return fig, fits


def team_pace_chart(laps, results):
    data = laps[laps["IsQuick"]].astype({"Team": str})
    colors = team_colors(results)
    order = data.groupby("Team")["LapTime (s)"].median().sort_values().index
    fig = go.Figure()
    for team in order:
        rows = data[data["Team"] == team]
        color = colors.get(team, "#888888")
        fig.add_trace(go.Box(
            y=rows["LapTime (s)"], name=team, marker=dict(color=color, size=5), line=dict(color=color, width=2),
            fillcolor=rgba(color, 0.3), boxpoints="outliers",
            customdata=rows[["Driver", "LapNumber"]],
            hovertemplate="%{customdata[0]} · Lap %{customdata[1]}<br>%{y:.3f} s<extra>" + team + "</extra>",
        ))
    style(fig, height=480, showlegend=False)
    fig.update_yaxes(title="Lap time (s)")
    return fig


def driver_gap_chart(laps, results):
    styles = driver_styles(results)
    medians = laps[laps["IsQuick"]].groupby("Driver", observed=True)["LapTime (s)"].median().dropna().sort_values()
    gaps = medians - medians.iloc[0]
    fig = go.Figure(go.Bar(
        x=gaps.values, y=gaps.index, orientation="h",
        marker=dict(color=[styles.get(d, ("#888888", ""))[0] for d in gaps.index]),
        text=[f"+{g:.3f}" if g else "fastest" for g in gaps.values], textposition="outside",
        textfont=dict(color=MUTED, size=11),
        customdata=medians.values,
        hovertemplate="<b>%{y}</b><br>Median lap %{customdata:.3f} s (+%{x:.3f} s)<extra></extra>",
    ))
    style(fig, height=24 * len(gaps) + 90, showlegend=False, barcornerradius=4, bargap=0.3)
    fig.update_yaxes(autorange="reversed", showgrid=False)
    fig.update_xaxes(title="Gap to fastest median lap (s)", range=[0, gaps.max() * 1.18 + 0.05])
    return fig


def lap_time_chart(laps, drivers, results, periods):
    styles = driver_styles(results)
    reference = laps.loc[laps["IsQuick"], "LapTime (s)"].median()
    fig = go.Figure()
    for driver in drivers:
        rows = laps[(laps["Driver"] == driver) & (laps["LapTime (s)"] < reference * 1.12)]
        color, dash = styles.get(driver, ("#888888", "solid"))
        fig.add_trace(go.Scatter(
            x=rows["LapNumber"], y=rows["LapTime (s)"], mode="lines+markers", name=driver,
            line=dict(color=color, width=2, dash=dash), marker=dict(size=7, color=color, line=dict(color=SURFACE, width=1)),
            customdata=np.stack([rows["Compound"].astype(str), rows["TyreLife"].fillna(0)], axis=-1),
            hovertemplate="%{fullData.name}: %{y:.3f} s · %{customdata[0]} (%{customdata[1]:.0f} laps)<extra></extra>",
        ))
    add_status_bands(fig, periods)
    style(fig, height=440, hovermode="x unified")
    fig.update_xaxes(title="Lap")
    fig.update_yaxes(title="Lap time (s)")
    return fig


def ideal_laps(laps, results):
    sectors = ["Sector1 (s)", "Sector2 (s)", "Sector3 (s)"]
    valid = laps[laps["Driver"].isin(results["Driver"]) & laps["LapTime (s)"].notna() & ~laps["PitIn"]
                 & ~laps["PitOut"] & (laps["LapNumber"] > 1)]
    best = valid.groupby("Driver", observed=True).agg(
        Fastest=("LapTime (s)", "min"), **{f"Best S{i + 1}": (s, "min") for i, s in enumerate(sectors)},
    )
    best["Ideal"] = best[[f"Best S{i}" for i in (1, 2, 3)]].sum(axis=1)
    best["Time left on table"] = best["Fastest"] - best["Ideal"]
    best = best.join(results.set_index("Driver")[["Team"]], how="inner").sort_values("Fastest")
    return best.reset_index()


def lap_delta(tel_a, tel_b):
    time_b = np.interp(tel_a["Distance"], tel_b["Distance"], tel_b["Time"])
    return time_b - tel_a["Time"].to_numpy()


def add_corner_lines(fig, corners, x_range=None, label_row_y=1.0):
    for _, corner in corners.iterrows():
        if x_range and not x_range[0] <= corner["Distance"] <= x_range[1]:
            continue
        fig.add_vline(x=corner["Distance"], line=dict(color=GRID, width=1, dash="dot"), layer="below")
        text = f"{corner['Number']}{corner['Letter'] or ''}"
        fig.add_annotation(
            x=corner["Distance"], y=label_row_y, yref="paper", text=text, showarrow=False,
            yanchor="bottom", font=dict(size=10, color=MUTED),
        )


def head_to_head_chart(tel_a, tel_b, name_a, name_b, color_a, color_b, corners):
    fig = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.035, row_heights=[0.22, 0.42, 0.2, 0.16],
    )
    delta = lap_delta(tel_a, tel_b)
    fig.add_trace(go.Scatter(
        x=tel_a["Distance"], y=delta, mode="lines", name="Gap", showlegend=False,
        line=dict(color=INK, width=2), fill="tozeroy", fillcolor="rgba(237, 237, 242, 0.08)",
        hovertemplate=f"{name_a} ahead by %{{y:.3f}} s<extra></extra>",
    ), row=1, col=1)
    for tel, name, color, dash in [(tel_a, name_a, color_a, "solid"), (tel_b, name_b, color_b, "dot")]:
        common = dict(x=tel["Distance"], mode="lines", legendgroup=name, line=dict(color=color, width=2, dash=dash))
        fig.add_trace(go.Scatter(y=tel["Speed"], name=name, hovertemplate=name + ": %{y} km/h<extra></extra>",
                                 **common), row=2, col=1)
        fig.add_trace(go.Scatter(y=tel["Throttle"], name=name, showlegend=False,
                                 hovertemplate=name + ": %{y}% throttle<extra></extra>", **common), row=3, col=1)
        fig.add_trace(go.Scatter(y=tel["Brake"].astype(int), name=name, showlegend=False, line_shape="hv",
                                 hovertemplate=name + ": %{y:brake}<extra></extra>", **common), row=4, col=1)
    add_corner_lines(fig, corners)
    style(fig, height=720, hovermode="x unified")
    fig.update_yaxes(title_text=f"Gap (s)<br><sup>+ = {name_a} ahead</sup>", row=1, col=1)
    fig.update_yaxes(title_text="Speed (km/h)", row=2, col=1)
    fig.update_yaxes(title_text="Throttle (%)", range=[-5, 105], row=3, col=1)
    fig.update_yaxes(title_text="Brake", tickvals=[0, 1], ticktext=["off", "on"], range=[-0.15, 1.15], row=4, col=1)
    fig.update_xaxes(title_text="Distance (m)", row=4, col=1)
    fig.update_layout(legend=dict(y=1.06))
    return fig, delta


def rotate(x, y, degrees):
    angle = np.radians(degrees)
    return x * np.cos(angle) - y * np.sin(angle), x * np.sin(angle) + y * np.cos(angle)


def track_dominance_chart(tel_a, tel_b, name_a, name_b, color_a, color_b, corners, rotation, sectors=25):
    edges = np.linspace(0, tel_a["Distance"].max(), sectors + 1)
    speed_a = tel_a.groupby(pd.cut(tel_a["Distance"], edges), observed=False)["Speed"].mean()
    speed_b = tel_b.groupby(pd.cut(tel_b["Distance"], edges), observed=False)["Speed"].mean()
    winner_a = (speed_a >= speed_b).to_numpy()

    x, y = rotate(tel_a["X"].to_numpy(), tel_a["Y"].to_numpy(), rotation)
    sector_index = np.clip(np.searchsorted(edges, tel_a["Distance"].to_numpy(), side="right") - 1, 0, sectors - 1)
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=y, mode="lines", line=dict(color=GRID, width=14), hoverinfo="skip", showlegend=False))
    shown = set()
    for i in range(sectors):
        idx = np.flatnonzero(sector_index == i)
        if idx.size == 0:
            continue
        idx = np.append(idx, min(idx[-1] + 1, len(x) - 1))
        name, color = (name_a, color_a) if winner_a[i] else (name_b, color_b)
        fig.add_trace(go.Scatter(
            x=x[idx], y=y[idx], mode="lines", name=f"{name} faster", legendgroup=name,
            showlegend=name not in shown, line=dict(color=color, width=7),
            hovertemplate=f"Mini-sector {i + 1}<br>{name_a} {speed_a.iloc[i]:.0f} km/h · "
                          f"{name_b} {speed_b.iloc[i]:.0f} km/h<extra></extra>",
        ))
        shown.add(name)
    cx, cy = rotate(corners["X"].to_numpy(), corners["Y"].to_numpy(), rotation)
    centre_x, centre_y = x.mean(), y.mean()
    norm = np.hypot(cx - centre_x, cy - centre_y) + 1e-9
    push = 0.06 * max(np.ptp(x), np.ptp(y))
    cx, cy = cx + (cx - centre_x) / norm * push, cy + (cy - centre_y) / norm * push
    fig.add_trace(go.Scatter(
        x=cx, y=cy, mode="text", text=[f"{n}{l or ''}" for n, l in zip(corners["Number"], corners["Letter"])],
        textfont=dict(color=MUTED, size=11), hoverinfo="skip", showlegend=False,
    ))
    style(fig, height=500)
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False, scaleanchor="x", scaleratio=1)
    return fig, int(winner_a.sum()), sectors


def brake_trace_chart(driver_tel, laps, corners, zoom):
    fig = go.Figure()
    offset = 0.3
    for i, lap_number in enumerate(laps):
        lap = driver_tel[driver_tel["LapNumber"] == lap_number]
        fig.add_trace(go.Scatter(
            x=lap["Distance"], y=lap["Brake"].astype(float) + i * offset, mode="lines", name=f"Lap {lap_number}",
            line=dict(color=LAP_COLORS[i % len(LAP_COLORS)], width=2.5, shape="hv"),
            customdata=lap["Speed"], hovertemplate=f"Lap {lap_number}" + " · %{x:.0f} m · %{customdata} km/h<extra></extra>",
        ))
    add_corner_lines(fig, corners, x_range=zoom)
    style(fig, height=460, hovermode="closest")
    fig.update_xaxes(title="Distance (m)", range=list(zoom))
    fig.update_yaxes(showticklabels=False, showgrid=False, title="Brake application (stacked by lap)")
    return fig


def braking_points(driver_tel, laps, corners, window=350):
    rows = []
    for _, corner in corners.iterrows():
        label = f"T{corner['Number']}{corner['Letter'] or ''}"
        for lap_number in laps:
            lap = driver_tel[driver_tel["LapNumber"] == lap_number]
            seg = lap[(lap["Distance"] >= corner["Distance"] - window) & (lap["Distance"] <= corner["Distance"] + 30)]
            brake = seg["Brake"].to_numpy()
            if brake.size == 0 or brake[0]:
                continue
            onset = np.flatnonzero(brake)
            if onset.size == 0:
                continue
            point = seg.iloc[onset[0]]
            rows.append({"Corner": label, "Lap": lap_number, "Before corner (m)": corner["Distance"] - point["Distance"],
                         "Entry speed (km/h)": point["Speed"]})
    data = pd.DataFrame(rows)
    if data.empty:
        return data
    counts = data.groupby("Corner")["Lap"].transform("count")
    return data[counts >= max(2, 0.6 * len(laps))]


def braking_point_chart(points, laps):
    order = list(dict.fromkeys(points["Corner"]))
    fig = go.Figure()
    n = len(laps)
    for i, lap_number in enumerate(laps):
        rows = points[points["Lap"] == lap_number]
        x = [order.index(c) + (i - (n - 1) / 2) * 0.09 for c in rows["Corner"]]
        fig.add_trace(go.Scatter(
            x=x, y=rows["Before corner (m)"], mode="markers", name=f"Lap {lap_number}",
            marker=dict(color=LAP_COLORS[i % len(LAP_COLORS)], size=11, line=dict(color=SURFACE, width=2)),
            customdata=rows[["Corner", "Entry speed (km/h)"]],
            hovertemplate=f"Lap {lap_number} · " + "%{customdata[0]}<br>Brakes %{y:.0f} m before the corner"
                                                   "<br>%{customdata[1]} km/h at the brake point<extra></extra>",
        ))
    style(fig, height=420)
    fig.update_xaxes(tickvals=list(range(len(order))), ticktext=order, showgrid=False, title="Corner")
    fig.update_yaxes(title="Braking point (m before corner)")
    return fig


def apex_speeds(tel, corners, window=80):
    speeds = {}
    for _, corner in corners.iterrows():
        seg = tel[(tel["Distance"] - corner["Distance"]).abs() <= window]
        if not seg.empty:
            speeds[f"T{corner['Number']}{corner['Letter'] or ''}"] = seg["Speed"].min()
    return pd.Series(speeds)


def apex_speed_chart(tel_a, tel_b, name_a, name_b, color_a, color_b, corners):
    speed_a, speed_b = apex_speeds(tel_a, corners), apex_speeds(tel_b, corners)
    fig = go.Figure()
    for speeds, name, color in [(speed_a, name_a, color_a), (speed_b, name_b, color_b)]:
        fig.add_trace(go.Bar(
            x=speeds.index, y=speeds.values, name=name, marker=dict(color=color, line=dict(color=SURFACE, width=2)),
            hovertemplate=name + " · %{x}: %{y} km/h<extra></extra>",
        ))
    style(fig, height=500, barmode="group", bargap=0.25, barcornerradius=4)
    fig.update_yaxes(title="Minimum speed (km/h)")
    return fig, (speed_a - speed_b).dropna()
