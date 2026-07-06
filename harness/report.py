"""Aggregate everything into results/REPORT.md — the one-page read."""

from __future__ import annotations

import json
import statistics
from pathlib import Path

from .agreement import compute_agreement, load_jsonl

ROOT = Path(__file__).resolve().parent.parent


def build_report() -> str:
    checks = load_jsonl(ROOT / "results" / "checks.jsonl")
    judgments = {j["case_id"]: j for j in load_jsonl(ROOT / "results" / "judgments.jsonl")}
    struggles = {s["case_id"]: s for s in load_jsonl(ROOT / "results" / "struggle.jsonl")}
    cases = {c["id"]: c for c in load_jsonl(ROOT / "golden" / "cases.jsonl")}
    agreement = compute_agreement(ROOT / "results" / "judgments.jsonl", ROOT / "golden" / "human_labels.jsonl")

    n = len(checks)
    det_pass = sum(1 for c in checks if c["deterministic_pass"])
    judge_pass = sum(1 for c in checks if judgments.get(c["case_id"], {}).get("overall_pass"))
    flagged = [s for s in struggles.values() if s["struggling"]]
    latencies = sorted(c["latency_s"] for c in checks)
    total_tool_calls = sum(c["tool_calls"] for c in checks)
    total_tool_errors = sum(c["tool_errors"] for c in checks)

    def dim_mean(dim: str) -> str:
        vals = [judgments[c["case_id"]][dim] for c in checks if c["case_id"] in judgments]
        return f"{statistics.mean(vals):.2f}" if vals else "—"

    lines = [
        "# Eval Report",
        "",
        f"Agent: `{load_jsonl(ROOT / 'transcripts' / 'index.jsonl')[0]['agent_model']}` · "
        f"Judge: `{next(iter(judgments.values()))['judge_model'] if judgments else '—'}` · "
        f"{n} golden cases",
        "",
        "## Aggregates",
        "",
        "| Metric | Value |",
        "|---|---|",
        f"| Deterministic pass rate (layer 1) | **{det_pass}/{n}** |",
        f"| Judge pass rate (layer 2) | **{judge_pass}/{n}** |",
        f"| task_completion / grounding / safety_scope / efficiency (mean) | {dim_mean('task_completion')} / {dim_mean('grounding')} / {dim_mean('safety_scope')} / {dim_mean('efficiency')} |",
        f"| Tool error rate | {total_tool_errors}/{total_tool_calls} calls |",
        f"| Struggle flags (layer 3) | {len(flagged)}/{n} cases |",
        f"| Latency p50 / max | {latencies[n // 2]:.1f}s / {latencies[-1]:.1f}s |",
        f"| Total tokens | {sum(c['tokens'] for c in checks):,} |",
        "",
    ]

    if agreement["status"] == "ok":
        lines += [
            "## Judge ↔ human agreement",
            "",
            f"Raw agreement **{agreement['raw_agreement']}** · Cohen's kappa **{agreement['cohens_kappa']}** "
            f"on {agreement['n_labeled']} hand-labeled cases.",
            "",
        ]
        if agreement["disagreements"]:
            lines.append("Disagreements (the most informative rows in this file):")
            lines.append("")
            for d in agreement["disagreements"]:
                lines.append(
                    f"- `{d['case_id']}` — judge said **{'pass' if d['judge'] else 'fail'}**, "
                    f"human said **{'pass' if d['human'] else 'fail'}**. Human: {d['human_note']} "
                    f"Judge: {d['judge_rationale']}"
                )
            lines.append("")
    else:
        lines += ["## Judge ↔ human agreement", "", f"⚠ {agreement['note']}", ""]

    lines += [
        "## Per-case results",
        "",
        "| Case | Category | Layer 1 (det) | Layer 2 (judge) | Layer 3 (struggle) | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for check in checks:
        cid = check["case_id"]
        judgment = judgments.get(cid, {})
        struggle = struggles.get(cid, {})
        notes = "; ".join(check["failures"]) or ""
        if struggle.get("flags"):
            notes = (notes + " · " if notes else "") + "; ".join(struggle["flags"])
        if judgment and not judgment.get("overall_pass"):
            notes = (notes + " · " if notes else "") + judgment["rationale"][:160]
        lines.append(
            f"| {cid} | {cases[cid]['category']} "
            f"| {'✅' if check['deterministic_pass'] else '❌'} "
            f"| {'✅' if judgment.get('overall_pass') else ('❌' if judgment else '—')} "
            f"| {'⚠' if struggle.get('struggling') else 'ok'} "
            f"| {notes} |"
        )
    return "\n".join(lines) + "\n"


def write_report() -> Path:
    out = ROOT / "results" / "REPORT.md"
    out.write_text(build_report())
    return out
