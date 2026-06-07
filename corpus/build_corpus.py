"""
Build the persona knowledge-base corpus.

Outputs (into --out, default ./corpus):
  resume.md          cleaned resume markdown
  repo-<name>.md     one per repo: purpose, tech stack, links, commit digest
  chunks.jsonl       every chunk (id, source, heading_path, text) for retrieval eval
  corpus_manifest.json   summary of what was built

Then you upload resume.md + repo-*.md to the Retell Knowledge Base. chunks.jsonl
is consumed by eval/retrieval_eval.py to measure precision/recall on YOUR corpus.

Usage:
  python corpus/build_corpus.py --handle <github_handle> --resume resume.txt
  # GITHUB_TOKEN / GITHUB_HANDLE read from environment if not passed.

No hardcoded facts: everything comes from the live GitHub API + your resume file.
"""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

from github_extract import Repo, extract, is_noise
from chunk import chunk_documents

try:
    from dotenv import load_dotenv  # optional convenience
    load_dotenv()
except Exception:
    pass


def _slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def resume_to_md(resume_path: str | None) -> str:
    """Turn a resume file into markdown. Supports .md/.txt (passthrough), .pdf,
    .docx. If no file is given, emits a clearly-marked placeholder so the build
    still runs — but you MUST supply the real resume before going live."""
    if not resume_path:
        return ("# Resume\n\n> ⚠️ No resume supplied at build time. Run again with "
                "`--resume <file>` so the persona is grounded in real data.\n")
    p = Path(resume_path)
    if not p.exists():
        raise FileNotFoundError(f"resume not found: {resume_path}")

    ext = p.suffix.lower()
    if ext in (".md", ".txt"):
        text = p.read_text(encoding="utf-8", errors="replace")
    elif ext == ".pdf":
        try:
            import pdfplumber  # lazy; only needed for PDF resumes
        except ImportError:
            raise SystemExit("PDF resume needs pdfplumber: pip install pdfplumber")
        with pdfplumber.open(str(p)) as pdf:
            text = "\n\n".join(page.extract_text() or "" for page in pdf.pages)
    elif ext == ".docx":
        try:
            import docx  # python-docx
        except ImportError:
            raise SystemExit("DOCX resume needs python-docx: pip install python-docx")
        d = docx.Document(str(p))
        text = "\n".join(par.text for par in d.paragraphs)
    else:
        raise SystemExit(f"unsupported resume type: {ext} (use .md/.txt/.pdf/.docx)")

    # If it already looks like markdown (has headings), keep as-is; else wrap.
    if re.search(r"^#{1,3}\s", text, re.M):
        return text
    return f"# Resume\n\n{text.strip()}\n"


def commit_digest(repo: Repo) -> str:
    """Chronological digest of meaningful commits (oldest→newest), bucketed by
    month under `###` sub-headings.

    The month buckets matter: commit-history questions are the differentiator,
    and the chunker (and Retell's) split on headings — so each month becomes its
    own retrievable chunk instead of one giant undifferentiated commit list,
    which makes a specific commit fact actually findable by retrieval."""
    meaningful = [c for c in repo.commits if not is_noise(c["message"])]
    meaningful = list(reversed(meaningful))  # oldest first reads as a story
    if not meaningful:
        return "_No substantive commit history beyond routine commits._"

    buckets: dict[str, list[str]] = {}
    for c in meaningful:
        date = (c.get("date") or "")[:10]
        month = date[:7] or "undated"
        buckets.setdefault(month, []).append(f"- `{date}` {c['message']}")

    parts: list[str] = []
    for month in sorted(buckets):
        parts.append(f"### Commits in {month} ({repo.name})")
        parts.append("\n".join(buckets[month]))
    return "\n\n".join(parts)


def repo_to_md(repo: Repo) -> str:
    """One markdown doc per repo: purpose, tech, links, commit digest."""
    out: list[str] = [f"# Repo: {repo.name}\n"]

    meta = []
    if repo.description:
        meta.append(f"**Purpose:** {repo.description}")
    if repo.language:
        meta.append(f"**Primary language:** {repo.language}")
    if repo.topics:
        meta.append(f"**Topics / tech:** {', '.join(repo.topics)}")
    if repo.stars:
        meta.append(f"**Stars:** {repo.stars}")
    meta.append(f"**Repository:** {repo.html_url}")
    if repo.homepage:
        meta.append(f"**Live / homepage:** {repo.homepage}")
    if repo.created_at:
        meta.append(f"**Created:** {repo.created_at[:10]} · "
                    f"**Last pushed:** {repo.pushed_at[:10]}")
    out.append("\n\n".join(meta) + "\n")

    out.append("## README\n")
    out.append(repo.readme.strip() if repo.readme.strip()
               else "_This repo has no README._")
    out.append("\n## Commit history (digest)\n")
    out.append("The meaningful commits for this repo, oldest first. "
               "Use these to answer questions about how the project evolved.\n")
    out.append(commit_digest(repo))
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser(description="Build the persona corpus.")
    ap.add_argument("--handle", default=os.getenv("GITHUB_HANDLE"),
                    help="GitHub handle (or set GITHUB_HANDLE)")
    ap.add_argument("--resume", default=None, help="path to resume .md/.txt/.pdf/.docx")
    ap.add_argument("--out", default="corpus", help="output dir")
    ap.add_argument("--include-forks", action="store_true")
    ap.add_argument("--max-commits", type=int, default=300)
    args = ap.parse_args()

    if not args.handle:
        raise SystemExit("Provide --handle or set GITHUB_HANDLE in the environment.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    docs: dict[str, str] = {}

    # 1. Resume
    print("Building resume.md …")
    resume_md = resume_to_md(args.resume)
    (out / "resume.md").write_text(resume_md, encoding="utf-8")
    docs["resume.md"] = resume_md

    # 2. Repos (READMEs + commit digests)
    print(f"Extracting repos for @{args.handle} …")
    repos = extract(args.handle, os.getenv("GITHUB_TOKEN"),
                    include_forks=args.include_forks, max_commits=args.max_commits)
    for repo in repos:
        fname = f"repo-{_slug(repo.name)}.md"
        md = repo_to_md(repo)
        (out / fname).write_text(md, encoding="utf-8")
        docs[fname] = md

    # 3. Chunk everything for the offline retrieval eval
    print("Chunking corpus …")
    chunks = chunk_documents(docs)
    with (out / "chunks.jsonl").open("w", encoding="utf-8") as f:
        for c in chunks:
            f.write(json.dumps(c.to_dict(), ensure_ascii=False) + "\n")

    # 4. Manifest
    manifest = {
        "handle": args.handle,
        "files": sorted(docs.keys()),
        "repo_count": len(repos),
        "chunk_count": len(chunks),
        "repos": [
            {"name": r.name, "commits_ingested": len(r.commits),
             "readme_chars": len(r.readme)} for r in repos
        ],
    }
    (out / "corpus_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"\n[ok] Corpus built in {out}/")
    print(f"  {len(docs)} markdown files | {len(chunks)} chunks | "
          f"{len(repos)} repos")
    print("  Next: upload resume.md + repo-*.md to your Retell Knowledge Base.")
    print("  Sanity-check: open 10 random chunks — does each make sense alone?")


if __name__ == "__main__":
    main()
