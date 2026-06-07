"""
Markdown-aware recursive chunking for the knowledge base.

Spec (Technical Spec §3.3):
  - recursive ~512-token chunks, ~15% overlap
  - split on headings → paragraphs → sentences
  - each chunk must stand alone (carry its heading path so a chunk retrieved
    without its neighbours still makes sense)

Token counting uses a lightweight word→token heuristic (≈1.33 tokens/word) so
the pipeline has no heavy tokenizer dependency. Retell re-chunks on its side at
ingestion anyway; this chunking is what the *offline retrieval eval* scores
against, so it only needs to be consistent and sane, not byte-identical to
Retell's internal splitter.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

TARGET_TOKENS = 512
OVERLAP_RATIO = 0.15
WORDS_PER_TOKEN = 0.75  # ~1.33 tokens per word


@dataclass
class Chunk:
    id: str
    source: str          # logical source file, e.g. "repo-foo.md" or "resume.md"
    heading_path: str    # "Repo foo > Commit history"
    text: str

    def to_dict(self) -> dict:
        return {"id": self.id, "source": self.source,
                "heading_path": self.heading_path, "text": self.text}


def est_tokens(text: str) -> int:
    words = len(text.split())
    return int(round(words / WORDS_PER_TOKEN)) if words else 0


def _split_sentences(text: str) -> list[str]:
    # naive but adequate: split on sentence-ending punctuation followed by space
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p for p in parts if p]


def _split_paragraphs(text: str) -> list[str]:
    return [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]


def _sections(markdown: str) -> list[tuple[str, str]]:
    """Split markdown into (heading_path, body) sections on # / ## / ### lines."""
    lines = markdown.splitlines()
    sections: list[tuple[str, str]] = []
    stack: list[tuple[int, str]] = []  # (level, title)
    buf: list[str] = []

    def flush():
        if buf and any(s.strip() for s in buf):
            path = " > ".join(t for _, t in stack) or "(intro)"
            sections.append((path, "\n".join(buf).strip()))

    for line in lines:
        m = re.match(r"^(#{1,4})\s+(.*)$", line)
        if m:
            flush()
            buf = []
            level = len(m.group(1))
            title = m.group(2).strip()
            stack = [(lv, t) for lv, t in stack if lv < level]
            stack.append((level, title))
        else:
            buf.append(line)
    flush()
    return sections


def chunk_markdown(markdown: str, source: str) -> list[Chunk]:
    """Chunk one markdown document into self-contained ~512-token chunks."""
    chunks: list[Chunk] = []
    overlap_tokens = int(TARGET_TOKENS * OVERLAP_RATIO)
    idx = 0

    for heading_path, body in _sections(markdown):
        # Build units = paragraphs; oversized paragraphs break into sentences.
        units: list[str] = []
        for para in _split_paragraphs(body):
            if est_tokens(para) <= TARGET_TOKENS:
                units.append(para)
            else:
                units.extend(_split_sentences(para))

        current: list[str] = []
        current_tokens = 0

        def emit(parts: list[str]):
            nonlocal idx
            text = "\n\n".join(parts).strip()
            if not text:
                return
            # Prepend heading path so the chunk stands alone.
            standalone = f"[{heading_path}]\n{text}"
            chunks.append(Chunk(
                id=f"{source}#{idx:04d}",
                source=source,
                heading_path=heading_path,
                text=standalone,
            ))
            idx += 1

        for unit in units:
            ut = est_tokens(unit)
            if current and current_tokens + ut > TARGET_TOKENS:
                emit(current)
                # carry overlap: keep tail units summing to ~overlap_tokens
                carry, ctok = [], 0
                for u in reversed(current):
                    t = est_tokens(u)
                    if ctok + t > overlap_tokens:
                        break
                    carry.insert(0, u)
                    ctok += t
                current = carry + [unit]
                current_tokens = ctok + ut
            else:
                current.append(unit)
                current_tokens += ut
        if current:
            emit(current)

    return chunks


def chunk_documents(docs: dict[str, str]) -> list[Chunk]:
    """docs: {source_filename: markdown}. Returns all chunks across docs."""
    out: list[Chunk] = []
    for source, md in docs.items():
        out.extend(chunk_markdown(md, source))
    return out
