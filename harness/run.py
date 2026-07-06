"""Entrypoint: python -m harness.run [--stage run|judge|report|all] [--limit N]"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def load_cases(limit: int | None) -> list[dict]:
    cases = [json.loads(l) for l in (ROOT / "golden" / "cases.jsonl").read_text().splitlines() if l.strip()]
    return cases[:limit] if limit else cases


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(exist_ok=True)
    path.write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n")


def stage_run(limit: int | None) -> None:
    import anthropic

    from .agent import run_case

    client = anthropic.Anthropic()
    transcripts = []
    for i, case in enumerate(load_cases(limit), 1):
        print(f"[{i:>2}] running {case['id']} ...", flush=True)
        transcripts.append(run_case(case, client))
    write_jsonl(ROOT / "transcripts" / "index.jsonl", transcripts)
    print(f"wrote {len(transcripts)} transcripts -> transcripts/index.jsonl")


def stage_judge(limit: int | None) -> None:
    import anthropic

    from .agreement import load_jsonl
    from .judge import judge_case
    from .metrics import check_case
    from .struggle import detect_struggle

    client = anthropic.Anthropic()
    cases = {c["id"]: c for c in load_cases(limit)}
    transcripts = [t for t in load_jsonl(ROOT / "transcripts" / "index.jsonl") if t["case_id"] in cases]
    checks, judgments, struggles = [], [], []
    for i, transcript in enumerate(transcripts, 1):
        case = cases[transcript["case_id"]]
        checks.append(check_case(case, transcript))
        struggles.append(detect_struggle(transcript))
        print(f"[{i:>2}] judging {case['id']} ...", flush=True)
        judgments.append(judge_case(case, transcript, client))
    write_jsonl(ROOT / "results" / "checks.jsonl", checks)
    write_jsonl(ROOT / "results" / "judgments.jsonl", judgments)
    write_jsonl(ROOT / "results" / "struggle.jsonl", struggles)
    print("wrote results/checks.jsonl, results/judgments.jsonl, results/struggle.jsonl")


def stage_report() -> None:
    from .report import write_report

    out = write_report()
    print(f"wrote {out}")
    print(out.read_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="Three-layer eval harness for a tool-calling agent.")
    parser.add_argument("--stage", choices=["run", "judge", "report", "all"], default="all")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N cases (smoke test).")
    args = parser.parse_args()

    if args.stage in ("run", "all"):
        stage_run(args.limit)
    if args.stage in ("judge", "all"):
        stage_judge(args.limit)
    if args.stage in ("report", "all"):
        stage_report()


if __name__ == "__main__":
    sys.exit(main())
