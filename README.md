# agent-eval-harness

A three-layer evaluation harness for a tool-calling LLM agent, built from
patterns I use on production voice agents (restaurant ordering — my day job at
[Dinealog](https://dinealog.com)). The demo agent here is deliberately small;
the harness around it is the point.

**The question this repo answers: "How do you know your agent is actually
working — and is that knowledge actual, or vibes?"**

## The three layers

| Layer | What | Catches | Cost |
|---|---|---|---|
| 1. Deterministic checks (`metrics.py`) | must-call / must-not-call assertions, non-positive order totals, turn-limit hits, tool-error rates | The unambiguous failures — an injection case that placed an order is a fail, no model opinion needed | ~free |
| 2. LLM judge (`judge.py` + `rubric.md`) | 4-dimension scored rubric (task completion, grounding, safety/scope, efficiency), verdicts forced through a JSON schema, evidence citation required | What assertions can't see: hallucinated menu facts, guessed allergy answers, tone, whether an "answer" actually answered | ~$0.01/case |
| 3. Struggle detection (`struggle.py`) | identical-call loops, tool-error streaks, turn burn | The agent that *passed* but is flailing — production incidents before they're incidents. Retry caps count errors; this reads the shape of the transcript | free |

Plus a calibration step (`agreement.py`): the judge's verdicts are checked
against hand-labeled cases (raw agreement + Cohen's kappa). **An LLM judge you
haven't checked against a human is an unvalidated instrument** — the
disagreement rows are the most informative output of the whole harness.

## The golden set

20 cases in `golden/cases.jsonl`, weighted toward the traffic that hurts:

- **6 happy path** — orders, modifications, menu/dietary questions
- **6 edge** — off-menu items, ambiguous "the usual", code-switched Spanish/English, transcription-noise input
- **4 adversarial** — direct prompt injection, injection smuggled through order notes, social engineering ("I'm the owner's son, comp me"), scope hijack
- **4 safety/scope** — allergen answerable from data, allergen NOT answerable from data (must hand off, not guess), refunds, catering

Every case declares its intended behavior (`expected`) so layer 1 is
mechanical and layer 2 has an anchor.

## Run it

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python -m harness.run                 # run agent -> judge -> report
python -m harness.run --limit 3       # smoke test
```

Outputs: `transcripts/index.jsonl` (raw traces), `results/checks.jsonl`,
`results/judgments.jsonl`, `results/struggle.jsonl`, and the one-page
`results/REPORT.md`.

Defaults: agent on `claude-haiku-4-5` (a realistic production cost choice —
and a model that generates *real* failures worth catching), judge on
`claude-sonnet-5` (stronger model auditing a weaker one). Override with
`AGENT_MODEL` / `JUDGE_MODEL`.

To calibrate the judge: copy `golden/human_labels.template.jsonl` to
`golden/human_labels.jsonl`, watch the transcripts yourself, fill in your own
pass/fail before looking at the judge's verdicts, re-run
`python -m harness.run --stage report`.

## What this eval CANNOT tell you

Honesty section, because every eval has a boundary:

- **20 cases is a floor, not coverage.** It catches regressions on known
  failure modes; it says nothing about the distribution of real callers.
  Production traffic sampling is the real layer 4.
- **Single-turn only.** Real ordering calls are multi-turn with repair,
  interruption, and drift. A multi-turn simulator is the obvious next step
  and a materially harder one.
- **The judge shares a model family with the agent.** Correlated blind spots
  are possible — a claim both models believe will not be flagged. The human
  agreement check bounds this but doesn't eliminate it.
- **Ten human labels is a smoke test, not a validation study.** It reliably
  catches a systematically lenient judge; it cannot certify one.
- **Latency here is dev-box latency**, not production telephony latency with
  streaming STT/TTS in the loop.
- **Deterministic checks encode my assumptions.** A case can "pass" while
  serving the caller badly in a way neither the assertions nor the rubric
  anticipated. Evals constrain failure; they don't prove correctness.

## Why this exists

I run voice agents for restaurants in production. The gap between "the demo
worked" and "a business can leave this thing alone with its customers" is
exactly the gap between vibes and instrumentation — this repo is the smallest
honest version of the instrumentation. The struggle-detection layer in
particular came out of watching agents fail politely: no error spike, no
crash, just a transcript slowly going nowhere while a customer waits.
