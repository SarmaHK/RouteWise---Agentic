"""Disruption Monitoring Engine (Workstream C, Phase C4 — Coder Wake).

Monitors GTFS-RT feed alerts and corridor delays, detects disruptions, provides
deterministic disruption injection and restoration for demo and testing scenarios,
and emits signals triggering the Agent's REPLANNING state.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class DisruptionMonitor:
    """Coder Wake disruption watcher and simulator."""

    _instance: Optional["DisruptionMonitor"] = None

    def __init__(self, feed_path: Optional[Path] = None) -> None:
        self.feed_path = (
            feed_path
            or Path(__file__).resolve().parents[2] / "data" / "mock-realtime" / "delay_feed.json"
        )
        self.backup_path = self.feed_path.with_suffix(".json.orig_backup")
        self._ensure_backup()

    @classmethod
    def get_instance(cls) -> "DisruptionMonitor":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _ensure_backup(self) -> None:
        """Cache pristine original feed on first initialization."""
        if self.feed_path.exists() and not self.backup_path.exists():
            try:
                with open(self.feed_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(self.backup_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                pass

    def get_active_disruptions(self) -> list[dict[str, Any]]:
        """Return list of entities currently experiencing high delays or disruptions."""
        if not self.feed_path.exists():
            return []
        try:
            with open(self.feed_path, "r", encoding="utf-8") as f:
                feed = json.load(f)

            disrupted = []
            for entity in feed.get("entity", []):
                t_up = entity.get("trip_update", {})
                trip_id = t_up.get("trip", {}).get("trip_id", "")
                r_id = t_up.get("trip", {}).get("route_id", "")
                delay_min = float(t_up.get("delay_minutes", 0.0))
                risk = t_up.get("delay_risk", "low")
                alert = entity.get("alert", {})

                if risk == "high" or delay_min >= 45.0:
                    disrupted.append(
                        {
                            "entity_id": entity.get("id"),
                            "trip_id": trip_id,
                            "route_id": r_id,
                            "delay_minutes": delay_min,
                            "delay_risk": risk,
                            "alert_header": alert.get("header_text", "Severe corridor disruption"),
                            "cause": alert.get("cause", "UNKNOWN"),
                        }
                    )
            return disrupted
        except Exception:
            return []

    def inject_disruption(
        self,
        trip_id: str = "trip_train_mainline_1005",
        delay_minutes: float = 55.0,
        delay_risk: str = "high",
        alert_header: str = "Landslide clearance operation between Hatton and Kotagala. Speed restriction 10 km/h.",
    ) -> dict[str, Any]:
        """Inject an active disruption into the real-time delay feed (simulates sudden landslide/delay)."""
        self._ensure_backup()
        if not self.feed_path.exists():
            return {"injected": False, "error": "Feed file does not exist"}

        with open(self.feed_path, "r", encoding="utf-8") as f:
            feed = json.load(f)

        matched = False
        target_norm = trip_id.lower().strip()
        for entity in feed.get("entity", []):
            t_up = entity.get("trip_update", {})
            t_id = t_up.get("trip", {}).get("trip_id", "").lower()
            if target_norm in t_id or t_id in target_norm or (target_norm == "r1" and "1005" in t_id):
                t_up["delay_minutes"] = float(delay_minutes)
                t_up["delay_risk"] = delay_risk
                entity["alert"] = {
                    "cause": "WEATHER",
                    "effect": "SIGNIFICANT_DELAYS",
                    "header_text": alert_header,
                }
                matched = True

        if not matched:
            # Add entity
            feed.setdefault("entity", []).append(
                {
                    "id": f"rt_injected_{trip_id}",
                    "trip_update": {
                        "trip": {
                            "trip_id": trip_id,
                            "route_id": "route_train_mainline_colombo_badulla",
                            "start_time": "05:55:00",
                            "start_date": "20260905",
                        },
                        "delay_minutes": float(delay_minutes),
                        "delay_risk": delay_risk,
                    },
                    "alert": {
                        "cause": "WEATHER",
                        "effect": "SIGNIFICANT_DELAYS",
                        "header_text": alert_header,
                    },
                }
            )

        with open(self.feed_path, "w", encoding="utf-8") as f:
            json.dump(feed, f, indent=2)

        # Invalidate delay predictor in-memory cache if active
        try:
            from models.delay.predictor import get_delay_predictor

            pred = get_delay_predictor()
            pred._feed_cache = pred._load_feed()
        except Exception:
            pass

        return {
            "injected": True,
            "trip_id": trip_id,
            "delay_minutes": delay_minutes,
            "delay_risk": delay_risk,
            "alert_header": alert_header,
        }

    def restore_disruption(self) -> dict[str, Any]:
        """Restore pristine delay feed state."""
        if self.backup_path.exists():
            try:
                with open(self.backup_path, "r", encoding="utf-8") as f:
                    content = f.read()
                with open(self.feed_path, "w", encoding="utf-8") as f:
                    f.write(content)
            except Exception:
                self._fallback_restore()
        else:
            self._fallback_restore()

        # Invalidate delay predictor cache
        try:
            from models.delay.predictor import get_delay_predictor

            pred = get_delay_predictor()
            pred._feed_cache = pred._load_feed()
        except Exception:
            pass

        return {"restored": True}

    def _fallback_restore(self) -> None:
        """Ensure trip 1005 is low delay if backup was unavailable."""
        if not self.feed_path.exists():
            return
        try:
            with open(self.feed_path, "r", encoding="utf-8") as f:
                feed = json.load(f)
            for entity in feed.get("entity", []):
                t_up = entity.get("trip_update", {})
                t_id = t_up.get("trip", {}).get("trip_id", "")
                if "1005" in t_id and "_disrupted" not in t_id:
                    t_up["delay_minutes"] = 10.0
                    t_up["delay_risk"] = "low"
                    entity.pop("alert", None)
            with open(self.feed_path, "w", encoding="utf-8") as f:
                json.dump(feed, f, indent=2)
        except Exception:
            pass


def get_disruption_monitor() -> DisruptionMonitor:
    """Return singleton instance of DisruptionMonitor."""
    return DisruptionMonitor.get_instance()
