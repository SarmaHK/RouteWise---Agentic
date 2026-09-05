"""Spatial Transit Graph Engine (Workstream B).

Provides:
- Geodesic / spatial distance calculation (Haversine formula).
- First/last-mile connection heuristics (walk/tuk transfers).
- Multi-modal path candidate generation connecting scheduled lines.
- GTFS-RT feed integration for delay and congestion alerts.
- PostGIS-compatible data structures.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, time, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

from app.schemas.candidate import CandidateAvailability, RouteCandidate
from app.schemas.route import DataSource, Leg
from app.services.transit.seeds import (
    STATIONS,
    StationSeed,
    TRIPS,
    resolve_station,
)

# Sri Lanka Standard Time timezone (+05:30)
SLST = timezone(timedelta(hours=5, minutes=30))

# Average travel speeds in Sri Lanka
WALK_SPEED_KMH = 4.5
TUK_SPEED_KMH = 28.0

# Base tariff rates (LKR)
TUK_BASE_FARE_LKR = 150.0
TUK_PER_KM_LKR = 100.0


def haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance between two points on Earth in kilometers."""
    r = 6371.0  # Earth radius in km
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return round(r * c, 2)


class SpatialTransitGraph:
    """Multi-modal transit routing engine for Sri Lanka."""

    def __init__(self, delay_feed_path: Optional[Path] = None) -> None:
        self._delay_feed_path = (
            delay_feed_path
            or Path(__file__).resolve().parents[4] / "data" / "mock-realtime" / "delay_feed.json"
        )
        self._delays: dict[str, dict[str, Any]] = self._load_delay_feed()

    def _load_delay_feed(self) -> dict[str, dict[str, Any]]:
        """Load real-time delay feed if available."""
        if not self._delay_feed_path.exists():
            return {}
        try:
            with open(self._delay_feed_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            delays = {}
            for entity in data.get("entity", []):
                trip_up = entity.get("trip_update", {})
                trip_id = trip_up.get("trip", {}).get("trip_id")
                if trip_id:
                    delays[trip_id] = {
                        "delay_minutes": float(trip_up.get("delay_minutes", 0.0)),
                        "delay_risk": trip_up.get("delay_risk", "low"),
                        "alert": entity.get("alert"),
                    }
            return delays
        except Exception:
            return {}

    def get_trip_delay(self, trip_id: str) -> tuple[str, float]:
        """Return (delay_risk, delay_min_estimate) for a trip."""
        info = self._delays.get(trip_id)
        if info:
            return info.get("delay_risk", "low"), info.get("delay_minutes", 0.0)
        return "low", 5.0

    def find_candidates(
        self,
        origin_name: str,
        destination_name: str,
        departure_time: Optional[datetime] = None,
        preferences: Optional[dict[str, Any]] = None,
    ) -> list[RouteCandidate]:
        """Generate multi-modal route candidates between origin and destination."""
        origin_st = resolve_station(origin_name)
        dest_st = resolve_station(destination_name)

        if not origin_st or not dest_st or origin_st.id == dest_st.id:
            return []

        candidates: list[RouteCandidate] = []

        # ------------------------------------------------------------------ #
        # Case 1: Colombo Fort <-> Ella (Golden Demo Corridor)
        # ------------------------------------------------------------------ #
        if (origin_st.id in ("colombo_fort", "colombo_fort_bus") and dest_st.id in ("ella", "ella_bus_junction")) or \
           (dest_st.id in ("colombo_fort", "colombo_fort_bus") and origin_st.id in ("ella", "ella_bus_junction")):

            # Candidate R1: Scenic Train (Podi Menike) with short walk/tuk
            d_risk, d_min = self.get_trip_delay("trip_train_mainline_1005")
            candidates.append(
                RouteCandidate(
                    id="R1",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Walk + short tuk to the station, then the scenic hill-country train Colombo -> Ella.",
                    modes=["walk", "tuk", "train"],
                    total_duration_min=420.0,
                    total_fare_lkr=1600.0,
                    transfers=1,
                    walking_km=0.3,
                    delay_risk=d_risk,
                    delay_min_estimate=d_min,
                    availability=CandidateAvailability.unknown,
                    notes="Scenic hill-country line (Podi Menike) via Nanu Oya & Hatton.",
                    data_source=DataSource.simulated,
                )
            )

            # Candidate R2: Direct Express Bus
            b_risk, b_min = self.get_trip_delay("trip_bus_colombo_ella_99")
            candidates.append(
                RouteCandidate(
                    id="R2",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Direct bus Colombo -> Ella with a short walk at each end.",
                    modes=["walk", "bus"],
                    total_duration_min=360.0,
                    total_fare_lkr=1200.0,
                    transfers=0,
                    walking_km=1.5,
                    delay_risk=b_risk,
                    delay_min_estimate=b_min,
                    availability=CandidateAvailability.unknown,
                    notes="Direct Route 99 service via Ratnapura and Beragala.",
                    data_source=DataSource.simulated,
                )
            )

            # Candidate R3: Multi-modal Tuk + Train + Connecting Bus (Faster, premium)
            candidates.append(
                RouteCandidate(
                    id="R3",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Tuk + train + connecting bus — fastest, but 2 transfers and over budget.",
                    modes=["tuk", "train", "bus"],
                    total_duration_min=330.0,
                    total_fare_lkr=2350.0,
                    transfers=2,
                    walking_km=0.4,
                    delay_risk="low",
                    delay_min_estimate=10.0,
                    availability=CandidateAvailability.unknown,
                    notes="Intercity Express to Peradeniya, AC feeder bus through Nuwara Eliya to Ella.",
                    data_source=DataSource.simulated,
                )
            )
            return candidates

        # ------------------------------------------------------------------ #
        # Case 2: Colombo Fort <-> Kandy
        # ------------------------------------------------------------------ #
        if (origin_st.id in ("colombo_fort", "colombo_fort_bus") and dest_st.id in ("kandy", "kandy_goods_shed")) or \
           (dest_st.id in ("colombo_fort", "colombo_fort_bus") and origin_st.id in ("kandy", "kandy_goods_shed")):

            d_risk, d_min = self.get_trip_delay("trip_train_colombo_kandy_1029")
            candidates.append(
                RouteCandidate(
                    id="C1",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Intercity train Colombo Fort -> Kandy (low walking, comfortable).",
                    modes=["walk", "train"],
                    total_duration_min=150.0,
                    total_fare_lkr=1500.0,
                    transfers=0,
                    walking_km=0.3,
                    delay_risk=d_risk,
                    delay_min_estimate=d_min,
                    availability=CandidateAvailability.unknown,
                    notes="Class 1 & 2 reserved Intercity Express.",
                    data_source=DataSource.simulated,
                )
            )

            b_risk, b_min = self.get_trip_delay("trip_bus_colombo_kandy_1")
            candidates.append(
                RouteCandidate(
                    id="C2",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Express bus Colombo -> Kandy (cheaper, a bit more walking).",
                    modes=["walk", "bus"],
                    total_duration_min=180.0,
                    total_fare_lkr=900.0,
                    transfers=0,
                    walking_km=1.0,
                    delay_risk=b_risk,
                    delay_min_estimate=b_min,
                    availability=CandidateAvailability.unknown,
                    notes="Frequent Route 01 AC Express bus service.",
                    data_source=DataSource.simulated,
                )
            )
            return candidates

        # ------------------------------------------------------------------ #
        # Case 3: Kandy <-> Ella
        # ------------------------------------------------------------------ #
        if (origin_st.id in ("kandy", "kandy_goods_shed") and dest_st.id in ("ella", "ella_bus_junction")) or \
           (dest_st.id in ("kandy", "kandy_goods_shed") and origin_st.id in ("ella", "ella_bus_junction")):

            d_risk, d_min = self.get_trip_delay("trip_train_kandy_ella_1126")
            candidates.append(
                RouteCandidate(
                    id="K1",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Scenic hill-country train Kandy -> Ella (minimal walking).",
                    modes=["walk", "train"],
                    total_duration_min=380.0,
                    total_fare_lkr=1200.0,
                    transfers=0,
                    walking_km=0.4,
                    delay_risk=d_risk,
                    delay_min_estimate=d_min,
                    availability=CandidateAvailability.unknown,
                    notes="World-famous scenic mountain rail route passing tea plantations.",
                    data_source=DataSource.simulated,
                )
            )

            b_risk, b_min = self.get_trip_delay("trip_bus_kandy_ella_47")
            candidates.append(
                RouteCandidate(
                    id="K2",
                    origin=origin_name,
                    destination=destination_name,
                    summary="Direct bus Kandy -> Ella (cheaper, more walking at the stops).",
                    modes=["walk", "bus"],
                    total_duration_min=330.0,
                    total_fare_lkr=800.0,
                    transfers=0,
                    walking_km=1.2,
                    delay_risk=b_risk,
                    delay_min_estimate=b_min,
                    availability=CandidateAvailability.unknown,
                    notes="Route 47 mountain bus service.",
                    data_source=DataSource.simulated,
                )
            )
            return candidates

        # ------------------------------------------------------------------ #
        # Case 4: General Multi-modal Graph Routing across Sri Lanka
        # ------------------------------------------------------------------ #
        dist_km = haversine_distance_km(
            origin_st.latitude, origin_st.longitude, dest_st.latitude, dest_st.longitude
        )

        # 1. Scheduled / Intercity option
        rail_dur = round((dist_km / 45.0) * 60.0 + 30.0, 1)
        rail_fare = round(max(300.0, dist_km * 5.5), 0)
        candidates.append(
            RouteCandidate(
                id=f"GEN_T_{origin_st.id[:3]}_{dest_st.id[:3]}".upper(),
                origin=origin_name,
                destination=destination_name,
                summary=f"Train connection {origin_st.name} -> {dest_st.name} with short station transfers.",
                modes=["walk", "train", "tuk"],
                total_duration_min=rail_dur,
                total_fare_lkr=rail_fare,
                transfers=1 if dist_km > 150 else 0,
                walking_km=0.5,
                delay_risk="low" if dist_km < 100 else "moderate",
                delay_min_estimate=12.0,
                availability=CandidateAvailability.unknown,
                notes="Rail line connection via Sri Lanka Railways network.",
                data_source=DataSource.simulated,
            )
        )

        # 2. Highway / Express Bus option
        bus_dur = round((dist_km / 50.0) * 60.0 + 20.0, 1)
        bus_fare = round(max(250.0, dist_km * 4.8), 0)
        candidates.append(
            RouteCandidate(
                id=f"GEN_B_{origin_st.id[:3]}_{dest_st.id[:3]}".upper(),
                origin=origin_name,
                destination=destination_name,
                summary=f"Express bus service {origin_st.name} -> {dest_st.name}.",
                modes=["walk", "bus"],
                total_duration_min=bus_dur,
                total_fare_lkr=bus_fare,
                transfers=1 if dist_km > 200 else 0,
                walking_km=1.1,
                delay_risk="moderate",
                delay_min_estimate=20.0,
                availability=CandidateAvailability.unknown,
                notes="Interprovincial express bus service.",
                data_source=DataSource.simulated,
            )
        )

        return candidates

    def get_route_legs(
        self,
        route_id: str,
        origin_name: str = "Colombo Fort",
        destination_name: str = "Ella",
        departure_time: Optional[datetime] = None,
    ) -> list[Leg]:
        """Expand a candidate route_id into ordered, detailed Leg objects."""
        now_dt = departure_time or datetime.now(SLST).replace(hour=6, minute=0, second=0, microsecond=0)
        legs: list[Leg] = []

        rid = (route_id or "").upper()

        if rid == "R1":
            # Colombo Fort -> Ella via Train (Scenic Hill Country)
            # Leg 1: Walk to tuk stand
            t0 = now_dt
            t1 = t0 + timedelta(minutes=5)
            legs.append(
                Leg(
                    id="L1_walk",
                    mode="walk",
                    origin="Hotel / Starting point",
                    destination="Pettah Tuk Stand",
                    departure_time=t0,
                    arrival_time=t1,
                    duration_min=5.0,
                    fare_lkr=0.0,
                    walking_km=0.2,
                    delay_risk="none",
                    delay_min_estimate=0.0,
                    notes="Short walk to main road.",
                    data_source=DataSource.simulated,
                )
            )

            # Leg 2: Short tuk to Colombo Fort Station
            t2 = t1 + timedelta(minutes=10)
            legs.append(
                Leg(
                    id="L2_tuk",
                    mode="tuk",
                    origin="Pettah Tuk Stand",
                    destination="Colombo Fort Railway Station",
                    departure_time=t1,
                    arrival_time=t2,
                    duration_min=10.0,
                    fare_lkr=200.0,
                    walking_km=0.0,
                    delay_risk="none",
                    delay_min_estimate=2.0,
                    notes="Metered three-wheeler transfer to station entrance.",
                    data_source=DataSource.simulated,
                )
            )

            # Leg 3: Scenic train Podi Menike
            t3 = t2 + timedelta(minutes=15)  # 15 min buffer
            t4 = t3 + timedelta(minutes=390)
            legs.append(
                Leg(
                    id="L3_train",
                    mode="train",
                    origin="Colombo Fort Railway Station",
                    destination="Ella Railway Station",
                    departure_time=t3,
                    arrival_time=t4,
                    duration_min=390.0,
                    fare_lkr=1400.0,
                    walking_km=0.1,
                    delay_risk="low",
                    delay_min_estimate=10.0,
                    notes="Podi Menike Express (Train #1005). Scenic mountain line via Nanu Oya.",
                    data_source=DataSource.simulated,
                )
            )
            return legs

        elif rid == "R2":
            # Direct bus
            t0 = now_dt
            t1 = t0 + timedelta(minutes=15)
            legs.append(
                Leg(
                    id="L1_walk",
                    mode="walk",
                    origin="Starting point",
                    destination="Bastian Mawatha Bus Terminal",
                    departure_time=t0,
                    arrival_time=t1,
                    duration_min=15.0,
                    fare_lkr=0.0,
                    walking_km=0.9,
                    delay_risk="none",
                    delay_min_estimate=0.0,
                    notes="Walk to central bus terminal.",
                    data_source=DataSource.simulated,
                )
            )

            t2 = t1 + timedelta(minutes=10)
            t3 = t2 + timedelta(minutes=325)
            legs.append(
                Leg(
                    id="L2_bus",
                    mode="bus",
                    origin="Bastian Mawatha Bus Terminal",
                    destination="Ella Bus Junction",
                    departure_time=t2,
                    arrival_time=t3,
                    duration_min=325.0,
                    fare_lkr=1200.0,
                    walking_km=0.0,
                    delay_risk="moderate",
                    delay_min_estimate=30.0,
                    notes="Route 99 Direct Bus Colombo-Badulla via Beragala.",
                    data_source=DataSource.simulated,
                )
            )

            t4 = t3 + timedelta(minutes=10)
            legs.append(
                Leg(
                    id="L3_walk_dest",
                    mode="walk",
                    origin="Ella Bus Junction",
                    destination="Ella Town Centre",
                    departure_time=t3,
                    arrival_time=t4,
                    duration_min=10.0,
                    fare_lkr=0.0,
                    walking_km=0.6,
                    delay_risk="none",
                    delay_min_estimate=0.0,
                    notes="Walk from junction to destination.",
                    data_source=DataSource.simulated,
                )
            )
            return legs

        elif rid == "R3":
            # Tuk + Train + Bus
            t0 = now_dt
            t1 = t0 + timedelta(minutes=15)
            legs.append(
                Leg(
                    id="L1_tuk",
                    mode="tuk",
                    origin="Starting point",
                    destination="Colombo Fort Station",
                    departure_time=t0,
                    arrival_time=t1,
                    duration_min=15.0,
                    fare_lkr=350.0,
                    walking_km=0.1,
                    delay_risk="none",
                    delay_min_estimate=0.0,
                    notes="Direct tuk transfer.",
                    data_source=DataSource.simulated,
                )
            )
            t2 = t1 + timedelta(minutes=15)
            t3 = t2 + timedelta(minutes=140)
            legs.append(
                Leg(
                    id="L2_train",
                    mode="train",
                    origin="Colombo Fort Station",
                    destination="Peradeniya Junction",
                    departure_time=t2,
                    arrival_time=t3,
                    duration_min=140.0,
                    fare_lkr=1100.0,
                    walking_km=0.1,
                    delay_risk="low",
                    delay_min_estimate=5.0,
                    notes="Intercity Express to Central Province.",
                    data_source=DataSource.simulated,
                )
            )
            t4 = t3 + timedelta(minutes=20)
            t5 = t4 + timedelta(minutes=140)
            legs.append(
                Leg(
                    id="L3_bus",
                    mode="bus",
                    origin="Peradeniya Bus Stop",
                    destination="Ella Junction",
                    departure_time=t4,
                    arrival_time=t5,
                    duration_min=140.0,
                    fare_lkr=900.0,
                    walking_km=0.2,
                    delay_risk="low",
                    delay_min_estimate=5.0,
                    notes="Connecting AC mountain express.",
                    data_source=DataSource.simulated,
                )
            )
            return legs

        # Fallback for general corridors
        t0 = now_dt
        t1 = t0 + timedelta(minutes=10)
        t2 = t1 + timedelta(minutes=180)
        return [
            Leg(
                id="L1_transfer",
                mode="walk",
                origin=origin_name,
                destination=f"{origin_name} Station",
                departure_time=t0,
                arrival_time=t1,
                duration_min=10.0,
                fare_lkr=0.0,
                walking_km=0.4,
                delay_risk="none",
                delay_min_estimate=0.0,
                notes="Initial connection to transit stop.",
                data_source=DataSource.simulated,
            ),
            Leg(
                id="L2_main",
                mode="train" if "T" in rid else "bus",
                origin=f"{origin_name} Station",
                destination=f"{destination_name} Station",
                departure_time=t1,
                arrival_time=t2,
                duration_min=180.0,
                fare_lkr=1200.0,
                walking_km=0.1,
                delay_risk="low",
                delay_min_estimate=10.0,
                notes=f"Scheduled transit service to {destination_name}.",
                data_source=DataSource.simulated,
            ),
        ]


_transit_graph_instance: Optional[SpatialTransitGraph] = None


def get_transit_graph() -> SpatialTransitGraph:
    """Return singleton instance of SpatialTransitGraph."""
    global _transit_graph_instance
    if _transit_graph_instance is None:
        _transit_graph_instance = SpatialTransitGraph()
    return _transit_graph_instance

