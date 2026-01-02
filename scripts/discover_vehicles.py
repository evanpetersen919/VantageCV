#!/usr/bin/env python3
"""Discover vehicle actors in UE5 level and categorize them."""

import requests
import json

base_url = "http://localhost:30010"

def categorize(mesh_name):
    """Categorize mesh by keywords in name."""
    mesh_lower = mesh_name.lower()
    if 'bicycle' in mesh_lower or 'cycle' in mesh_lower:
        return 'bicycle'
    elif 'motorcycle' in mesh_lower or 'avenger' in mesh_lower or 'cafe_racer' in mesh_lower:
        return 'motorcycle'
    elif 'bus' in mesh_lower or 'marcopolo' in mesh_lower or 'paz_' in mesh_lower:
        return 'bus'
    elif 'truck' in mesh_lower or 'pickup' in mesh_lower or 'pick_up' in mesh_lower or 'hilux' in mesh_lower or 'zil_' in mesh_lower:
        return 'truck'
    else:
        return 'car'

# Get all actors and categorize
categories = {'car': [], 'truck': [], 'bus': [], 'motorcycle': [], 'bicycle': []}

print("Discovering vehicle actors in UE5...")
print()

for i in range(1, 51):
    path = f'/Game/automobile.automobile:PersistentLevel.StaticMeshActor_{i}'
    try:
        r = requests.put(
            f'{base_url}/remote/object/property',
            json={'objectPath': path + '.StaticMeshComponent0', 'propertyName': 'StaticMesh', 'access': 'READ_ACCESS'},
            timeout=1
        )
        if r.status_code == 200:
            mesh = r.json().get('StaticMesh', '')
            if mesh:
                mesh_name = mesh.split('.')[-1]
                category = categorize(mesh_name)
                categories[category].append(f'StaticMeshActor_{i}')
                print(f"  {category}: StaticMeshActor_{i} ({mesh_name})")
    except:
        pass

# Check SkeletalMeshActors too
for i in range(1, 20):
    path = f'/Game/automobile.automobile:PersistentLevel.SkeletalMeshActor_{i}'
    try:
        r = requests.put(f'{base_url}/remote/object/describe', json={'objectPath': path}, timeout=1)
        if r.status_code == 200:
            categories['motorcycle'].append(f'SkeletalMeshActor_{i}')
            print(f"  motorcycle: SkeletalMeshActor_{i}")
    except:
        pass

print()
print("=" * 60)
print("SUMMARY")
print("=" * 60)
for cat, actors in categories.items():
    print(f"  {cat}: {len(actors)} actors")

print()
print("=" * 60)
print("YAML CONFIG (copy to configs/research_v2.yaml)")
print("=" * 60)
print("vehicle_actors:")
for cat, actors in categories.items():
    print(f"  {cat}:")
    for a in actors:
        print(f'    - "{a}"')
