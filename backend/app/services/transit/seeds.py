"""Seed dataset for Sri Lanka transit network (Workstream B).

Contains verified transit stations, schedules, routes, and fare rules for Sri Lanka:
- Main Line (Colombo Fort -> Peradeniya -> Hatton -> Nanu Oya -> Ella -> Badulla)
- Coastal Line (Colombo Fort -> Galle -> Matara)
- Northern Line (Colombo Fort -> Anuradhapura -> Jaffna)
- Express & Intercity Bus network (SLTB & private operators)
- Multi-modal transfers (tuk-tuk first/last-mile, walking)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class StationSeed:
    id: str
    name: str
    latitude: float
    longitude: float
    city: str
    district: str
    modes_served: list[str] = field(default_factory=lambda: ["walk", "tuk"])
    is_hub: bool = False


@dataclass
class RouteSeed:
    id: str
    name: str
    mode: str  # 'train' | 'bus' | 'tuk' | 'walk' | 'taxi'
    origin_id: str
    destination_id: str
    agency: str
    distance_km: float
    is_scenic: bool = False


@dataclass
class TripSeed:
    id: str
    route_id: str
    trip_headsign: str
    departure_time_str: str  # "HH:MM"
    arrival_time_str: str    # "HH:MM"
    duration_min: float
    base_fare_lkr: float
    stops: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Station fixtures (real Sri Lanka coordinates)
# --------------------------------------------------------------------------- #
STATIONS: dict[str, StationSeed] = {
    "colombo_fort": StationSeed(
        id="colombo_fort",
        name="Colombo Fort",
        latitude=6.9344,
        longitude=79.8504,
        city="Colombo",
        district="Colombo",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "colombo_fort_bus": StationSeed(
        id="colombo_fort_bus",
        name="Colombo Fort Central Bus Stand (Bastian Mawatha)",
        latitude=6.9332,
        longitude=79.8530,
        city="Colombo",
        district="Colombo",
        modes_served=["bus", "tuk", "walk"],
        is_hub=True,
    ),
    "peradeniya": StationSeed(
        id="peradeniya",
        name="Peradeniya Junction",
        latitude=7.2625,
        longitude=80.5947,
        city="Peradeniya",
        district="Kandy",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "kandy": StationSeed(
        id="kandy",
        name="Kandy",
        latitude=7.2906,
        longitude=80.6337,
        city="Kandy",
        district="Kandy",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "kandy_goods_shed": StationSeed(
        id="kandy_goods_shed",
        name="Kandy Goods Shed Bus Station",
        latitude=7.2895,
        longitude=80.6321,
        city="Kandy",
        district="Kandy",
        modes_served=["bus", "tuk", "walk"],
        is_hub=True,
    ),
    "hatton": StationSeed(
        id="hatton",
        name="Hatton",
        latitude=6.8964,
        longitude=80.5958,
        city="Hatton",
        district="Nuwara Eliya",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=False,
    ),
    "nanu_oya": StationSeed(
        id="nanu_oya",
        name="Nanu Oya",
        latitude=6.9461,
        longitude=80.7486,
        city="Nanu Oya",
        district="Nuwara Eliya",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "nuwara_eliya": StationSeed(
        id="nuwara_eliya",
        name="Nuwara Eliya Town",
        latitude=6.9697,
        longitude=80.7780,
        city="Nuwara Eliya",
        district="Nuwara Eliya",
        modes_served=["bus", "tuk", "walk"],
        is_hub=False,
    ),
    "ella": StationSeed(
        id="ella",
        name="Ella",
        latitude=6.8667,
        longitude=81.0466,
        city="Ella",
        district="Badulla",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "ella_bus_junction": StationSeed(
        id="ella_bus_junction",
        name="Ella Bus Junction",
        latitude=6.8690,
        longitude=81.0450,
        city="Ella",
        district="Badulla",
        modes_served=["bus", "tuk", "walk"],
        is_hub=False,
    ),
    "badulla": StationSeed(
        id="badulla",
        name="Badulla",
        latitude=6.9895,
        longitude=81.0557,
        city="Badulla",
        district="Badulla",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "galle": StationSeed(
        id="galle",
        name="Galle",
        latitude=6.0367,
        longitude=80.2170,
        city="Galle",
        district="Galle",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "matara": StationSeed(
        id="matara",
        name="Matara",
        latitude=5.9496,
        longitude=80.5353,
        city="Matara",
        district="Matara",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "negombo": StationSeed(
        id="negombo",
        name="Negombo",
        latitude=7.2083,
        longitude=79.8358,
        city="Negombo",
        district="Gampaha",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
    "jaffna": StationSeed(
        id="jaffna",
        name="Jaffna",
        latitude=9.6615,
        longitude=80.0255,
        city="Jaffna",
        district="Jaffna",
        modes_served=["train", "bus", "tuk", "walk"],
        is_hub=True,
    ),
}

# Aliases to match natural language variations
STATION_ALIASES: dict[str, str] = {
    "colombo": "colombo_fort",
    "colombo fort": "colombo_fort",
    "fort": "colombo_fort",
    "kandy": "kandy",
    "kandy town": "kandy",
    "ella": "ella",
    "badulla": "badulla",
    "galle": "galle",
    "matara": "matara",
    "nanu oya": "nanu_oya",
    "nuwara eliya": "nuwara_eliya",
    "hatton": "hatton",
    "peradeniya": "peradeniya",
    "negombo": "negombo",
    "jaffna": "jaffna",
}


# --------------------------------------------------------------------------- #
# Scheduled line routes & trips
# --------------------------------------------------------------------------- #
ROUTES: list[RouteSeed] = [
    RouteSeed(
        id="route_train_mainline_colombo_badulla",
        name="Main Line Hill Country Express (Colombo Fort -> Ella/Badulla)",
        mode="train",
        origin_id="colombo_fort",
        destination_id="ella",
        agency="Sri Lanka Railways",
        distance_km=271.0,
        is_scenic=True,
    ),
    RouteSeed(
        id="route_bus_colombo_ella_direct",
        name="Route 99 Direct Bus (Colombo -> Ella via Ratnapura/Beragala)",
        mode="bus",
        origin_id="colombo_fort_bus",
        destination_id="ella_bus_junction",
        agency="SLTB / Interprovincial",
        distance_km=210.0,
        is_scenic=False,
    ),
    RouteSeed(
        id="route_train_colombo_kandy",
        name="Intercity Express Train (Colombo Fort -> Kandy)",
        mode="train",
        origin_id="colombo_fort",
        destination_id="kandy",
        agency="Sri Lanka Railways",
        distance_km=116.0,
        is_scenic=False,
    ),
    RouteSeed(
        id="route_bus_colombo_kandy",
        name="Route 01 Intercity Express Bus (Colombo Fort -> Kandy)",
        mode="bus",
        origin_id="colombo_fort_bus",
        destination_id="kandy_goods_shed",
        agency="SLTB / NTC Express",
        distance_km=115.0,
        is_scenic=False,
    ),
    RouteSeed(
        id="route_train_kandy_ella",
        name="Kandy -> Ella Scenic Highland Train",
        mode="train",
        origin_id="kandy",
        destination_id="ella",
        agency="Sri Lanka Railways",
        distance_km=156.0,
        is_scenic=True,
    ),
    RouteSeed(
        id="route_bus_kandy_ella",
        name="Route 47 Bus Kandy -> Ella (via Nuwara Eliya/Welimada)",
        mode="bus",
        origin_id="kandy_goods_shed",
        destination_id="ella_bus_junction",
        agency="SLTB Hill Country",
        distance_km=140.0,
        is_scenic=False,
    ),
    RouteSeed(
        id="route_train_colombo_galle",
        name="Coastal Line Express (Colombo Fort -> Galle)",
        mode="train",
        origin_id="colombo_fort",
        destination_id="galle",
        agency="Sri Lanka Railways",
        distance_km=115.0,
        is_scenic=True,
    ),
    RouteSeed(
        id="route_bus_colombo_galle_expressway",
        name="EX01 Southern Expressway Bus (Colombo -> Galle)",
        mode="bus",
        origin_id="colombo_fort_bus",
        destination_id="galle",
        agency="SLTB Expressway",
        distance_km=125.0,
        is_scenic=False,
    ),
    RouteSeed(
        id="route_train_colombo_jaffna",
        name="Yal Devi / Uttara Devi Express (Colombo Fort -> Jaffna)",
        mode="train",
        origin_id="colombo_fort",
        destination_id="jaffna",
        agency="Sri Lanka Railways",
        distance_km=398.0,
        is_scenic=False,
    ),
]

TRIPS: list[TripSeed] = [
    TripSeed(
        id="trip_train_mainline_1005",
        route_id="route_train_mainline_colombo_badulla",
        trip_headsign="Badulla via Ella (Podi Menike)",
        departure_time_str="05:55",
        arrival_time_str="15:15",
        duration_min=420.0,
        base_fare_lkr=1500.0,
        stops=["colombo_fort", "peradeniya", "hatton", "nanu_oya", "ella", "badulla"],
    ),
    TripSeed(
        id="trip_train_mainline_1015",
        route_id="route_train_mainline_colombo_badulla",
        trip_headsign="Badulla via Ella (Udarata Menike)",
        departure_time_str="08:30",
        arrival_time_str="17:50",
        duration_min=420.0,
        base_fare_lkr=1500.0,
        stops=["colombo_fort", "peradeniya", "hatton", "nanu_oya", "ella", "badulla"],
    ),
    TripSeed(
        id="trip_bus_colombo_ella_99",
        route_id="route_bus_colombo_ella_direct",
        trip_headsign="Passara/Ella via Ratnapura",
        departure_time_str="06:30",
        arrival_time_str="12:30",
        duration_min=360.0,
        base_fare_lkr=1200.0,
        stops=["colombo_fort_bus", "ella_bus_junction"],
    ),
    TripSeed(
        id="trip_train_colombo_kandy_1029",
        route_id="route_train_colombo_kandy",
        trip_headsign="Kandy Intercity Express",
        departure_time_str="07:00",
        arrival_time_str="09:30",
        duration_min=150.0,
        base_fare_lkr=1500.0,
        stops=["colombo_fort", "peradeniya", "kandy"],
    ),
    TripSeed(
        id="trip_bus_colombo_kandy_1",
        route_id="route_bus_colombo_kandy",
        trip_headsign="Kandy AC Express Bus",
        departure_time_str="06:45",
        arrival_time_str="09:45",
        duration_min=180.0,
        base_fare_lkr=900.0,
        stops=["colombo_fort_bus", "kandy_goods_shed"],
    ),
    TripSeed(
        id="trip_train_kandy_ella_1126",
        route_id="route_train_kandy_ella",
        trip_headsign="Ella / Badulla Scenic",
        departure_time_str="08:47",
        arrival_time_str="15:07",
        duration_min=380.0,
        base_fare_lkr=1200.0,
        stops=["kandy", "peradeniya", "hatton", "nanu_oya", "ella"],
    ),
    TripSeed(
        id="trip_bus_kandy_ella_47",
        route_id="route_bus_kandy_ella",
        trip_headsign="Badulla via Ella Direct Bus",
        departure_time_str="07:15",
        arrival_time_str="12:45",
        duration_min=330.0,
        base_fare_lkr=800.0,
        stops=["kandy_goods_shed", "ella_bus_junction"],
    ),
    TripSeed(
        id="trip_train_colombo_galle_8056",
        route_id="route_train_colombo_galle",
        trip_headsign="Galle / Matara Coastal Commuter",
        departure_time_str="06:50",
        arrival_time_str="09:00",
        duration_min=130.0,
        base_fare_lkr=700.0,
        stops=["colombo_fort", "galle"],
    ),
    TripSeed(
        id="trip_bus_colombo_galle_ex01",
        route_id="route_bus_colombo_galle_expressway",
        trip_headsign="Galle Highway Express",
        departure_time_str="07:00",
        arrival_time_str="08:30",
        duration_min=90.0,
        base_fare_lkr=950.0,
        stops=["colombo_fort_bus", "galle"],
    ),
    TripSeed(
        id="trip_train_colombo_jaffna_4077",
        route_id="route_train_colombo_jaffna",
        trip_headsign="Yal Devi Express",
        departure_time_str="05:45",
        arrival_time_str="12:45",
        duration_min=420.0,
        base_fare_lkr=2200.0,
        stops=["colombo_fort", "jaffna"],
    ),
]


def resolve_station(name: Optional[str]) -> Optional[StationSeed]:
    """Find a station seed by name or alias (case-insensitive, whitespace-trimmed)."""
    if not name:
        return None
    cleaned = " ".join(name.strip().lower().split())
    # Exact id match
    if cleaned in STATIONS:
        return STATIONS[cleaned]
    # Alias match
    alias_target = STATION_ALIASES.get(cleaned)
    if alias_target and alias_target in STATIONS:
        return STATIONS[alias_target]
    # Substring match
    for st_id, station in STATIONS.items():
        if cleaned in station.name.lower() or station.name.lower() in cleaned:
            return station
    return None
