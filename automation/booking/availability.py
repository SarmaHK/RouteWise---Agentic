"""Transit Availability Service (Workstream C, Phase C1).

Provides real/simulated seat and ticket availability status for Sri Lankan
transit routes and legs, adhering to the CandidateAvailability schema:
- 'available': Ample seat inventory
- 'limited': Fewer than 5 seats remaining (high demand)
- 'unavailable': Sold out or suspended due to disruption
- 'unknown': Route/service not found or unverified
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional


class AvailabilityService:
    """Deterministic availability engine for transit routes and legs."""

    _instance: Optional["AvailabilityService"] = None

    def __init__(self, delay_feed_path: Optional[Path] = None) -> None:
        self.delay_feed_path = (
            delay_feed_path
            or Path(__file__).resolve().parents[2] / "data" / "mock-realtime" / "delay_feed.json"
        )

    @classmethod
    def get_instance(cls) -> "AvailabilityService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _is_route_disrupted(self, route_id: str) -> bool:
        """Check if GTFS-RT feed has high delay or suspension for this route."""
        if not self.delay_feed_path.exists():
            return False
        try:
            with open(self.delay_feed_path, "r", encoding="utf-8") as f:
                feed = json.load(f)
            rid = route_id.lower().strip()

            if rid == "r1":
                target_trips = ["trip_train_mainline_1005"]
            elif rid == "r2":
                target_trips = ["trip_bus_colombo_ella_99"]
            elif rid == "r3":
                target_trips = ["trip_train_kandy_ella_1126", "trip_bus_kandy_ella_47"]
            else:
                target_trips = [rid]

            for entity in feed.get("entity", []):
                t_up = entity.get("trip_update", {})
                trip_id = t_up.get("trip", {}).get("trip_id", "").lower()
                r_id = t_up.get("trip", {}).get("route_id", "").lower()
                delay_risk = t_up.get("delay_risk", "").lower()
                delay_min = float(t_up.get("delay_minutes", 0.0))

                for target in target_trips:
                    if target == trip_id or (target in trip_id and "_disrupted" not in trip_id) or (target in r_id):
                        if delay_risk == "high" or delay_min >= 45.0:
                            return True
            return False
        except Exception:
            return False

    def check_availability(
        self,
        route_id: str,
        travel_date: Optional[str] = None,
        seat_class: Optional[str] = None,
    ) -> dict[str, Any]:
        """Check availability status for a route.

        Returns:
            dict with availability: 'available' | 'limited' | 'unavailable' | 'unknown',
            available_seats: int,
            quotas: dict
        """
        rid = (route_id or "").strip().lower()

        # Disruption gate: severe disruption makes service unavailable
        if self._is_route_disrupted(rid):
            return {
                "route_id": route_id,
                "availability": "unavailable",
                "available_seats": 0,
                "status_reason": "Service suspended or heavily delayed due to active corridor disruption.",
                "quotas": {"first_class": 0, "second_class": 0, "third_class": 0},
            }

        # Canonical Golden Demo routes
        if rid == "r1":
            # Colombo Fort -> Ella Scenic Main Line Train (Podi Menike)
            # High-demand tourist corridor — observation/1st class is limited
            return {
                "route_id": route_id,
                "availability": "limited",
                "available_seats": 4,
                "status_reason": "High-demand scenic corridor; 1st class & observation seats limited (< 5 remaining).",
                "quotas": {"observation": 2, "second_class": 2, "third_class": 12},
            }
        elif rid == "r2":
            # Colombo -> Ella Route 99 Express Bus
            return {
                "route_id": route_id,
                "availability": "available",
                "available_seats": 18,
                "status_reason": "Regular unreserved express bus seating available at Pettah.",
                "quotas": {"ac_express": 6, "standard": 12},
            }
        elif rid == "r3":
            # Multi-modal Tuk + Train + AC Bus
            return {
                "route_id": route_id,
                "availability": "available",
                "available_seats": 15,
                "status_reason": "Multi-modal connecting segments have confirmed seat inventory.",
                "quotas": {"second_class_train": 15, "ac_feeder_bus": 8},
            }
        elif rid in ("c1", "k1"):
            # Intercity Express Colombo <-> Kandy
            return {
                "route_id": route_id,
                "availability": "available",
                "available_seats": 28,
                "status_reason": "Class 1 & 2 air-conditioned seats available.",
                "quotas": {"first_class": 10, "second_class": 18},
            }
        elif rid in ("c2", "k2"):
            # Highway / Express Bus Colombo <-> Kandy
            return {
                "route_id": route_id,
                "availability": "available",
                "available_seats": 20,
                "status_reason": "Semi-luxury bus departure available.",
                "quotas": {"semi_luxury": 20},
            }

        if not rid:
            return {
                "route_id": route_id,
                "availability": "unknown",
                "available_seats": 0,
                "status_reason": "Empty route identifier provided.",
                "quotas": {},
            }

        # Deterministic hash-based seat allocation for generalized corridors
        route_hash = sum(ord(c) for c in rid)
        if route_hash % 11 == 0:
            return {
                "route_id": route_id,
                "availability": "unavailable",
                "available_seats": 0,
                "status_reason": "Fully booked for selected departure window.",
                "quotas": {},
            }
        elif route_hash % 5 == 0:
            return {
                "route_id": route_id,
                "availability": "limited",
                "available_seats": 4,
                "status_reason": "Few seats remaining.",
                "quotas": {"standard": 4},
            }
        else:
            return {
                "route_id": route_id,
                "availability": "available",
                "available_seats": 25,
                "status_reason": "Regular scheduled inventory available.",
                "quotas": {"standard": 25},
            }


def get_availability_service() -> AvailabilityService:
    """Return singleton instance of AvailabilityService."""
    return AvailabilityService.get_instance()
