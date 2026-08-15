from __future__ import annotations

import argparse
import csv
from pathlib import Path

import pandas as pd

from ml.demand_forecast import train_forward_validated_model


def load_history(folder: Path) -> pd.DataFrame:
    rows = []
    for path in sorted(folder.glob("PUB_Demand_*.csv")):
        lines = [
            line
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip() and not line.startswith("\\")
        ]
        reader = csv.DictReader(lines)
        for raw in reader:
            try:
                hour = int(raw["Hour"])
                timestamp = pd.Timestamp(raw["Date"]) + pd.Timedelta(hours=hour - 1)
                demand = float(raw["Ontario Demand"])
            except (KeyError, ValueError, TypeError):
                continue
            rows.append({"timestamp": timestamp, "demand_mw": demand})
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Train forward-validated Ontario demand model")
    parser.add_argument("--input-dir", default="data/raw/demand")
    parser.add_argument("--output", default="models/demand_forecast.joblib")
    parser.add_argument("--test-days", type=int, default=90)
    args = parser.parse_args()

    frame = load_history(Path(args.input_dir))
    metrics = train_forward_validated_model(frame, args.output, args.test_days)
    print(metrics)


if __name__ == "__main__":
    main()
