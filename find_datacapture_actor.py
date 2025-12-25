"""
Query UE5 Remote Control API to find DataCapture actor path
"""

import requests
import json

UE5_HOST = "localhost"
UE5_PORT = 30010

def list_presets():
    """List all Remote Control presets."""
    url = f"http://{UE5_HOST}:{UE5_PORT}/remote/presets"
    response = requests.get(url)
    print(f"Presets: {response.status_code}")
    if response.text:
        data = response.json()
        print(json.dumps(data, indent=2))

def search_objects(search_term="DataCapture"):
    """Search for objects containing term."""
    url = f"http://{UE5_HOST}:{UE5_PORT}/remote/search/objects"
    payload = {
        "Query": search_term,
        "Limit": 100
    }
    
    try:
        response = requests.put(url, json=payload)
        print(f"\nSearch for '{search_term}': {response.status_code}")
        if response.text:
            data = response.json()
            print(json.dumps(data, indent=2))
            return data
    except Exception as e:
        print(f"Error: {e}")
    
    return None

def list_assets():
    """List all assets."""
    url = f"http://{UE5_HOST}:{UE5_PORT}/remote/search/assets"
    payload = {
        "Query": "*",
        "Limit": 100
    }
    
    try:
        response = requests.put(url, json=payload)
        print(f"\nAssets: {response.status_code}")
        if response.text:
            data = response.json()
            for asset in data.get("Assets", [])[:10]:
                print(f"  {asset.get('Path', 'unknown')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("=" * 60)
    print("Searching for DataCapture Actor in UE5")
    print("=" * 60)
    
    # Try different search methods
    result = search_objects("DataCapture")
    
    if not result or not result.get("Objects"):
        print("\nTrying broader search...")
        result = search_objects("Vantage")
    
    if not result or not result.get("Objects"):
        print("\nTrying to list all actors...")
        result = search_objects("*")
