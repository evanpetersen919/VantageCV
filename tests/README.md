# tests/

## `tests/unit/`

A real pytest suite (282 tests across 8 files) covering the fully pure-Python and
HTTP-mockable modules: `annotation.py`, `camera_system.py`, both config modules
(`research_v2/config.py` and the top-level `vantagecv/config.py`), `vehicle_spacing.py`,
`scene_validation_controller.py`'s semi-pure logic, `ue5_bridge.py` (HTTP-mocked via
`requests-mock`), and seed-determinism/RNG-isolation regression tests. Run it with:

```bash
pytest -m "not live_ue5"
```

CI (`.github/workflows/tests.yml`) runs this exact command on every push/PR to `main`.

Shared fixtures live in `tests/conftest.py`, including an autouse fixture that isolates
global `random` state between tests (several controllers mutate `random.seed()`
globally, which would otherwise leak between tests).

## `tests/integration/`

`setup_ue5_actors.py` is a standalone interactive script (not a pytest test) that
requires a live, running UE5 instance with the Remote Control plugin enabled. It's kept
separate from `tests/unit/` for that reason.

Tests marked `@pytest.mark.live_ue5` are reserved for future automated integration tests
that need a real UE5 connection — none exist yet, but the marker is already registered
in `pyproject.toml` and excluded from the default `pytest -m "not live_ue5"` CI run.

## Conventions for new tests

- Prefer unit tests for pure-Python logic that doesn't require a live UE5 connection —
  put them in `tests/unit/`.
- Tests that do require a live UE5 instance belong under `tests/integration/`, or should
  be marked `@pytest.mark.live_ue5` if written as pytest tests.
- Shared fixtures go in `tests/conftest.py`.
- See the `test-audit` skill (`.claude/skills/test-audit/SKILL.md`) for guidance on
  writing strong assertions and finding untested critical paths.
