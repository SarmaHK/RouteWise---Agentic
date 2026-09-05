"""Train XGBoost transit fare estimation model (Workstream B, Phase B4).

Trains an XGBoost regressor on Sri Lanka transit pricing features:
- distance_km: journey distance in kilometers
- mode_code: transport mode (0=walk, 1=tuk, 2=bus, 3=train, 4=taxi)
- hour_of_day: departure hour (0-23)
- transfers: number of interchanges
- is_peak: peak hour indicator (07:00-09:00, 17:00-19:00)
"""

from __future__ import annotations

import os
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
import xgboost as xgb
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

MODES_MAP = {
    "walk": 0,
    "tuk": 1,
    "bus": 2,
    "train": 3,
    "taxi": 4,
}


def generate_synthetic_fare_dataset(n_samples: int = 4000, seed: int = 42) -> pd.DataFrame:
    """Generate realistic Sri Lankan transit fare training data."""
    rng = np.random.default_rng(seed)

    modes = rng.choice(["walk", "tuk", "bus", "train", "taxi"], size=n_samples, p=[0.1, 0.25, 0.35, 0.25, 0.05])
    distances = []
    hours = rng.integers(0, 24, size=n_samples)
    transfers = []
    fares = []

    for mode, hr in zip(modes, hours):
        is_peak = 1 if (7 <= hr <= 9 or 17 <= hr <= 19) else 0

        if mode == "walk":
            dist = rng.uniform(0.1, 2.0)
            fare = 0.0
            xfer = 0
        elif mode == "tuk":
            dist = rng.uniform(0.5, 20.0)
            xfer = 0
            base = 150.0 + (30.0 if is_peak else 0.0)
            fare = base + dist * rng.uniform(90.0, 115.0)
        elif mode == "bus":
            dist = rng.uniform(5.0, 250.0)
            xfer = rng.choice([0, 1, 2], p=[0.7, 0.25, 0.05])
            base = rng.uniform(40.0, 80.0)
            per_km = rng.uniform(4.5, 6.5)
            fare = base + dist * per_km + (xfer * 50.0)
        elif mode == "train":
            dist = rng.uniform(15.0, 350.0)
            xfer = rng.choice([0, 1, 2], p=[0.8, 0.18, 0.02])
            base = rng.uniform(80.0, 150.0)
            per_km = rng.uniform(4.0, 6.0)
            fare = base + dist * per_km + (xfer * 80.0)
        else:  # taxi
            dist = rng.uniform(5.0, 150.0)
            xfer = 0
            base = 500.0 + (100.0 if is_peak else 0.0)
            fare = base + dist * rng.uniform(130.0, 160.0)

        # Add minor noise
        fare = max(0.0, fare + rng.normal(0, 15.0)) if mode != "walk" else 0.0
        distances.append(round(dist, 2))
        transfers.append(xfer)
        fares.append(round(fare, 0))

    df = pd.DataFrame({
        "distance_km": distances,
        "mode": modes,
        "mode_code": [MODES_MAP[m] for m in modes],
        "hour_of_day": hours,
        "is_peak": [1 if (7 <= h <= 9 or 17 <= h <= 19) else 0 for h in hours],
        "transfers": transfers,
        "fare_lkr": fares,
    })
    return df


def train_fare_model(output_dir: Path | None = None) -> Path:
    """Train the XGBoost model and save the artifact."""
    target_dir = output_dir or Path(__file__).resolve().parent
    target_dir.mkdir(parents=True, exist_ok=True)

    data_dir = Path(__file__).resolve().parents[2] / "data" / "static"
    data_dir.mkdir(parents=True, exist_ok=True)

    df = generate_synthetic_fare_dataset(n_samples=5000)
    df.to_csv(data_dir / "fare_training_data.csv", index=False)

    feature_cols = ["distance_km", "mode_code", "hour_of_day", "is_peak", "transfers"]
    X = df[feature_cols]
    y = df["fare_lkr"]

    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

    model = xgb.XGBRegressor(
        n_estimators=120,
        max_depth=5,
        learning_rate=0.08,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        objective="reg:squarederror",
    )
    model.fit(X_train, y_train)

    preds = model.predict(X_test)
    # Clip walk (mode_code=0) predictions strictly to 0
    walk_mask = X_test["mode_code"] == 0
    preds[walk_mask] = 0.0

    mae = mean_absolute_error(y_test, preds)
    rmse = np.sqrt(mean_squared_error(y_test, preds))
    r2 = r2_score(y_test, preds)

    print(f"XGBoost Fare Model Trained successfully!")
    print(f"Evaluation Metrics: MAE = {mae:.2f} LKR, RMSE = {rmse:.2f} LKR, R2 = {r2:.4f}")

    artifact = {
        "model": model,
        "feature_cols": feature_cols,
        "modes_map": MODES_MAP,
        "metrics": {"mae": float(mae), "rmse": float(rmse), "r2": float(r2)},
    }
    model_path = target_dir / "fare_model.joblib"
    joblib.dump(artifact, model_path)
    print(f"Model artifact saved to: {model_path}")
    return model_path


if __name__ == "__main__":
    train_fare_model()
