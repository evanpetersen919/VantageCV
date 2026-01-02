#!/usr/bin/env python3
"""Check actor positions in UE5 level."""

from vantagecv.ue5_bridge import UE5Bridge

def main():
    b = UE5Bridge()
    
    actors = [
        'StaticMeshActor_4',   # car
        'StaticMeshActor_9',   # bus
        'StaticMeshActor_25',  # truck
        'DataCapture_1',
        'SceneController_1',
    ]
    
    print("Actor positions in UE5 level:")
    print("-" * 80)
    
    for a in actors:
        try:
            path = f'/Game/automobile.automobile:PersistentLevel.{a}'
            loc = b.call_function(path, 'K2_GetActorLocation', {})['ReturnValue']
            rot = b.call_function(path, 'K2_GetActorRotation', {})['ReturnValue']
            print(f"{a:25s} Pos=({loc['X']:8.0f}, {loc['Y']:8.0f}, {loc['Z']:8.0f})  Rot=(P:{rot['Pitch']:6.1f}, Y:{rot['Yaw']:6.1f}, R:{rot['Roll']:6.1f})")
        except Exception as e:
            print(f"{a:25s} ERROR: {e}")
    
    print("-" * 80)
    print("Note: UE5 uses centimeters. Divide by 100 for meters.")
    print("Note: Rotation is (Pitch, Yaw, Roll) in degrees.")

if __name__ == "__main__":
    main()
