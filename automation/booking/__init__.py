"""Automation Booking Package (Workstream C)."""

from automation.booking.availability import AvailabilityService, get_availability_service
from automation.booking.browser_automation import (
    BrowserBookingAutomation,
    get_browser_automation,
)

__all__ = [
    "AvailabilityService",
    "get_availability_service",
    "BrowserBookingAutomation",
    "get_browser_automation",
]
