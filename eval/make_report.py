"""
Generate the 1-page eval PDF the assignment requires (Part C).

Reads eval/results/metrics.json + a hand-written narrative file
(eval/report_narrative.json) for the parts a script can't measure:
  - 3 failure modes (symptom → root cause → fix)
  - the one tradeoff you made + why
  - 2-week roadmap
  - header links (phone number, chat URL, repo)

Run:  python eval/make_report.py
Out:  eval/report.pdf

A starter eval/report_narrative.json is created on first run if missing — edit it
with your REAL discovered failure modes and links before submitting.
"""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer, Table,
                                TableStyle)
from xml.sax.saxutils import escape as _xml_escape


def esc(x) -> str:
    """Escape dynamic text so ReportLab doesn't parse <...>/& as markup.
    We add our own <b>/markup around escaped values, never inside them."""
    return _xml_escape(str(x if x is not None else ""))


RESULTS = Path("eval/results")
NARRATIVE = Path("eval/report_narrative.json")

NARRATIVE_TEMPLATE = {
    "candidate": "{{CANDIDATE_NAME}}",
    "date": "{{DATE}}",
    "links": {
        "phone": "{{PHONE_NUMBER}}",
        "chat_url": "{{PUBLIC_CHAT_URL}}",
        "repo": "{{GITHUB_REPO_URL}}",
    },
    "failure_modes": [
        {"symptom": "<what you observed>", "root_cause": "<why>", "fix": "<what you changed>"},
        {"symptom": "<...>", "root_cause": "<...>", "fix": "<...>"},
        {"symptom": "<...>", "root_cause": "<...>", "fix": "<...>"},
    ],
    "tradeoff": "<the one tradeoff you consciously made (e.g. smaller top-k for "
                "lower hallucination, accepting rare recall misses) and why>",
    "two_week_roadmap": [
        "<bullet 1>", "<bullet 2>", "<bullet 3>", "<bullet 4>",
    ],
    "cost": {
        "per_call": "<$ measured>",
        "per_chat_session": "<$ measured>",
        "total_spend": "<$ measured for build + tests + 7-day window>",
    },
}


def _fmt(v, suffix=""):
    return f"{v}{suffix}" if v is not None else "—"


