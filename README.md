# VantageCV: Synthetic Data Generation for Computer Vision

**Personal Portfolio Project | ML Engineering & Computer Vision**

I'm building a synthetic data generation system for computer vision that leverages Unreal Engine 5's photorealistic rendering with a Python/C++ hybrid pipeline, optimized for RTX 4080 hardware. This project demonstrates my ability to integrate game engine technology, deep learning, and high-performance computing.

## Key Features

- **Domain-Agnostic Plugin System**: Easily extensible architecture supporting multiple domains (industrial parts, automotive scenes, etc.)
- **Photorealistic Rendering**: Unreal Engine 5 with Lumen for realistic lighting and reflections
- **Custom C++ UE5 Plugins**: Native C++ plugins for high-performance scene control and data capture
- **Multi-Modal Annotations**: Automatic generation of bounding boxes, segmentation masks, and 6D poses
- **Domain Randomization**: Comprehensive randomization of lighting, materials, camera poses, and object arrangements
- **Multi-Task Learning**: Unified model for object detection, segmentation, and pose estimation
- **C++ Inference Optimization**: Custom TensorRT C++ backend for maximum RTX 4080 performance
- **Export Flexibility**: Support for COCO and YOLO annotation formats
- **MLflow Integration**: Complete experiment tracking and model versioning
- **Hybrid Python/C++ Pipeline**: Python ML automation with C++ performance-critical components

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    VantageCV System                          │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │  Unreal Engine 5 │───▶│  Python Bridge   │               │
│  │   C++ Plugins    │◀───│   Automation     │               │
│  │  (Native Code)   │    │   (Orchestration)│               │
│  └──────────────────┘    └──────────────────┘               │
│          │                        │                          │
│          ▼                        ▼                          │
│  ┌──────────────────┐    ┌──────────────────┐               │
│  │ Domain Configs   │    │  Annotation      │               │
│  │ - Industrial     │    │  Generator       │               │
│  │ - Automotive     │    │  (COCO/YOLO)     │               │
│  └──────────────────┘    └──────────────────┘               │
│                                   │                          │
│                                   ▼                          │
│                          ┌──────────────────┐               │
│                          │   ML Pipeline    │               │
│                          │  - PyTorch       │               │
│                          │  - Multi-Task    │               │
│                          │  - MLflow        │               │
│                          └──────────────────┘               │
│                                   │                          │
│                                   ▼                          │
│                          ┌──────────────────┐               │
│                          │ ONNX Export &    │               │
│                          │ TensorRT C++     │               │
│                          │ Optimization     │               │
│                          └──────────────────┘               │
└─────────────────────────────────────────────────────────────┘
```

## Project Structure

I'm using a **pragmatic, modular architecture** designed for iterative development and extensibility.

```
VantageCV/                         # Realistic starting point
├── README.md                      # This file
├── requirements.txt               # Python dependencies
├── .gitignore                     # Git ignore rules
│
├── vantagecv/                     # Core Python package
│   ├── __init__.py
│   ├── config.py                 # Config loader (YAML)
│   ├── generator.py              # Main generation logic
│   ├── annotator.py              # Annotation generation & export
│   ├── ue5_bridge.py             # UE5 Remote Control API client
│   └── utils.py                  # Helper functions
│
├── ue5_plugin/                    # C++ Unreal Engine 5 Plugin
│   ├── Source/
│   │   ├── VantageCV/
│   │   │   ├── Public/
│   │   │   │   ├── VantageCVModule.h
│   │   │   │   ├── SceneController.h
│   │   │   │   └── DataCapture.h
│   │   │   └── Private/
│   │   │       ├── VantageCVModule.cpp
│   │   │       ├── SceneController.cpp
│   │   │       └── DataCapture.cpp
│   │   └── VantageCV.Build.cs
│   └── VantageCV.uplugin
│
├── cpp/                           # C++ inference optimization
│   ├── inference/
│   │   ├── tensorrt_engine.h
│   │   ├── tensorrt_engine.cpp
│   │   └── cuda_kernels.cu       # Custom CUDA kernels
│   ├── CMakeLists.txt
│   └── build/                    # Build artifacts (gitignored)
│
├── domains/                       # Domain plugin system
│   ├── __init__.py
│   ├── base.py                   # Base domain class (abstract)
│   ├── industrial.py             # Industrial parts domain
│   └── automotive.py             # Automotive scenes
│
├── configs/                       # YAML configurations
│   ├── industrial.yaml           # Industrial domain config
│   └── automotive.yaml           # Automotive domain config
│
├── scripts/                       # Three essential scripts
│   ├── generate.py               # Generate synthetic dataset
│   ├── train.py                  # Train multi-task model
│   └── export.py                 # Export to ONNX with optimization
│
├── notebooks/                     # Jupyter notebooks
│   └── 01_quick_start.ipynb      # Quick start demo
│
├── data/                          # Generated data (gitignored)
│   └── synthetic/                # Synthetic images + annotations
│       ├── industrial/
│       │   ├── images/
│       │   └── annotations/
│       └── automotive/
│
└── models/                        # Saved models (gitignored)
    ├── checkpoints/              # Training checkpoints
    └── onnx/                     # Exported ONNX models
