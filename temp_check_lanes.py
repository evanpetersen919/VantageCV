import requests

lanes = {
    'lane_1': ['StaticMeshActor_32', 'StaticMeshActor_28'],
    'lane_2': ['StaticMeshActor_30', 'StaticMeshActor_36'],
    'lane_3': ['StaticMeshActor_38', 'StaticMeshActor_42'],
    'lane_4': ['StaticMeshActor_40', 'StaticMeshActor_37']
}

for lane_id, (start, end) in lanes.items():
    for name in [start, end]:
        r = requests.post("http://127.0.0.1:30010/remote/object/property", 
                         json={"objectPath": f"/Game/automobileV2.automobileV2:PersistentLevel.{name}", 
                               "propertyName": "RootComponent.RelativeLocation"})
        result = r.json()
        if "PropertyValue" in result:
            loc = result["PropertyValue"]
            print(f"{lane_id} {name}: X={loc['X']:.1f}, Y={loc['Y']:.1f}")
        else:
            print(f"{lane_id} {name}: ERROR - {result}")