def main():
    metrics_path = RESULTS / "metrics.json"
    metrics = json.loads(metrics_path.read_text(encoding="utf-8")) if metrics_path.exists() else {}
    if not NARRATIVE.exists():
        NARRATIVE.write_text(json.dumps(NARRATIVE_TEMPLATE, indent=2), encoding="utf-8")
        print(f"Created {NARRATIVE} — fill it in with real failure modes/links, then re-run.")

    nar = json.loads(NARRATIVE.read_text(encoding="utf-8"))

    styles = getSampleStyleSheet()
    h = ParagraphStyle("h", parent=styles["Heading2"], spaceBefore=6, spaceAfter=3,
                       textColor=colors.HexColor("#1a3c6e"), fontSize=11)
    small = ParagraphStyle("s", parent=styles["Normal"], fontSize=8, leading=10)
    body = ParagraphStyle("b", parent=styles["Normal"], fontSize=8.5, leading=11)

    doc = SimpleDocTemplate(str(Path("eval/report.pdf")), pagesize=letter,
                            topMargin=0.5 * inch, bottomMargin=0.4 * inch,
                            leftMargin=0.6 * inch, rightMargin=0.6 * inch)
    el = []

    # Header
    el.append(Paragraph(f"<b>AI Persona Agent — Eval Report</b> · {esc(nar.get('candidate',''))}",
                        ParagraphStyle("t", parent=styles["Title"], fontSize=15)))
    links = nar.get("links", {})
    el.append(Paragraph(
        f"{esc(nar.get('date',''))} &nbsp;|&nbsp; Voice: {esc(links.get('phone',''))} "
        f"&nbsp;|&nbsp; Chat: {esc(links.get('chat_url',''))} "
        f"&nbsp;|&nbsp; Repo: {esc(links.get('repo',''))}",
        small))
    el.append(Spacer(1, 6))

    # Voice quality
    v = metrics.get("voice") or {}
    el.append(Paragraph("Voice quality", h))
    vt = [["Metric", "Result"],
          ["First-response latency p50 / p95",
           f"{_fmt(v.get('latency_ms_p50'),' ms')} / {_fmt(v.get('latency_ms_p95'),' ms')}"],
          ["Transcription accuracy (WER)", _fmt(v.get("wer_mean"))],
          ["Booking success rate",
           f"{_fmt(v.get('booking_success_rate'))} (N={_fmt(v.get('booking_attempts'))})"],
          ["Barge-in pass rate", _fmt(v.get("barge_in_pass_rate"))],
          ["N test calls", _fmt(v.get("n_calls"))]]
    el.append(_table(vt))

    # Chat groundedness + retrieval
    g = metrics.get("chat_groundedness") or {}
    r = metrics.get("retrieval") or {}
    rc = metrics.get("refusal_correctness") or {}
    inj = metrics.get("injection_resistance") or {}
    el.append(Paragraph("Chat groundedness &amp; retrieval", h))
    jb = g.get("judged_by") or {}
    if jb:
        name_map = {"primary": g.get("primary_model", "primary"),
                    "backup": g.get("backup_model", "backup")}
        judge_desc = ", ".join(f"{name_map.get(k, k)}×{v}" for k, v in jb.items() if k != "none" and v)
    else:
        judge_desc = g.get("primary_model", g.get("judge_model", ""))
    gt = [["Metric", "Result", "Method / N"],
          ["Hallucination rate", _fmt(g.get("hallucination_rate")),
           f"LLM-judge ({judge_desc}), N={_fmt(g.get('n'))}"],
          ["Grounded / refused / fabricated",
           f"{_fmt(g.get('grounded'))} / {_fmt(g.get('refused'))} / {_fmt(g.get('fabricated'))}", ""],
          [f"Retrieval hit-rate@{r.get('k','k')} / MRR / recall@{r.get('k','k')}",
           f"{_fmt(r.get('hit_rate_at_k'))} / {_fmt(r.get('mrr'))} / {_fmt(r.get('recall_at_k'))}",
           f"{r.get('retriever', r.get('embedding_backend',''))}, N={_fmt(r.get('n_questions'))}"],
          ["Refusal correctness (out-of-corpus)", _fmt(rc.get("refusal_correctness")),
           f"N={_fmt(rc.get('n_out_of_corpus'))}"],
          ["Prompt-injection resistance", _fmt(inj.get("pass_rate")),
           f"battery N={_fmt(inj.get('n_adversarial'))}"]]
    el.append(_table(gt, [2.2 * inch, 2.0 * inch, 2.6 * inch]))

    # Failure modes
    el.append(Paragraph("3 failure modes discovered", h))
    for i, fm in enumerate(nar.get("failure_modes", [])[:3], 1):
        el.append(Paragraph(
            f"<b>{i}.</b> <b>Symptom:</b> {esc(fm.get('symptom',''))} "
            f"<b>Root cause:</b> {esc(fm.get('root_cause',''))} "
            f"<b>Fix:</b> {esc(fm.get('fix',''))}", body))

    # Tradeoff + roadmap + cost
    el.append(Paragraph("Tradeoff made", h))
    el.append(Paragraph(esc(nar.get("tradeoff", "")), body))

    el.append(Paragraph("What I'd build with 2 more weeks", h))
    for b in nar.get("two_week_roadmap", []):
        el.append(Paragraph(f"• {esc(b)}", body))

    cost = nar.get("cost", {})
    el.append(Paragraph("Cost", h))
    el.append(Paragraph(
        f"Per call: {esc(cost.get('per_call','—'))} &nbsp;·&nbsp; "
        f"Per chat session: {esc(cost.get('per_chat_session','—'))} &nbsp;·&nbsp; "
        f"Total spend: {esc(cost.get('total_spend','—'))}", body))

    doc.build(el)
    print("[ok] wrote eval/report.pdf")


def _table(data, widths=None):
    t = Table(data, colWidths=widths or [3.2 * inch, 3.6 * inch])
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#c9d3e0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f2f5fa")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]))
    return t


if __name__ == "__main__":
    main()
