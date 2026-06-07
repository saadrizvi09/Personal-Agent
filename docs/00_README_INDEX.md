# AI Persona Agent — Documentation Suite

**Project:** A RAG-grounded AI persona (voice + chat) that introduces itself, answers questions about the candidate's background/skills/projects from real resume + GitHub data, stays honest under adversarial probing, and books a confirmed interview end-to-end with no human in the loop.

**Context:** Submission for the Scaler AI Engineer screening assignment.

---

## How to read these docs

Read in order. Each builds on the previous.

| # | Document | What it answers | Read if you are… |
|---|----------|-----------------|------------------|
| 01 | [PRD](01_PRD.md) | *What* are we building and *why*. Scope, users, success criteria. | Anyone, start here |
| 02 | [SRS](02_SRS.md) | The exact functional + non-functional requirements, testable. | Building or grading |
| 03 | [Technical Spec](03_TECHNICAL_SPEC.md) | *How* it works: components, data flow, prompts, guardrails, APIs. | Implementing |
| 04 | [Architecture](04_ARCHITECTURE.md) | System diagrams, component responsibilities, deployment. | Implementing / repo diagram |
| 05 | [Eval Plan](05_EVAL_PLAN.md) | How we measure quality (30% of the grade). Methodology + metrics. | Building the eval harness |
| 06 | [Build Runbook](06_BUILD_RUNBOOK.md) | Step-by-step execution order with checkpoints. | Actually doing it |
| 07 | [Repo README template](07_REPO_README_TEMPLATE.md) | The public-facing README the assignment requires. | Final packaging |

---

## The one-paragraph summary

We build on **Retell** (single platform, ~600 ms voice latency, native barge-in, voice **and** chat agents driven by **one** knowledge base, embeddable web widget, native Cal.com + custom functions). The knowledge base is a cleaned Markdown corpus built from the candidate's **resume + all GitHub READMEs + commit history** — the commit history is the differentiator, since the assignment says it will ask things that exist only there. Booking runs through **Cal.com API v2** (check slots → verify → create booking). A telephone number is provisioned as a **US Twilio number through Retell** (Indian DID requires DLT/regulatory registration and is too slow for this task). A standalone **eval harness** measures latency, transcription accuracy, hallucination rate (LLM-judge + golden Q&A), retrieval precision/recall, and booking success, and produces the required 1-page PDF.

## What wins this assignment (read before building)

The platform makes a *working* agent easy; everyone capable will have one. Differentiation comes from three things, in priority order:

1. **Corpus engineering** — ingesting commit history, not just READMEs. Answers questions competitors' agents can't.
2. **Eval rigour** — a real measurement harness, not vibes. This is a full 30% and the easiest place to stand out.
3. **Honesty under pressure** — deliberate guardrail design + documented prompt-injection tests.

UI polish is explicitly **not** graded. Do not spend time there.

---

## Conventions in these docs

- `{{PLACEHOLDER}}` = fill in your real value before shipping (name, GitHub handle, Cal.com slug, etc.).
- "MUST / SHOULD / MAY" follow RFC 2119 meaning in the SRS.
- All cost figures are 2026 list prices; verify at build time.

## Known assignment ambiguity to resolve

The requirements **table** says Loom walkthrough ≤ 4 min; the **submission form** says ≤ 3 min. Build to **≤ 3 min** to satisfy both.
