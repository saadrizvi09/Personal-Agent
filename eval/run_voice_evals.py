"""
Voice-quality metrics: first-response latency (p50/p95), transcription accuracy
(WER), and booking success across N test calls.

Automated, fully-hands-off voice testing is brittle (you'd need a programmatic
caller + STT of the agent's audio). The honest, defensible approach for a
screening submission is: place N real test calls yourself following the voice
scripts, capture a few numbers per call, and let this script aggregate them.
A small honest N beats a big vague claim.

Capture file: eval/results/voice_calls.jsonl — one row per call:
  {
    "call_id": "call-01",
    "first_response_latency_ms": 920,        # caller-stops-speaking → first agent audio
    "scripted_text": "what languages do you know",   # what you said (for WER)
    "transcript_text": "what languages do you know", # Retell's transcript of you
    "booking_attempted": true,
    "booking_succeeded": true,
    "barge_in_tested": true,
    "barge_in_ok": true
  }

How to get latency: Retell's call detail / dashboard exposes per-turn timestamps;
or use a stopwatch on the recording. Document your method in the report.

Output: eval/results/voice_summary.json
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

RESULTS = Path("eval/results")


def _wer(ref: str, hyp: str) -> float:
    try:
        import jiwer
        return float(jiwer.wer(ref, hyp))
    except Exception:
        # tiny fallback: word-level edit distance / ref length
        r, h = ref.split(), hyp.split()
        d = [[0] * (len(h) + 1) for _ in range(len(r) + 1)]
        for i in range(len(r) + 1):
            d[i][0] = i
        for j in range(len(h) + 1):
            d[0][j] = j
        for i in range(1, len(r) + 1):
            for j in range(1, len(h) + 1):
                cost = 0 if r[i - 1] == h[j - 1] else 1
                d[i][j] = min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + cost)
        return d[len(r)][len(h)] / max(len(r), 1)


def main():
    path = RESULTS / "voice_calls.jsonl"
    if not path.exists():
        raise SystemExit(
            f"missing {path}.\nCreate it with one JSON row per test call "
            "(see the docstring in this file for the schema)."
        )
    rows = [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    if not rows:
        raise SystemExit("voice_calls.jsonl is empty.")

    latencies = [r["first_response_latency_ms"] for r in rows
                 if r.get("first_response_latency_ms") is not None]
    wers = [_wer(r["scripted_text"], r["transcript_text"]) for r in rows
            if r.get("scripted_text") and r.get("transcript_text")]
    attempts = [r for r in rows if r.get("booking_attempted")]
    successes = [r for r in attempts if r.get("booking_succeeded")]
    barge = [r for r in rows if r.get("barge_in_tested")]
    barge_ok = [r for r in barge if r.get("barge_in_ok")]

    summary = {
        "n_calls": len(rows),
        "latency_ms_p50": int(np.percentile(latencies, 50)) if latencies else None,
        "latency_ms_p95": int(np.percentile(latencies, 95)) if latencies else None,
        "latency_ms_max": int(max(latencies)) if latencies else None,
        "wer_mean": round(float(np.mean(wers)), 4) if wers else None,
        "booking_attempts": len(attempts),
        "booking_successes": len(successes),
        "booking_success_rate": round(len(successes) / len(attempts), 4) if attempts else None,
        "barge_in_tested": len(barge),
        "barge_in_pass_rate": round(len(barge_ok) / len(barge), 4) if barge else None,
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "voice_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
