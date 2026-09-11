# scripts/

Entry points for running the capture/generation pipeline against a running UE5 instance.
No logic that isn't trivial to test should live here — scripts parse args/config and call
into `vantagecv/research_v2/`.

## Live entry points (match current config layout)
- `generate_v2.py` — main generation entry point, reads `configs/research_v2.yaml`
- `capture.py`, `capture_props.py`, `capture_zones.py` — capture runs for specific scopes
- `test_randomization.py` — verifies scene/lighting/vehicle randomization is actually varying

## Manual debug tools (not wired into any test runner, kept as working utilities)
- `interactive_spawn_test.py`, `test_anchor_spawn.py`, `test_prop_validation.py` —
  one-off manual checks during development
- `detect_lighting.py` — standalone lighting diagnostic
- `download_coco.py`, `filter_coco_vehicles.py` — generic COCO dataset utilities
