# Lighting Configuration Policy

## DirectionalLight Immutability

**CRITICAL**: DirectionalLight_4 must be configured MANUALLY in UE5 and can NEVER be modified by code.

### Why?

1. **Eye Adaptation**: UE5 viewport uses Eye Adaptation (auto-exposure) which dynamically adjusts to scene brightness
2. **DataCapture Limitation**: SceneCaptureComponent2D should NOT use Eye Adaptation - it's non-deterministic for synthetic data
3. **Manual Configuration**: DirectionalLight must be set to the correct intensity for the scene ONCE, then locked

### Current Configuration

Configure in UE5 Editor (World Outliner → DirectionalLight_4):

- **Intensity**: 5.0 - 10.0 lux (adjust to taste - viewport will auto-adapt)
- **LightSourceAngle**: 2.0° (soft shadows)
- **Color**: Pure white (255, 255, 255)
- **Temperature**: 6500K (daylight)
- **CastShadows**: True
- **ShadowAmount**: 0.5 (50% shadow darkness)

### Code Rules

❌ **FORBIDDEN** - Scripts that modify DirectionalLight:
- Any `set_property()` calls to DirectionalLight_4
- Any intensity/color/shadow adjustments via Remote Control API
- Any runtime lighting configuration in C++

✅ **ALLOWED** - Read-only operations:
- Diagnostics that READ DirectionalLight settings
- Test scripts that capture images without modifying lighting

### Deleted Scripts

The following scripts were removed because they violated this policy:

1. `fix_all_settings.py` - Modified DirectionalLight intensity
2. `setup_realistic_lighting.py` - Configured DirectionalLight + Eye Adaptation
3. `reduce_light.py` - Adjusted DirectionalLight intensity by multiplier
4. `fix_shadows.py` - Modified LightSourceAngle, ShadowAmount, ShadowBias
5. `optimize_lighting.py` - Comprehensive DirectionalLight configuration
6. `configure_photorealistic_rendering.py` - Full scene lighting setup
7. `configure_physically_based_rendering.py` - Physically-based lighting config

### C++ Verification

DataCapture.cpp has been cleaned to remove all lighting configuration:

```cpp
// ❌ REMOVED - DO NOT RE-ADD
// void ADataCapture::ConfigureSceneLighting() { ... }
// #include "Engine/DirectionalLight.h"
// #include "Components/DirectionalLightComponent.h"
```

The BeginPlay() method does NOT call any lighting configuration functions.

### Manual Setup Steps

1. Open `VantageCV_Project.uproject` in UE5
2. Open World Outliner
3. Find and select `DirectionalLight_4`
4. In Details panel, set properties as listed above
5. Press Play to test in viewport
6. Run `python scripts/preview_capture.py` to test captures
7. **DO NOT** create scripts to automate this - it must remain manual

### Troubleshooting

**Captures still too bright/dark?**

1. ✅ Adjust DirectionalLight MANUALLY in UE5 Editor
2. ❌ Do NOT create a script to fix it
3. ✅ Test with `preview_capture.py` after each manual adjustment

**Viewport looks different from captures?**

- This is expected - viewport uses Eye Adaptation, captures don't
- Adjust DirectionalLight intensity until captures look right
- Viewport brightness is irrelevant (Eye Adaptation will compensate)

### Policy Enforcement

Before committing new code:

1. Search for `DirectionalLight` in all Python scripts
2. Verify no `set_property()` calls exist
3. Search C++ for lighting includes/configuration
4. Review this document to ensure compliance

**Last Updated**: 2025-01-XX  
**Enforced By**: Code review + documentation
