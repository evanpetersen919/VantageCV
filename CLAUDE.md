# CLAUDE.md

Guidance for Claude Code and compatible agents.
Cursor users: see also `AGENTS.md` and `.cursor/rules/`.

## Project

**VantageCV** — a synthetic computer vision dataset generator for autonomous vehicle
perception research, built with Unreal Engine 5.7 and Python. It generates COCO-format
2D bounding-box annotations for 5 vehicle classes across 7 capture locations, with
weather/time-of-day augmentation and seed-based reproducibility. This is a personal
portfolio project, not a paper submission — see README.md for the full feature list.
(No `docs/research/PROJECT_PLAN.md` exists yet — that path is only where a future research
writeup would go if this project's scope ever grows into one.)

There is currently no model training or evaluation in this repo (see README's "Future
Development": domain-adaptation evaluation is listed as not-yet-implemented).

## Behavioral Guidelines (Karpathy-inspired)

See `.cursor/rules/karpathy-guidelines.mdc` for the full guidelines (always-on in Cursor).
Summary:
1. **Think before coding** — state assumptions; ask when unclear; surface tradeoffs.
2. **Simplicity first** — minimum code; no speculative abstractions.
3. **Surgical changes** — only touch what the task requires.
4. **Goal-driven execution** — verifiable success criteria (tests, manual capture runs).

## Technology Stack

### Core
- **Python 3.11+**
- **Unreal Engine 5.7** as the simulation/rendering backend, controlled from Python over
  its Remote Control API (HTTP/REST) — see `vantagecv/ue5_bridge.py`.
- **C++ UE5 plugin** (`ue5_plugin/Source/VantageCV/`) for scene control and data capture.

### Python dependencies (see `pyproject.toml` / `requirements.txt`)
- torch, torchvision, numpy, opencv-python, pillow, pyyaml, albumentations, pycocotools
- onnx, onnxruntime-gpu
- mlflow (experiment tracking — not wandb/tensorboard, despite matplotlib/tensorboard
  being listed as plotting/logging utilities in requirements.txt)

Note: PyTorch Lightning and torch_geometric skills are present under `.claude/skills/`
from the template this setup was copied from, but neither is currently used in this
codebase — no training loop or graph/point-cloud code exists here yet.

## Domain Invariants

See `.cursor/rules/research-project.mdc` for the full list (unit conventions between UE5
centimeters and vehicle-dimension meters, class ID mapping, seed propagation, etc.) —
read it before touching `annotation.py`, `config.py`, or the UE5 plugin's randomization.

## Development Commands

### Environment Setup
```bash
python -m venv .venv
# Windows: .\.venv\Scripts\Activate.ps1   |  Linux/Mac: source .venv/bin/activate
pip install -r requirements.txt
pip install -e .
```

### Code Quality

`.flake8` and `.pre-commit-config.yaml` are present (copied from the shared tooling
template) but **not yet actively enforced** on this codebase — running them for the first
time will likely surface a large number of pre-existing findings. Run manually, don't
assume the codebase currently passes:
```bash
black .
isort .
flake8
```
`.claude/settings.json`'s auto-format hooks (black/isort) run on save; the stricter
flake8/mypy blocking hooks from the original template were intentionally **not** carried
over here for that reason (see AGENTS.md provenance note). CI (`.github/workflows/tests.yml`)
runs flake8 too, but as a separate, informational job with `continue-on-error: true` —
it will never block a merge given the current lint debt (see `flake8`'s ~3000+
pre-existing findings if you run it locally).

### Testing

`tests/unit/` has a real pytest suite (200+ tests) covering every fully-pure-Python
module: `annotation.py`, `camera_system.py`, both config modules, `vehicle_spacing.py`,
`scene_validation_controller.py`'s semi-pure logic, `ue5_bridge.py` (HTTP-mocked via
`requests-mock`), and seed-determinism/RNG-isolation regression tests. Run it with:
```bash
pytest -m "not live_ue5"
```
CI (`.github/workflows/tests.yml`) runs this exact command on every push/PR to `main`.
Tests marked `@pytest.mark.live_ue5` (none exist yet) are reserved for future
integration tests that need a real running UE5 instance — they're excluded from CI.
`tests/integration/setup_ue5_actors.py` and the manual one-off scripts under `scripts/`
(`interactive_spawn_test.py`, `test_anchor_spawn.py`, `test_prop_validation.py`) remain
separate from the pytest suite since they require a live UE5 connection. See the
`test-audit` skill (`.claude/skills/test-audit/`) for what's still untested (the
network-dependent parts of `scene_validation_controller.py`, `vehicle_spawn_controller.py`,
and the full generation pipeline end-to-end).

### Pipeline Entry Points
```bash
python scripts/generate_v2.py --config configs/research_v2.yaml
python scripts/capture_zones.py
python scripts/capture_props.py
python scripts/test_randomization.py
```

## Project Structure

```
vantagecv/                  — Python package
├── research_v2/            — active pipeline (16+ modules; not exhaustive below):
│                              orchestrator, camera_system, annotation,
│                              scene_controller, vehicle_spawner, vehicle_spacing,
│                              scene_validation_controller, validation,
│                              logging_utils, config, and other controllers
├── config.py, ue5_bridge.py, utils.py
ue5_plugin/Source/VantageCV/ — native C++ UE5 plugin
scripts/                    — capture/generation entry points + a few manual debug scripts
configs/                    — research_v2.yaml, vehicles.yaml, levels/, zones/
tests/integration/          — the one existing integration test setup script
docs/                       — setup guides, images
```

## Naming Conventions
- Files/modules: `snake_case.py`
- Classes: `PascalCase`
- Functions/variables: `snake_case`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_underscore_prefix`

## Before Committing
- Confirm `python -c "import vantagecv"` still works.
- If you touched `annotation.py`, `config.py`, or any config under `configs/`, check
  `.cursor/rules/research-project.mdc`'s domain invariants haven't been silently violated.
