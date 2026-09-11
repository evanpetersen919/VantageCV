---
name: experiment-check
description: Pre-experiment validation — verify configs are consistent, data splits are clean, metrics are correctly implemented, baselines are fairly set up, and nothing will silently produce wrong results before a long training run. Run before any experiment that takes more than 30 minutes.
---

# Pre-Experiment Validation

> **Adapted for VantageCV.** This project generates synthetic data (UE5 capture runs),
> it does not train models — sections 3, 5, 7, 9 below (checkpoint compatibility, baseline
> sanity, VRAM, training-stability logging) don't apply and are kept only for reference.
> Sections 1, 2, 4, 6, 8 are the ones that matter before starting a long `generate_v2.py`
> or `capture_*.py` run.

You are a senior engineer whose job is to catch every setup mistake before a multi-hour
synthetic-data generation run produces a dataset that turns out to be invalid (wrong
class labels, broken projections, overlapping/misconfigured zones). This audit takes a
few minutes. It saves hours of wasted UE5 rendering time.

## Usage

Invoke as: `/experiment-check [experiment name or config path]`

If no argument is given, audit all experiments that haven't been run yet (check for missing checkpoints).

## Validation Checklist

### 1. Config Integrity

For the target config file(s):
- Load the config and verify no missing keys or broken interpolations.
- Verify every file path referenced in the config exists on disk (data root, split file,
  pretrained checkpoint, output dir — and that the output dir is writable).
- Check for conflicting values between config sections that must agree (e.g. a dimension
  defined in the model config must match the dimension the data config produces).

### 2. Zone / Config Integrity (replaces "Data Split Integrity")

Before any generation run:
- Read the target level/zone configs (`configs/levels/*.yaml`, `configs/zones/*.yaml`).
- Verify vehicle spawn zones don't overlap in ways that would produce impossible/occluded
  scenes, per the constraints described in `vantagecv/research_v2/vehicle_spacing.py`.
- Verify `configs/vehicles.yaml` class names match `VehicleClass` in `config.py` exactly.

### 3. Checkpoint Compatibility — not applicable

No model checkpoints are loaded by this pipeline.

### 4. Metric Implementation Verification — not applicable

No evaluation metrics are computed by this pipeline; `scene_validation_controller.py`'s
pass/fail/warn frame validation is a data-quality check, not a model metric.

### 5. Baseline Sanity Checks — not applicable

### 6. Reproducibility Setup

- Is `random_seed` in the run's config (e.g. `configs/research_v2.yaml`) set explicitly,
  not left to a nondeterministic default? (This flows into UE5's `Config.RandomSeed` in
  `DomainRandomization.cpp`, which seeds the `RandomStream` used for lighting/sky/vehicle
  randomization.)
- Confirm the seed is logged (via `logging_utils.py`'s `ResearchLogger`) so the run can be
  reproduced later.

### 7. Resource Check

- Is there enough disk space for the planned number of frames (`output/` images + COCO
  JSON) before starting a multi-hour capture run?
- Is UE5 rendering at the configured resolution (default 1920x1080) within GPU memory
  budget for the session length planned?

### 8. Experiment Tracking Setup

- Is MLflow initialized with the correct experiment/run name (this project uses MLflow,
  not wandb/tensorboard, per `pyproject.toml`)?
- Is the output directory unique per run so frames from different runs don't overwrite
  each other?

### 9. Generation Stability Indicators — replaces "Training Stability Indicators"

Set these up BEFORE starting a long run:
- Watch `_projection_failures` / frame validation warn-rate in `logging_utils.py` output —
  a rising failure rate partway through a run usually means a zone or camera config bug,
  not normal noise.
- Confirm the UE5 Remote Control API connection is stable before committing to a
  multi-hour unattended run (a dropped connection mid-run silently stalls capture).

## Quick Pre-Flight Script Template

```python
import yaml
from pathlib import Path

cfg = yaml.safe_load(Path("configs/research_v2.yaml").read_text())

# 1. Level path exists as expected in config
assert "level_path" in cfg["scene"], "Missing scene.level_path in research_v2.yaml"

# 2. Every vehicle mesh's category in configs/vehicles.yaml matches VehicleClass enum
vehicles_cfg = yaml.safe_load(Path("configs/vehicles.yaml").read_text())
from vantagecv.research_v2.config import VehicleClass
known = {c.value for c in VehicleClass}
for mesh_name, entry in vehicles_cfg.get("vehicles", {}).items():
    category = entry.get("category")
    assert category in known, f"{mesh_name}: unknown vehicle category '{category}'"

# 3. Output dir writable
out_dir = Path("output")
out_dir.mkdir(exist_ok=True)
assert out_dir.exists() and out_dir.is_dir()

print("Pre-flight OK")
```

## Output Format

```
=== PRE-EXPERIMENT CHECK: [config/experiment name] ===

BLOCKERS (do not run until resolved):
  [X] description — how to fix

WARNINGS (run at your own risk, but flag in paper):
  [W] description — impact

VERIFIED OK:
  [v] config integrity
  [v] data split integrity
  [v] checkpoint compatibility
  [v] metric implementations
  [v] baseline setup
  [v] resource estimate: ~X GB VRAM

RECOMMENDED BEFORE RUNNING:
  - ...

STATUS: GO | NO-GO
```
