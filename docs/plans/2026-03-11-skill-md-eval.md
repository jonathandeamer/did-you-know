# SKILL.md instruction quality eval

> Record of a `/skill-creator` evaluation session on 2026-03-11. This file is kept as a record of development activity; it is not a plan or specification.

## Background

Five commits landed on 2026-03-10, all targeting the agent-facing SKILL.md. They made the following functional changes:

| Commit | Change |
|--------|--------|
| `d126d7f` | Switch delivery and refresh crons from vague "set up a cron job" to explicit `openclaw cron add` commands with `--session isolated`, `--announce`, `--no-deliver` |
| `76c0a27` | Align refresh cron schedule with Wikipedia's DYK update times (`7 0,12 * * *` instead of `0 */12 * * *`) |
| `6a1dc6c` | Require `--channel` and `--to` on the delivery cron, resolved from session context |
| `4ae2a26` | Gate the post-fact upsell on `dyk-prefs.json` existence; run Refresh workflow immediately after setting preferences (not deferred to cron) |
| `f7b8f8a` | Tighten upsell gating wording from interpretive ("only if the user isn't already set up") to procedural ("check whether the file exists") |

The question: do these changes actually produce different agent behavior, or would a model have inferred the right thing anyway?

## Method

Used `/skill-creator` to run a structured eval comparing the new SKILL.md against the pre-change version (snapshotted from `d126d7f^`).

### Test scenarios

Three scenarios, each run against both skill versions:

1. **New user asks for a fact** — `dyk-prefs.json` does not exist. Should the agent offer the preferences/delivery upsell?
2. **Returning user asks for a fact** — `dyk-prefs.json` exists. Should the agent suppress the upsell?
3. **User wants preferences + daily delivery** — "I like history and science, not really into sports. Also set me up with a daily fact around 8am." Tests the full workflow: prefs setup, immediate refresh, delivery cron, refresh cron.

### Assertions

13 total assertions across the 3 scenarios:

- **Eval 0** (3): fact served, upsell offered, prefs file checked before upsell decision
- **Eval 1** (2): fact served, upsell suppressed
- **Eval 2** (8): prefs initialized, prefs set correctly, refresh run before crons, delivery uses `openclaw cron add`, delivery has `--channel`/`--to`, delivery avoids round minutes, refresh cron aligned with Wikipedia schedule, refresh cron has `--no-deliver`

### Models

Initial runs used Opus (default). Re-ran with Haiku to test whether the instructions are robust enough for a less capable model. This turned out to be the more meaningful test.

### Environment notes

Subagents were blocked on Bash and Write permissions, so they described their intended workflows rather than executing commands. This was sufficient for grading — the assertions test what the agent *would do*, not whether the underlying scripts succeed. The old_skill eval 2 Haiku agent read the current SKILL.md instead of the snapshot; the Opus old_skill transcript was substituted for that eval's baseline.

## Results

| Eval | New SKILL.md | Old SKILL.md | Delta |
|------|-------------|-------------|-------|
| new-user-fact | 3/3 (100%) | 2/3 (67%) | +1 |
| returning-user-fact | 2/2 (100%) | 1/2 (50%) | +1 |
| prefs-and-delivery | 8/8 (100%) | 3/8 (38%) | +5 |
| **Overall** | **13/13 (100%)** | **6/13 (46%)** | **+7** |

The new SKILL.md passes every assertion. The old one fails exactly the 7 assertions that correspond to yesterday's changes.

### Per-assertion breakdown (old skill failures)

| Assertion | Why it fails |
|-----------|-------------|
| `prefs-file-checked` (evals 0 & 1) | Old skill had no prefs-file gate — upsell was unconditional |
| `no-upsell` (eval 1) | Returning user gets nagged every time |
| `refresh-before-cron` (eval 2) | Old skill deferred to cron schedule; new skill runs inline immediately |
| `delivery-has-channel-routing` (eval 2) | Old skill didn't specify `--channel`/`--to`; agent used wrong format |
| `delivery-avoids-round-minutes` (eval 2) | Old skill didn't mention this; agent used `0 8 * * *` |
| `refresh-cron-timing` (eval 2) | Old skill said "every 12 hours"; agent used generic `0 */12 * * *` |
| `refresh-cron-silent` (eval 2) | Old skill didn't distinguish visible vs invisible cron jobs |

### Opus vs Haiku finding

On eval 1 (returning user), Opus with the old SKILL.md *correctly suppressed the upsell* even though the instructions didn't tell it to — it inferred from common sense that nagging a returning user is wrong. Haiku followed the old instructions literally and would have shown the upsell.

This means testing with Opus alone would have hidden the bug. The old skill appeared to work because a smart model compensated for vague instructions. Haiku exposed the gap, confirming that the commits were necessary and that specificity in skill instructions is not just stylistic — it is the mechanism of correctness for less capable models.

## Artifacts

- Workspace: `did-you-know-workspace/iteration-1-haiku/`
- Baseline snapshot: `did-you-know-workspace/skill-snapshot/SKILL.md`
- Benchmark: `did-you-know-workspace/iteration-1-haiku/benchmark.json`
- Evals: `evals/evals.json`
