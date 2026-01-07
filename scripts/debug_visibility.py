#!/usr/bin/env python3
"""
Debug prop visibility - check if we can control anchor visibility
"""
import sys
from pathlib import Path
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))

def test_visibility():
    base_url = "http://127.0.0.1:30010/remote"
    level_path = "/Game/automobileV2.automobileV2"
    
    session = requests.Session()
    session.headers.update({"Content-Type": "application/json"})
    
    # Test with StaticMeshActor_4 (barrier anchor)
    test_actor = "StaticMeshActor_4"
    actor_path = f"{level_path}:PersistentLevel.{test_actor}"
    
    print(f"Testing visibility control on: {test_actor}")
    print(f"Full path: {actor_path}")
    print("=" * 60)
    
    # Try to make it visible
    print("\n1. Setting hidden=False (should make visible)...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "SetActorHiddenInGame",
            "parameters": {"bNewHidden": False}
        },
        timeout=5.0
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    # Check current visibility
    print("\n2. Getting IsHidden property...")
    response = session.put(
        f"{base_url}/object/property",
        json={
            "objectPath": actor_path,
            "propertyName": "bHidden"
        },
        timeout=5.0
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    # Try alternate method - GetActorHiddenInGame
    print("\n3. Calling GetActorHiddenInGame()...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "GetActorHiddenInGame"
        },
        timeout=5.0
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")
    
    print("\n" + "=" * 60)
    print("Check UE5 - did the sphere appear?")
    input("Press Enter to hide it again...")
    
    # Hide it
    print("\n4. Setting hidden=True (should hide)...")
    response = session.put(
        f"{base_url}/object/call",
        json={
            "objectPath": actor_path,
            "functionName": "SetActorHiddenInGame",
            "parameters": {"bNewHidden": True}
        },
        timeout=5.0
    )
    print(f"   Status: {response.status_code}")
    print(f"   Response: {response.text}")

if __name__ == "__main__":
    test_visibility()
