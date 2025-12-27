# UE5 Scene Setup for VantageCV

## Professional C++ Plugin Architecture

Follow these steps to set up your UE5 level with the VantageCV plugin.

## Prerequisites

1. ✅ VantageCV plugin compiled successfully (Ctrl+Alt+F11 in UE5)
2. ✅ Remote Control Web Interface plugin enabled
3. ✅ Level loaded (e.g., `/Game/main.umap`)

## Step 1: Place DataCapture Actor

**In Unreal Editor:**

1. **Create Blueprint from C++ Class:**
   - Tools → New C++ Class
   - Show All Classes → Search "DataCapture"
   - Select `ADataCapture` → Next
   - Name: `BP_DataCapture`
   - Click Create Class

2. **Place in Level:**
   - Drag `BP_DataCapture` from Content Browser into the viewport
   - Position at your camera location (where you want to capture from)
   - Rotate to face the objects you want to capture
   - **Recommended**: Position above your scene looking down at PCB

3. **Get the Actor Path:**
   - Select `BP_DataCapture` in World Outliner
   - Window → Developer Tools → Output Log
   - In console, type: `GetPathName BP_DataCapture`
   - Copy the output (e.g., `/Game/main.main:PersistentLevel.BP_DataCapture_C_0`)

## Step 2: Update Configuration

Edit `configs/industrial.yaml`:

```yaml
industrial:
  ue5:
    remote_control_port: 30010
    scene_controller_path: "/Game/main.main:PersistentLevel.BP_SceneController_C_UAID_B48C9D9F0BCA05AF02_1237591175"
    data_capture_path: "/Game/main.main:PersistentLevel.BP_DataCapture_C_0"  # UPDATE THIS
    target_actor_pattern: "StaticMeshActor"
```

## Step 3: Test the Setup

```bash
python tests/integration/test_hybrid_randomization.py
```

You should see:
- ✓ Lighting randomized
- ✓ Materials randomized
- ✓ **Frame captured** (new!)

Images will save to: `F:\Unreal Editor\VantageCV_Project\Saved\Screenshots\VantageCV\`

## Troubleshooting

**"Error: No valid world found"**
- DataCapture actor not placed in level
- Check actor path is correct in config

**"Frame capture returned false"**
- Output path may be invalid
- Check UE5 Output Log for detailed error

**"Object does not exist"**
- Actor path in config is wrong
- Re-copy the path from UE5 using `GetPathName` command

## Next Steps

Once frame capture works:
1. Generate 100-image test dataset
2. Implement annotation export (bounding boxes, poses)
3. Begin Phase 3: ML Pipeline
