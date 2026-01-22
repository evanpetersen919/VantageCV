# Location-Based Spawning - Implementation Summary

## What Changed

### Test Script: `scripts/test_randomization.py`

**Previous behavior**: Attempted to spawn across all detected locations simultaneously  
**New behavior**: Randomly selects ONE location (1, 2, or 3) per test iteration and spawns ONLY in that location

## Key Changes

### 1. Location Selection (Per-Iteration)
```python
# Each test iteration now picks one location randomly
selected_location = random.choice([1, 2, 3])  # Seed-based for determinism
```

### 2. Vehicle Zone Filtering
```python
# Filter parking anchors by Y-coordinate
for anchor_name in all_parking_anchors:
    transform = get_transform(anchor_name)
    if is_in_location(transform["Y"], selected_location):
        use_this_anchor()

# Filter lane definitions by Y-coordinate
# Filter sidewalk bounds by Y-coordinate
```

### 3. Prop Anchor Filtering
```python
# Extract props from detected_anchors_by_location for selected location only
location_props = detected_anchors_by_location[selected_location]
```

### 4. Output Naming
```python
# Filenames now include location
output_path = f"frame_{i:03d}_loc{selected_location}.png"
```

## Test Results

**Location 1** (Y ∈ [400, 20000]):
- ✅ 5 parking anchors detected
- ✅ 4 lane definitions detected
- ✅ 1 sidewalk detected
- ✅ 36 prop anchors detected
- ✅ Vehicles spawned successfully
- ✅ Props spawned successfully

**Location 2** (Y ∈ [20000, 39600]):
- ⚠️ 0 parking/lane/sidewalk anchors (not configured)
- ⚠️ Correctly skipped (no spawns)

**Location 3** (Y ∈ [39600, 59200]):
- ⚠️ 0 parking/lane/sidewalk anchors (not configured)
- ⚠️ Correctly skipped (no spawns)

## Logging Output

```
============================================================
LOCATION SELECTED: 1
  Y bounds: (400.0, 20000.0)
============================================================

[4/20] Location=1, Seed=2003, Vehicles=3, Parking=100%
  Filtered zones for Location 1:
    Parking: 5 anchors
    Lanes: 4 definitions
    Sidewalks: Yes
  Vehicles spawned: 4
  Prop anchors in Location 1: 36
  Props spawned: 18
```

## Determinism

- ✅ Same seed → same location selected
- ✅ Same seed → same vehicles spawned
- ✅ Same seed → same props spawned
- ✅ Seed 2000 → Location 2
- ✅ Seed 2001 → Location 3
- ✅ Seed 2003 → Location 1

## Cleanup

**Removed**:
- Global `ACTIVE_LOCATIONS` filtering at startup
- Pre-filtering of prop anchors before iteration loop

**Added**:
- `LOCATION_Y_BOUNDS` constant (matches zone/prop detection)
- `AVAILABLE_LOCATIONS = [1, 2, 3]` (only ready locations)
- Helper functions: `filter_anchors_by_location()`, `is_in_location()`
- Per-iteration location selection
- Per-iteration zone filtering
- Per-iteration prop filtering

## Next Steps

To enable Location 2 and 3:
1. Run `scripts/capture_zones.py` to detect zones in locations 2-3
2. Zones will automatically be available for spawning
3. Test script will spawn in locations 2-3 when selected

## Technical Notes

- **Vehicle zones** are filtered at runtime by querying Y-coordinates
- **Prop anchors** use pre-grouped `detected_anchors_by_location` dict
- **Original configs** are saved and restored after each iteration
- **No changes** to core spawning logic (math, thresholds, validation)
- **Backward compatible** with existing prop/vehicle controllers
