"""
Health-check for the Cal.com booking API keys.

Verifies, in order:
  1. CAL_API_KEY authenticates (GET /v2/me)
  2. CAL_EVENT_TYPE_ID is valid and slots can be fetched (real availability call)

Run from the repo root:  python booking/check_cal.py
Fill CAL_API_KEY + CAL_EVENT_TYPE_ID in .env first.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests

import calcom  # noqa: E402  (after load_dotenv so env is populated)


def _safe(s: str) -> str:
    return str(s)[:200].encode("ascii", "replace").decode()


def main():
    key = os.getenv("CAL_API_KEY", "")
    etid = os.getenv("CAL_EVENT_TYPE_ID", "")
    base = os.getenv("CAL_API_BASE", "https://api.cal.com")
    if not key:
        raise SystemExit("CAL_API_KEY is not set in .env.")

    ok = True

    # 1. Key auth
    try:
        r = requests.get(f"{base}/v2/me",
                         headers={"Authorization": f"Bearer {key}",
                                  "cal-api-version": "2024-06-14"}, timeout=20)
        if r.status_code < 400:
            data = r.json().get("data", {})
            who = data.get("username") or data.get("email") or "ok"
            print(f"  [OK]   CAL_API_KEY authenticates (user: {who})")
        else:
            ok = False
            print(f"  [FAIL] CAL_API_KEY -> {r.status_code}: {_safe(r.text)}")
    except Exception as e:
        ok = False
        print(f"  [FAIL] CAL_API_KEY -> {type(e).__name__}: {_safe(e)}")

    # 2. Event type + slots
    if not etid:
        print("  [WARN] CAL_EVENT_TYPE_ID not set — skipping slots check.")
        ok = False
    else:
        try:
            slots = calcom.get_available_slots()
            print(f"  [OK]   CAL_EVENT_TYPE_ID={etid} valid; fetched {len(slots)} open slots "
                  f"(showing up to 3): {slots[:3]}")
        except calcom.CalError as e:
            ok = False
            print(f"  [FAIL] slots fetch (check CAL_EVENT_TYPE_ID / plan) -> {_safe(e)}")

    print("\n" + ("Cal.com is configured correctly." if ok else
                  "Fix the FAIL/WARN line(s) above, then re-run."))


if __name__ == "__main__":
    main()
