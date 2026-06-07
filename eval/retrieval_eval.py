"""
Retrieval precision@k / recall@k / hit-rate / MRR on YOUR corpus.

This scores the **actual production retriever** — the same hybrid (dense Mistral
embeddings + BM25) used by the live chat backend (web/api/index.py) — against
the corpus it serves (corpus/chunks.jsonl). So the numbers reflect what a grader
actually experiences, not a weaker stand-in.

Method:
  - Build the production index: precomputed Mistral chunk embeddings
    (web/api/embeddings.json) + a BM25 index over the same chunks, using the
    same tokenizer (separator-stripped, so 'gitbot' ~ 'git-bot').
  - Embed each in-corpus golden question with Mistral (same model as live).
  - Score = 0.65 * norm(dense cosine) + 0.35 * norm(BM25)  — identical to live.
  - For each question take top-k and compare to its gold chunk id(s).

Metrics:
  - hit_rate@k / MRR : answerability — did the answering chunk reach top-k, and
    how high. These are the meaningful headline numbers when a question has a
    single gold chunk (precision@k is then capped at 1/k by construction).
  - precision@k / recall@k : reported too, with that cap noted.

Fallbacks (so it still runs anywhere): if the Mistral key or embeddings.json is
absent, it falls back to sentence-transformers, then TF-IDF (dense-only).

Out-of-corpus questions (source == null) are skipped — they're scored by the
judge (refusal correctness), not by retrieval.

Inputs : corpus/chunks.jsonl, web/api/embeddings.json, eval/golden_qa.jsonl
Output : eval/results/retrieval_summary.json, retrieval_per_question.json
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

RESULTS = Path("eval/results")
K = int(os.getenv("RETRIEVAL_K", "5"))
EMB_PATH = Path("web/api/embeddings.json")


def load_chunks(path="corpus/chunks.jsonl") -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"missing {path} — run corpus/build_corpus.py first.")
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def load_golden(path="eval/golden_qa.jsonl") -> list[dict]:
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"missing {path} — copy golden_qa.example.jsonl and fill it.")
    rows = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if "_README" in row:
            continue
        rows.append(row)
    return rows


def _tok(s: str) -> list[str]:
    """Same tokenizer as the production backend: also emit a separator-stripped
    form so name variants match ('git-bot' ~ 'gitbot')."""
    s = s.lower()
    toks = re.findall(r"[a-z0-9]+", s)
    toks += re.findall(r"[a-z0-9]+", re.sub(r"[-_./]+", "", s))
    return toks


def _norm01(a: np.ndarray) -> np.ndarray:
    a = a - a.min()
    m = a.max()
    return a / m if m > 0 else a


def _l2norm(m: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(m, axis=1, keepdims=True)
    n[n == 0] = 1.0
    return m / n


def _mistral_index(chunks):
    """Production index: aligned Mistral chunk matrix + an embed(query) fn.
    Returns (chunk_matrix, embed_fn, model) or None if unavailable."""
    if not EMB_PATH.exists():
        return None
    key = os.getenv("MISTRAL_API_KEY")
    if not key:
        return None
    try:
        from openai import OpenAI
    except Exception:
        return None
    emb = json.loads(EMB_PATH.read_text(encoding="utf-8"))
    model = emb.get("model", "mistral-embed")
    dims = emb["dims"]
    by_id = {e["id"]: e["vec"] for e in emb["emb"]}
    mat = np.array([by_id.get(c["id"], [0.0] * dims) for c in chunks], dtype=np.float32)
    mat = _l2norm(mat)
    client = OpenAI(api_key=key, base_url="https://api.mistral.ai/v1", max_retries=2, timeout=30)

    def embed(texts: list[str]) -> np.ndarray:
        out = []
        for i in range(0, len(texts), 32):
            r = client.embeddings.create(model=model, input=texts[i:i + 32])
            out.extend(d.embedding for d in r.data)
        v = np.array(out, dtype=np.float32)
        return _l2norm(v)

    return mat, embed, f"mistral:{model}+bm25 (production hybrid)"


def _fallback_index(chunk_texts, questions):
    """Dense-only fallback: sentence-transformers, else TF-IDF."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        allv = model.encode(chunk_texts + questions, normalize_embeddings=True,
                            show_progress_bar=False)
        allv = np.asarray(allv, dtype=np.float32)
        return allv[:len(chunk_texts)], allv[len(chunk_texts):], "sentence-transformers/all-MiniLM-L6-v2 (dense-only)"
    except Exception:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(stop_words="english")
        mat = _l2norm(vec.fit_transform(chunk_texts + questions).toarray().astype(np.float32))
        return mat[:len(chunk_texts)], mat[len(chunk_texts):], "tfidf (dense-only)"


def main():
    chunks = load_chunks()
    golden = [g for g in load_golden() if g.get("source")]  # in-corpus only
    if not golden:
        raise SystemExit("No in-corpus golden questions with a 'source' field.")

    chunk_ids = [c["id"] for c in chunks]
    chunk_texts = [c["text"] for c in chunks]
    questions = [g["question"] for g in golden]

    def golds_for(g) -> list[str]:
        s = g.get("source")
        return s if isinstance(s, list) else [s]

    # Production hybrid (dense Mistral + BM25), or dense-only fallback.
    prod = _mistral_index(chunks)
    bm25 = None
    if prod is not None:
        chunk_mat, embed_fn, backend = prod
        q_mat = embed_fn(questions)
        try:
            from rank_bm25 import BM25Okapi
            bm25 = BM25Okapi([_tok(t) for t in chunk_texts])
        except Exception:
            backend += " [bm25 unavailable -> dense-only]"
    else:
        chunk_mat, q_mat, backend = _fallback_index(chunk_texts, questions)

    def scores_for(i: int) -> np.ndarray:
        dense = chunk_mat @ q_mat[i]
        if bm25 is not None:
            bm = np.array(bm25.get_scores(_tok(questions[i])), dtype=np.float32)
            return 0.65 * _norm01(dense) + 0.35 * _norm01(bm)
        return dense

    precisions, recalls, hits, rr = [], [], 0, []
    per_q = []
    for i, g in enumerate(golden):
        sims = scores_for(i)
        ranked = list(np.argsort(-sims))
        topk_idx = ranked[:K]
        retrieved = [chunk_ids[j] for j in topk_idx]
        gold = set(golds_for(g))
        inter = gold & set(retrieved)
        precisions.append(len(inter) / K)
        recalls.append(len(inter) / len(gold))
        hit = len(inter) > 0
        hits += int(hit)
        # reciprocal rank of the first gold chunk anywhere in the ranking
        rank = next((r + 1 for r, j in enumerate(ranked) if chunk_ids[j] in gold), 0)
        rr.append(1.0 / rank if rank else 0.0)
        per_q.append({"id": g["id"], "gold": sorted(gold), "hit": hit,
                      "first_gold_rank": rank, "top_k": retrieved})

    summary = {
        "k": K,
        "n_questions": len(golden),
        "retriever": backend,
        "hit_rate_at_k": round(hits / len(golden), 4),
        "mrr": round(float(np.mean(rr)), 4),
        "recall_at_k": round(float(np.mean(recalls)), 4),
        "precision_at_k": round(float(np.mean(precisions)), 4),
        "notes": "hit_rate@k & MRR are the headline answerability metrics; "
                 "precision@k is capped at 1/k because most questions have a single gold chunk.",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval_summary.json").write_text(json.dumps(summary, indent=2))
    (RESULTS / "retrieval_per_question.json").write_text(json.dumps(per_q, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