```

### Architecture Principles

- **Modularity**: Clean separation between configuration, domain logic, and execution
- **Extensibility**: New domains can be added by implementing the base class
- **Separation of Concerns**: Python for ML orchestration, C++ for performance-critical paths
- **Production-Ready Design**: Following software engineering best practices

## Development Environment

### Hardware

- **GPU**: NVIDIA RTX 4080 (16GB VRAM)
- **Development Machine**: Windows 11

### Software Stack

- **Rendering**: Unreal Engine 5.1+
- **C++ Development**: Visual Studio 2026
- **Python**: 3.9+
- **CUDA**: 11.8+
- **TensorRT**: 8.6+
- **Build Tools**: CMake 3.18+

### Pipeline Overview

#### 1. Synthetic Data Generation

UE5 renders photorealistic scenes with domain randomization, automatically generating annotations for object detection, segmentation, and 6D pose estimation.

#### 2. Multi-Task Model Training

PyTorch-based training pipeline with unified model architecture handling three CV tasks simultaneously.

#### 3. Inference Optimization

Export to ONNX and optimize with custom TensorRT C++ backend for real-time performance on RTX 4080.

## Development Roadmap

I'm building this project in **4 phases**:

**Status: Phase 1 Complete | Ready for Phase 2**

### Phase 1: Foundation (COMPLETED)
- [x] Set up project structure and dependencies (Python + C++)
- [x] Create basic UE5 C++ plugin for scene control
- [x] Implement Python-UE5 bridge communication (Remote Control API)
- [x] Implement base domain class with abstract methods
- [x] Create simple config loader (YAML)
- [x] Write industrial domain with UE5 communication
- [x] Test basic image capture and annotation generation
- [x] Create automotive domain (demonstrates extensibility)
- [x] Implement COCO and YOLO annotation exporters
- [x] Support both UE5 rendering and mock data modes

### Phase 2: Core Pipeline (4/5 COMPLETE)
- [x] Implement complete annotation pipeline (bbox, masks, 6D poses)
- [x] Add COCO and YOLO exporters
- [x] Build domain randomization system
- [x] Create data validation utilities
- [x] Complete UE5 C++ plugin implementation (SceneController, DataCapture)
- [ ] Generate first 1000-image photorealistic dataset

### Phase 3: ML Pipeline (Week 3)
- [ ] Implement multi-task model architecture
- [ ] Build training loop with proper logging
- [ ] Add evaluation metrics (mAP, mIoU, ADD-S)
- [ ] Train baseline model on synthetic data
- [ ] Compare with model trained on limited real data

### Phase 4: Optimization & Polish (Week 4)
- [ ] Export model to ONNX
- [ ] Build C++ TensorRT inference engine
- [ ] Optimize with custom CUDA kernels (if needed)
- [ ] Benchmark inference performance (Python vs C++)
- [ ] Add automotive domain (demonstrate extensibility)
- [ ] Create demo notebook and video
- [ ] Write documentation

### Phase 5: Documentation & Showcase
- [ ] Record demo video showing domain switching and real-time inference
- [ ] Create performance comparison charts
- [ ] Write technical blog post on architecture decisions
- [ ] Finalize documentation for portfolio presentation

## Performance Targets

*Benchmarks will be updated as development progresses*

### Target Metrics (To Be Validated)

**Synthetic Data Generation:**
- Rendering: 3-5 seconds/image (UE5 @ 1920x1080)
- Target throughput: 1000 images/hour

**Model Training (RTX 4080):**
- ResNet-50 backbone with multi-task heads
- Expected training time: 3-5 hours (10K images)

**Inference Optimization Goals:**
- Baseline PyTorch: ~40-50 FPS
- ONNX Runtime: ~80-100 FPS (2x improvement)
- TensorRT C++: ~180-200 FPS (4x improvement target)

**Success Criteria:**
- Demonstrate synthetic data reduces labeling requirements
- Achieve real-time inference (>30 FPS) with TensorRT
- Multi-task model performs competitively on all three tasks

## Key Implementation Details

### UE5 C++ Plugin Architecture

**Production-Ready Native C++ Implementation:**
- **VantageCVModule**: Plugin initialization with Remote Control API endpoint registration
- **SceneController**: Professional scene randomization (lighting, materials, camera, object placement)
- **DataCapture**: High-performance image capture and ground truth annotation extraction
- Comprehensive logging with dedicated log categories (LogVantageCV, LogSceneController, LogDataCapture)
- Async image writing via ImageWriteQueue for non-blocking capture
- JSON serialization for Python-compatible annotation format
- Full type safety with UE5 reflection system (UFUNCTION, UPROPERTY, USTRUCT)

**Plugin Features:**
- Multi-light randomization (DirectionalLight, PointLight, SpotLight) with intensity/color/direction control
- Dynamic material instance creation for runtime parameter randomization (metallic, roughness, specular, base color)
- Spherical camera placement with configurable distance and FOV ranges
- Actor spawning with collision handling and lifetime tracking
- 3D-to-2D bounding box projection from actor bounds
- 6D pose extraction (translation, rotation, scale) in JSON format
- Segmentation mask rendering via scene capture source switching
- Tag-based actor filtering for domain-specific annotation

**Python Bridge Integration:**
```python
from vantagecv.ue5_bridge import UE5Bridge

