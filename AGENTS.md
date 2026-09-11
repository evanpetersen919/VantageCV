# Agent instructions — VantageCV

This repo is configured for **Cursor** and **Claude Code**. Read this file first in either tool.

## Behavioral baseline

Follow the Karpathy-inspired guidelines in `.cursor/rules/karpathy-guidelines.mdc` (always on in Cursor):

1. Think before coding — state assumptions, ask when unclear
2. Simplicity first — minimum code for the request
3. Surgical changes — only touch what the task requires
4. Goal-driven execution — define verifiable success criteria (tests, manual capture runs)

## Project context

VantageCV is a synthetic computer vision dataset generator for autonomous vehicle
perception research — Unreal Engine 5.7 + Python, producing COCO-format annotated
imagery with controlled environmental parameters (weather, time-of-day, 7 capture
locations, 5 vehicle classes). It's a personal portfolio project, not a paper submission,
and currently has no model training/evaluation component. See `CLAUDE.md` for the full
stack and structure, and `.cursor/rules/research-project.mdc` for domain invariants —
apply that file when editing `vantagecv/`, `ue5_plugin/`, `tests/`, `configs/`, or `scripts/`.

## Skills (optional, on demand)

| Skill | Path | Use when |
|-------|------|----------|
| python-pro | `.claude/skills/python-pro/` | Python structure, tooling, async |
| pytorch-lightning | `.claude/skills/pytorch-lightning/` | Not currently used in this codebase — kept for if training is added |
| torch_geometric | `.claude/skills/torch_geometric/` | Not currently used — no graph/point-cloud work in this project |
| matplotlib | `.claude/skills/matplotlib/` | Plots and figures (matplotlib is an actual dependency) |
| audit | `.claude/skills/audit/` | Deep adversarial code audit — filled in with VantageCV's real invariants |
| research-audit | `.claude/skills/research-audit/` | Paper-quality audit — not currently applicable (no paper submission exists) |
| reviewer | `.claude/skills/reviewer/` | Adversarial reviewer simulation — not currently applicable (no paper draft exists) |
| experiment-check | `.claude/skills/experiment-check/` | Pre-flight check before a long UE5 generation/capture run |
| test-audit | `.claude/skills/test-audit/` | Finds weak/missing tests — filled in with VantageCV's real critical paths |

Cursor mirrors these under `.cursor/skills/` if you use Cursor's skill format too.

## Claude Code extras

- `CLAUDE.md` — merged stack + project + behavioral guidelines
- `.claude/settings.json` — hooks: auto black/isort formatting on save, bash-command
  logging, pip-audit/safety check on dependency file changes. The blocking flake8/mypy
  hooks from the upstream template were deliberately removed here — this codebase isn't
  lint/type-clean yet, and a blocking hook would halt unrelated edits on pre-existing
  issues. Run `flake8`/`mypy` manually via `/lint` when you want that check.
- `.claude/commands/` — `/test`, `/lint` slash commands

## Provenance

This setup was imported from `evanpetersen919/Research-Skills`, a reusable Claude
Code + Cursor scaffolding template. The `audit`, `experiment-check`, and `test-audit`
skills have been filled in with VantageCV's real invariants and critical paths.
`research-audit` and `reviewer` are paper-submission-oriented and don't apply to this
project yet (no paper exists) — they're left as clearly-marked not-applicable rather than
filled with invented research claims.
