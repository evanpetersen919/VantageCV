# VantageCV Unreal Engine 5 Plugin

## Overview
Professional UE5 plugin for photorealistic synthetic data generation with ground truth annotations. Enables Python-driven control of scene randomization and automated capture of RGB images, bounding boxes, segmentation masks, and 6D poses.

## Features
- **Scene Randomization**: Lighting, materials, camera, and object placement control
- **High-Resolution Capture**: Configurable image resolution up to 4K+
- **Multi-Modal Annotations**: Bounding boxes, segmentation masks, 6D poses in JSON format
- **Remote Control API**: Python integration via HTTP for automated dataset generation
- **Professional Logging**: Comprehensive UE_LOG statements for debugging

## Installation

### 1. Copy Plugin to UE5 Project
```bash
# Copy plugin to your UE5 project's Plugins folder
cp -r ue5_plugin/Source/VantageCV <YourProject>/Plugins/VantageCV
cp ue5_plugin/VantageCV.uplugin <YourProject>/Plugins/VantageCV/
```

### 2. Enable Plugin in Unreal Editor
1. Open your UE5 project in Unreal Editor
2. Go to **Edit > Plugins**
3. Search for "VantageCV"
4. Check the **Enabled** checkbox
5. Restart Unreal Editor

### 3. Enable Remote Control Web Interface
1. Go to **Edit > Project Settings**
2. Navigate to **Plugins > Remote Control**
3. Enable **Remote Control Web Interface**
4. Set **Remote Control HTTP Server Port** to `30010`
5. Restart Unreal Editor

### 4. Verify Installation
Check Output Log for:
```
LogVantageCV: VantageCV Module Started Successfully
LogVantageCV: Remote Control Endpoints Registered for SceneController and DataCapture actors
```

## Usage

### Place Actors in Scene
1. Drag **SceneController** actor into level (manages randomization)
2. Drag **DataCapture** actor into level (captures images and annotations)
3. Tag objects you want to annotate with custom tags (e.g., "PCB", "Vehicle", "Pedestrian")

### Python Integration
```python
from vantagecv.ue5_bridge import UE5Bridge

# Connect to UE5 Remote Control API
bridge = UE5Bridge(host="localhost", port=30010)

# Randomize scene
bridge.call_function("SceneController", "RandomizeLighting", 
    MinIntensity=50000.0, MaxIntensity=100000.0,
    MinTemperature=5000.0, MaxTemperature=6500.0)

bridge.call_function("SceneController", "RandomizeMaterials",
    TargetTags=["PCB", "Component"])

bridge.call_function("SceneController", "RandomizeCamera",
    MinDistance=50.0, MaxDistance=200.0, MinFOV=60.0, MaxFOV=90.0)

# Capture data
bridge.call_function("DataCapture", "CaptureFrame",
    OutputPath="F:/datasets/industrial/images/0001.png",
    Width=1920, Height=1080)

bbox_json = bridge.call_function("DataCapture", "GenerateBoundingBoxes",
    TargetTags=["PCB", "Component"])

pose_json = bridge.call_function("DataCapture", "GeneratePoseAnnotations",
    TargetTags=["PCB", "Component"])
```

## API Reference

### SceneController

#### `RandomizeLighting(MinIntensity, MaxIntensity, MinTemperature, MaxTemperature)`
Randomizes all lights in scene within specified ranges.
- **MinIntensity/MaxIntensity**: Light intensity range (lumens)
- **MinTemperature/MaxTemperature**: Color temperature range (Kelvin)

#### `RandomizeMaterials(TargetTags)`
Creates dynamic material instances and randomizes metallic, roughness, specular.
- **TargetTags**: Array of actor tags to target (e.g., ["PCB", "Component"])

#### `RandomizeCamera(MinDistance, MaxDistance, MinFOV, MaxFOV)`
Randomizes camera position and field of view.
- **MinDistance/MaxDistance**: Camera distance from origin (cm)
- **MinFOV/MaxFOV**: Field of view range (degrees)

#### `SpawnRandomObjects(NumObjects, ObjectClasses)`
Spawns objects at random positions with random rotations.
- **NumObjects**: Number of objects to spawn
- **ObjectClasses**: Array of object class names

#### `ClearSpawnedObjects()`
Destroys all previously spawned objects.

#### `SetLightingPreset(PresetName)`
Applies predefined lighting configuration.
- **PresetName**: "IndustrialLED", "OutdoorSun", "StudioSoft"

### DataCapture

#### `CaptureFrame(OutputPath, Width, Height)`
Captures current scene to PNG file.
- **OutputPath**: Full path to output PNG (e.g., "F:/dataset/img_0001.png")
- **Width/Height**: Image resolution in pixels
- **Returns**: Boolean success

#### `GenerateBoundingBoxes(TargetTags)`
Generates 2D bounding boxes for all tagged actors.
- **TargetTags**: Array of actor tags to annotate
- **Returns**: JSON string with annotations

