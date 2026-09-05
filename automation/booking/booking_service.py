"""Booking Reservation Service (Workstream C, Phase C3).

Implements autonomous reservation hold preparation for Sri Lankan transit routes.

SAFETY INVARIANTS:
1. Hold only: Generates a temporary 15-minute reservation hold reference.
2. No payment processing: NEVER debits cards, initiates bank transfers, or invokes
   live payment gateways.
3. Explicit simulation marker: All records explicitly marked as data_source="simulated".
"""

from __future__ import annotations

import hashlib
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from automation.booking.availability import AvailabilityService, get_availability_service


class BookingService:
    """Autonomous reservation hold engine."""

    _instance: Optional["BookingService"] = None

    def __init__(self) -> None:
        self.availability_service = get_availability_service()
        # In-memory store of active holds
        self._holds: dict[str, dict[str, Any]] = {}

    @classmethod
    def get_instance(cls) -> "BookingService":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def prepare_hold(
        self,
        route_id: str,
        traveler_name: Optional[str] = "Traveler",
        seats: int = 1,
        total_fare_lkr: Optional[float] = None,
        seat_class: Optional[str] = "second",
    ) -> dict[str, Any]:
        """Prepare a 15-minute temporary reservation hold for a route candidate.

        Returns:
            dict containing:
                prepared: bool
                reference: str (RW-<route_id>-<hash>)
                status: 'HELD' | 'FAILED'
                expires_in_minutes: int (15)
                expires_at: str (ISO 8601)
                total_fare_lkr: float
                currency: 'LKR'
                route_id: str
                traveler_name: str
                seats: int
                seat_class: str
        """
        rid = (route_id or "R1").strip().upper()
        traveler = (traveler_name or "Traveler").strip()
        num_seats = max(1, min(seats, 6))

        # Check seat availability
        avail = self.availability_service.check_availability(rid)
        if avail.get("availability") == "unavailable":
            return {
                "prepared": False,
                "reference": None,
                "status": "UNAVAILABLE",
                "route_id": rid,
                "traveler_name": traveler,
                "seats": num_seats,
                "expires_in_minutes": 0,
                "total_fare_lkr": 0.0,
                "currency": "LKR",
                "message": f"Cannot hold seats on '{rid}': service is unavailable or disrupted.",
                "data_source": "simulated",
            }

        # Calculate estimated fare if not supplied
        if total_fare_lkr is None or total_fare_lkr <= 0:
            fare_table = {
                "R1": 1600.0,
                "R2": 1200.0,
                "R3": 2350.0,
                "C1": 1100.0,
                "C2": 950.0,
                "K1": 1100.0,
                "K2": 950.0,
            }
            fare = fare_table.get(rid, 1500.0) * num_seats
        else:
            fare = float(total_fare_lkr)

        # Generate unique verifiable reference: RW-<route_id>-<timestamp-hash>
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(minutes=15)
        seed = f"{rid}:{traveler}:{num_seats}:{int(now.timestamp())}"
        ref_hash = hashlib.sha256(seed.encode("utf-8")).hexdigest()[:6].upper()
        reference = f"RW-{rid}-{ref_hash}"

        hold_record = {
            "prepared": True,
            "reference": reference,
            "status": "HELD",
            "route_id": rid,
            "traveler_name": traveler,
            "seats": num_seats,
            "seat_class": seat_class or "second",
            "total_fare_lkr": round(fare, 2),
            "currency": "LKR",
            "created_at": now.isoformat(),
            "expires_at": expires_at.isoformat(),
            "expires_in_minutes": 15,
            "data_source": "simulated",
            "is_confirmed_payment": False,
            "safety_invariant": "HOLD_ONLY_NO_FUNDS_DEBITED",
        }

        self._holds[reference] = hold_record
        return hold_record

    def get_hold(self, reference: str) -> Optional[dict[str, Any]]:
        """Retrieve previously prepared hold details by reference code."""
        return self._holds.get(reference.strip().upper())


def get_booking_service() -> BookingService:
    """Return singleton instance of BookingService."""
    return BookingService.get_instance()
