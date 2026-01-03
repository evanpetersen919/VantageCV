import requests
import json

base_url = "http://127.0.0.1:30010/remote"

print("Testing Remote Control API...")
print("="*60)

# Try different methods to get actors

# Method 1: Search for actors by name pattern
print("\nMethod 1: Searching for StaticMeshActor by name pattern...")
search_payload = {
    "query": "StaticMeshActor",
    "limit": 100
}
response = requests.put(f"{base_url}/search/assets", json=search_payload)
print(f"Search Status: {response.status_code}")
if response.status_code == 200:
    print(f"Search Response: {response.text[:500]}")

# Method 2: Try to get a specific actor you know exists
print("\nMethod 2: Trying to get StaticMeshActor_15 directly...")
actor_path = "PersistentLevel.StaticMeshActor_15"
get_payload = {
    "objectPath": actor_path,
    "functionName": "K2_GetActorLocation"
}
response = requests.put(f"{base_url}/object/call", json=get_payload)
print(f"Direct Actor Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    print(f"Location: {data.get('ReturnValue', 'No data')}")
else:
    print(f"Error: {response.text}")

# Method 3: Try getting world actors
print("\nMethod 3: Get all actors with WorldContextObject...")
world_payload = {
    "objectPath": "/Script/Engine.Default__GameplayStatics",
    "functionName": "GetAllActorsOfClass",
    "parameters": {
        "WorldContextObject": None,
        "ActorClass": "/Script/Engine.StaticMeshActor"
    },
    "generateTransaction": False
}
response = requests.put(f"{base_url}/object/call", json=world_payload)
print(f"Status: {response.status_code}")
if response.status_code == 200:
    data = response.json()
    actors = data.get("ReturnValue", [])
    print(f"Total StaticMeshActors found: {len(actors)}")
    
    if actors:
        print("\nFirst 20 actors:")
        for i, actor in enumerate(actors[:20]):
            print(f"  {i+1}. {actor}")
        
        if len(actors) > 20:
            print(f"  ... and {len(actors) - 20} more")
else:
    print(f"Error: {response.text}")
