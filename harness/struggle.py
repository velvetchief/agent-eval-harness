"""Layer 3: struggle detection — is the agent flailing, not just failing?

Pattern I first built for production small-business agents at KiloByte: retry
caps tell you a tool errored N times; they don't tell you the agent is stuck
in a loop, burning turns, or thrashing between tools. These heuristics read
the SHAPE of a transcript. A case can pass its checks and still get flagged —
that flag is tomorrow's incident, caught today.
"""

from __future__ import annotations

import json


def detect_struggle(transcript: dict) -> dict:
    calls = transcript["tool_calls"]
    flags: list[str] = []

    # Identical call repeated: same tool, same arguments. One repeat can be a
    # sensible retry; two identical repeats means the agent isn't updating on
    # the result it already has.
    seen: dict[str, int] = {}
    for call in calls:
        key = f"{call['name']}::{json.dumps(call['input'], sort_keys=True)}"
        seen[key] = seen.get(key, 0) + 1
    for key, count in seen.items():
        if count >= 3:
            flags.append(f"identical call x{count}: {key.split('::')[0]}")

    # Consecutive error streak: errors are fine, not adapting to them isn't.
    streak = best_streak = 0
    for call in calls:
        streak = streak + 1 if call["is_error"] else 0
        best_streak = max(best_streak, streak)
    if best_streak >= 2:
        flags.append(f"tool error streak of {best_streak}")

    # Turn burn: high turn count relative to work actually completed.
    if transcript["turns"] >= 6 and len(calls) <= transcript["turns"] // 2:
        flags.append(f"{transcript['turns']} turns for {len(calls)} tool calls")

    if transcript["hit_turn_limit"]:
        flags.append("hit turn limit")

    return {
        "case_id": transcript["case_id"],
        "struggling": bool(flags),
        "flags": flags,
    }
