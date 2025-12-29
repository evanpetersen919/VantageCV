# VantageCV - UE5 Scene Setup Guide for Automotive Domain

## Asset Requirements

### Free Asset Sources (Recommended for Testing)

**1. Unreal Engine Marketplace (FREE)**
- **City Sample Vehicles** (Epic Games) - High-quality cars, buses
- **Vehicle Variety Pack** - Multiple vehicle types
- **Modular Neighborhood Pack** - Urban environments
- **Road and Path Pack** - Streets, highways

**2. Quixel Megascans (FREE with UE5)**
- Search for: "car", "vehicle", "road", "urban"
- Photorealistic assets
- Access via Bridge in UE5

**3. SketchFab (FREE CC0)**
- Download low-poly vehicles
- Import as FBX to UE5

**4. TurboSquid (Some FREE)**
- Search: "low poly car", "vehicle pack"

### Minimum Required Assets

For 5 vehicle classes, you need:
- **2-3 car models** (sedan, SUV, sports car)
- **1-2 truck models** (pickup, delivery truck)
- **1 bus model** (city bus or school bus)
- **1-2 motorcycle models**
- **1-2 bicycle models**

**Environment Assets:**
- Road/street materials (asphalt, lane markings)
- Urban buildings (modular or static)
- Lighting (sun, street lights)
- Sky dome

---

## UE5 Project Setup

### Step 1: Create New Project

1. Open **Epic Games Launcher** → **Unreal Engine 5.7.1**
2. Create new project:
   - Template: **Blank** (or **Third Person** for quick camera setup)
   - Project Type: **Blueprint** or **C++**
   - Location: `C:/UnrealProjects/VantageCV_Automotive`
   - Name: `VantageCV_Automotive`

### Step 2: Install VantageCV Plugin

```powershell
# Copy plugin to project
Copy-Item -Recurse F:/vscode/VantageCV/ue5_plugin/* "C:/UnrealProjects/VantageCV_Automotive/Plugins/VantageCV/"
```

3. **Right-click** `.uproject` file → **Generate Visual Studio project files**
4. Open project in UE5
5. **Edit → Plugins** → Search "VantageCV" → Enable → Restart

### Step 3: Enable Remote Control

1. **Edit → Project Settings**
2. **Plugins → Remote Control**
3. Enable **Remote Control Web Interface**
4. Set **Remote Control HTTP Server Port**: `30010`
5. Restart editor

---

## Scene Setup

### Level 1: Basic Test Scene (15 minutes)

**Goal:** Get 1 vehicle generating data ASAP

1. **Create New Level**
   - File → New Level → Empty Level
   - Save as `Levels/VehicleCapture_Test`

2. **Add Essential Actors**
   - **Directional Light** (Sun)
     - Drag from Place Actors panel
     - Intensity: 10.0
     - Rotation: (-50, 0, 0) for daylight
   
   - **Sky Atmosphere**
     - Place Actors → Visual Effects → Sky Atmosphere
   
   - **SkyLight**
     - Intensity: 1.0
     - Check "Real Time Capture"
   
   - **Post Process Volume**
     - Check "Infinite Extent (Unbound)"
     - Settings → Auto Exposure: Disabled (for consistent captures)

3. **Add Ground Plane**
   - Place Actors → Basic → Plane
   - Scale: (100, 100, 1)
   - Material: Search "M_Asphalt" or create simple gray material

4. **Import First Vehicle**
   - Content Browser → Import (FBX/Static Mesh)
   - Drag vehicle into scene
   - **Add Tag**: Select vehicle → Details panel → Tags → Add "car"

5. **Add VantageCV Actors**
   - Place Actors → Search "SceneController" → Drag to level
   - Place Actors → Search "DataCapture" → Drag to level
   - Position DataCapture camera looking at vehicle

6. **Test Capture**
   - Play in Editor
   - Check Output Log for: `LogVantageCV: VantageCV Module Started Successfully`

---

### Level 2: Production Scene (Multi-Vehicle)

**Goal:** Realistic street scene with multiple vehicles

#### Scene Layout

```
Urban Street Scene:
├── Road (100m × 20m)
├── Sidewalks (both sides)
├── Buildings (background)
├── Street Lights (6-8)
├── Traffic Lights (2-4)
└── Spawn Zones (marked with box triggers)
    ├── Car Zone (4-6 spawn points)
    ├── Truck Zone (2 spawn points)
    ├── Bus Zone (1-2 spawn points)
    ├── Motorcycle Zone (2-3 spawn points)
    └── Bicycle Zone (2-3 spawn points)
```

#### Camera Setup

**Option A: Fixed Camera Positions** (Simple)
- Place 5-10 camera actors at different angles
- Tag with "CameraPoint"
- SceneController randomly selects one per capture

