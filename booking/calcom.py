"""
Cal.com API v2 client — availability + confirmed bookings.

Implements the "safe pattern": get slots → verify the chosen slot is still
free → book. Cal.com pins API versions per endpoint via the `cal-api-version`
header; we keep slots and bookings versions configurable because Cal.com
revises them independently.

Docs: https://cal.com/docs/api-reference/v2
"""

from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import requests

CAL_API_BASE = os.getenv("CAL_API_BASE", "https://api.cal.com")
CAL_API_KEY = os.getenv("CAL_API_KEY", "")
CAL_EVENT_TYPE_ID = os.getenv("CAL_EVENT_TYPE_ID", "")
VERSION_SLOTS = os.getenv("CAL_API_VERSION_SLOTS", "2024-09-04")
VERSION_BOOKINGS = os.getenv("CAL_API_VERSION_BOOKINGS", "2024-08-13")
DEFAULT_TZ = os.getenv("DEFAULT_TIMEZONE", "Asia/Kolkata")


class CalError(RuntimeError):
    pass


def _headers(version: str) -> dict:
    if not CAL_API_KEY:
        raise CalError("CAL_API_KEY is not set")
    return {
        "Authorization": f"Bearer {CAL_API_KEY}",
        "cal-api-version": version,
        "Content-Type": "application/json",
    }


def get_available_slots(start_date: str | None = None,
                        end_date: str | None = None,
                        timezone_name: str | None = None,
                        event_type_id: str | None = None) -> list[str]:
    """Return a flat list of open slot start-times (ISO 8601) for the window.

    start_date / end_date are ISO dates ('2026-06-10'); defaults to the next
    7 days starting tomorrow. Returns at most a few dozen slots.
    """
    tz = timezone_name or DEFAULT_TZ
    etid = event_type_id or CAL_EVENT_TYPE_ID
    if not etid:
        raise CalError("CAL_EVENT_TYPE_ID is not set")

    if not start_date:
        start_date = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    if not end_date:
        end_date = (datetime.fromisoformat(start_date) + timedelta(days=7)).date().isoformat()

    r = requests.get(
        f"{CAL_API_BASE}/v2/slots",
        headers=_headers(VERSION_SLOTS),
        params={
            "eventTypeId": etid,
            "start": start_date,
            "end": end_date,
            "timeZone": tz,
        },
        timeout=30,
    )
    if r.status_code >= 400:
        raise CalError(f"slots {r.status_code}: {r.text[:300]}")
    payload = r.json().get("data", {})

    # The v2 slots response is { "data": { "YYYY-MM-DD": [ {"start": iso}, ... ] } }
    slots: list[str] = []
    if isinstance(payload, dict):
        for _day, day_slots in sorted(payload.items()):
            for s in day_slots:
                start = s.get("start") if isinstance(s, dict) else s
                if start:
                    slots.append(start)
    elif isinstance(payload, list):  # tolerate flat-list shape
        for s in payload:
            start = s.get("start") if isinstance(s, dict) else s
            if start:
                slots.append(start)
    return slots


def slot_is_free(slot_start: str, timezone_name: str | None = None,
                 event_type_id: str | None = None) -> bool:
    """Re-check immediately before booking to avoid double-booking."""
    day = slot_start[:10]
    free = get_available_slots(day, day, timezone_name, event_type_id)
    # Compare on the instant, tolerating timezone-offset formatting differences.
    target = _instant(slot_start)
    return any(_instant(s) == target for s in free)


def book_meeting(slot_start: str, attendee_name: str, attendee_email: str,
                 timezone_name: str | None = None, notes: str = "",
                 event_type_id: str | None = None) -> dict:
    """Create a confirmed booking. Returns the Cal.com booking object."""
    tz = timezone_name or DEFAULT_TZ
    etid = event_type_id or CAL_EVENT_TYPE_ID
    if not etid:
        raise CalError("CAL_EVENT_TYPE_ID is not set")

    body = {
        "start": slot_start,
        "eventTypeId": int(etid),
        "attendee": {
            "name": attendee_name,
            "email": attendee_email,
            "timeZone": tz,
            "language": "en",
        },
    }
    if notes:
        body["metadata"] = {"notes": notes[:480]}

    r = requests.post(
        f"{CAL_API_BASE}/v2/bookings",
        headers=_headers(VERSION_BOOKINGS),
        json=body,
        timeout=30,
    )
    if r.status_code >= 400:
        raise CalError(f"booking {r.status_code}: {r.text[:300]}")
    return r.json().get("data", r.json())


def _instant(iso: str) -> datetime:
    """Parse an ISO timestamp to a UTC datetime for comparison."""
    s = iso.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        # fall back: strip subsecond / offset oddities
        dt = datetime.fromisoformat(s[:19])
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
