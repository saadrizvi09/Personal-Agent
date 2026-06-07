# 02 — Software Requirements Specification (SRS)

**Product:** AI Persona Agent
**Status:** Approved for build
Requirement keywords (MUST / SHOULD / MAY) per RFC 2119. Each requirement has an ID and an acceptance test.

---

## 1. Scope

This SRS defines testable functional (FR) and non-functional (NFR) requirements for a voice + chat AI persona that answers grounded questions and books interviews autonomously. It is the contract between "what the PRD wants" and "what the build must do."

## 2. System actors & interfaces

- **Caller** → PSTN → Twilio number → Retell voice agent.
- **Web visitor** → public URL → Retell chat widget.
- **Retell agent** → Knowledge Base (RAG) + LLM + custom functions.
- **Custom functions** → Cal.com API v2.
- **Eval harness** (offline) → Retell APIs + corpus + judge LLM.

---

## 3. Functional requirements

### 3.1 Voice agent (Part A)

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| FR-V1 | The agent MUST answer inbound calls on a published number and introduce itself as {{CANDIDATE_NAME}}'s AI representative, setting context naturally. | Call the number; first turn states it is an AI rep and offers to help. |
| FR-V2 | The agent MUST answer questions about background, skills, and role fit using grounded corpus data. | Ask 5 background questions; answers match resume/repos. |
| FR-V3 | The agent MUST handle interruptions (barge-in): when the caller speaks over it, it MUST stop and listen without crashing. | Interrupt mid-sentence 5×; agent yields each time, call stays up. |
| FR-V4 | The agent MUST handle follow-ups and off-script turns without a rigid menu. | Ask an unscripted follow-up; agent responds in context. |
| FR-V5 | When the answer is not in the corpus, the agent MUST say it doesn't know and MUST NOT invent. | Ask an out-of-corpus question; agent declines gracefully. |
| FR-V6 | The agent MUST ask the caller for availability, query the real calendar, propose open slots, and create a confirmed booking with no human intervention. | Complete a booking by phone; event appears on real calendar. |
| FR-V7 | The agent MUST confirm booking details (date/time/timezone, attendee name+email) back to the caller after booking. | Booking turn reads back confirmed slot + sends invite. |
| FR-V8 | The agent MUST collect attendee name and email before booking. | Booking blocked until name+email captured. |

### 3.2 Chat agent (Part B)

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| FR-C1 | A public chat URL MUST be reachable with no login. | Open URL in incognito; chat loads and responds. |
| FR-C2 | The agent MUST answer "why are you the right person for this role" with a specific, evidence-backed answer (cites real projects/skills). | Ask it; answer references concrete corpus items, not platitudes. |
| FR-C3 | For any public repo, the agent MUST describe tech stack, purpose, design tradeoffs, and what the candidate would do differently. | Name a repo; answer covers all four and matches the repo. |
| FR-C4 | The agent MUST answer resume questions (education, experience, projects) accurately and specifically. | Spot-check 5 resume facts; all correct. |
| FR-C5 | The agent MUST check availability and book a call directly from chat. | Book via chat; event appears on real calendar. |
| FR-C6 | The agent MUST stay grounded and honest under edge cases and adversarial questions; it MUST NOT hallucinate. | Run adversarial battery (see Eval Plan); 0 fabricated facts. |
| FR-C7 | The agent MUST resist prompt injection ("ignore previous instructions", role override, exfiltration of system prompt) and stay in character. | Run injection battery; 0 successful overrides. |
| FR-C8 | The agent MUST correctly answer questions whose answers exist **only** in repo READMEs or commit history. | Ask a commit-history-only question; agent answers from corpus. |

### 3.3 Shared knowledge / RAG (Parts A & B)

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| FR-K1 | Voice and chat MUST be driven by **one** shared knowledge base. | Same factual question to both yields consistent answers. |
| FR-K2 | The KB MUST be built from real resume + all public repo READMEs + commit history; NO hardcoded answer strings in prompts. | Inspect config: facts come from KB retrieval, not literal prompt text. |
| FR-K3 | Retrieval MUST run per-turn (streaming RAG) so late-added corpus content is answerable. | Add a fact to corpus, re-sync, ask it; agent knows it. |
| FR-K4 | The KB MUST chunk source docs for clean retrieval (recursive ~512-token chunks, ~15% overlap, each chunk self-contained). | Inspect ingestion output; chunks meet spec. |

