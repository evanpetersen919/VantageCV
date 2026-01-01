# VantageCV: Research-Grade Synthetic Vehicle Dataset Generator

**Personal Portfolio Project | ML Engineering & Computer Vision**

A minimal, modular synthetic data generation system for vehicle detection using Unreal Engine 5's photorealistic rendering with Python orchestration.

## Current Status

**Version 2.0.0 - Research v2 Pipeline Active**

| Component | Status |
|-----------|--------|
| Scene Controller | ✅ Working |
| Vehicle Spawner | ✅ Working |
| Camera System | ✅ Working |
| Annotation Generator | ✅ Working |
| Frame Validation | ✅ Working |
| Dataset Orchestrator | ✅ Working |
| UE5 Integration | ⏳ Requires UE5 setup |

## Key Features

- **Minimal Design**: Single environment, single camera, 5 vehicle classes
- **Structured Logging**: JSON logs with module names, timestamps, and error hints
- **Fail-Fast Validation**: Invalid frames rejected with explicit reasons
- **COCO Format Output**: Standard annotation format for ML pipelines
- **Reproducible**: Seed-based randomization for ablation studies

## Target Scope

| In Scope | Out of Scope |
|----------|--------------|
| 5 vehicle classes (car, truck, bus, motorcycle, bicycle) | Pedestrians |
| 2D bounding boxes | 3D bounding boxes |
| Single straight road | Multiple environments |
| Day/night lighting | Weather effects |
| Single dashcam | Multi-camera setups |
| COCO annotations | KITTI, custom formats |

## Quick Start

```bash
# Generate 100 synthetic images
python scripts/generate_v2.py --num-images 100 --seed 42

# Validate configuration without generating
python scripts/generate_v2.py --dry-run

# Use custom config
python scripts/generate_v2.py --config configs/research_v2.yaml
```

## Project Structure

```
VantageCV/
├── vantagecv/                    # Core Python package
│   ├── __init__.py               # Package exports
│   ├── config.py                 # YAML config loader
│   ├── ue5_bridge.py             # UE5 Remote Control API client
│   ├── utils.py                  # Helper functions
│   └── research_v2/              # ★ PRIMARY SYSTEM
│       ├── config.py             # Dataclass configuration
│       ├── logging_utils.py      # Structured JSON logging
│       ├── scene_controller.py   # Module 1: Scene management
│       ├── vehicle_spawner.py    # Module 2: Vehicle placement
│       ├── camera_system.py      # Module 3: Camera intrinsics/extrinsics
│       ├── annotation.py         # Module 5: COCO annotation generation
│       ├── validation.py         # Module 6: Frame validation
│       └── orchestrator.py       # Module 7: Pipeline coordination
│
├── ue5_plugin/                   # C++ Unreal Engine 5 Plugin
│   ├── Source/VantageCV/
│   │   ├── Public/
│   │   │   ├── ResearchController.h   # ★ Research v2 controller
│   │   │   ├── DataCapture.h
│   │   │   └── SceneController.h
│   │   └── Private/
│   │       ├── ResearchController.cpp
│   │       ├── DataCapture.cpp
│   │       └── SceneController.cpp
│   └── VantageCV.uplugin
│
├── configs/
│   └── research_v2.yaml          # ★ Single config file
│
├── scripts/
│   ├── generate_v2.py            # ★ Primary entry point
│   ├── discover_level.py         # UE5 level discovery
│   ├── preflight_check.py        # Pre-generation validation
│   ├── download_coco.py          # COCO dataset downloader
│   └── filter_coco_vehicles.py   # Vehicle subset filter
│
├── data/
│   ├── research_v2/              # Generated output
│   │   ├── images/
│   │   ├── annotations/
│   │   ├── logs/
│   │   └── metadata/
│   └── coco_vehicles/            # Comparison data
│
└── tests/
    └── integration/
        └── setup_ue5_actors.py   # UE5 actor setup
```

## Architecture

```
┌────────────────────────────────────────────────────────────┐
│                    VantageCV Research v2                    │
├────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │   Scene     │───▶│   Vehicle   │───▶│   Camera    │    │
│  │ Controller  │    │   Spawner   │    │   System    │    │
│  │  (Module 1) │    │  (Module 2) │    │  (Module 3) │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│         │                   │                  │           │
│         ▼                   ▼                  ▼           │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    │
│  │  Renderer   │───▶│ Annotation  │───▶│ Validation  │    │
│  │  (UE5/Sim)  │    │  Generator  │    │  (Module 6) │    │
│  │  (Module 4) │    │  (Module 5) │    │             │    │
│  └─────────────┘    └─────────────┘    └─────────────┘    │
│                            │                  │           │
│                            ▼                  ▼           │
│                     ┌─────────────────────────────┐       │
│                     │    Dataset Orchestrator     │       │
│                     │         (Module 7)          │       │
│                     │  - Controls scene resets    │       │
│                     │  - Tracks statistics        │       │
│                     │  - Exports COCO JSON        │       │
│                     └─────────────────────────────┘       │
│                                                             │
└────────────────────────────────────────────────────────────┘
```

## Vehicle Distribution

| Count | Probability | Purpose |
|-------|-------------|---------|
| 1 vehicle | 20% | Class/pose/scale learning |
| 2-4 vehicles | 50% | Realistic traffic |
| 5-6 vehicles | 30% | Occlusion stress testing |

## Class Distribution

| Class | Weight |
|-------|--------|
| car | 35% |
| truck | 25% |
| bus | 15% |
| motorcycle | 15% |
| bicycle | 10% |

## Output Format

### COCO Annotations
```json
{
  "images": [...],
  "annotations": [
    {
      "id": 1,
      "image_id": 0,
      "category_id": 1,
      "bbox": [x, y, width, height],
      "area": 1234.5,
      "iscrowd": 0
    }
  ],
  "categories": [
    {"id": 1, "name": "car"},
    {"id": 2, "name": "truck"},
    ...
  ]
}
```

### Structured Logs
```json
{
  "timestamp": "2025-01-01T12:00:00.000Z",
  "module": "VehicleSpawner",
  "level": "INFO",
  "message": "Spawned 4 vehicles",
  "data": {"class_counts": {"car": 2, "truck": 1, "bus": 1}}
}
```

## Development Environment

### Requirements
- **Python**: 3.10+
- **UE5**: 5.3+ (optional for simulation mode)
- **GPU**: NVIDIA RTX 4080 or equivalent

### Installation
```bash
pip install -r requirements.txt
pip install -e .
```

### Running Tests
```bash
# Dry run (no UE5 required)
python scripts/generate_v2.py --dry-run

# Full generation (UE5 required)
python scripts/generate_v2.py --num-images 100
```

## UE5 Setup

See [ue5_plugin/SCENE_SETUP_GUIDE.md](ue5_plugin/SCENE_SETUP_GUIDE.md) for:
- Plugin installation
- Level setup
- Vehicle asset configuration
- Remote Control API setup

## Design Principles

1. **Correctness over Completeness**: Simple, working code beats complex, broken code
2. **Observability over Features**: Everything logs, nothing fails silently
3. **Controlled Scope over Realism**: Intentionally minimal for research validity
4. **Fail-Fast Philosophy**: Invalid frames rejected immediately with reasons

## License

This is a personal portfolio project. All rights reserved.

## Author

**Evan Petersen | Portfolio Project 2025**
