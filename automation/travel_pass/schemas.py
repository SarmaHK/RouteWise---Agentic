"""Travel Pass Data Schemas (Workstream C, Phase C5).

Defines the structured offline Travel Pass model conforming to DESIGN_SYSTEM.md §11.9
and API_CONTRACTS.md §3.
"""

from __future__ import annotations

from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.route import PlanResponse


class TravelPass(BaseModel):
    """Structured offline-ready Travel Pass voucher."""

    model_config = ConfigDict(populate_by_name=True, arbitrary_types_allowed=True)

    pass_id: str = Field(description="Unique voucher pass token, e.g. 'PASS-RW-2026-X83K'.")
    booking_reference: str = Field(
        description="Verifiable booking hold reference, e.g. 'RW-R1-4F786D'."
    )
    status: str = Field(
        default="HELD", description="Reservation status: 'HELD' | 'OFFLINE_CONFIRMED'."
    )
    traveler_name: str = Field(default="Samantha Perera", description="Name of the primary traveler.")
    seats: int = Field(default=1, description="Number of reserved seats.")
    seat_class: str = Field(default="second", description="Travel class / accommodation type.")
    total_fare_lkr: float = Field(description="Total journey fare in Sri Lankan Rupees.")
    currency: str = Field(default="LKR", description="Currency ISO code.")

    origin: str = Field(default="Colombo Fort", description="Trip origin station / city.")
    destination: str = Field(default="Ella", description="Trip destination station / city.")
    departure_time: Optional[str] = Field(default=None, description="Scheduled departure timestamp.")
    arrival_time: Optional[str] = Field(default=None, description="Estimated arrival timestamp.")
    duration_min: Optional[float] = Field(default=None, description="Total journey duration in minutes.")

    route_id: str = Field(description="Identifier of the chosen route candidate (e.g. 'R1').")
    summary: str = Field(description="Headline journey description.")
    legs: list[dict[str, Any]] = Field(
        default_factory=list, description="Ordered transit segments (walk, tuk, train, bus)."
    )

    qr_code_svg: str = Field(description="Embedded offline SVG QR code data.")
    offline_instructions: str = Field(
        default="Show this pass to the station booking clerk or bus conductor for boarding verification.",
        description="Guidance for offline transit conductors.",
    )
    is_offline_ready: bool = Field(
        default=True, description="True indicates pass requires no internet connection to present."
    )
    generated_at: str = Field(description="Pass creation timestamp (ISO 8601).")
    expires_at: str = Field(description="Reservation hold expiration timestamp (ISO 8601).")
    plan: Optional[PlanResponse] = Field(
        default=None, description="Complete underlying PlanResponse."
    )


class TravelPassRequest(BaseModel):
    """Payload to generate a Travel Pass."""

    plan: PlanResponse = Field(description="The finalized route plan response.")
    booking_reference: Optional[str] = Field(
        default=None, description="Optional booking reference code (auto-generated if omitted)."
    )
    traveler_name: Optional[str] = Field(
        default="Samantha Perera", description="Name of traveler."
    )
    seats: int = Field(default=1, ge=1, le=6, description="Number of seats.")
    seat_class: Optional[str] = Field(default="second", description="Seating class.")
