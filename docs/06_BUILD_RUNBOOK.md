# 06 — Build Runbook

**Product:** AI Persona Agent
Execution order with checkpoints. Do these in sequence; each gate must pass before moving on. Rough effort estimates assume focused work.

---

## Phase 0 — Prep & audit (≈1 hr)
- [ ] Confirm GitHub handle; list all public repos. Confirm count and that all are under one account.
- [ ] **Audit every repo for private/sensitive content** before ingestion (keys, client data, anything you don't want a recruiter reading). Exclude as needed.
- [ ] Locate current resume (PDF or Markdown). Confirm it's safe to expose publicly.
- [ ] Create accounts: Retell (starts at $0 with **$10 free credits** — no card needed to start), Cal.com (free tier). Add a card only for the ~$2 phone number when you reach Phase 4. Pick cheap components (e.g. Gemini Flash Lite ~$0.003/min) to stretch the credit.
- **Gate:** clean list of repos + resume, nothing private.

## Phase 1 — Corpus build (≈2–3 hrs) ← biggest differentiator
- [ ] Extract all READMEs.
- [ ] Extract **commit history** per repo (message + date), summarize into a per-repo commit digest (filter merge/chore noise).
- [ ] Parse resume → `resume.md` (education, experience, projects, skills).
- [ ] Produce one `repo-<name>.md` per repo: purpose, tech stack, design decisions, commit digest.
- [ ] Chunk: recursive ~512 tokens, ~15% overlap, headings-first, each chunk self-contained (no dangling "see above").
- [ ] Sanity pass: read 10 random chunks — does each make sense alone?
- **Gate:** corpus folder of clean Markdown, commit history included.

## Phase 2 — Knowledge base + chat agent (≈2 hrs)
- [ ] Create Retell Knowledge Base; upload corpus.
- [ ] Write the shared system prompt (persona + grounding + honesty/injection + booking) from Technical Spec §4.
- [ ] Put 5–8 hottest facts directly in the prompt (name, focus, top skills, why-fit).
- [ ] Create Chat Agent on the KB.
- [ ] Test in console: ask resume Qs, repo Qs, a commit-history-only Q, and an out-of-corpus Q (must refuse).
- **Gate:** chat agent answers grounded, refuses cleanly, knows a commit-only fact.

## Phase 3 — Booking (≈2 hrs)
- [ ] Cal.com: create event type (e.g. `interview`, 30 min); get API key + slug; set `cal-api-version`.
- [ ] Wire `get_available_slots` + `book_meeting` (native Cal.com integration or custom functions).
- [ ] Implement the safe pattern: ask details → get slots → **verify slot free** → book → confirm read-back.
- [ ] Test: book from chat; confirm real event + invite; force a conflict → agent offers alternative.
- **Gate:** a real booking lands on your calendar from chat.

## Phase 4 — Voice agent (≈2–3 hrs)
- [ ] Create Voice Agent on the **same** KB + same prompt + same functions.
- [ ] Provision a **US number** via Retell/Twilio.
- [ ] Tune for voice: short responses, non-reasoning model, pre-speech pause, rely on turn-taking model for barge-in.
- [ ] Test calls: intro, background Qs, **interrupt mid-sentence** (must yield, no crash), out-of-corpus Q (refuse), full booking by phone.
- [ ] Measure first-response latency on a few calls — confirm well under 2 s.
- **Gate:** phone booking works end-to-end; barge-in stable; latency < 2 s.

## Phase 5 — Public chat URL (≈30 min)
- [ ] Embed the Retell chat widget on a minimal static page; deploy (any free host).
- [ ] Open in incognito — loads, responds, books. (No login, no polish needed.)
- **Gate:** public URL works for a stranger.

## Phase 6 — Guardrail hardening (≈1–2 hrs)
- [ ] Run the adversarial battery (false premise, injection, role override, pressure) on both voice + chat.
- [ ] Fix any fabrication or override; re-test.
- **Gate:** 0 fabrications, 0 successful injections.

## Phase 7 — Eval harness + report (≈3–4 hrs) ← second differentiator
- [ ] Build golden Q&A set (30–50, incl. out-of-corpus + commit-only).
- [ ] Run chat + voice evals; collect latency, WER, booking success, transcripts.
- [ ] Run judge model for hallucination; manually verify ~20%.
- [ ] Compute retrieval precision/recall.
- [ ] Identify the **3 real failure modes** observed; write root cause + fix.
- [ ] Pick **one tradeoff** + justify; draft **2-week roadmap**.
- [ ] Generate the 1-page PDF.
- **Gate:** PDF complete with real, N-stated numbers.

## Phase 8 — Repo + diagram + cost (≈2 hrs)
- [ ] Public GitHub repo: corpus scripts + eval harness + `07_REPO_README` content.
- [ ] Architecture diagram (from doc 04).
- [ ] Setup instructions; `.env.example`; **no secrets committed**.
- [ ] Cost breakdown per call / per chat session (measured).
- **Gate:** a stranger could follow the README.

## Phase 9 — Loom + submit (≈1 hr)
- [ ] Record Loom **≤ 3 min** (table says 4, form says 3 — use 3): architecture + the one hard problem you solved (e.g., latency tuning or grounding under injection).
- [ ] Final live check: call the number + open the chat URL fresh.
- [ ] Fill the submission form: name/email, number, chat URL, repo, PDF, Loom, honest build-time estimate.
- **Gate:** everything live; submitted.

## Phase 10 — Keep alive (7+ days)
- [ ] Leave all surfaces live; spot-check daily. They will call/chat unannounced.

---

## Critical "don't get burned" list
- **No Indian number** — DLT/regulatory delay will sink your timeline. US number.
- **No hardcoded answers** — they will ask commit-history questions to catch this.
- **No secrets in the repo.**
- **Re-verify live status** on submission day and through the window.
- **Real numbers in the eval** — a small honest N beats inflated claims; graders test honesty.
- **Loom ≤ 3 min.**

## Total rough estimate
~18–24 hours of focused work. Report your **honest** total build time on the form (it doesn't affect scoring).
