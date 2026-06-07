"""
Booking backend — FastAPI service that Retell's custom functions call.

Retell (voice + chat) is configured with two custom functions whose URLs point
here. When the agent decides to check the calendar or book, Retell POSTs the
collected arguments to these endpoints; we talk to Cal.com and return a result
the agent reads back to the caller. No human in the loop.

Endpoints:
  GET  /                       health
  POST /functions/get-availability   → open slots for a window
  POST /functions/book-meeting       → verify-then-book a confirmed meeting

Security: set BOOKING_WEBHOOK_SECRET and configure the same value in Retell as
a custom header (Authorization: Bearer <secret>). Requests without it are
rejected so strangers can't drive your calendar.

Run locally:
  uvicorn booking.main:app --reload --port 8000
Deploy free: Render / Railway / Fly.io (uvicorn booking.main:app --host 0.0.0.0 --port $PORT)
"""

from __future__ import annotations

import json
import os

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import calcom  # noqa: E402  (after load_dotenv so env is populated)

WEBHOOK_SECRET = os.getenv("BOOKING_WEBHOOK_SECRET", "")

app = FastAPI(title="AI Persona — Booking Backend", version="1.0.0")


# ── Auth ─────────────────────────────────────────────────────────────────────
def _check_auth(authorization: str | None):
    if not WEBHOOK_SECRET:
        return  # secret unset → open (fine for local dev; set it in prod)
    expected = f"Bearer {WEBHOOK_SECRET}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="unauthorized")


# ── Argument extraction ──────────────────────────────────────────────────────
async def _args(request: Request) -> dict:
    """Retell sends function args; depending on config they arrive either flat
    or nested under "args". Accept both."""
    try:
        body = await request.json()
    except Exception:
        return {}
    if isinstance(body, dict) and isinstance(body.get("args"), dict):
        return body["args"]
    return body if isinstance(body, dict) else {}


# ── Health ───────────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {
        "service": "ai-persona-booking",
        "status": "ok",
        "cal_configured": bool(os.getenv("CAL_API_KEY") and os.getenv("CAL_EVENT_TYPE_ID")),
    }


# ── get-availability ─────────────────────────────────────────────────────────
@app.post("/functions/get-availability")
async def get_availability(request: Request,
                           authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    args = await _args(request)
    try:
        slots = calcom.get_available_slots(
            start_date=args.get("start_date"),
            end_date=args.get("end_date"),
            timezone_name=args.get("timezone"),
        )
    except calcom.CalError as e:
        return {"success": False,
                "message": "I couldn't reach my calendar just now. "
                           "Want me to try a different day?",
                "error": str(e)}

    # Return a compact, speakable subset (agents read these aloud).
    top = slots[:8]
    if not top:
        return {"success": True, "slots": [],
                "message": "I don't have any open slots in that window. "
                           "Want me to look further out?"}
    return {"success": True, "slots": top, "count": len(slots),
            "message": f"I found {len(slots)} open slots; here are the soonest few."}


# ── book-meeting ─────────────────────────────────────────────────────────────
class BookArgs(BaseModel):
    slot_start: str
    attendee_name: str
    attendee_email: str
    timezone: str | None = None
    notes: str | None = ""


@app.post("/functions/book-meeting")
async def book_meeting(request: Request,
                       authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    raw = await _args(request)
    try:
        args = BookArgs(**raw)
    except Exception as e:
        return {"success": False,
                "message": "I still need a slot, your name, and your email to book.",
                "error": str(e)}

    # 1. Verify the slot is still free (anti double-booking).
    try:
        if not calcom.slot_is_free(args.slot_start, args.timezone):
            alts = calcom.get_available_slots(
                start_date=args.slot_start[:10], timezone_name=args.timezone)
            return {"success": False, "slots": alts[:5],
                    "message": "That slot was just taken. Here are the nearest "
                               "alternatives — which works?"}
    except calcom.CalError as e:
        return {"success": False,
                "message": "I had trouble confirming that slot. Want to try another?",
                "error": str(e)}

    # 2. Book.
    try:
        booking = calcom.book_meeting(
            slot_start=args.slot_start,
            attendee_name=args.attendee_name,
            attendee_email=args.attendee_email,
            timezone_name=args.timezone,
            notes=args.notes or "",
        )
    except calcom.CalError as e:
        return {"success": False,
                "message": "The booking didn't go through. Want me to try again "
                           "or pick another time?",
                "error": str(e)}

    event_id = booking.get("uid") or booking.get("id")
    return {
        "success": True,
        "event_id": event_id,
        "start": booking.get("start", args.slot_start),
        "attendee_email": args.attendee_email,
        "message": (f"You're booked for {args.slot_start}. I've sent a calendar "
                    f"invite to {args.attendee_email}. Confirmation id {event_id}."),
    }


# ── Vapi tool endpoint (voice) ───────────────────────────────────────────────
# Vapi posts tool calls as {message:{toolCalls:[{id, function:{name, arguments}}]}}
# and expects {results:[{toolCallId, result}]} where result is a string the LLM
# reads back. Same Cal.com logic as above; one endpoint dispatches both tools.
def _availability(args: dict) -> dict:
    try:
        slots = calcom.get_available_slots(args.get("start_date"), args.get("end_date"),
                                           args.get("timezone"))
        if not slots:
            return {"success": True, "slots": [], "message": "No open slots in that window."}
        return {"success": True, "slots": slots[:8], "count": len(slots)}
    except calcom.CalError as e:
        return {"success": False, "message": "Couldn't reach the calendar.", "error": str(e)}


def _book(args: dict) -> dict:
    try:
        if not (args.get("slot_start") and args.get("attendee_name") and args.get("attendee_email")):
            return {"success": False, "message": "I need a slot, your name, and your email to book."}
        if not calcom.slot_is_free(args["slot_start"], args.get("timezone")):
            alts = calcom.get_available_slots(start_date=args["slot_start"][:10],
                                              timezone_name=args.get("timezone"))
            return {"success": False, "slots": alts[:5],
                    "message": "That slot was just taken; here are alternatives."}
        b = calcom.book_meeting(args["slot_start"], args["attendee_name"], args["attendee_email"],
                                args.get("timezone"), args.get("notes", "") or "")
        eid = b.get("uid") or b.get("id")
        return {"success": True, "event_id": eid, "start": b.get("start", args["slot_start"]),
                "message": f"Booked for {args['slot_start']}; invite sent. Confirmation {eid}."}
    except calcom.CalError as e:
        return {"success": False, "message": "The booking didn't go through.", "error": str(e)}


@app.post("/functions/vapi-tool")
async def vapi_tool(request: Request, authorization: str | None = Header(default=None)):
    _check_auth(authorization)
    body = await request.json()
    tool_calls = (body.get("message") or {}).get("toolCalls") or body.get("toolCalls") or []
    results = []
    for tc in tool_calls:
        fn = tc.get("function") or {}
        name = fn.get("name")
        args = fn.get("arguments") or {}
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except json.JSONDecodeError:
                args = {}
        if name == "get_availability":
            res = _availability(args)
        elif name == "book_meeting":
            res = _book(args)
        else:
            res = {"success": False, "error": f"unknown tool {name}"}
        results.append({"toolCallId": tc.get("id"), "result": json.dumps(res)})
    return {"results": results}
