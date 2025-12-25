# VantageCV Architecture

## System Overview

VantageCV is a hybrid Python/C++ system for generating photorealistic synthetic training data using Unreal Engine 5.

```
┌─────────────────────────────────────────────────────────────────┐
│                        Python Interface                         │
│  ┌────────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Generator.py  │→│ Annotator.py │→│  MLflow Logger   │   │
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
│          ├── coco.json                                          │
│          └── yolo/                                              │
└───────────────────────────────────────────────────────────────────┘
            │
            │ ONNX models
            ↓
┌───────────────────────────────────────────────────────────────────┐
│                  TensorRT Inference Engine                       │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              C++/CUDA Implementation                     │   │
│  │  - Custom CUDA kernels (preprocessing, NMS)             │   │
│  │  - TensorRT optimization                                │   │
│  │  - FP16/INT8 quantization                               │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────────────┘
```

## Component Details

### Python Layer (`vantagecv/`)

**Generator** - Orchestrates synthetic data generation
- Connects to UE5 via Remote Control API
- Batch generation with domain randomization
- MLflow experiment tracking
- Configurable via YAML

**Annotator** - Converts UE5 scene data to CV formats
- COCO JSON format
- YOLO text format  
- Semantic segmentation masks
- 6DOF pose annotations

**Config** - YAML-driven configuration system
- Domain-specific settings (automotive, industrial)
- Scene composition parameters
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

### C++ Inference (`cpp/inference_engine/`)

**TensorRTEngine** - Optimized model inference
- ONNX → TensorRT conversion
- FP16 precision for RTX GPUs
- Batch processing support
- CUDA stream management

**Custom CUDA Kernels**
- Preprocessing (normalization, letterbox)
- Non-Maximum Suppression (NMS)
- Post-processing (bounding box decoding)

## Data Flow

1. **Python** sends HTTP request to UE5 Remote Control API
2. **VantageCVSubsystem** receives request, finds DataCapture actor
3. **DataCapture** renders scene using configured camera
4. **IImageWrapper** compresses to PNG on background thread
5. **Scene data** extracted for annotation generation
6. **Python Annotator** converts to COCO/YOLO format
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

## Domain Plugin System

Domains extend VantageCV for specific use cases:

```python
# domains/automotive.py
class AutomotiveDomain(BaseDomain):
    def configure_scene(self, config):
        # Urban environment setup
        # Vehicle spawning
        # Traffic simulation
        
    def generate_annotations(self, scene_data):
        # Vehicle bounding boxes
        # Lane detection labels
        # Traffic sign classification
```

## Performance Characteristics

- **Rendering**: ~60ms per 1920x1080 frame (RTX 4080)
- **PNG export**: ~50ms async (IImageWrapper)
- **Annotation**: ~10ms per frame
- **TensorRT inference**: ~5ms per image (FP16)

Total throughput: **~8 FPS** for full pipeline (rendering + annotation + inference)

## Extension Points

1. **New domains** - Add to `domains/` with domain-specific logic
2. **Custom annotators** - Subclass `BaseAnnotator` for new formats
3. **Rendering modes** - Add to DataCapture (depth, normal, optical flow)
4. **Randomization** - Extend SceneController with new variation types

## References

- [Unreal Engine Subsystems](https://docs.unrealengine.com/5.0/en-US/subsystems-in-unreal-engine/)
- [Remote Control API](https://docs.unrealengine.com/5.0/en-US/remote-control-api-in-unreal-engine/)
- [IImageWrapper Module](https://docs.unrealengine.com/5.0/en-US/API/Runtime/ImageWrapper/)
- [TensorRT Documentation](https://docs.nvidia.com/deeplearning/tensorrt/)
