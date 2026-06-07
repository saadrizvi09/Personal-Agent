"""
Retrieval precision@k / recall@k on YOUR corpus.

Replicates retrieval offline against the same chunked corpus the Retell KB is
built from (corpus/chunks.jsonl), so we can score whether the right chunk is
retrieved for each golden question.

Method:
  - Embed every corpus chunk and every (in-corpus) golden question.
  - For each question, take the top-k chunks by cosine similarity.
  - precision@k = (relevant retrieved) / k   averaged over questions
  - recall@k    = (relevant retrieved) / (relevant total) averaged over questions
    where "relevant" = the gold `source` chunk id for that question.

Embeddings: uses sentence-transformers if installed (better); otherwise falls
back to scikit-learn TF-IDF so it runs anywhere with no model download.

Out-of-corpus questions (source == null) are skipped here — they're scored by
the judge (refusal correctness), not by retrieval.

Inputs : corpus/chunks.jsonl, eval/golden_qa.jsonl
Output : eval/results/retrieval_summary.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np

RESULTS = Path("eval/results")
K = int(os.getenv("RETRIEVAL_K", "5"))


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


def _embed(texts: list[str]):
    """Return an (n, d) normalized matrix. Prefer sentence-transformers."""
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        emb = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(emb), "sentence-transformers/all-MiniLM-L6-v2"
    except Exception:
        from sklearn.feature_extraction.text import TfidfVectorizer
        vec = TfidfVectorizer(stop_words="english")
        mat = vec.fit_transform(texts).toarray().astype(np.float32)
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms, "tfidf"


def main():
    chunks = load_chunks()
    golden = [g for g in load_golden() if g.get("source")]  # in-corpus only
    if not golden:
        raise SystemExit("No in-corpus golden questions with a 'source' field.")

    chunk_ids = [c["id"] for c in chunks]
    chunk_texts = [c["text"] for c in chunks]
    questions = [g["question"] for g in golden]

    def golds_for(g) -> list[str]:
        """A question's gold chunk(s). 'source' may be a single id or a list,
        since several questions are legitimately answered by more than one chunk."""
        s = g.get("source")
        return s if isinstance(s, list) else [s]

    # Embed chunks + questions together so the vector space is shared (TF-IDF needs this).
    all_emb, backend = _embed(chunk_texts + questions)
    chunk_emb = all_emb[:len(chunk_texts)]
    q_emb = all_emb[len(chunk_texts):]

    precisions, recalls, hits = [], [], 0
    per_q = []
    for i, g in enumerate(golden):
        sims = chunk_emb @ q_emb[i]
        topk_idx = np.argsort(-sims)[:K]
        retrieved = [chunk_ids[j] for j in topk_idx]
        gold = set(golds_for(g))
        inter = gold & set(retrieved)
        # precision@k: fraction of retrieved that are gold.
        precisions.append(len(inter) / K)
        # recall@k: fraction of this question's gold chunks retrieved.
        recalls.append(len(inter) / len(gold))
        # answerability: did we retrieve at least one chunk that answers it?
        hit = len(inter) > 0
        hits += int(hit)
        per_q.append({"id": g["id"], "gold": sorted(gold),
                      "hit": hit, "top_k": retrieved})

    summary = {
        "k": K,
        "n_questions": len(golden),
        "embedding_backend": backend,
        "precision_at_k": round(float(np.mean(precisions)), 4),
        "recall_at_k": round(float(np.mean(recalls)), 4),
        "hit_rate": round(hits / len(golden), 4),
        "hit_rate_note": "fraction of questions with >=1 answering chunk in top-k (answerability)",
    }
    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "retrieval_summary.json").write_text(json.dumps(summary, indent=2))
    (RESULTS / "retrieval_per_question.json").write_text(json.dumps(per_q, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
