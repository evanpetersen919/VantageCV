# UE5 Scene Setup Guide - Exact Coordinates

## Understanding UE5 Units
- **1 Unreal Unit = 1 Centimeter**
- Example: 100 units = 1 meter, 1000 units = 10 meters
- Your camera range [800, 2000] = 8 to 20 meters from vehicles

---

## Recommended Scene Layout

### Scene Center (Vehicle Parking Area)
Choose a location away from world origin for cleaner organization:
- **Recommended: X=10000, Y=10000, Z=0**
- This gives you a clean 10m x 10m area from world origin
- Vehicles will be arranged in a grid around this center

### Vehicle Placement
Place your 5 vehicles in a realistic parking/road configuration:

**Layout 1: Parking Lot (Side-by-Side)**
```
Vehicle 1: X=9000,  Y=10000, Z=0,  Rotation=(0,0,0)
Vehicle 2: X=10000, Y=10000, Z=0,  Rotation=(0,0,0)
Vehicle 3: X=11000, Y=10000, Z=0,  Rotation=(0,0,0)
Vehicle 4: X=9500,  Y=11500, Z=0,  Rotation=(0,0,0)
Vehicle 5: X=10500, Y=11500, Z=0,  Rotation=(0,0,0)
```
- Spacing: 10 meters (1000 units) between vehicles
- Creates natural parking lot scene

**Layout 2: Road Scene (Two Lanes)**
```
Vehicle 1: X=10000, Y=9000,  Z=0, Rotation=(0,90,0)  # Lane 1
Vehicle 2: X=10000, Y=10500, Z=0, Rotation=(0,90,0)  # Lane 1
Vehicle 3: X=11500, Y=9000,  Z=0, Rotation=(0,-90,0) # Lane 2 (opposite)
Vehicle 4: X=11500, Y=10500, Z=0, Rotation=(0,-90,0) # Lane 2 (opposite)
Vehicle 5: X=10000, Y=12000, Z=0, Rotation=(0,90,0)  # Lane 1
```
- Simulates two-lane traffic
- Lane spacing: 15 meters (1500 units)
- Vehicle spacing: 15 meters along lane

---

## VantageCV Actor Placement

### DataCapture_1 Actor
**CRITICAL:** This actor's position defines where the camera orbits!

**Position: X=10000, Y=10000, Z=200**
- Place at the center of your vehicle scene
- Z=200 (2 meters up) ensures camera clears ground plane
- Camera will orbit around this point at 800-2000cm radius

### SceneController_1 Actor
**Position: Anywhere (doesn't affect capture)**
- Suggestion: X=5000, Y=5000, Z=0
- Only controls lighting randomization
- Physical location doesn't matter

### DomainRandomization_1 Actor
**IMPORTANT:** Distractors spawn around this actor's location!

**Current Problem:** If this actor is at (0,0,0), distractors spawn at world origin
**Solution:** Place it at scene center or nearby
**Position: X=10000, Y=10000, Z=0**

**Why this fixes "huge objects at origin":**
- Distractors spawn at `DomainRandomization_1 location + random offset`
- Current config: distance_range [1000, 3000] = 10-30m from this actor
- If actor is at (0,0,0), distractors appear at origin
- If actor is at scene center (10000, 10000, 0), distractors appear 10-30m from vehicles ✅

---

## Understanding Distractor Objects

**What are they?**
- Random geometric shapes (cubes, spheres, cylinders) spawned during randomization
- Research technique called "Domain Randomization" for robust computer vision
- Purpose: Make model generalize better by training on cluttered scenes

**Current Settings (automotive.yaml):**
```yaml
distractor_scale_range: [0.3, 1.0]      # 30cm to 1m objects
distractor_count_range: [3, 8]          # 3-8 objects per image
distractor_distance_range: [1000, 3000] # 10-30m from DomainRandomization actor
```

**Is it normal?**
- YES - they're intentionally spawned for training robustness
- Should appear AROUND your scene, not AT the scene center
- Should be small background clutter, not massive objects

**If you DON'T want distractors:**
Edit [configs/automotive.yaml](../configs/automotive.yaml):
```yaml
domain_randomization:
  enabled: true
  distractors:
    enabled: false  # ← Set this to false
```

---

## Quick Setup Checklist

1. **Position Ground Plane:** Z=0
2. **Position Vehicles:** Use one of the layouts above
3. **Position DataCapture_1:** At scene center (e.g., X=10000, Y=10000, Z=200)
4. **Position DomainRandomization_1:** At scene center (e.g., X=10000, Y=10000, Z=0)
5. **Position SceneController_1:** Anywhere (e.g., X=5000, Y=5000, Z=0)

---

## Camera Behavior

With DataCapture at (10000, 10000, 200):
- **Orbit radius:** 800-2000 cm (8-20 meters)
- **Orbit center:** (10000, 10000, 200)
- **Elevation angles:** 15-60° (realistic driving/surveillance angles)
- **FOV:** 70-100° (wide to telephoto)

Camera will randomize position in spherical coordinates around your vehicles.

---

## Debugging Tips

**All images look the same?**
- Run `python scripts/preflight_check.py` to verify randomization

**Camera pointing at wrong thing?**
- Check DataCapture_1 actor position - this is the orbit center
- Camera always looks at this point

**Distractors too big?**
- Reduce `distractor_scale_range` in config
- Current: [0.3, 1.0] = 30cm to 1m objects

**Distractors at origin?**
- Move DomainRandomization_1 actor to scene center (10000, 10000, 0)

**Need to rebuild after C++ changes?**
1. Open your UE5 project folder
2. Right-click `.uproject` → Generate Visual Studio project files
3. Open `.sln` in Visual Studio 2022
4. Build → Build Solution (Ctrl+Shift+B)
5. Close and restart UE5 Editor
