# AI Persona Agent — {{CANDIDATE_NAME}}

A RAG-grounded AI persona you can **call** or **chat with**. It answers questions about my background, skills, and projects from my real resume and GitHub repos, stays honest under adversarial probing, and **books a confirmed interview end-to-end with no human in the loop**.

Built for the Scaler AI Engineer screening assignment.

> **Live surfaces**
> - 📞 Voice: `{{PHONE_NUMBER}}`
> - 💬 Chat: `{{PUBLIC_CHAT_URL}}`
> - 📄 Eval report: `eval/report.pdf`

---

## What it does
- **Voice + chat over one knowledge base** — same persona, same facts, two channels.
- **Grounded in real data** — resume + all public repo READMEs + **commit history**. No hardcoded answers; if it doesn't know, it says so.
- **Books interviews** — checks my real calendar (Cal.com), proposes open slots, confirms a booking, sends an invite — autonomously.
- **Honest under pressure** — resists prompt injection and false-premise questions; stays in character.

## Architecture

> One brain, two frontends. Voice and chat are thin frontends over a shared knowledge base, shared system prompt, and shared booking functions.

![Architecture](docs/architecture.png)

```
Resume + repos (READMEs + commit history) → cleaned Markdown corpus
        ↓
   Retell Knowledge Base (streaming RAG)
     ↓                         ↓
 Voice Agent (US number)   Chat Agent (public widget)
     └──── shared functions: get_available_slots / book_meeting ────┘
                         ↓
                  Cal.com API v2 → confirmed booking + invite
```

| Layer | Tech | Why |
|-------|------|-----|
| Voice + chat + RAG | Retell | ~600 ms latency, native barge-in, voice+chat on one KB |
| Telephony | US number via Twilio | Instant provisioning |
| Scheduling | Cal.com API v2 | Agent-friendly, free tier, native integration |
| Corpus | Markdown (resume + READMEs + commits) | Answers questions that exist only in commit history |
| Evals | Python harness (judge model + golden Q&A) | Reproducible measurement |

## Setup

### Prerequisites
- Retell account + API key
- Cal.com account + API key, one event type configured
- GitHub access to extract corpus
- Python 3.11+ for the corpus + eval scripts

### 1. Build the corpus
```bash
cp .env.example .env   # fill in GITHUB_TOKEN, etc.
python corpus/build_corpus.py --handle {{GITHUB_HANDLE}} --resume resume.pdf
# → outputs corpus/*.md (resume + per-repo with commit digests)
```

### 2. Configure Retell
- Create a Knowledge Base; upload `corpus/*.md`.
- Create Voice + Chat agents on that KB using `prompts/system_prompt.md`.
- Provision a US number; embed the chat widget (see `web/`).

### 3. Configure Cal.com
- Create an `interview` event type.
- Wire `get_available_slots` and `book_meeting` (config in `booking/`).

### 4. Run evals
```bash
python eval/run_chat_evals.py
python eval/run_voice_evals.py
python eval/judge.py && python eval/retrieval_eval.py
python eval/metrics.py && python eval/make_report.py   # → eval/report.pdf
```

> **Secrets:** all keys live in `.env` (gitignored). Never commit credentials. See `.env.example`.

## Cost breakdown

Built on free tiers / trial credits. The only unavoidable spend is the inbound phone number.

| Item | Free coverage | Rate after free | Per unit |
|------|---------------|-----------------|----------|
| Voice (Retell) | $10 free credits | ~$0.07–0.13 / min | **Per call (~4 min): ≈ ${{CALL_COST}}** |
| Chat (Retell) | covered by same credits | ~$0.002 / message | **Per chat session (~12 msgs): ≈ ${{CHAT_COST}}** |
| LLM | Gemini Flash Lite (~$0.003/min) / free-tier for chat+judge | — | folded into voice min |
| Cal.com | free tier | — | $0 |
| Chat-widget hosting | Vercel/Netlify free tier | — | $0 |
| **Phone number** | **none (trial numbers can't take unannounced calls)** | ~$1–2/mo + per-min | flat |

**Total real spend** for build + test + 7-day live window: **≈ ${{TOTAL_SPEND}}** (~$2–5; almost entirely the phone number — compute/chat covered by Retell's free credit).

## Evaluation summary
See `eval/report.pdf` for full results. Headline (N stated in report):

| Metric | Result |
|--------|--------|
| Voice first-response latency (p50 / p95) | {{LAT_P50}} / {{LAT_P95}} |
| Transcription accuracy (WER) | {{WER}} |
| Booking success rate | {{BOOKING_SUCCESS}} |
| Hallucination rate (golden Q&A + judge) | {{HALLUCINATION}} |
| Retrieval precision@k / recall@k | {{PRECISION}} / {{RECALL}} |
| Prompt-injection resistance | {{INJECTION_PASS}} |

## Repo layout
```
corpus/      # extraction + chunking scripts
prompts/     # shared system prompt + guardrails
booking/     # Cal.com function definitions
web/         # minimal page embedding the chat widget
eval/        # golden set, harness, judge, report generator
docs/        # PRD, SRS, spec, architecture, eval plan, runbook
```

## Notes
- UI is intentionally minimal — the assignment does not grade UI polish.
- Telephony uses a US number by design; an Indian DID requires DLT/regulatory registration (3–7 business days), which the timeline doesn't allow.
