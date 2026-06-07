"""
Health-check for the Retell API key + helper to find your chat agent id.

Verifies RETELL_API_KEY authenticates, then lists your agents so you can copy
the right agent_id into RETELL_CHAT_AGENT_ID. If RETELL_CHAT_AGENT_ID is already
set, confirms it exists in your account.

Run from the repo root:  python eval/check_retell.py

Note: Retell's API surface shifts between versions. If /list-agents 404s, check
your Retell dashboard for the current endpoint and adjust LIST_PATH below.
"""

from __future__ import annotations

import os

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

import requests

BASE = os.getenv("RETELL_API_BASE", "https://api.retellai.com")
KEY = os.getenv("RETELL_API_KEY", "")
CHAT_AGENT = os.getenv("RETELL_CHAT_AGENT_ID", "")
LIST_PATH = "/list-agents"


def _safe(s: str) -> str:
    return str(s)[:200].encode("ascii", "replace").decode()


def main():
    if not KEY:
        raise SystemExit("RETELL_API_KEY is not set in .env.")
    try:
        r = requests.get(f"{BASE}{LIST_PATH}",
                         headers={"Authorization": f"Bearer {KEY}"}, timeout=20)
    except Exception as e:
        raise SystemExit(f"[FAIL] could not reach Retell: {type(e).__name__}: {_safe(e)}")

    if r.status_code >= 400:
        raise SystemExit(f"[FAIL] RETELL_API_KEY -> {r.status_code}: {_safe(r.text)}")

    # Voice agents and chat agents live on separate endpoints in Retell.
    def _agents(path):
        rr = requests.get(f"{BASE}{path}", headers={"Authorization": f"Bearer {KEY}"}, timeout=20)
        if rr.status_code >= 400:
            return []
        data = rr.json()
        if isinstance(data, dict):
            data = data.get("data") or data.get("agents") or []
        return data

    voice = _agents("/list-agents")
    chat = _agents("/list-chat-agents")
    all_ids = set()
    print(f"  [OK]   RETELL_API_KEY authenticates.\n")
    for label, lst in (("VOICE", voice), ("CHAT", chat)):
        seen = set()
        uniq = [a for a in lst if (a.get("agent_id") or a.get("id")) not in seen
                and not seen.add(a.get("agent_id") or a.get("id"))]
        print(f"  {label} agents ({len(uniq)}):")
        for a in uniq:
            aid = a.get("agent_id") or a.get("id"); all_ids.add(aid)
            name = a.get("agent_name") or a.get("name") or ""
            print(f"    - {aid}  {name}  [{a.get('channel','')}]")
        print()

    if CHAT_AGENT:
        if CHAT_AGENT in all_ids:
            print(f"  [OK]   RETELL_CHAT_AGENT_ID={CHAT_AGENT} found.")
        else:
            print(f"  [FAIL] RETELL_CHAT_AGENT_ID={CHAT_AGENT} not found above.")
    else:
        print("  [WARN] RETELL_CHAT_AGENT_ID not set — copy your CHAT agent's id into .env.")


if __name__ == "__main__":
    main()
