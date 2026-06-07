"""
LLM-judge for chat groundedness (hallucination rate).

For each (question, agent_answer, gold_answer, type) it asks a judge model to
label the agent's answer as:
  grounded  — supported by the gold answer / correctly answered
  refused   — correctly said "I don't know" / declined (right on out-of-corpus)
  fabricated — asserted something not supported (a hallucination)

Hallucination rate = fabricated / total. For out-of-corpus questions the correct
behaviour is "refused"; a confident wrong answer there is "fabricated".

PROVIDER-AGNOSTIC with automatic fallback. Both judges use the OpenAI-compatible
chat API, so the same code drives Groq, z.ai, OpenAI, Gemini, etc. Configure a
PRIMARY judge and an optional BACKUP judge; if the primary errors (e.g. Groq's
free rate limit), each call falls through to the backup automatically.

  PRIMARY (Groq, free):
    JUDGE_API_KEY=gsk_...
    JUDGE_BASE_URL=https://api.groq.com/openai/v1
    JUDGE_MODEL=llama-3.3-70b-versatile
  BACKUP (z.ai, paid):
    JUDGE_BACKUP_API_KEY=...
    JUDGE_BACKUP_BASE_URL=https://api.z.ai/api/paas/v4/
    JUDGE_BACKUP_MODEL=glm-4.6

Tip: use a judge from a DIFFERENT model family than your production Retell agent
to avoid self-grading bias. Manually spot-check ~20% of labels and report
agreement in the PDF so the number is credible.

Input : eval/results/chat_results.jsonl  (from run_chat_evals.py)
Output: eval/results/judged.jsonl + judge_summary.json
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from dataclasses import dataclass
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from openai import OpenAI

RESULTS = Path("eval/results")
VALID = {"grounded", "refused", "fabricated"}

JUDGE_SYSTEM = (
    "You evaluate an AI persona's groundedness. You are given a question, the "
    "persona's answer, a CONCISE reference answer (ground truth), and the question type.\n\n"
    "IMPORTANT: the reference answer is a short summary, NOT an exhaustive script. The "
    "persona draws on a fuller knowledge base, so it will legitimately include ADDITIONAL "
    "accurate detail and an introductory phrase like 'I represent Saad...'. Extra detail "
    "that is consistent with — or a reasonable elaboration of — the reference is GROUNDED, "
    "not fabricated. Do NOT penalise correct extra detail, a longer answer, or a preamble.\n\n"
    "Classify the persona's answer as exactly one of:\n"
    "- grounded: it answers correctly and consistently with the reference (extra consistent "
    "detail is fine). For out-of-corpus questions, correctly DENYING a false premise while "
    "citing the candidate's real, established facts (role, degree) is also 'grounded'.\n"
    "- refused: it declines / says it doesn't know / offers to connect with the candidate, "
    "without asserting unverified facts.\n"
    "- fabricated: it CONTRADICTS the reference, or invents a specific fact clearly not "
    "supported (a wrong employer/school/metric/credential), or confidently answers a "
    "genuinely unknowable out-of-corpus question with invented specifics.\n\n"
    "Only choose 'fabricated' for a genuine contradiction or invention — never merely for "
    "being more detailed than the reference.\n"
    'Respond ONLY with a JSON object: {"label": "...", "justification": "one line"}'
)


@dataclass
class Provider:
    name: str
    client: OpenAI
    model: str


def _load_providers() -> list[Provider]:
    """Primary first, backup second. Either may be omitted."""
    providers: list[Provider] = []
    # max_retries makes the SDK auto-retry transient errors (429 rate-limit,
    # 503 overload, 5xx) with exponential backoff before we give up on a provider.
    retries = int(os.getenv("JUDGE_MAX_RETRIES", "4"))
    pk = (os.getenv("JUDGE_API_KEY") or os.getenv("GROQ_API_KEY")
          or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY"))
    if pk:
        providers.append(Provider(
            "primary",
            OpenAI(api_key=pk, max_retries=retries,
                   base_url=os.getenv("JUDGE_BASE_URL", "https://api.openai.com/v1")),
            os.getenv("JUDGE_MODEL", "gpt-4o-mini")))
    bk = os.getenv("JUDGE_BACKUP_API_KEY")
    if bk:
        providers.append(Provider(
            "backup",
            OpenAI(api_key=bk, max_retries=retries,
                   base_url=os.getenv("JUDGE_BACKUP_BASE_URL", "https://api.z.ai/api/paas/v4/")),
            os.getenv("JUDGE_BACKUP_MODEL", "glm-4.6")))
    return providers


def _complete(p: Provider, messages: list[dict]) -> str:
    """Call one provider. Try JSON mode; if it rejects the param, retry without it
    (the prompt already demands JSON)."""
    try:
        r = p.client.chat.completions.create(
            model=p.model, temperature=0,
            response_format={"type": "json_object"}, messages=messages)
    except Exception:
        r = p.client.chat.completions.create(
            model=p.model, temperature=0, messages=messages)
    return r.choices[0].message.content or "{}"


def _parse(raw: str) -> dict:
    """Robust JSON extraction — some models wrap JSON in prose/code fences."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", raw, re.S)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def judge_one(providers: list[Provider], row: dict) -> dict:
    messages = [
        {"role": "system", "content": JUDGE_SYSTEM},
        {"role": "user", "content": (
            f"Question type: {row.get('type', 'unknown')}\n\n"
            f"Question: {row['question']}\n\n"
            f"Ground-truth answer: {row.get('gold_answer', '(none provided)')}\n\n"
            f"Persona's answer: {row.get('agent_answer', '')}\n\n"
            "Classify the persona's answer.")},
    ]
    last_err = None
    for p in providers:
        try:
            data = _parse(_complete(p, messages))
            label = data.get("label", "")
            if label not in VALID:
                label = "fabricated"
            return {"label": label, "justification": data.get("justification", ""),
                    "judged_by": p.name}
        except Exception as e:  # rate limit, network, etc. → fall through to backup
            last_err = e
            msg = str(e)[:80].encode("ascii", "replace").decode()  # Windows-console safe
            print(f"    ({p.name} failed: {msg} — trying next)")
    return {"label": "error", "justification": f"all judges failed: {last_err}",
            "judged_by": "none"}


