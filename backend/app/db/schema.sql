-- ============================================================================
-- RouteWise Agentic — PostgreSQL + PostGIS Transit Intelligence Schema
-- Workstream B: Transit Intelligence & ML
-- ============================================================================

-- Enable PostGIS extension for spatial types and functions
CREATE EXTENSION IF NOT EXISTS postgis;

-- 1. Stations / Transit Hubs
-- Captures physical railway stations, bus terminals, and multi-modal transfer hubs.
CREATE TABLE IF NOT EXISTS stations (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    latitude DOUBLE PRECISION NOT NULL,
    longitude DOUBLE PRECISION NOT NULL,
    geom GEOMETRY(Point, 4326),
    city VARCHAR(100),
    district VARCHAR(100),
    modes_served TEXT[] NOT NULL DEFAULT '{}', -- e.g. ARRAY['train', 'bus', 'tuk', 'walk']
    is_hub BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_stations_geom ON stations USING GIST (geom);
CREATE INDEX IF NOT EXISTS idx_stations_name ON stations (LOWER(name));

-- 2. Transit Routes
-- Scheduled lines (e.g. Sri Lanka Railways Main Line, Express Bus 01 Colombo-Kandy).
CREATE TABLE IF NOT EXISTS routes (
    id VARCHAR(64) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    mode VARCHAR(32) NOT NULL, -- 'train' | 'bus' | 'tuk' | 'walk' | 'taxi' | 'ferry'
    origin_station_id VARCHAR(64) NOT NULL REFERENCES stations(id),
    destination_station_id VARCHAR(64) NOT NULL REFERENCES stations(id),
    agency VARCHAR(100) DEFAULT 'Sri Lanka Railways / SLTB',
    distance_km DOUBLE PRECISION NOT NULL,
    is_scenic BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_routes_mode ON routes (mode);
CREATE INDEX IF NOT EXISTS idx_routes_origin_dest ON routes (origin_station_id, destination_station_id);

-- 3. Trips (GTFS-style)
-- Individual scheduled runs of a route on a specific service calendar.
CREATE TABLE IF NOT EXISTS trips (
    id VARCHAR(64) PRIMARY KEY,
    route_id VARCHAR(64) NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
    service_id VARCHAR(64) NOT NULL DEFAULT 'daily',
    trip_headsign VARCHAR(255),
    direction SMALLINT NOT NULL DEFAULT 0, -- 0 = outbound, 1 = inbound
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_trips_route ON trips (route_id);

-- 4. Stop Times (GTFS-style)
-- Ordered sequence of stops, arrivals, and departures for each trip.
CREATE TABLE IF NOT EXISTS stop_times (
    id BIGSERIAL PRIMARY KEY,
    trip_id VARCHAR(64) NOT NULL REFERENCES trips(id) ON DELETE CASCADE,
    station_id VARCHAR(64) NOT NULL REFERENCES stations(id),
    stop_sequence INTEGER NOT NULL,
    arrival_time TIME NOT NULL,
    departure_time TIME NOT NULL,
    dist_traveled_km DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    CONSTRAINT uq_trip_stop_sequence UNIQUE (trip_id, stop_sequence)
);

CREATE INDEX IF NOT EXISTS idx_stop_times_station ON stop_times (station_id);
CREATE INDEX IF NOT EXISTS idx_stop_times_trip ON stop_times (trip_id, stop_sequence);

-- 5. Fares
-- Tariff guidelines and base fares for transit segments.
CREATE TABLE IF NOT EXISTS fares (
    id VARCHAR(64) PRIMARY KEY,
    route_id VARCHAR(64) REFERENCES routes(id) ON DELETE CASCADE,
    mode VARCHAR(32) NOT NULL,
    base_fare_lkr DOUBLE PRECISION NOT NULL,
    per_km_lkr DOUBLE PRECISION NOT NULL,
    class_tier VARCHAR(32) DEFAULT 'standard', -- '3rd_class' | '2nd_class' | '1st_class' | 'ac_bus' | 'normal_bus'
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_fares_route_mode ON fares (route_id, mode);
