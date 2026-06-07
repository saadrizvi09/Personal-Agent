# Eval harness

Reproducible measurement for Part C. The harness *existing* is itself evidence of
eval rigour — but the numbers must be real and measured, with N stated.

## Order of operations

```bash
# 0. Build the corpus first (produces corpus/chunks.jsonl used by retrieval eval)
python corpus/build_corpus.py --handle <you> --resume resume.txt

# 1. Author the golden set: copy the template and fill 30–50 real Q&A
cp eval/golden_qa.example.jsonl eval/golden_qa.jsonl   # then edit

# 2. Chat groundedness — run golden + adversarial questions against the live agent
python eval/run_chat_evals.py            # --mode manual if you collect by hand
python eval/judge.py                      # LLM-judge → hallucination rate

# 3. Retrieval precision/recall on your own corpus
python eval/retrieval_eval.py

# 4. Voice quality — place N test calls, log them, then aggregate
#    (create eval/results/voice_calls.jsonl per run_voice_evals.py's schema)
python eval/run_voice_evals.py

# 5. Aggregate + generate the 1-page PDF
python eval/metrics.py
python eval/make_report.py                # → eval/report.pdf
```

## What each metric means

| Metric | Script | How it's measured |
|---|---|---|
| First-response latency p50/p95 | `run_voice_evals.py` | caller-stops-speaking → first agent audio, across N calls |
| Transcription accuracy (WER) | `run_voice_evals.py` | `jiwer` WER of scripted utterance vs Retell transcript |
| Booking success rate | `run_voice_evals.py` | confirmed bookings / valid attempts |
| Barge-in pass rate | `run_voice_evals.py` | interruptions handled without crash |
| Hallucination rate | `judge.py` | LLM-judge labels each answer grounded/refused/fabricated |
| Refusal correctness | `metrics.py` | on out-of-corpus Qs, did it correctly refuse? |
| Retrieval precision@k / recall@k | `retrieval_eval.py` | top-k retrieved vs gold source chunk |
| Injection resistance | `metrics.py` | adversarial battery pass rate |

## Making the hallucination number credible

The judge is a model, so don't take it on faith. **Manually label ~20%** of the
`judged.jsonl` rows yourself and report judge–human agreement in the PDF. A judge
you spot-checked is defensible; one you didn't isn't. Use a **different model
family** than the production Retell agent to avoid self-grading bias.

`judge.py` is provider-agnostic (OpenAI-compatible) — set `JUDGE_API_KEY`,
`JUDGE_BASE_URL`, `JUDGE_MODEL`. Free options: **Groq** (`llama-3.3-70b-versatile`)
or **Gemini** (`gemini-2.0-flash`); paid: OpenAI `gpt-4o-mini` (~cents total). See
`.env.example` for the exact base-URL presets.

## Files

```
golden_qa.example.jsonl   template — copy to golden_qa.jsonl and fill
adversarial.jsonl         injection / false-premise / pressure battery (ready to use)
run_chat_evals.py         drives the live Retell chat agent (api or manual mode)
judge.py                  LLM-judge → grounded/refused/fabricated
retrieval_eval.py         precision@k / recall@k over corpus/chunks.jsonl
run_voice_evals.py        aggregates your logged test calls → latency/WER/booking
metrics.py                merges everything → results/metrics.json
make_report.py            results/metrics.json + report_narrative.json → report.pdf
results/                  all run artifacts (gitignored)
```
