from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
from sklearn.metrics import mean_absolute_error


FEATURES = [
    "hour",
    "day_of_week",
    "month",
    "lag_1",
    "lag_24",
    "lag_168",
    "rolling_24",
    "rolling_168",
]


@dataclass(frozen=True)
class ForecastMetrics:
    train_end: str
    test_start: str
    mae_mw: float
    seasonal_naive_mae_mw: float


def build_features(frame: pd.DataFrame) -> pd.DataFrame:
    data = frame.copy()
    data["timestamp"] = pd.to_datetime(data["timestamp"])
    data = data.sort_values("timestamp").reset_index(drop=True)
    data["hour"] = data["timestamp"].dt.hour
    data["day_of_week"] = data["timestamp"].dt.dayofweek
    data["month"] = data["timestamp"].dt.month
    data["lag_1"] = data["demand_mw"].shift(1)
    data["lag_24"] = data["demand_mw"].shift(24)
    data["lag_168"] = data["demand_mw"].shift(168)
    data["rolling_24"] = data["demand_mw"].shift(1).rolling(24).mean()
    data["rolling_168"] = data["demand_mw"].shift(1).rolling(168).mean()
    return data.dropna().reset_index(drop=True)


def train_forward_validated_model(
    frame: pd.DataFrame,
    output_path: str | Path,
    test_days: int = 90,
) -> ForecastMetrics:
    data = build_features(frame)
    if len(data) < 24 * (test_days + 14):
        raise ValueError("Insufficient hourly history for requested forward holdout")

    split = len(data) - 24 * test_days
    train = data.iloc[:split]
    test = data.iloc[split:]

    model = HistGradientBoostingRegressor(
        learning_rate=0.05,
        max_iter=350,
        max_leaf_nodes=31,
        l2_regularization=1.0,
        random_state=42,
    )
    model.fit(train[FEATURES], train["demand_mw"])
    prediction = model.predict(test[FEATURES])

    metrics = ForecastMetrics(
        train_end=str(train["timestamp"].iloc[-1]),
        test_start=str(test["timestamp"].iloc[0]),
        mae_mw=float(mean_absolute_error(test["demand_mw"], prediction)),
        seasonal_naive_mae_mw=float(mean_absolute_error(test["demand_mw"], test["lag_168"])),
    )

    artifact = {
        "model": model,
        "features": FEATURES,
        "metrics": asdict(metrics),
        "trained_rows": len(train),
    }
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(artifact, output)
    return metrics