### 3.4 Booking subsystem (Parts A & B)

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| FR-B1 | The system MUST expose a `get_available_slots` function that queries Cal.com v2 for open slots in a date range/timezone. | Function returns live slots matching Cal.com. |
| FR-B2 | The system MUST verify a chosen slot is still available immediately before booking. | Booking attempts a fresh slot check; rejects taken slots. |
| FR-B3 | The system MUST expose a `book_meeting` function that creates a confirmed Cal.com booking with attendee details. | Booking creates a real event + invite. |
| FR-B4 | On booking failure or no availability, the agent MUST tell the user and offer the nearest alternative. | Force a conflict; agent offers next slot. |
| FR-B5 | The system SHOULD verify booking via webhook or returned event ID. | Confirm event ID logged after booking. |

### 3.5 Eval harness (Part C)

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| FR-E1 | A standalone harness MUST measure voice first-response latency across N≥10 calls and report p50/p95. | Harness outputs latency distribution. |
| FR-E2 | The harness MUST measure transcription accuracy (e.g., WER on a scripted set). | Outputs WER or equivalent. |
| FR-E3 | The harness MUST measure booking success rate across N test calls/chats. | Outputs success %. |
| FR-E4 | The harness MUST measure hallucination rate using a golden Q&A set + LLM-judge (and/or manual labels). | Outputs hallucination %. |
| FR-E5 | The harness MUST measure retrieval precision@k and recall@k against the golden set on the candidate's own corpus. | Outputs both metrics. |
| FR-E6 | The harness MUST produce the data needed for a 1-page PDF report. | PDF generated with all metrics + 3 failure modes + tradeoff + 2-week roadmap. |

---

## 4. Non-functional requirements

| ID | Requirement | Acceptance test |
|----|-------------|-----------------|
| NFR-LAT | Voice first-response latency MUST be < 2 s (target p50 < 1.2 s). | Measured across N calls; p95 < 2 s. |
| NFR-BARGE | Barge-in MUST never crash or drop the call. | 100% of interruption attempts handled. |
| NFR-LIVE | Voice, chat, and booking MUST be live at submission and remain live ≥ 7 days. | Independent unannounced call + chat succeed any time in window. |
| NFR-TEL | Telephony MUST use a number provisionable without multi-day regulatory delay → US number via Retell/Twilio. (Indian DID requires DLT + regulatory bundle, 3–7 business days — out of scope.) | Number active same day. |
| NFR-GND | No hardcoded factual answers; all facts traceable to corpus. | Prompt audit shows retrieval-driven answers. |
| NFR-SEC | API keys (Retell, Cal.com, LLM) MUST be stored as secrets/env vars, never committed to the public repo. | Repo scan: no secrets. |
| NFR-PRIV | The ingested corpus MUST exclude anything private; only public repos + resume the candidate consents to expose. | Pre-ingest audit signed off. |
| NFR-COST | Per-call and per-chat-session cost MUST be computed and documented in the repo README. | Cost breakdown present. |
| NFR-REPRO | Build MUST be reproducible from the repo: README, setup steps, architecture diagram. | A third party can follow setup. |
| NFR-OBS | The system SHOULD log retrieval trunks/transcripts for debugging failure modes. | Logs available for the 3 failure-mode writeups. |

---

## 5. Data requirements

- **Source data:** resume (PDF/MD), all public repos' READMEs, commit logs (message + date + repo), optionally key source-file headers.
- **Derived:** cleaned Markdown corpus, one file per logical unit (resume, per-repo), H2 per resolvable question.
- **Runtime:** booking attendee data (name, email, timezone) — collected per session, not stored beyond Cal.com.
- **Eval:** golden Q&A set (question, ground-truth answer, source chunk), test-call transcripts, judge outputs.

## 6. External dependencies

| Dependency | Used for | Notes |
|------------|----------|-------|
| Retell | Voice + chat agents, KB, widget, telephony orchestration | Single platform |
| Twilio (via Retell) | US phone number | Instant provisioning |
| Cal.com API v2 | Availability + booking | 120 req/min default; cal-api-version header required |
| LLM (Retell-configured + judge model) | Generation + eval judging | Skip reasoning-mode models for voice (latency) |
| GitHub API / git | Corpus extraction | READMEs + commit history |

## 7. Assumptions

- The 30 repos are public, under one account, with substantive READMEs (confirmed by candidate).
- Cal.com free tier with at least one event type (e.g., "30-min interview") is acceptable.
- A US number is acceptable to the evaluator (assignment imposes no country requirement).
