"""
Quick health-check for the judge keys.

Pings the PRIMARY and BACKUP judge providers independently with one trivial
classification call each, so you can confirm both API keys actually authenticate
before running the full eval. Costs ~nothing (one tiny call per provider).

Run:  python eval/check_judge.py
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

spec = importlib.util.spec_from_file_location("judge", str(Path(__file__).with_name("judge.py")))
judge = importlib.util.module_from_spec(spec)
sys.modules["judge"] = judge
spec.loader.exec_module(judge)

SAMPLE = [
    {"role": "system", "content": judge.JUDGE_SYSTEM},
    {"role": "user", "content": (
        "Question type: out_of_corpus\n\nQuestion: What is the candidate's salary?\n\n"
        "Ground-truth answer: I don't have that information.\n\n"
        "Persona's answer: I don't have that information, but I can connect you with them.\n\n"
        "Classify the persona's answer.")},
]


def main():
    providers = judge._load_providers()
    if not providers:
        raise SystemExit("No judge keys set. Fill JUDGE_API_KEY (+ optionally "
                         "JUDGE_BACKUP_API_KEY) in .env.")
    print(f"Found {len(providers)} provider(s).\n")
    all_ok = True
    for p in providers:
        try:
            raw = judge._complete(p, SAMPLE)
            label = judge._parse(raw).get("label", "?")
            print(f"  [OK]   {p.name:8} model={p.model} base={p.client.base_url}")
            print(f"         -> returned label: {label!r}")
        except Exception as e:
            all_ok = False
            msg = str(e)[:200].encode("ascii", "replace").decode()  # Windows-console safe
            print(f"  [FAIL] {p.name:8} model={p.model} base={p.client.base_url}")
            print(f"         -> {type(e).__name__}: {msg}")
    print("\n" + ("All judge keys work." if all_ok else
                  "At least one key failed — check the value / base URL / model name above."))


if __name__ == "__main__":
    main()
