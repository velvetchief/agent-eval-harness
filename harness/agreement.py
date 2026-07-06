"""Judge calibration: does the LLM judge agree with a human?

An LLM judge you haven't checked against human labels is an unvalidated
instrument. This computes raw agreement and Cohen's kappa between the judge's
overall_pass and hand-labeled verdicts on a subset of cases. Ten labels is a
smoke test, not a validation study — the README is explicit about that — but
it reliably catches a judge that is systematically lenient.
"""

from __future__ import annotations

import json
from pathlib import Path


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def cohens_kappa(pairs: list[tuple[bool, bool]]) -> float:
    n = len(pairs)
    if n == 0:
        return float("nan")
    observed = sum(1 for a, b in pairs if a == b) / n
    judge_yes = sum(1 for a, _ in pairs if a) / n
    human_yes = sum(1 for _, b in pairs if b) / n
    expected = judge_yes * human_yes + (1 - judge_yes) * (1 - human_yes)
    if expected == 1:
        return 1.0
    return round((observed - expected) / (1 - expected), 3)


def compute_agreement(judgments_path: Path, labels_path: Path) -> dict:
    if not labels_path.exists():
        return {
            "status": "no_labels",
            "note": (
                "golden/human_labels.jsonl not found. Hand-label at least 10 "
                "cases (copy the template, watch the transcripts, decide "
                "pass/fail yourself) and re-run. Until then the judge is "
                "an unvalidated instrument."
            ),
        }
    judgments = {j["case_id"]: j for j in load_jsonl(judgments_path)}
    labels = [l for l in load_jsonl(labels_path) if l.get("human_pass") is not None]
    pairs, disagreements = [], []
    for label in labels:
        judgment = judgments.get(label["case_id"])
        if not judgment:
            continue
        pairs.append((judgment["overall_pass"], label["human_pass"]))
        if judgment["overall_pass"] != label["human_pass"]:
            disagreements.append(
                {
                    "case_id": label["case_id"],
                    "judge": judgment["overall_pass"],
                    "human": label["human_pass"],
                    "human_note": label.get("note", ""),
                    "judge_rationale": judgment["rationale"],
                }
            )
    if not pairs:
        return {"status": "no_overlap", "note": "No labeled cases matched judged cases."}
    return {
        "status": "ok",
        "n_labeled": len(pairs),
        "raw_agreement": round(sum(1 for a, b in pairs if a == b) / len(pairs), 3),
        "cohens_kappa": cohens_kappa(pairs),
        "disagreements": disagreements,
    }
