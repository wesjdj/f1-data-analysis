"""Export the race data that app.py uses to compact Parquet files in data/."""

import argparse
import os
import re

import fastf1
import pandas as pd

RACES = [
    (2025, "British Grand Prix"),
    (2026, "Australian Grand Prix"),
]


def slug(year, event):
    return f"{year}-{re.sub(r'[^a-z0-9]+', '-', event.lower()).strip('-')}"


def save(frame, race_dir, name):
    frame.to_parquet(os.path.join(race_dir, f"{name}.parquet"), compression="zstd", index=False)


def lap_telemetry(lap):
    car = lap.get_car_data(pad=1, pad_side="both")
    pos = lap.get_pos_data(pad=1, pad_side="both")
    return car.merge_channels(pos, frequency="original").slice_by_lap(lap).add_distance()


def export_laps(session, race_dir):
    laps = session.laps
    quick = laps.index.isin(laps.pick_quicklaps().index)
    save(pd.DataFrame({
        "Driver": laps["Driver"].astype("category"),
        "Team": laps["Team"].astype("category"),
        "LapNumber": laps["LapNumber"].astype("Int16"),
        "LapTime (s)": laps["LapTime"].dt.total_seconds().astype("float32"),
        "SessionTime (s)": laps["Time"].dt.total_seconds().astype("float32"),
        "Sector1 (s)": laps["Sector1Time"].dt.total_seconds().astype("float32"),
        "Sector2 (s)": laps["Sector2Time"].dt.total_seconds().astype("float32"),
        "Sector3 (s)": laps["Sector3Time"].dt.total_seconds().astype("float32"),
        "SpeedTrap": laps["SpeedST"].astype("float32"),
        "Position": laps["Position"].astype("Int8"),
        "Stint": laps["Stint"].astype("Int8"),
        "Compound": laps["Compound"].astype("category"),
        "TyreLife": laps["TyreLife"].astype("float32"),
        "PitIn": laps["PitInTime"].notna(),
        "PitOut": laps["PitOutTime"].notna(),
        "TrackStatus": laps["TrackStatus"].astype(str),
        "IsQuick": quick,
    }), race_dir, "laps")


def export_results(session, race_dir):
    results = session.results
    save(pd.DataFrame({
        "Driver": results["Abbreviation"],
        "FullName": results["FullName"],
        "Team": results["TeamName"],
        "TeamColor": "#" + results["TeamColor"].fillna("888888"),
        "GridPosition": results["GridPosition"].astype("float32"),
        "Position": results["Position"].astype("float32"),
        "ClassifiedPosition": results["ClassifiedPosition"].astype(str),
        "Status": results["Status"].astype(str),
        "Points": results["Points"].astype("float32"),
    }), race_dir, "results")


def export_telemetry(session, race_dir):
    frames = []
    for _, lap in session.laps.iterlaps():
        if pd.isna(lap["LapNumber"]):
            continue
        try:
            telemetry = lap_telemetry(lap)
        except Exception:
            continue
        frames.append(pd.DataFrame({
            "Driver": lap["Driver"],
            "LapNumber": int(lap["LapNumber"]),
            "Distance": telemetry["Distance"].astype("float32"),
            "Time": telemetry["Time"].dt.total_seconds().astype("float32"),
            "Speed": telemetry["Speed"].round().astype("int16"),
            "Throttle": telemetry["Throttle"].clip(0, 100).round().astype("int8"),
            "Brake": telemetry["Brake"].astype(bool),
            "Gear": telemetry["nGear"].astype("int8"),
            "X": telemetry["X"].astype("float32"),
            "Y": telemetry["Y"].astype("float32"),
        }))
    telemetry = pd.concat(frames, ignore_index=True)
    telemetry["Driver"] = telemetry["Driver"].astype("category")
    telemetry["LapNumber"] = telemetry["LapNumber"].astype("int16")
    save(telemetry, race_dir, "telemetry")


def export_race(year, event, out_dir):
    session = fastf1.get_session(year, event, "R")
    session.load(weather=False, messages=False)
    race_dir = os.path.join(out_dir, slug(year, event))
    os.makedirs(race_dir, exist_ok=True)

    export_laps(session, race_dir)
    export_results(session, race_dir)
    circuit = session.get_circuit_info()
    save(circuit.corners[["Number", "Letter", "Distance", "X", "Y"]], race_dir, "corners")
    save(pd.DataFrame({
        "Year": [year],
        "Event": [event],
        "Circuit": [session.event["Location"]],
        "Country": [session.event["Country"]],
        "Date": [session.event["EventDate"].date().isoformat()],
        "TotalLaps": [int(session.laps["LapNumber"].max())],
        "Rotation": [float(circuit.rotation)],
    }), race_dir, "race")
    export_telemetry(session, race_dir)
    print(f"Exported {year} {event} to {race_dir}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="data")
    parser.add_argument("--cache", default="cache")
    args = parser.parse_args()
    os.makedirs(args.cache, exist_ok=True)
    fastf1.Cache.enable_cache(args.cache)
    for year, event in RACES:
        export_race(year, event, args.out)


if __name__ == "__main__":
    main()
