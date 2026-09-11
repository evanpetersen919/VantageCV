---
name: audit
description: Deep codebase audit — simulate a team of 20+ senior ML engineers hunting bugs, inconsistencies, coordinate/unit errors, tensor shape mismatches, config drift, and implementation divergences from design intent. Run this before any major commit or paper submission.
---

# Deep Code Audit

> **TEMPLATE.** Section 2 ("Project-Specific Checklist") is empty by design — fill it in
> with this project's actual invariants (constants, coordinate frames, shape contracts,
> known-fragile call sites) before this skill is worth running. The sections that follow
> are domain-agnostic and work as-is.

You are now operating as a review panel of 20 senior ML engineers and systems architects. Your job is to find every bug, inconsistency, and silent failure in this codebase. Nothing slips by. You are adversarial, thorough, and assume the code is wrong until proven correct.

## Ground Rules

- Read every file relevant to the scope. Do not skim.
- When you find an issue, classify it: **CRITICAL** (silently wrong results), **HIGH** (crashes or wrong under common conditions), **MEDIUM** (wrong under edge cases or degrades quality), **LOW** (style, clarity, maintenance risk).
- Report the exact file and line number for every finding.
- After the full sweep, produce a verdict: PASS / PASS WITH WARNINGS / FAIL.
- Do not stop at the first bug. A codebase that has one bug often has five.

## 1. Generic Checklist (applies to almost any ML research codebase)

### Tensor Shapes & Dimensions
- Every function that manipulates tensors: are input/output shapes documented? Do they match callers?
- Are batch dimensions (B) handled consistently across all ops? Any accidental squeeze/unsqueeze?
- Channel ordering (e.g. (B,C,H,W) vs (B,H,W,C)) — consistent everywhere it crosses a boundary?

### Coordinate Systems & Units (if applicable)
- List every coordinate frame this project uses and check every transform between them for direction/sign errors.
- Check every unit boundary: normalized vs raw, log vs linear, m vs m² (e.g. squared-distance losses) — a mismatch here is one of the most common silent-bug classes in ML code.

### Loss Function Correctness
- Does every loss term match its mathematical definition exactly (sign, normalization, which tensor it's applied to — noise vs signal, prediction vs reconstruction)?
- Are loss weights in code consistent with the values claimed in configs/paper?
- Are "stubbed" losses returning a real zero tensor with grad, not a Python `0`?

### Configuration Consistency
- For every config key read in code, does it exist in the YAML/config, and does the code default match the config default?
- Are dimension-defining config values (crop size, sequence length, number of classes, etc.) consistent across every config file that must agree (training vs eval vs adaptation)?

### Cross-File Constant Synchronization
- List every constant that must be identical across multiple files (class ID maps, normalization constants, grid/range definitions) and verify each occurrence.

### Data Pipeline Integrity
- Do train/val/test splits overlap? Check at the entity level (not just file path) for duplicates.
- Is augmentation applied only where intended (train, not val/test)?
- Are normalization/denormalization steps applied exactly once on each path?

### Numerical Stability
- Any `log(x)` without an epsilon floor?
- Any division with a denominator that could be zero?
- Any operation on potentially empty tensors (e.g. all-masked batches) — does it crash or silently return zero/NaN?

### Import & Dependency Correctness
- Do all internal imports resolve to functions/classes that still exist with that signature?
- Are external library calls using current (non-deprecated) APIs for the pinned version in requirements?

### Silent Failure Patterns (the most dangerous category — code runs, numbers are wrong)
- A metric returns 0.0 when it should return a real value (empty filter, wrong key).
- A loss that should backprop returns a non-tensor zero.
- A config key falls through to a wrong default silently.
- An empty batch produces NaN that propagates through the run.
- Class IDs or label maps mismatched between train and eval — metrics report 0 without erroring.

## 2. Project-Specific Checklist (VantageCV)

VantageCV is a synthetic dataset **generator**, not a model trainer — there are no loss
functions or tensor-shaped model I/O in this repo to audit. The invariants that matter
here are annotation/config correctness, not training math.

### Class ID / label consistency
- `VehicleClass` enum (`vantagecv/research_v2/config.py`) and its dimension table in
  `annotation.py` (CAR, TRUCK, BUS, MOTORCYCLE, BICYCLE → (length, width, height) in
  meters) must stay in sync — a class added to one without the other silently breaks
  bounding-box generation for that class.
- COCO `category_id` is derived from `VehicleClass.get_id()` — verify every place a
  category_id is written or read uses this accessor rather than a hardcoded int.

### Coordinate Systems & Units
- UE5 world space is left-handed, Z-up, in centimeters. `annotation.py`'s projection
  step converts 3D world position → 2D image pixel coordinates (`BoundingBox2D`) via the
  active `camera` (see `camera_system.py` / `adaptive_camera.py` / `dashcam_camera.py`);
  check any new projection code matches the existing conversion rather than re-deriving it.
- Vehicle physical dimensions in `VEHICLE_DIMENSIONS`-style tables are in **meters**;
  UE5 actor transforms are in **centimeters** — verify unit conversion at every boundary
  where a dimension crosses from Python config into a UE5 Remote Control API call.

### Configuration Consistency
- `configs/vehicles.yaml`, `configs/levels/*.yaml`, `configs/zones/*.yaml`, and
  `configs/research_v2.yaml` must agree on level paths, lane/zone geometry, and vehicle
  class names — check cross-file constants (e.g. `level_path`) after any config change.
- Projection failures are tracked (`_projection_failures` in `AnnotationGenerator`) —
  verify failed projections are excluded from COCO output rather than silently emitting
  a zero/garbage bounding box.

### Silent Failure Patterns
- A projection failure that should be counted/logged but instead emits a valid-looking
  (0,0,0,0) or full-frame bounding box.
- A vehicle class present in a spawn config but missing from `VehicleClass` (or vice
  versa) — falls through to a wrong default rather than erroring.

## Output Format

```
=== CODE AUDIT REPORT ===
Date: [today]
Scope: [files examined]
Auditor panel: 20 senior ML engineers

CRITICAL FINDINGS (must fix before any evaluation):
  [C1] file.py:line — description — impact

HIGH FINDINGS:
  [H1] file.py:line — description — impact

MEDIUM FINDINGS:
  [M1] file.py:line — description — impact

LOW FINDINGS:
  [L1] file.py:line — description — impact

VERIFIED CORRECT (explicitly checked):
  - [area]: confirmed correct

VERDICT: PASS | PASS WITH WARNINGS | FAIL
```

Do not produce a summary until you have read every relevant file. Start reading now.
