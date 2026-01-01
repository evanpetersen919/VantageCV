# VantageCV Asset Setup - SIMPLIFIED

## The Simple Way

### 1. Download ONE Asset Pack (5 minutes)

**City Sample Project (FREE)** - This is all you need:
1. Open Epic Games Launcher
2. Go to Unreal Engine → Marketplace
3. Search "City Sample"
4. Click "Free" → Add to Project → Select VantageCV_Project

This pack includes:
- ✅ Vehicles (cars, trucks, buses, motorcycles)
- ✅ Traffic signs and lights
- ✅ Street lamps and poles
- ✅ Jersey barriers and guardrails
- ✅ Trees and bushes
- ✅ Street furniture (benches, trash cans, hydrants)
- ✅ Buildings and structures

**That's literally everything you need from ONE free download.**

### 2. Organize into 5 Folders (5 minutes)

In UE5 Content Browser, create this structure and drag assets in:

```
Content/Props/
├── Signs/      (drag ANY signs here - stop, yield, speed limit, parking, etc.)
├── Poles/      (drag ANY poles here - street lamps, traffic lights, utility poles)
├── Barriers/   (drag ANY barriers - jersey barriers, guardrails, bollards)
├── Vegetation/ (drag ANY plants - trees, bushes, shrubs)
└── Furniture/  (drag ANY objects - fire hydrants, benches, trash cans)
```

**That's it.** The system randomly picks from whatever meshes are in each folder.

### 3. Minimum Setup (Use City Sample Assets)

After adding City Sample to your project, find these in Content Browser and drag to folders:

| Folder | What to Grab from City Sample |
|--------|-------------------------------|
| Signs/ | Search "sign" - grab 3-5 different ones |
| Poles/ | Search "lamp" or "light" or "pole" - grab 3-4 |
| Barriers/ | Search "barrier" or "guard" - grab 2-3 |
| Vegetation/ | Search "tree" or "bush" - grab 3-5 |
| Furniture/ | Search "hydrant" or "bench" or "trash" - grab 2-3 |

**Total: ~15-20 meshes, 5 minutes of dragging.**

### 3. How It Works

The C++ code automatically:
- Finds meshes in each category folder
- Picks random meshes when spawning
- Gets mesh bounds at runtime
- Adjusts position to place on ground
- Applies scale variations (0.9-1.1x)
- Handles collision/spacing based on actual size

### 4. Add the C++ Component

Add `DistractorSpawner` component to your `DomainRandomization` actor:

```cpp
// In DomainRandomizationActor.h
UPROPERTY()
class UDistractorSpawner* DistractorSpawner;

// In BeginPlay()
DistractorSpawner = NewObject<UDistractorSpawner>(this);
DistractorSpawner->RegisterComponent();
```

### 5. Call from Python Integration

The existing `SceneController.cpp` will pass distractor data from Python:

```cpp
void ASceneController::SpawnScene(FString JsonParams)
{
    // Parse JSON from Python
    TSharedPtr<FJsonObject> JsonObject;
    TSharedRef<TJsonReader<>> Reader = TJsonReaderFactory<>::Create(JsonParams);
    FJsonSerializer::Deserialize(Reader, JsonObject);

    // Get distractors array
    TArray<FDistractorData> Distractors;
    const TArray<TSharedPtr<FJsonValue>>* DistractorArray;
    if (JsonObject->TryGetArrayField(TEXT("distractors"), DistractorArray))
    {
        for (const TSharedPtr<FJsonValue>& Value : *DistractorArray)
        {
            TSharedPtr<FJsonObject> Obj = Value->AsObject();
            FDistractorData Data;
            Data.Name = Obj->GetStringField(TEXT("name"));
            Data.Category = Obj->GetStringField(TEXT("category"));
            Data.X = Obj->GetNumberField(TEXT("x"));
            Data.Y = Obj->GetNumberField(TEXT("y"));
            Data.Scale = Obj->GetNumberField(TEXT("scale"));
            Data.Rotation = Obj->GetNumberField(TEXT("rotation"));
            Distractors.Add(Data);
        }
    }

    // Spawn distractors
    DistractorSpawner->SpawnDistractors(Distractors);
}
```

### 6. Testing

Run your Python script:
```bash
python scripts/generate_research.py --num-images 1
```

The system will:
1. Python generates scene with distractors
2. Sends JSON to UE5 with category names
3. UE5 picks random mesh from that category folder
4. Automatically handles scale/positioning
5. No manual configuration needed

## How Scale/Size Variations Are Handled

### Problem
- Fire hydrant: 1m tall
- Street lamp: 5m tall
- Tree: 8m tall
- How to place them correctly?

### Solution (Automatic in C++)

```cpp
// 1. Get actual mesh size at runtime
FBox Bounds = Mesh->GetBoundingBox();
FVector MeshSize = Bounds.GetSize(); // e.g., (50, 50, 500) for street lamp

// 2. Adjust Z to place on ground (not floating/buried)
float HalfHeight = MeshSize.Z * 0.5f * Scale;
Location.Z = HalfHeight; // Bottom of mesh touches ground

// 3. Apply scale with variation
float ScaleVariation = FMath::RandRange(0.9f, 1.1f);
Actor->SetActorScale3D(FVector(Scale * ScaleVariation));

// 4. Spacing based on actual size
float ObjectRadius = FMath::Max(MeshSize.X, MeshSize.Y) * 0.5f * Scale;
float MinSpacing = ObjectRadius * 2.0f; // Larger objects need more space
```

### Example

**Street Lamp (5m tall):**
- Bounds: (0.5m × 0.5m × 5m)
- HalfHeight: 2.5m
- Placed at Z=2.5m → bottom at ground level
- MinSpacing: 0.5m × 2 = 1m

**Tree (8m tall, 3m wide):**
- Bounds: (3m × 3m × 8m)
- HalfHeight: 4m
- Placed at Z=4m → bottom at ground level
- MinSpacing: 3m × 2 = 6m (more space around trees)

## Comparison

### Old Approach (COMPLEX):
1. Download assets ✓
2. Tag each asset manually ✗
3. Create Blueprint for each asset ✗
4. Update C++ with hardcoded paths ✗
5. Create 5 separate levels ✗
6. Configure each level ✗

### New Approach (SIMPLE):
1. Download assets ✓
2. Drag into category folders ✓
3. Done ✓

## Benefits

✅ **No manual configuration** - Just organize by folder  
✅ **Add assets anytime** - Drop new meshes in folders, automatically used  
✅ **Automatic scale handling** - Works with any mesh size  
✅ **Proper ground placement** - No floating/buried objects  
✅ **Intelligent spacing** - Larger objects get more space  
✅ **Random variety** - Picks random mesh from category each spawn  

## What You Actually Need to Do

1. Open Epic Games Launcher → Marketplace
2. Download City Sample Project (FREE)
3. Download Vehicle Variety Pack (FREE)
4. In UE5 Project: Create folder structure (Props/TrafficSigns, Props/Poles, etc.)
5. Drag assets from City Sample into category folders
6. Add DistractorSpawner.cpp/.h to your plugin
7. Compile
8. Run Python script

Done. The system handles everything else automatically.
