"""Automation Booking Package (Workstream C)."""

from automation.booking.availability import AvailabilityService, get_availability_service
from automation.booking.booking_service import BookingService, get_booking_service
from automation.booking.browser_automation import (
    BrowserBookingAutomation,
    get_browser_automation,
)

__all__ = [
    "AvailabilityService",
    "get_availability_service",
    "BookingService",
    "get_booking_service",
    "BrowserBookingAutomation",
    "get_browser_automation",
]
