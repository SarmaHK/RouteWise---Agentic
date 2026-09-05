"""Fare Predictor using trained XGBoost model (Workstream B, Phase B4)."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np

MODES_MAP = {
    "walk": 0,
    "tuk": 1,
    "bus": 2,
    "train": 3,
    "taxi": 4,
}


class FarePredictor:
    """Predicts transit fares in LKR using trained XGBoost regressor."""

    _instance: Optional["FarePredictor"] = None

    def __init__(self, model_path: Optional[Path] = None) -> None:
        self.model_path = model_path or Path(__file__).resolve().parent / "fare_model.joblib"
        self._model = None
        self._load_model()

    def _load_model(self) -> None:
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
                self._model = artifact.get("model")
            except Exception:
                self._model = None

    @classmethod
    def get_instance(cls) -> "FarePredictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def predict_fare(
        self,
        mode: str,
        distance_km: float,
        transit_class: str = "second",
        hour: int = 8,
    ) -> float:
        """Convenience method to predict fare for a given mode and distance."""
        return self.predict_leg_fare(distance_km=distance_km, mode=mode, hour=hour)

    def predict_leg_fare(
        self,
        distance_km: float,
        mode: str,
        hour: int = 8,
        transfers: int = 0,
    ) -> float:
        """Predict fare in LKR for a single transit leg."""
        mode_clean = (mode or "").lower().strip()
        if mode_clean == "walk" or distance_km <= 0.05:
            return 0.0

        mode_code = MODES_MAP.get(mode_clean, 2)  # default to bus
        is_peak = 1 if (7 <= hour <= 9 or 17 <= hour <= 19) else 0

        if self._model is not None:
            X = np.array([[float(distance_km), mode_code, hour, is_peak, transfers]])
            try:
                pred = float(self._model.predict(X)[0])
                return max(0.0, round(pred, 0))
            except Exception:
                pass

        # Robust heuristic fallback (Sri Lankan tariff rates)
        if mode_clean == "tuk":
            return round(150.0 + distance_km * 105.0, 0)
        elif mode_clean == "train":
            return round(max(100.0, 120.0 + distance_km * 5.2), 0)
        elif mode_clean == "bus":
            return round(max(50.0, 60.0 + distance_km * 5.8), 0)
        elif mode_clean == "taxi":
            return round(500.0 + distance_km * 145.0, 0)
        return round(distance_km * 5.0, 0)

    def predict_route_fare(
        self,
        route_id: str,
        legs: Optional[list[dict[str, Any]]] = None,
    ) -> float:
        """Predict total fare for a route or set of legs."""
        if legs:
            total = 0.0
            for leg in legs:
                dist = float(leg.get("walking_km" if leg.get("mode") == "walk" else "distance_km", 0.0) or 0.0)
                dur = float(leg.get("duration_min", 0.0) or 0.0)
                if dist == 0.0 and dur > 0:
                    # Estimate distance from duration
                    dist = dur * 0.6
                mode = leg.get("mode", "bus")
                total += self.predict_leg_fare(dist, mode)
            return max(0.0, round(total, 0))

        rid = (route_id or "").upper()
        # Corridor-specific known routes
        if rid == "R1":
            return 1600.0
        elif rid == "R2":
            return 1200.0
        elif rid == "R3":
            return 2350.0
        elif rid == "C1":
            return 1500.0
        elif rid == "C2":
            return 900.0
        elif rid == "K1":
            return 1200.0
        elif rid == "K2":
            return 800.0

        # General default
        return 1200.0


def get_fare_predictor() -> FarePredictor:
    """Return singleton instance of FarePredictor."""
    return FarePredictor.get_instance()

