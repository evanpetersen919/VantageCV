# VantageCV Architecture

## System Overview

VantageCV is a hybrid Python/C++ system for generating photorealistic synthetic training data using Unreal Engine 5.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Python Interface                         │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  orchestrator  │→│ annotation.py │→│  MLflow Logger   │   │
│  │  .py           │  │              │  │                  │   │
│  └────────┬───────┘  └──────────────┘  └──────────────────┘   │
│           │                                                      │
│           │ HTTP/REST (Remote Control API)                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            ↓
┌───────────┴──────────────────────────────────────────────────────┐
│                    Unreal Engine 5.7                             │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │               VantageCV C++ Plugin                       │   │
│  │  ┌──────────────────┐  ┌───────────────────────────┐   │   │
│  │  │ VantageCVSubsystem│→│   Remote Control Module   │   │   │
│  │  └────────┬──────────┘  └───────────────────────────┘   │   │
│  │           │                                              │   │
│  │           ├→ DataCapture Actor                          │   │
│  │           │    - SceneCaptureComponent2D                │   │
│  │           │    - Async PNG export (IImageWrapper)       │   │
│  │           │                                              │   │
│  │           └→ SceneController Actor                      │   │
│  │                - Lighting randomization                 │   │
│  │                - Material variation                     │   │
│  │                - Object placement                       │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                Photorealistic Rendering                 │   │
│  │  - Path tracing / Lumen GI                              │   │
│  │  - Nanite geometry                                      │   │
│  │  - MetaHuman characters                                 │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
            │
            │ PNG images + JSON annotations
            ↓
┌───────────────────────────────────────────────────────────────────┐
│                    Training Data Output                          │
│  data/synthetic/{domain}/                                        │
│    ├── images/                                                   │
│    │     ├── 00001.png                                          │
│    │     └── ...                                                │
│    └── annotations/                                             │
│          └── coco.json                                          │
└───────────────────────────────────────────────────────────────────┘
```

## Component Details

### Python Layer (`vantagecv/research_v2/`)

**orchestrator.py** - Orchestrates synthetic data generation
- Connects to UE5 via Remote Control API
- Batch generation with domain randomization
- MLflow experiment tracking
- Configurable via YAML

**annotation.py** - Converts UE5 scene data to CV formats
- COCO JSON format, 2D bounding boxes

**config.py** - YAML-driven configuration system
- Scene composition parameters (`configs/research_v2.yaml`, `configs/vehicles.yaml`, `configs/levels/`, `configs/zones/`)
- Rendering quality presets

### UE5 Plugin (`ue5_plugin/`)

**VantageCVSubsystem** (Engine Subsystem)
- Global singleton accessible via Remote Control API
- Manages actor lifecycle in Editor mode
- Bridges Python HTTP calls to C++ actor methods

**DataCapture Actor**
- `USceneCaptureComponent2D` for rendering
- Async PNG export via `IImageWrapper` (research-grade quality)
- Bounding box generation from scene geometry
- Segmentation mask rendering
- Pose annotation extraction

**SceneController Actor**
- Procedural lighting variation
- Material parameter randomization  
- Dynamic object spawning
- Camera path generation

## Data Flow

1. **Python** sends HTTP request to UE5 Remote Control API
2. **VantageCVSubsystem** receives request, finds DataCapture actor
3. **DataCapture** renders scene using configured camera
4. **IImageWrapper** compresses to PNG on background thread
5. **Scene data** extracted for annotation generation
6. **annotation.py** converts to COCO format
7. **MLflow** logs images, annotations, and metadata

## Key Design Decisions

### Why Engine Subsystem?
- **Globally accessible** without needing object paths
- **Persists across level loads** in Editor mode
- **Production pattern** used by Epic for editor tools

### Why IImageWrapper over ImageWriteQueue?
- **Higher quality** PNG compression (100% quality setting)
- **Async execution** doesn't block rendering thread
- **More control** over compression parameters
- **Research-grade** output suitable for publication

### Why Hybrid Python/C++?
- **Python** for experimentation, visualization, ML training
- **C++** for performance-critical rendering and inference
- **Best of both** - rapid iteration + production speed

## Extension Points

1. **Rendering modes** - Add to DataCapture (depth, normal, optical flow)
2. **Randomization** - Extend SceneController with new variation types
3. **Annotation formats** - Extend `annotation.py` beyond COCO 2D boxes

## References

- [Unreal Engine Subsystems](https://docs.unrealengine.com/5.0/en-US/subsystems-in-unreal-engine/)
- [Remote Control API](https://docs.unrealengine.com/5.0/en-US/remote-control-api-in-unreal-engine/)
- [IImageWrapper Module](https://docs.unrealengine.com/5.0/en-US/API/Runtime/ImageWrapper/)
