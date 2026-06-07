"""
Precompute dense embeddings for the corpus chunks (semantic retrieval).

Embeds every chunk with Mistral's embedding model and writes
web/api/embeddings.json, which the chat backend loads for hybrid
(dense + BM25) retrieval — robust to phrasing and name variants
(e.g. "gitbot" ~ "git-bot"), like a production KB.

Run after every corpus rebuild:  python corpus/embed_corpus.py
"""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

from openai import OpenAI

KEY = os.getenv("MISTRAL_API_KEY")
MODEL = "mistral-embed"
BATCH = 32
SLEEP = 1.3  # throttle the free embedding tier


def main():
    if not KEY:
        raise SystemExit("Set MISTRAL_API_KEY.")
    chunks = [json.loads(l) for l in Path("corpus/chunks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    client = OpenAI(api_key=KEY, base_url="https://api.mistral.ai/v1")

    out = []
    for i in range(0, len(chunks), BATCH):
        batch = chunks[i:i + BATCH]
        for attempt in range(4):
            try:
                r = client.embeddings.create(model=MODEL, input=[c["text"] for c in batch])
                break
            except Exception as e:
                if attempt == 3:
                    raise
                print(f"  retry {i} ({str(e)[:60]})"); time.sleep(8)
        for c, e in zip(batch, r.data):
            out.append({"id": c["id"], "vec": e.embedding})
        print(f"  embedded {i + len(batch)}/{len(chunks)}")
        time.sleep(SLEEP)

    dims = len(out[0]["vec"]) if out else 0
    Path("web/api").mkdir(parents=True, exist_ok=True)
    Path("web/api/embeddings.json").write_text(
        json.dumps({"model": MODEL, "dims": dims, "emb": out}), encoding="utf-8")
    print(f"[ok] wrote web/api/embeddings.json — {len(out)} chunks, {dims} dims")


if __name__ == "__main__":
    main()