**Option B: Random Camera Orbit** (Better)
- DataCapture actor uses `RandomizeCamera()` function
- Orbits around scene center
- Distance: 500-2000 cm (5-20 meters)
- FOV: 60-90 degrees

---

## Vehicle Configuration

### Tagging System (CRITICAL)

Each vehicle must have proper tags:

1. **Select vehicle in level**
2. **Details panel → Tags**
3. **Add tags:**
   - Class tag: `car`, `truck`, `bus`, `motorcycle`, or `bicycle`
   - Optional: `vehicle` (for all vehicles)

Example:
```
Car_01: Tags = ["car", "vehicle"]
Truck_01: Tags = ["truck", "vehicle"]
Bus_01: Tags = ["bus", "vehicle"]
```

### Blueprint Setup (Optional but Recommended)

Create Blueprint for each vehicle class:

1. **Content Browser → Right-click → Blueprint Class → Actor**
2. Name: `BP_Car_Base`
3. Add **Static Mesh Component** → Set mesh
4. **Class Defaults → Tags** → Add `["car", "vehicle"]`
5. Duplicate for other classes (BP_Truck_Base, BP_Bus_Base, etc.)

---

## Lighting Presets

Configure for different times of day:

### Preset 1: Clear Day
- Directional Light Intensity: 10.0
- Color Temperature: 6500K
- Sun Angle: -50 degrees

### Preset 2: Overcast
- Directional Light Intensity: 3.0
- Color Temperature: 7000K
- Sky Light Intensity: 1.5

### Preset 3: Night
- Directional Light Intensity: 0.1
- Street Lights: Intensity 5000 (Point Lights)
- Sky Light Intensity: 0.2

---

## Material Setup

### Vehicle Materials

For best randomization results:

1. **Create Master Material**
   - Right-click → Material → `M_Vehicle_Master`
   - Add parameters:
     - `BaseColor` (Vector3)
     - `Metallic` (Scalar)
     - `Roughness` (Scalar)
     - `ClearCoat` (Scalar) for car paint

2. **Create Material Instances**
   - Right-click M_Vehicle_Master → Create Material Instance
   - Name: `MI_Vehicle_Random`
   - Apply to vehicles

3. **SceneController will randomize these at runtime**

---

## Quick Start Checklist

- [ ] UE5 project created
- [ ] VantageCV plugin installed and enabled
- [ ] Remote Control Web Interface enabled (port 30010)
- [ ] At least 1 vehicle of each class imported
- [ ] All vehicles tagged correctly (car/truck/bus/motorcycle/bicycle)
- [ ] SceneController actor placed in level
- [ ] DataCapture actor placed with camera view
- [ ] Directional Light + Sky Atmosphere added
- [ ] Test: Play in Editor → Check Output Log for VantageCV messages

---

## Test Python Connection

After scene setup:

```powershell
cd F:/vscode/VantageCV

# Test connection
python -c "from vantagecv.ue5_bridge import UE5Bridge; bridge = UE5Bridge(); print('Connected!' if bridge.is_connected() else 'Failed')"

# Test capture
python scripts/generate.py --domain automotive --num-images 10 --use-ue5
```

---

## Troubleshooting

**"Remote Control Module Not Found"**
- Verify plugin enabled: Edit → Plugins → VantageCV
- Regenerate project files: Right-click .uproject → Generate VS files

**"No actors found with tag 'car'"**
- Check vehicle tags in Details panel
- Ensure tag spelling matches exactly

**Black/empty captures**
- Check DataCapture camera position (must see vehicles)
- Verify lighting in scene (sun + sky light)

**Python connection fails**
- Check UE5 editor is running with level open
- Verify port 30010 not blocked by firewall
- Test: `curl http://localhost:30010/remote/info`

---

## Next Steps

1. **Import assets** (start with 1-2 vehicles per class)
2. **Build basic scene** (ground + lighting + 5 vehicles)
3. **Tag all vehicles** correctly
4. **Test Python bridge** connection
5. **Generate 10 test images**
6. **Iterate on scene** (add more vehicles, better lighting)
7. **Generate 1000-image dataset**

---

## Recommended Free Asset Packs

**Immediate Download:**
1. **City Sample** (Epic Games) - FREE, massive city with vehicles
2. **Vehicle Variety Pack** (Marketplace) - Multiple vehicle types
3. **Modular Streets** (Quixel Megascans) - Roads and urban elements

**Installation:**
- Epic Games Launcher → Unreal Engine → Marketplace
- Find asset → Add to Cart (FREE) → Install to VantageCV_Automotive project

---

**Estimated Setup Time:**
- Basic scene (1 vehicle): 30 minutes
- Production scene (all classes): 2-3 hours
- First 10 captures: 15 minutes
- Full 1000 images: 1-2 hours generation time
