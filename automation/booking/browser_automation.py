"""Browser Booking Automation (Workstream C, Phase C2 — Coder Work).

Simulates autonomous browser-driven navigation and form interaction for transit
reservations against Sri Lanka Railways / NTC Express Bus ticketing portals.

Safety Invariant:
- Holds only (never commits or debits real payment).
- Operates against local fixture / simulated sandbox.
- Seamless fallback to AvailabilityService if browser runtime is not active.
"""

from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from typing import Any, Optional

from automation.booking.availability import AvailabilityService, get_availability_service


class BrowserBookingAutomation:
    """Autonomous agent browser automation client for transit reservations."""

    _instance: Optional["BrowserBookingAutomation"] = None

    def __init__(self, fixture_path: Optional[Path] = None) -> None:
        self.fixture_path = (
            fixture_path
            or Path(__file__).resolve().parent / "fixtures" / "mock_booking_portal.html"
        )
        self.availability_service = get_availability_service()

    @classmethod
    def get_instance(cls) -> "BrowserBookingAutomation":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _read_portal_fixture(self) -> str:
        """Read HTML content from mock booking portal fixture."""
        if not self.fixture_path.exists():
            return ""
        try:
            with open(self.fixture_path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception:
            return ""

    def check_availability_via_portal(
        self,
        origin: str = "Colombo Fort",
        destination: str = "Ella",
        travel_date: Optional[str] = None,
    ) -> list[dict[str, Any]]:
        """Inspect the ticketing portal for available transit services and seat counts.

        Parses table rows from the mock booking portal.
        """
        html = self._read_portal_fixture()
        if not html:
            # Fallback directly to deterministic availability service
            r1 = self.availability_service.check_availability("R1", travel_date=travel_date)
            r2 = self.availability_service.check_availability("R2", travel_date=travel_date)
            r3 = self.availability_service.check_availability("R3", travel_date=travel_date)
            return [r1, r2, r3]

        services = []
        # Extract <tr> rows matching data-route-id
        row_pattern = re.compile(
            r'<tr\s+id="row-([^"]+)"\s+data-route-id="([^"]+)">.*?<td><strong>([^<]+)</strong></td>\s*'
            r'<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*<td>([^<]+)</td>\s*'
            r'<td>LKR\s*([\d,]+)</td>\s*<td><span[^>]*>(\d+)</span>\s*seats</td>\s*'
            r'<td><span[^>]*>([^<]+)</span></td>',
            re.DOTALL | re.IGNORECASE,
        )

        for match in row_pattern.finditer(html):
            _, route_id_attr, route_id, service_name, dep, arr, fare_str, seats_str, status_badge = (
                match.groups()
            )
            fare = float(fare_str.replace(",", ""))
            seats = int(seats_str)
            status_clean = status_badge.strip().lower()

            services.append(
                {
                    "route_id": route_id.strip(),
                    "service_name": service_name.strip(),
                    "departure": dep.strip(),
                    "arrival": arr.strip(),
                    "fare_lkr": fare,
                    "available_seats": seats,
                    "availability": status_clean,
                    "origin": origin,
                    "destination": destination,
                    "travel_date": travel_date or "2026-09-05",
                    "source": "browser_portal_scrape",
                }
            )

        if not services:
            # Fallback if HTML regex didn't catch rows
            for rid in ("R1", "R2", "R3"):
                services.append(self.availability_service.check_availability(rid))

        return services

    def hold_seat_via_portal(
        self,
        route_id: str,
        traveler_name: Optional[str] = "Traveler",
        seats: int = 1,
        total_fare_lkr: Optional[float] = None,
    ) -> dict[str, Any]:
        """Simulate autonomous browser interaction filling the hold reservation form.

        Returns a structured reservation hold voucher without debiting any money.
        """
        rid = (route_id or "R1").strip().upper()
        traveler = traveler_name or "Samantha Perera"
        num_seats = max(1, min(seats, 4))

        # Check availability first
        avail = self.availability_service.check_availability(rid)
        if avail.get("availability") == "unavailable":
            return {
                "prepared": False,
                "reference": None,
                "status": "UNAVAILABLE",
                "route_id": rid,
                "message": f"Route '{rid}' has no available inventory or is disrupted.",
                "expires_in_minutes": 0,
                "total_fare_lkr": 0.0,
                "data_source": "simulated",
            }

        # Determine estimated fare
        if total_fare_lkr is None:
            fare_table = {"R1": 1400.0, "R2": 1200.0, "R3": 1950.0, "C1": 1100.0, "K1": 1100.0}
            base_fare = fare_table.get(rid, 1500.0)
            calculated_fare = base_fare * num_seats
        else:
            calculated_fare = float(total_fare_lkr)

        # Generate deterministic, verifiable booking reference hash
        ts = int(time.time()) // 300  # 5-minute bucket for stability
        token_seed = f"{rid}:{traveler}:{num_seats}:{ts}"
        ref_hash = hashlib.sha256(token_seed.encode("utf-8")).hexdigest()[:6].upper()
        booking_ref = f"RW-{rid}-{ref_hash}"

        return {
            "prepared": True,
            "reference": booking_ref,
            "status": "HELD",
            "route_id": rid,
            "traveler_name": traveler,
            "seats": num_seats,
            "total_fare_lkr": calculated_fare,
            "currency": "LKR",
            "expires_in_minutes": 15,
            "data_source": "simulated",
            "safety_note": "Simulated hold only — no live funds debited.",
            "portal": "Sri Lanka Transit e-Ticketing (Simulated)",
        }


def get_browser_automation() -> BrowserBookingAutomation:
    """Return singleton instance of BrowserBookingAutomation."""
    return BrowserBookingAutomation.get_instance()
