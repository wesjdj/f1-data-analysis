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


def export_race(year, event, out_dir):
    session = fastf1.get_session(year, event, "R")
    session.load(weather=False, messages=False)
    race_dir = os.path.join(out_dir, slug(year, event))
    os.makedirs(race_dir, exist_ok=True)

    laps = session.laps
    quick = laps.index.isin(laps.pick_quicklaps().index)
    pd.DataFrame({
        "Driver": laps["Driver"].astype("category"),
        "Team": laps["Team"].astype("category"),
        "LapNumber": laps["LapNumber"].astype("Int16"),
        "LapTime (s)": laps["LapTime"].dt.total_seconds().astype("float32"),
        "IsQuick": quick,
    }).to_parquet(os.path.join(race_dir, "laps.parquet"), compression="zstd", index=False)

    frames = []
    for _, lap in laps.iterlaps():
        if pd.isna(lap["LapNumber"]):
            continue
        try:
            telemetry = lap.get_telemetry()
        except Exception:
            continue
        frames.append(pd.DataFrame({
            "Driver": lap["Driver"],
            "LapNumber": int(lap["LapNumber"]),
            "Distance": telemetry["Distance"].astype("float32"),
            "Brake": telemetry["Brake"].astype(bool),
        }))
    telemetry = pd.concat(frames, ignore_index=True)
    telemetry["Driver"] = telemetry["Driver"].astype("category")
    telemetry["LapNumber"] = telemetry["LapNumber"].astype("int16")
    telemetry.to_parquet(os.path.join(race_dir, "telemetry.parquet"), compression="zstd", index=False)

    corners = session.get_circuit_info().corners[["Number", "Letter", "Distance"]]
    corners.to_parquet(os.path.join(race_dir, "corners.parquet"), compression="zstd", index=False)

    pd.DataFrame({"Year": [year], "Event": [event]}).to_parquet(os.path.join(race_dir, "race.parquet"), index=False)
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
