# 01 — Product Requirements Document (PRD)

**Product:** AI Persona Agent
**Owner:** {{CANDIDATE_NAME}}
**Status:** Approved for build
**Last updated:** {{DATE}}

---

## 1. Problem & purpose

Scaler's screening asks: build an AI persona of yourself that a recruiter can **call** and **chat with**, that answers honestly and specifically about your background, and that **books a real interview end-to-end with no human in the loop**. The implicit test: can you ship a production-grade conversational AI system under real-world constraints — latency, grounding, evaluation, and honesty under adversarial pressure.

This product is that persona. It is not a chatbot demo; it is a graded artifact that must stay live and survive unannounced probing for at least 7 days.

## 2. Goals (what success looks like)

- A caller dials a number, talks to the persona, and walks away with a **confirmed calendar booking** — no human touched it.
- A visitor opens a public URL, chats with the **same persona** over the **same knowledge**, and can also book.
- Every factual claim is **grounded** in the real resume / GitHub corpus. When the answer isn't in the corpus, the persona **says so** instead of inventing.
- The persona **holds character and stays honest** under edge cases, adversarial questions, and prompt-injection attempts.
- A 1-page eval report quantifies all of the above with real measurements.

## 3. Non-goals (explicitly out of scope)

- UI/visual polish — the assignment states it is **not evaluated**. Use the platform's default widget.
- Multi-language support, mobile apps, authentication/accounts, analytics dashboards.
- Generalised assistant capabilities beyond representing the candidate.
- An Indian phone number (regulatory cost; see SRS NFR-TEL).

## 4. Users

| User | Need | Interaction |
|------|------|-------------|
| Scaler recruiter / evaluator | Verify the candidate's fit, probe for honesty, book an interview | Phone call + public chat, unannounced |
| Candidate ({{CANDIDATE_NAME}}) | Be represented accurately; receive booked meetings on real calendar | Configures persona; owns calendar |
| Adversarial tester (also Scaler) | Break grounding, force hallucination, inject prompts | Stress the system |

## 5. Product scope — three parts (mirrors the grading rubric)

### Part A — Voice Agent (35%)
A phone number that, when called:
- Introduces itself as the candidate's AI representative and sets context naturally.
- Answers questions about background, skills, and fit for the role.
- Handles interruptions, follow-ups, and off-script conversation — no rigid Q&A trees.
- Recovers gracefully when it doesn't know something (says so; does not invent).
- Asks for the caller's availability, checks the real calendar, proposes slots, and books a confirmed meeting — no human intervention.

### Part B — Chat Interface (35%)
A public chat URL that:
- Answers "why are you the right person for this role" with a specific, evidence-backed answer.
- Discusses any public GitHub repo: tech stack, purpose, design tradeoffs, what you'd do differently.
- Answers resume questions (education, experience, projects) accurately and specifically.
- Checks availability and books a call directly from chat.
- Stays honest and grounded under edge cases, adversarial questions, and prompt injection — never hallucinates or breaks character.
- Is **RAG-grounded over the real resume + GitHub repos**. No hardcoded answers. Must handle questions whose answers live only in READMEs or commit history.

### Part C — Evals Report (30%)
A 1-page PDF covering:
- Voice quality: first-response latency, transcription accuracy, task-completion (booking success) across N test calls.
- Chat groundedness: hallucination rate + how measured (judge model / manual labelling / golden Q&A set) + retrieval precision/recall on own corpus.
- 3 failure modes discovered, root cause for each, and the fix.
- One tradeoff consciously made (cost vs latency, accuracy vs coverage, etc.) and why.
- What you'd build with 2 more weeks.

## 6. Success metrics

| Metric | Target | Why |
|--------|--------|-----|
| Voice first-response latency (p50) | < 1.2 s | Comfortably under the 2 s hard limit |
| Voice first-response latency (p95) | < 2.0 s | Hard requirement ceiling |
| Barge-in handled without crash | 100% of attempts | Hard requirement |
| Booking success rate (valid request → confirmed event) | ≥ 90% across N≥10 calls | Core task completion |
| Hallucination rate (golden Q&A) | < 5% | Honesty is graded |
| "I don't know" correctly triggered on out-of-corpus Qs | ≥ 90% | Anti-invention requirement |
| Retrieval precision@k / recall@k on golden set | report both; precision ≥ 0.8 | Eval rigour |
| Prompt-injection resistance | 0 successful jailbreaks in test battery | Honesty under pressure |
| Uptime during 7-day live window | ~100% | "Keep everything live ≥ 7 days" |

## 7. Constraints

- **Hard deadline:** all surfaces must be **live at submission** (no screenshots/videos of past runs) and stay live ≥ 7 days.
- **Latency:** voice first response < 2 s; barge-in must not crash.
- **Grounding:** persona reads real resume + GitHub; no hardcoded strings.
- **Budget:** target is a near-free build. Retell starts at $0 with **$10 free credits** (no platform fee, 10 free knowledge bases); Cal.com free tier and free static hosting cover the rest. The **only unavoidable spend is the phone number** (~$1–2/mo + a few cents/min telephony) because a reliable *inbound* PSTN number that accepts unannounced calls is never free. Realistic real spend: **$2–5**. Cost is not a constraint, but must be *reported* per call / per chat session.
- **Identity:** the corpus exposes the candidate's real resume and public repos. Confirm nothing private is in those repos before ingestion.

## 8. Key product decisions (rationale lives in Technical Spec)

| Decision | Choice | One-line reason |
|----------|--------|-----------------|
| Platform | Retell | Voice + chat on one KB, ~600 ms latency, native barge-in, Cal.com + functions |
| Telephony | US number via Retell→Twilio | Instant; Indian DID needs DLT registration (3–7 days) |
| Calendar | Cal.com API v2 | Best-documented agent API, free tier, native integration |
| Corpus | Resume + READMEs + **commit history** → Markdown KB | Commit history answers questions competitors can't |
| Evals | Standalone Python harness | Reproducible, defensible, produces the PDF |

## 9. Risks & mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Agent invents facts under pressure | Fails honesty (30% + character) | Strict system prompt + grounding guardrail + tested refusal behavior |
| Latency creeps over 2 s | Hard-requirement fail | Use Retell defaults (~600 ms); keep system prompt lean; measure before submit |
| Booking double-books or fails silently | Task-completion fail | Check-slots-before-book pattern; confirm event ID; webhook verification |
| Repo/corpus leaks something private | Reputational/privacy | Audit all 30 repos before ingest; exclude anything sensitive |
| Platform outage during 7-day window | Live-requirement fail | Monitor uptime; keep credentials/config reproducible to re-deploy fast |
| Loom length ambiguity (3 vs 4 min) | Minor | Build to ≤ 3 min |

## 10. Deliverables checklist (submission form)

- [ ] Full name and email
- [ ] Voice agent phone number (live)
- [ ] Public chat URL (live)
- [ ] Public GitHub repo (README, architecture diagram, setup, cost breakdown)
- [ ] Eval report (1-page PDF)
- [ ] Loom walkthrough link (≤ 3 min: architecture + one hard problem solved)
- [ ] Total build time (honest estimate; does not affect scoring)