bridge = UE5Bridge(host="localhost", port=30010)
bridge.call_function("SceneController", "RandomizeLighting", 
    MinIntensity=50000.0, MaxIntensity=100000.0,
    MinTemperature=5000.0, MaxTemperature=6500.0)
bridge.call_function("DataCapture", "CaptureFrame",
    OutputPath="F:/dataset/img_0001.png", Width=1920, Height=1080)
```

See [ue5_plugin/README.md](ue5_plugin/README.md) for complete API documentation and installation instructions.

### UE5 Integration Strategy

**Custom C++ Plugin Approach** (chosen for maximum performance):
- Native C++ plugin for scene manipulation and data capture
- Python bridge using UE5's Remote Control API for high-level orchestration
- Direct memory access for image data transfer via render targets
- Async rendering pipeline for maximum throughput

Alternative approaches considered:
- Remote Control API only (simpler but slower)
- Python Plugin (good, but less performant than native C++)

### Domain Configuration

YAML-based configuration for object spawning probabilities, randomization ranges (lighting, camera, materials), and annotation formats.

### Multi-Task Model Architecture

Shared ResNet-50 backbone with Feature Pyramid Network feeding three task-specific heads: Detection (Faster R-CNN), Segmentation (Mask R-CNN), and Pose Estimation (PoseCNN).

### Loss Function Weighting

Weighted multi-task loss combining detection, segmentation, and pose estimation losses.

## Domain Plugin System

Extensible architecture allows adding new domains by implementing the base domain class with methods for scene setup, randomization, and object class definitions.

## License

This is a personal portfolio project. All rights reserved.

## About This Project

This portfolio project showcases my expertise in:
- Computer vision and deep learning
- High-performance C++ and GPU programming
- Game engine integration for ML applications
- End-to-end ML system design and optimization

Built to demonstrate production-level engineering skills for ML/CV roles.

## Acknowledgments

- Unreal Engine 5 by Epic Games
- PyTorch by Meta AI
- ONNX Runtime by Microsoft
- MLflow by Databricks
- Computer Vision community

## Roadmap

- [x] **Phase 1**: Core infrastructure and plugin system (COMPLETE)
- [ ] **Phase 2**: Industrial and automotive domains (in progress - mock data working)
- [ ] **Phase 3**: Multi-task learning pipeline
- [ ] **Phase 4**: ONNX optimization and benchmarking
- [ ] **Phase 5**: Additional domains (retail, medical, agriculture)
- [ ] **Phase 6**: Real-time inference API
- [ ] **Phase 7**: Web-based visualization dashboard
- [ ] **Phase 8**: Distributed rendering support


---

**Evan Petersen | Portfolio Project 2025**
