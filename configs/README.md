# configs/

YAML configs loaded directly via PyYAML (no OmegaConf/Hydra in this project).

- `research_v2.yaml` — main pipeline config: experiment name, random seed, image count,
  UE5 connection (host/port), scene/level path
- `vehicles.yaml` — per-mesh vehicle metadata (rotation offset, category, dimensions) —
  `category` values here must match `VehicleClass` in `vantagecv/research_v2/config.py`
- `levels/` — per-level anchor/zone definitions
- `zones/` — NOT loaded by the pipeline at runtime: `SCHEMA.yaml` documents the zone
  manifest file format, and `automobile.zones.yaml` is a saved output example from
  `scripts/capture_zones.py --output <path>` (that script's `--output` path is
  user-specified, not hardcoded to this folder)

Any value that must match between `research_v2.yaml`, `vehicles.yaml`, and the
`VehicleClass` enum (vehicle category names) or between a level config and the UE5 level
it targets (`level_path`) is a place drift silently breaks generation — see
`.cursor/rules/research-project.mdc`'s domain invariants.
