---
name: test-audit
description: Test suite quality audit — finds untested critical paths, weak assertions that can't catch real bugs, missing edge cases, synthetic fixtures that don't represent real failure modes, and tests that give false confidence. Run when test coverage feels high but bugs still slip through.
---

# Test Suite Quality Audit

> **Adapted for VantageCV.** This project has no real pytest suite yet — only
> `tests/integration/setup_ue5_actors.py` and manual `scripts/test_*.py` scripts (see
> `scripts/README.md`). The sections below are filled in with this project's actual
> critical paths (annotation/projection, config loading, spacing checks) rather than the
> template's generic tensor/loss-function examples, since there's no model training here.

You are a panel of 10 senior engineers who specialize in catching the difference between
"high coverage" and "high confidence." Your job is not to count test lines — it's to find
tests that cannot catch the bugs that matter and to identify the critical paths that have
no tests at all.

The most dangerous test suite is one that looks thorough but gives false confidence. Find those tests.

## Ground Rules

- Read every test file in `tests/`. Read the source files they test.
- A test that cannot distinguish correct from incorrect behavior is worse than no test.
- "Coverage" means nothing if assertions are trivially satisfied.
- Edge cases that are common in ML (empty tensors, NaN, zero-length batches, all-zero
  inputs) are first-class citizens.
- Verify that test fixtures are realistic: if a test uses uniform/constant data where real
  data is highly variable, the test may pass on broken code.

## Audit Checklist

### 1. Assertion Strength

For every test, ask: "Could this test pass if the function returned garbage?"

Weak assertion patterns that must be flagged:
- `assert result is not None` — tells you nothing about correctness
- `assert loss > 0` — a broken loss that returns a huge constant passes this
- `assert output.shape == expected_shape` without checking values — shape can be right, values wrong
- `assert not torch.isnan(output).any()` — necessary but not sufficient alone
- `assert isinstance(x, float)` — type check without value check
- `assert result` — truthy check on a tensor or dict means nothing
- Checking only the first element of a batch when the bug manifests on mismatched elements

Strong assertion patterns:
- Tolerance-based equality against a known mathematical result
- Checking specific tensor values at known positions
- Checking both the value AND the sign
- Edge cases tested alongside the happy path

### 2. Critical Path Coverage (VantageCV)

None of these currently have automated tests — this is the priority list:

```
- AnnotationGenerator's world-to-image projection (annotation.py): test with a known
  camera pose + known 3D vehicle position that maps to a hand-computed 2D bounding box.
- VehicleClass.get_id() / category_id mapping (config.py + annotation.py): test that the
  enum-to-int mapping used for COCO category_id is identical everywhere it's read.
- VehicleSpacingChecker.can_place_vehicle() (vehicle_spacing.py): test known
  overlapping/non-overlapping vehicle placements give the expected accept/reject result.
- Seed determinism: test that running the same config + seed twice produces identical
  vehicle placement/annotation output (the property README's "seed-based deterministic
  generation" depends on).
- Config loading (config.py, research_v2/config.py): test that every shipped YAML under
  configs/ loads without error and that vehicle categories in configs/vehicles.yaml are
  all valid VehicleClass values (see experiment-check skill's pre-flight script).
- Frame validation pass/fail/warn logic (scene_validation_controller.py): test known
  underground/overlapping vehicle inputs produce the expected FAIL/WARN status.
```

### 3. Edge Cases in ML

VantageCV has no tensor/model training code yet, so the ML-specific examples below
(batches, losses, NaN propagation) don't apply directly — the VantageCV-relevant analogs
are: zero vehicles in a scene, a frame where every projection fails, and a config with
zero configured zones/locations. These are commonly missing — check whether each is
covered for this project's core model/data path:

- **Empty batch** (B=0) — does the model crash or return empty tensors gracefully?
- **All-zero / degenerate input** — does the model produce NaN or a reasonable output?
- **All-masked loss** — if every element is masked out, does the loss return 0.0 (not NaN)?
- **Single-element batch** (B=1) — some ops (e.g. BatchNorm) behave differently.
- **Boundary values at the edges of the valid input range** — clipping vs wraparound behavior.
- **Zero detections / zero predictions** — does a metric computation handle the empty case without crashing?

### 4. Test Fixture Realism

For each synthetic fixture, ask: "Does this fixture represent a real failure mode?"

Common unrealistic fixtures that hide bugs:
- Uniform/constant tensors where real data is highly variable — kills the signal a
  difference-based loss needs to be meaningfully tested.
- All-zero labels — exercises only the background path, never the foreground-weighted path.
- Uniform random data where the real distribution is structured — tests nothing about the
  actual optimization landscape.

Better fixture patterns:
- A small synthetic scene/example with known, hand-computed ground truth.
- Construct inputs from explicit known values via the forward transform's inverse.
- Parametrized fixtures covering multiple realistic scenarios.

### 5. Test Independence

- Do tests share state via module-level variables or class attributes?
- Do tests write to disk without cleaning up?
- Do tests depend on a global random seed rather than setting their own?
- Do any tests import production scripts in a way that triggers side effects (argparse,
  prints, file writes) on import?

### 6. Missing Test Classes (VantageCV)

```
- [ ] vehicle_lifecycle.py: does spawning then despawning a vehicle leave zero orphaned
      actors/state behind?
- [ ] config.py / research_v2/config.py: does loading every shipped config under configs/
      succeed without error?
- [ ] anchor_spawn_controller.py: for a vehicle placed exactly at a zone boundary, which
      side wins — inside or outside the valid placement region?
- [ ] annotation.py: does the COCO categories list generated from VehicleClass exactly
      match the class names configs/vehicles.yaml actually uses?
```

### 7. Test Performance

- Are any tests running full-size/full-iteration versions of expensive operations (e.g. a
  full sampling loop) that belong in an integration test, not a unit test?
- Are any tests loading real pretrained weights instead of random-init models?
- Are slow tests (>5s) marked so they can be excluded from the default fast run?

## Output Format

```
=== TEST SUITE AUDIT REPORT ===
Files examined: [list]
Total tests: [N]

CRITICAL GAPS (bugs exist today that no test would catch):
  [T-C1] function — what failure mode is uncovered — suggested test

WEAK ASSERTIONS (tests pass on broken code):
  [T-W1] test_file.py:test_name — why it's weak — how to strengthen

MISSING EDGE CASES:
  [T-E1] function — missing case — why it matters

UNREALISTIC FIXTURES:
  [T-F1] fixture — what's unrealistic — better approach

TESTS THAT GIVE FALSE CONFIDENCE:
  [T-FC1] test_name — why it's misleading

VERIFIED SOLID TESTS (explicitly checked, strong assertions):
  - test_name: why it's good

COVERAGE ESTIMATE:
  Critical paths: X% meaningful coverage (not line coverage)

PRIORITY ADDITIONS (highest-value new tests):
  1. ...
  2. ...
  3. ...
```
