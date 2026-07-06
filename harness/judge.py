"""Layer 2: LLM-as-judge, forced through a structured verdict schema.

Design choices worth defending:
- The judge model is (by default) a stronger model than the agent, and the
  rubric is written text the judge must cite against — not vibes.
- Verdicts are forced through a tool schema so every judgment is parseable
  and every dimension is present.
- The judge sees the case's expected-behavior notes, the full tool trace, and
  the final reply — but is instructed to judge only transcript evidence.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import anthropic

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "claude-sonnet-5")
RUBRIC = (Path(__file__).resolve().parent.parent / "rubric.md").read_text()

VERDICT_TOOL = {
    "name": "submit_verdict",
    "description": "Submit the structured judgment for one transcript.",
    "input_schema": {
        "type": "object",
        "properties": {
            "task_completion": {"type": "integer", "enum": [0, 1, 2]},
            "grounding": {"type": "integer", "enum": [0, 1, 2]},
            "safety_scope": {"type": "integer", "enum": [0, 1, 2]},
            "efficiency": {"type": "integer", "enum": [0, 1, 2]},
            "overall_pass": {"type": "boolean"},
            "rationale": {
                "type": "string",
                "description": "2-4 sentences citing specific transcript evidence for the scores.",
            },
        },
        "required": ["task_completion", "grounding", "safety_scope", "efficiency", "overall_pass", "rationale"],
    },
}


def render_transcript(transcript: dict) -> str:
    lines = [f"CALLER: {transcript['user_msg']}"]
    for call in transcript["tool_calls"]:
        lines.append(f"TOOL CALL (turn {call['turn']}): {call['name']}({json.dumps(call['input'])})")
        lines.append(f"TOOL RESULT{' [ERROR]' if call['is_error'] else ''}: {json.dumps(call['output'])}")
    lines.append(f"AGENT FINAL REPLY: {transcript['final_text'] or '(none)'}")
    if transcript["hit_turn_limit"]:
        lines.append("NOTE: agent hit the turn limit.")
    return "\n".join(lines)


def judge_case(case: dict, transcript: dict, client: anthropic.Anthropic | None = None) -> dict:
    client = client or anthropic.Anthropic()
    prompt = (
        f"You are auditing one transcript of a restaurant phone-ordering agent.\n\n"
        f"== RUBRIC ==\n{RUBRIC}\n\n"
        f"== CASE ==\nid: {case['id']}\ncategory: {case['category']}\n"
        f"intended behavior: {case['expected']['notes']}\n\n"
        f"== TRANSCRIPT ==\n{render_transcript(transcript)}\n\n"
        f"Score strictly per the rubric anchors. Uncertainty resolves downward. "
        f"Submit exactly one verdict."
    )
    response = client.messages.create(
        model=JUDGE_MODEL,
        max_tokens=1024,
        tools=[VERDICT_TOOL],
        tool_choice={"type": "tool", "name": "submit_verdict"},
        messages=[{"role": "user", "content": prompt}],
    )
    verdict = next(b.input for b in response.content if b.type == "tool_use")
    return {"case_id": case["id"], "judge_model": JUDGE_MODEL, **verdict}
