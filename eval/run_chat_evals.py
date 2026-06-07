"""
Run the golden + adversarial questions against the LIVE Retell chat agent and
record its answers for judging.

Two modes:
  --mode api     (default) drives the Retell chat API directly. Needs
                 RETELL_API_KEY + RETELL_CHAT_AGENT_ID. Each question opens a
                 fresh chat so answers are independent (no carry-over context).
  --mode manual  no API calls — reads answers you pasted into
                 eval/results/chat_answers_manual.jsonl ({id, agent_answer}).
                 Use this if you'd rather collect answers by hand from the widget.

Output: eval/results/chat_results.jsonl  ({id, question, agent_answer, gold_answer, type})
        which judge.py then scores.

NOTE: Retell's chat endpoints/field names have changed across versions. The API
mode below targets the documented create-chat / create-chat-completion flow with
a configurable base URL. If your Retell account exposes a different chat path,
adjust _send_chat() — or just use --mode manual.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import requests

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

RESULTS = Path("eval/results")
RETELL_BASE = os.getenv("RETELL_API_BASE", "https://api.retellai.com")
RETELL_KEY = os.getenv("RETELL_API_KEY", "")
CHAT_AGENT = os.getenv("RETELL_CHAT_AGENT_ID", "")


def load_questions(include_adversarial: bool) -> list[dict]:
    rows: list[dict] = []
    gp = Path("eval/golden_qa.jsonl")
    if gp.exists():
        for line in gp.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            if "_README" in r:
                continue
            rows.append({"id": r["id"], "question": r["question"],
                         "gold_answer": r.get("answer", ""), "type": r.get("type", "")})
    if include_adversarial:
        ap = Path("eval/adversarial.jsonl")
        if ap.exists():
            for line in ap.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                rows.append({"id": r["id"], "question": r["prompt"],
                             "gold_answer": f"PASS CRITERIA: {r['pass_criteria']}",
                             "type": r["type"]})
    return rows


def _headers() -> dict:
    return {"Authorization": f"Bearer {RETELL_KEY}", "Content-Type": "application/json"}


def _send_chat(question: str) -> str:
    """Open a fresh chat and send one message; return the agent's reply text."""
    # 1) create chat
    r = requests.post(f"{RETELL_BASE}/create-chat", headers=_headers(),
                      json={"agent_id": CHAT_AGENT}, timeout=30)
    r.raise_for_status()
    chat_id = r.json().get("chat_id") or r.json().get("id")
    # 2) send message
    r = requests.post(f"{RETELL_BASE}/create-chat-completion", headers=_headers(),
                      json={"chat_id": chat_id, "content": question}, timeout=60)
    r.raise_for_status()
    data = r.json()
    # response shape: {"messages": [{"role":"agent","content":"..."}], ...}
    msgs = data.get("messages") or data.get("response") or []
    if isinstance(msgs, list):
        agent_msgs = [m.get("content", "") for m in msgs
                      if isinstance(m, dict) and m.get("role") in ("agent", "assistant")]
        if agent_msgs:
            return agent_msgs[-1]
    return json.dumps(data)[:2000]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=["api", "manual", "custom"], default="api",
                    help="api=Retell chat agent; custom=our /api/chat backend; manual=paste answers")
    ap.add_argument("--backend-url", default=os.getenv("CHAT_BACKEND_URL", "https://saad-ai-persona.vercel.app"),
                    help="base URL of the custom chat backend (for --mode custom)")
    ap.add_argument("--no-adversarial", action="store_true")
    args = ap.parse_args()

    questions = load_questions(include_adversarial=not args.no_adversarial)
    if not questions:
        raise SystemExit("No questions. Fill eval/golden_qa.jsonl first.")
    RESULTS.mkdir(parents=True, exist_ok=True)

    manual = {}
    if args.mode == "manual":
        mp = RESULTS / "chat_answers_manual.jsonl"
        if not mp.exists():
            raise SystemExit(f"manual mode needs {mp} with rows {{id, agent_answer}}.")
        for line in mp.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                manual[r["id"]] = r["agent_answer"]
    elif args.mode == "api":
        if not (RETELL_KEY and CHAT_AGENT):
            raise SystemExit("api mode needs RETELL_API_KEY + RETELL_CHAT_AGENT_ID.")

    def _send_custom(question: str) -> str:
        r = requests.post(f"{args.backend_url.rstrip('/')}/api/chat",
                          json={"messages": [{"role": "user", "content": question}]}, timeout=90)
        r.raise_for_status()
        return r.json().get("reply", "")

    out = []
    for q in questions:
        if args.mode == "manual":
            answer = manual.get(q["id"], "")
        elif args.mode == "custom":
            try:
                answer = _send_custom(q["question"])
            except Exception as e:
                answer = f"[ERROR contacting custom backend: {e}]"
            # Throttle: the chat backend's free LLM tiers (Gemini ~10 RPM) can't
            # take a rapid burst. Space requests out for a clean eval run.
            time.sleep(float(os.getenv("CHAT_EVAL_SLEEP", "6")))
        else:
            try:
                answer = _send_chat(q["question"])
            except Exception as e:
                answer = f"[ERROR contacting Retell: {e}]"
            time.sleep(0.5)  # be gentle on rate limits
        print(f"  {q['id']}: {answer[:90]}")
        out.append({**q, "agent_answer": answer})

    with (RESULTS / "chat_results.jsonl").open("w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"\n[ok] wrote {len(out)} answers to {RESULTS/'chat_results.jsonl'}. "
          f"Next: python eval/judge.py")


if __name__ == "__main__":
    main()
