#!/usr/bin/env python3
"""
Detect current directional light settings from UE5 and display them.
Use this to find the baseline sun rotation/intensity, then adjust
time augmentation states accordingly.

Usage:
    python scripts/detect_lighting.py
"""
import sys
import json
import requests
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

BASE_URL = "http://127.0.0.1:30010/remote"
LEVEL = "/Game/automobileV2.automobileV2"


def call_remote(object_path, function_name, parameters=None):
    payload = {
        "objectPath": object_path,
        "functionName": function_name,
    }
    if parameters:
        payload["parameters"] = parameters
    try:
        r = requests.put(f"{BASE_URL}/object/call", json=payload, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [ERROR] {e}")
    return None


def get_property(object_path, property_name):
    payload = {
        "objectPath": object_path,
        "access": "READ_ACCESS",
        "propertyName": property_name,
    }
    try:
        r = requests.put(f"{BASE_URL}/object/property", json=payload, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception as e:
        print(f"  [ERROR] {e}")
    return None


def detect_actor(name):
    """Check if actor exists and return its rotation + location."""
    path = f"{LEVEL}:PersistentLevel.{name}"
    rot = call_remote(path, "K2_GetActorRotation")
    loc = call_remote(path, "K2_GetActorLocation")
    if rot and "ReturnValue" in rot:
        return {
            "rotation": rot["ReturnValue"],
            "location": loc["ReturnValue"] if loc and "ReturnValue" in loc else None,
        }
    return None


def main():
    print("=" * 60)
    print("UE5 LIGHTING DETECTION")
    print("=" * 60)

    # ── Directional Light ──────────────────────────────────────
    dir_light_names = [
        "DirectionalLight",
        "DirectionalLight_1",
        "DirectionalLight_2",
        "DirectionalLight_3",
        "DirectionalLight_4",
        "SunLight",
        "Sun",
        "Light_Directional",
    ]

    print("\n── Directional Light (Sun) ──")
    found_dir = None
    for name in dir_light_names:
        info = detect_actor(name)
        if info:
            found_dir = name
            rot = info["rotation"]
            loc = info["location"]
            print(f"  Actor: {name}")
            print(f"  Rotation: Pitch={rot.get('Pitch', 0):.2f}  Yaw={rot.get('Yaw', 0):.2f}  Roll={rot.get('Roll', 0):.2f}")
            if loc:
                print(f"  Location: X={loc.get('X', 0):.1f}  Y={loc.get('Y', 0):.1f}  Z={loc.get('Z', 0):.1f}")

            # Try to read light intensity
            light_path = f"{LEVEL}:PersistentLevel.{name}.LightComponent0"
            for prop in ["Intensity", "LightColor", "Temperature", "bUseTemperature",
                         "IndirectLightingIntensity", "VolumetricScatteringIntensity",
                         "SourceAngle", "SourceSoftAngle"]:
                val = get_property(light_path, prop)
                if val:
                    print(f"  {prop}: {json.dumps(val.get(prop, val), indent=None)}")
            break
    else:
        print("  [NOT FOUND] No DirectionalLight detected")

    # ── Sky Light ──────────────────────────────────────────────
    sky_names = ["SkyLight", "SkyLight_1", "Sky_Light", "AmbientLight"]

    print("\n── Sky Light ──")
    found_sky = None
    for name in sky_names:
        info = detect_actor(name)
        if info:
            found_sky = name
            rot = info["rotation"]
            print(f"  Actor: {name}")
            print(f"  Rotation: Pitch={rot.get('Pitch', 0):.2f}  Yaw={rot.get('Yaw', 0):.2f}  Roll={rot.get('Roll', 0):.2f}")

            light_path = f"{LEVEL}:PersistentLevel.{name}.LightComponent"
            for alt_path_suffix in ["LightComponent", "SkyLightComponent0", "LightComponent0"]:
                alt_path = f"{LEVEL}:PersistentLevel.{name}.{alt_path_suffix}"
                for prop in ["Intensity", "LightColor", "SkyDistanceThreshold",
                             "bLowerHemisphereIsBlack", "IndirectLightingIntensity",
                             "VolumetricScatteringIntensity"]:
                    val = get_property(alt_path, prop)
                    if val:
                        print(f"  {prop} (via {alt_path_suffix}): {json.dumps(val.get(prop, val), indent=None)}")
            break
    else:
        print("  [NOT FOUND] No SkyLight detected")

    # ── Exponential Height Fog ─────────────────────────────────
    fog_names = ["ExponentialHeightFog", "ExponentialHeightFog_1",
                 "ExponentialFog", "HeightFog"]

    print("\n── Exponential Height Fog ──")
    for name in fog_names:
        info = detect_actor(name)
        if info:
            print(f"  Actor: {name}")
            fog_path = f"{LEVEL}:PersistentLevel.{name}.HeightFogComponent0"
            for prop in ["FogDensity", "FogHeightFalloff", "FogInscatteringColor",
                         "FogMaxOpacity", "StartDistance",
                         "DirectionalInscatteringExponent",
                         "DirectionalInscatteringStartDistance"]:
                val = get_property(fog_path, prop)
                if val:
                    print(f"  {prop}: {json.dumps(val.get(prop, val), indent=None)}")
            break
    else:
        print("  [NOT FOUND] No ExponentialHeightFog detected")

    # ── Post Process Volume ────────────────────────────────────
    pp_names = ["PostProcessVolume", "PostProcessVolume_1",
                "GlobalPostProcess", "PP_Volume"]

    print("\n── Post Process Volume ──")
    for name in pp_names:
        info = detect_actor(name)
        if info:
            print(f"  Actor: {name}")
            # Settings are nested under the component
            pp_path = f"{LEVEL}:PersistentLevel.{name}"
            for prop in ["BloomIntensity", "AutoExposureBias",
                         "AutoExposureMinBrightness", "AutoExposureMaxBrightness",
                         "bOverride_AutoExposureBias"]:
                val = get_property(pp_path, prop)
                if val:
                    print(f"  {prop}: {json.dumps(val.get(prop, val), indent=None)}")
            break
    else:
        print("  [NOT FOUND] No PostProcessVolume detected")

    # ── Summary ────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("CURRENT BASELINE (copy these into time augmentation states)")
    print("=" * 60)
    if found_dir:
        info = detect_actor(found_dir)
        rot = info["rotation"]
        pitch = rot.get("Pitch", 0)
        yaw = rot.get("Yaw", 0)
        print(f"\n  DirectionalLight: {found_dir}")
        print(f"  Current sun_pitch = {pitch:.2f}")
        print(f"  Current sun_yaw   = {yaw:.2f}")
        print()
        print("  Suggested time states (centred around current baseline):")
        print(f"    morning:   sun_pitch={pitch - 5:.1f},  sun_yaw={yaw - 70:.1f}")
        print(f"    noon:      sun_pitch={pitch:.1f},  sun_yaw={yaw:.1f}   ← current")
        print(f"    afternoon: sun_pitch={pitch + 5:.1f},  sun_yaw={yaw + 40:.1f}")
    print("=" * 60)


if __name__ == "__main__":
    main()
