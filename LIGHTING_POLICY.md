# Lighting Configuration

## DirectionalLight Randomization

DirectionalLight intensity, angle, and rotation are randomized at runtime by
`ADomainRandomization::RandomizeLighting()` in
`ue5_plugin/Source/VantageCV/Private/DomainRandomization.cpp`, gated by
`Config.Lighting.bEnabled`. This is an intentional feature for environmental
augmentation (see README's "6 time-of-day states" / weather augmentation), not
a violation of any policy — an earlier version of this document claimed the
opposite (that DirectionalLight was manually locked and never touched by code),
which no longer reflects the codebase and has been removed.

### Behavior

- Intensity is randomized within `Config.Lighting.IntensityRange`, clamped to a
  minimum of 50.0 to keep captures correctly exposed.
- Sun elevation/azimuth are randomized within `Config.Lighting.ElevationRange` /
  `AzimuthRange` and applied as the DirectionalLight's rotation.
- `RandomizeSky()` (same file) independently randomizes sky light color and
  intensity from `Config.Sky.SkyColorPalette`.

### Determinism

Randomization uses a seeded `RandomStream` (see seed-based reproducibility in
README), so a given seed reproduces the same lighting for a given frame — this
is what makes `SceneCaptureComponent2D` output deterministic despite the
randomization, not manual/frozen lighting.