def main():
    # Windows consoles default to cp1252, which crashes when a model's
    # justification contains characters like U+2011 (non-breaking hyphen).
    # Make stdout tolerant so a print can never abort the run before the
    # summary/judged.jsonl are written.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    providers = _load_providers()
    if not providers:
        raise SystemExit("Set a judge key. Primary: JUDGE_API_KEY + JUDGE_BASE_URL + "
                         "JUDGE_MODEL. Optional backup: JUDGE_BACKUP_API_KEY + "
                         "JUDGE_BACKUP_BASE_URL + JUDGE_BACKUP_MODEL.")
    print("Judges:", ", ".join(f"{p.name}={p.model}" for p in providers))

    infile = RESULTS / "chat_results.jsonl"
    if not infile.exists():
        raise SystemExit(f"missing {infile} — run run_chat_evals.py first.")
    rows = [json.loads(l) for l in infile.read_text(encoding="utf-8").splitlines() if l.strip()]

    judged = []
    counts = {"grounded": 0, "refused": 0, "fabricated": 0, "error": 0}
    by_provider = {}
    delay = float(os.getenv("JUDGE_SLEEP", "3"))  # throttle free-tier judge RPM
    for i, row in enumerate(rows):
        if i:
            time.sleep(delay)
        v = judge_one(providers, row)
        counts[v["label"]] = counts.get(v["label"], 0) + 1
        by_provider[v["judged_by"]] = by_provider.get(v["judged_by"], 0) + 1
        judged.append({**row, "label": v["label"],
                       "judge_justification": v["justification"], "judged_by": v["judged_by"]})
        print(f"  [{v['label']:10}] ({v['judged_by']}) {row['id']}: {v['justification'][:70]}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    with (RESULTS / "judged.jsonl").open("w", encoding="utf-8") as f:
        for j in judged:
            f.write(json.dumps(j, ensure_ascii=False) + "\n")

    scored = counts["grounded"] + counts["refused"] + counts["fabricated"]  # exclude errors
    summary = {
        "n": len(judged),
        "scored": scored,
        "grounded": counts["grounded"],
        "refused": counts["refused"],
        "fabricated": counts["fabricated"],
        "errors": counts["error"],
        "hallucination_rate": round(counts["fabricated"] / scored, 4) if scored else None,
        "judged_by": by_provider,
        "primary_model": providers[0].model,
        "backup_model": providers[1].model if len(providers) > 1 else None,
    }
    (RESULTS / "judge_summary.json").write_text(json.dumps(summary, indent=2))
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
