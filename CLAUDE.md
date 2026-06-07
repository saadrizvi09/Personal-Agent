# CLAUDE.md — AI Persona Agent

Guidance for AI coding agents (and humans) working in this repo.

## What this is
A RAG-grounded AI persona (voice + chat) for the Scaler AI Engineer screening
assignment. It introduces itself, answers grounded questions about the candidate
from their real resume + GitHub repos, stays honest under adversarial probing,
and books a confirmed interview end-to-end with no human in the loop.

Full design docs are in `docs/` (read `docs/00_README_INDEX.md` first). The PRD,
SRS, technical spec, architecture, eval plan, and build runbook there are the
source of truth for *intent*.

## Architecture in one line
**One brain, two frontends.** Chat (Part B) is a **custom free RAG stack** —
`web/api/index.py` (FastAPI on Vercel): BM25 retrieval over the corpus + Gemini
2.5 Flash → Groq Llama-3.3-70B fallback + booking tool-calls; served at a Vercel
URL via `web/index.html`. Voice (Part A) is **Retell** (US number, managed
STT/LLM/TTS, barge-in) over a Retell KB. Both share the same corpus, the same
persona/system prompt, and the same **booking backend** (`booking/`, FastAPI on
Vercel → Cal.com API v2). Corpus + eval harness are offline Python.

History note: chat was originally built on Retell too, but moved to the custom
free stack to avoid per-message credit burn (reliability: stays live the full
7-day window) and to own the RAG. Retell's KB/agent for chat may still exist but
is no longer the live surface.

## Component map
| Path | What | Notes |
|------|------|-------|
| `corpus/` | Builds the KB corpus from GitHub (READMEs + **commit history**) + resume | `build_corpus.py` is the entrypoint; outputs `corpus/*.md` + `chunks.jsonl` |
| `booking/` | FastAPI booking service (Cal.com v2), deployed to Vercel; called by chat backend + Retell voice functions | `main.py` app, `calcom.py` client, `api/index.py` Vercel entry; verify-then-book |
| `web/` | **Custom chat (Part B):** `index.html` UI + `api/index.py` FastAPI backend (BM25 + Gemini→Groq + booking tools) + `api/chunks.jsonl` corpus | live at the Vercel URL; $0/unmetered |
| `prompts/` | Shared system prompt + Retell **voice** function defs | `system_prompt.md` is config, NOT code. The chat backend embeds its own copy of the same persona rules in `web/api/index.py` (keep them in sync) |
| `eval/` | Golden set, adversarial battery, judge, retrieval P/R, PDF report | the 30%-weighted differentiator |
| `docs/` | PRD/SRS/spec/architecture/eval-plan/runbook | intent + rationale |

## Hard rules (do not violate)
- **No hardcoded answers.** All persona facts come from the Retell Knowledge Base
  (RAG) over the real corpus. The only inline facts allowed are the tiny
  high-frequency "Known facts" block in `prompts/system_prompt.md` (name, focus,
  top skills, one-line why-fit) — kept inline purely to skip retrieval latency.
  Never paste resume/repo content into prompts.
- **No secrets in git.** Everything sensitive is in `.env` (gitignored). The repo
  ships `.env.example` only. The booking backend rejects requests lacking
  `BOOKING_WEBHOOK_SECRET`.
- **Honesty is the product.** The persona must refuse out-of-corpus questions and
  resist injection rather than fabricate. Changes that make it more "helpful" by
  guessing are regressions.
- **Commit history is the differentiator.** The corpus ingests commit digests, not
  just READMEs — graders may ask commit-only questions. Don't drop that.

## Conventions
- Python 3.11+. Stdlib + the deps in `requirements.txt`. Keep deps light.
- Eval judge (`eval/judge.py`) is provider-agnostic via the OpenAI-compatible
  chat API — works with OpenAI / Groq / Gemini by swapping `JUDGE_BASE_URL` +
  `JUDGE_API_KEY` + `JUDGE_MODEL`. Uses JSON-mode for the grounded/refused/
  fabricated verdict. Tiny usage; free tiers (Groq/Gemini) cost nothing. Use a
  different model family than the Retell agent to avoid self-grading bias.
- Cal.com v2 pins API versions per endpoint via the `cal-api-version` header
  (`CAL_API_VERSION_SLOTS` / `CAL_API_VERSION_BOOKINGS`) — they revise these
  independently, so keep them configurable.
- Retell chat/widget snippets and field names drift between versions. If the live
  dashboard gives a different embed snippet or chat path than what's in
  `web/index.html` / `eval/run_chat_evals.py`, prefer the dashboard's — adjust the
  code to match, don't fight it.

## What's code vs. what's dashboard
A lot of "the build" is Retell dashboard configuration (KB upload, agent creation,
number provisioning, function wiring) — that's done by a human in Retell, not in
this repo. This repo is everything that *is* code: corpus pipeline, booking
backend, eval harness, prompts/config, and the chat page. Don't try to provision
Retell/Twilio/Cal.com from code unless explicitly asked.

## Running things
```bash
pip install -r requirements.txt
python corpus/build_corpus.py --handle <handle> --resume resume.txt
uvicorn booking.main:app --reload --port 8000
python eval/run_chat_evals.py && python eval/judge.py && python eval/retrieval_eval.py
python eval/metrics.py && python eval/make_report.py
```

## Submission checklist (assignment)
Name/email · live voice number · public chat URL · this repo (README + diagram +
setup + cost) · 1-page eval PDF · Loom ≤ 3 min · honest build-time estimate.
Keep all surfaces live ≥ 7 days; they call/chat unannounced.
