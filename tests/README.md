# tests/

There is currently no automated pytest suite here — only
`tests/integration/setup_ue5_actors.py`. See the `test-audit` skill
(`.claude/skills/test-audit/SKILL.md`) for the prioritized list of what should be tested
first (annotation projection, class ID mapping, vehicle spacing checks, config loading,
seed determinism).

Conventions for when tests are added:
- Prefer unit tests for pure-Python logic (`vantagecv/research_v2/annotation.py`,
  `config.py`, `vehicle_spacing.py`) that don't require a live UE5 connection.
- Tests that do require a live UE5 instance belong under `tests/integration/`, matching
  the existing `setup_ue5_actors.py`.
- Shared fixtures go in `tests/conftest.py`.
