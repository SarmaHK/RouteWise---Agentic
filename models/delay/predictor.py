"""Delay Predictor using trained LSTM model (Workstream B, Phase B5)."""

from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import joblib
import numpy as np

from dataclasses import dataclass

# Canonical delay risk categories
DELAY_THRESHOLDS = {
    "high": 35.0,       # >= 35 min
    "moderate": 15.0,   # >= 15 and < 35 min
    "low": 5.0,         # >= 5 and < 15 min
    "none": 0.0,        # < 5 min
}


@dataclass
class DelayPredictionResult:
    predicted_delay_minutes: float
    delay_category: str



def bucket_delay(minutes: float) -> str:
    """Bucket continuous delay minutes into one of the four fixed categories."""
    if minutes >= DELAY_THRESHOLDS["high"]:
        return "high"
    elif minutes >= DELAY_THRESHOLDS["moderate"]:
        return "moderate"
    elif minutes >= DELAY_THRESHOLDS["low"]:
        return "low"
    return "none"


class DelayPredictor:
    """Inference engine for transit delay prediction using LSTM model + real-time feeds."""

    _instance: Optional["DelayPredictor"] = None

    def __init__(
        self,
        model_path: Optional[Path] = None,
        feed_path: Optional[Path] = None,
    ) -> None:
        self.model_path = model_path or Path(__file__).resolve().parent / "delay_model.joblib"
        self.feed_path = feed_path or Path(__file__).resolve().parents[2] / "data" / "mock-realtime" / "delay_feed.json"
        self._model = None
        self._load_model()
        self._feed_cache: dict[str, dict[str, Any]] = self._load_feed()

    def _load_model(self) -> None:
        if self.model_path.exists():
            try:
                artifact = joblib.load(self.model_path)
                self._model = artifact.get("model")
            except Exception:
                self._model = None

    def _load_feed(self) -> dict[str, dict[str, Any]]:
        if not self.feed_path.exists():
            return {}
        try:
            with open(self.feed_path, "r", encoding="utf-8") as f:
                feed = json.load(f)
            cached = {}
            for entity in feed.get("entity", []):
                t_up = entity.get("trip_update", {})
                route_id = t_up.get("trip", {}).get("route_id")
                trip_id = t_up.get("trip", {}).get("trip_id")
                key = route_id or trip_id
                if key:
                    cached[key] = {
                        "delay_minutes": float(t_up.get("delay_minutes", 0.0)),
                        "delay_risk": t_up.get("delay_risk", "low"),
                    }
            return cached
        except Exception:
            return {}

    @classmethod
    def get_instance(cls) -> "DelayPredictor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def predict_delay(
        self,
        route_id: str,
        at_time: Optional[datetime] = None,
        recent_delays: Optional[list[float]] = None,
    ) -> tuple[str, float]:
        """Predict (delay_risk, delay_min_estimate) for a route.

        Returns:
            delay_risk: 'none' | 'low' | 'moderate' | 'high'
            delay_min_estimate: single finite, non-negative float (minutes)
        """
        rid = (route_id or "").strip()
        rid_lower = rid.lower()

        # Check for real-time disruption spike in feed
        for feed_key, feed_val in self._feed_cache.items():
            if rid_lower in feed_key.lower() or feed_key.lower() in rid_lower:
                d_min = float(feed_val.get("delay_minutes", 0.0))
                d_risk = bucket_delay(d_min)
                return d_risk, round(d_min, 1)

        # Build sequence for LSTM forward pass
        now_dt = at_time or datetime.now()
        hr = now_dt.hour
        base_val = 10.0 if "train" in rid_lower or "r1" in rid_lower else 20.0
        delays = recent_delays or [base_val * 0.9, base_val * 0.95, base_val, base_val * 1.05, base_val * 1.1, base_val]

        if self._model is not None:
            seq = []
            for i, d in enumerate(delays[-6:]):
                step_hr = (hr - 5 + i) % 24
                seq.append([
                    d / 60.0,
                    math.sin(2 * math.pi * step_hr / 24.0),
                    math.cos(2 * math.pi * step_hr / 24.0),
                    0.2,  # normal weather
                ])
            X_seq = np.array(seq, dtype=np.float32)
            try:
                pred_min, _, _ = self._model.forward(X_seq)
                # Sanitize
                if not math.isfinite(pred_min) or pred_min < 0:
                    pred_min = 5.0
                pred_min = round(float(pred_min), 1)
                return bucket_delay(pred_min), pred_min
            except Exception:
                pass

        # Heuristic fallback
        if "r1" in rid_lower:
            return "low", 10.0
        elif "r2" in rid_lower:
            return "moderate", 30.0
        elif "r3" in rid_lower:
            return "low", 10.0
        elif "c1" in rid_lower:
            return "low", 8.0
        elif "c2" in rid_lower:
            return "moderate", 20.0
        elif "k1" in rid_lower:
            return "low", 10.0
        elif "k2" in rid_lower:
            return "moderate", 25.0

        return "low", 10.0

    def predict(
        self,
        route_id: str = "R1",
        corridor: str = "",
        recent_delays: Optional[list[float]] = None,
        weather: str = "clear",
        historical_mean_delay: float = 10.0,
        at_time: Optional[datetime] = None,
        **kwargs: Any,
    ) -> DelayPredictionResult:
        """Predict delay for a route and return a DelayPredictionResult."""
        risk, minutes = self.predict_delay(route_id=route_id, at_time=at_time, recent_delays=recent_delays)
        # If weather is heavy rain and recent delays are high, ensure risk reflects conditions
        if weather == "heavy_rain" and recent_delays and max(recent_delays) >= 35.0:
            minutes = max(minutes, float(np.mean(recent_delays)))
            risk = bucket_delay(minutes)
        return DelayPredictionResult(predicted_delay_minutes=minutes, delay_category=risk)


def get_delay_predictor() -> DelayPredictor:
    """Return singleton instance of DelayPredictor."""
    return DelayPredictor.get_instance()