**JSON Format:**
```json
{
  "annotations": [
    {
      "class": "BP_PCB_C",
      "x_min": 320.5,
      "y_min": 180.2,
      "x_max": 1580.3,
      "y_max": 920.8,
      "width": 1259.8,
      "height": 740.6
    }
  ]
}
```

#### `GenerateSegmentationMask(OutputPath, Width, Height)`
Renders semantic segmentation mask to PNG.
- **OutputPath**: Full path to output PNG
- **Width/Height**: Mask resolution in pixels
- **Returns**: Boolean success

#### `GeneratePoseAnnotations(TargetTags)`
Generates 6D pose (translation, rotation, scale) for all tagged actors.
- **TargetTags**: Array of actor tags to annotate
- **Returns**: JSON string with pose data

**JSON Format:**
```json
{
  "poses": [
    {
      "class": "BP_PCB_C",
      "translation": [150.0, 200.0, 50.0],
      "rotation": [0.0, 0.0, 90.0],
      "scale": [1.0, 1.0, 1.0]
    }
  ]
}
```

#### `SetResolution(Width, Height)`
Updates render target resolution.
- **Width/Height**: Target resolution in pixels

## Build Configuration

### VantageCV.Build.cs Dependencies
```csharp
PublicDependencyModuleNames.AddRange(new string[]
{
    "Core",
    "CoreUObject",
    "Engine",
    "InputCore",
    "RenderCore",
    "RHI",
    "ImageWrapper",
    "RemoteControl",           // Remote Control API
    "RemoteControlProtocol",   // HTTP protocol
    "ImageWriteQueue",         // Async image export
    "JsonUtilities",           // JSON serialization
    "Json"                     // JSON parsing
});
```

### Required Plugins
- **RemoteControl**: Enabled in VantageCV.uplugin
- **RemoteControlWebInterface**: Enabled in Project Settings

## Architecture

### Module Lifecycle
```cpp
FVantageCVModule::StartupModule()
  → Verify RemoteControl module availability
  → Register Remote Control endpoints
  → Log initialization status

FVantageCVModule::ShutdownModule()
  → Unregister endpoints
  → Cleanup resources
```

### Scene Randomization Flow
```
Python Bridge → HTTP Request → Remote Control API → SceneController Actor
  → GetSceneLights() → Randomize intensity/color/direction
  → GetActorsByTags() → Randomize material parameters
  → GetPlayerCameraManager() → Randomize position/FOV
```

### Data Capture Flow
```
Python Bridge → HTTP Request → Remote Control API → DataCapture Actor
  → CaptureComponent->CaptureScene() → RenderTarget
  → ReadRenderTargetPixels() → TArray<FColor>
  → ImageWriteQueue->Enqueue() → Async PNG export
```

### Annotation Extraction Flow
```
DataCapture Actor
  → GetAnnotatableActors(Tags)
  → For each actor:
      → GetActorBounds() → Calculate 3D bounding box
      → ProjectWorldToScreen() → Convert to 2D screen space
      → GetActorLocation/Rotation/Scale() → 6D pose
  → FJsonObject serialization → JSON string
```

## Troubleshooting

### Plugin Not Loading
- Check Output Log for "VantageCV Module Started Successfully"
- Verify RemoteControl plugin is enabled
- Regenerate Visual Studio project files (Right-click .uproject → Generate VS project files)

### Remote Control API Not Responding
- Check Project Settings → Remote Control → Web Interface Enabled
- Verify port 30010 is not blocked by firewall
- Test connection: `curl http://localhost:30010/remote/info`

### No Annotations Generated
- Verify actors are tagged correctly (Actor Details → Tags)
- Check TargetTags array matches actor tags exactly
- Enable LogDataCapture logging: `Log LogDataCapture VeryVerbose`

### Black/Empty Captures
- Ensure SceneCaptureComponent2D is positioned correctly
- Check RenderTarget initialization in DataCapture::BeginPlay()
- Verify lighting is present in scene

## Performance Optimization

### High-Resolution Captures
- Use async ImageWriteQueue (already implemented)
- Disable post-processing for faster rendering
- Reduce SceneCaptureComponent2D quality settings

### Large Batch Generation
- Call ClearSpawnedObjects() periodically to avoid memory bloat
- Use Level Streaming for complex scenes
- Consider Garbage Collection calls after N captures

## Development

### Adding Custom Annotations
Extend `DataCapture` class with new UFUNCTION:
```cpp
UFUNCTION(BlueprintCallable, Category = "VantageCV")
FString GenerateCustomAnnotation(const TArray<FString>& TargetTags);
```

### Custom Randomization
Extend `SceneController` class with domain-specific logic:
```cpp
UFUNCTION(BlueprintCallable, Category = "VantageCV")
void RandomizeWeather(float MinRainIntensity, float MaxRainIntensity);
```

### Logging
Use dedicated log categories:
```cpp
DEFINE_LOG_CATEGORY_STATIC(LogVantageCV, Log, All);
UE_LOG(LogVantageCV, Log, TEXT("Message: %s"), *YourString);
```

## License
See LICENSE file in project root.

## Author
Evan Petersen - December 2025

## Support
Report issues at: https://github.com/evanpetersen919/VantageCV
