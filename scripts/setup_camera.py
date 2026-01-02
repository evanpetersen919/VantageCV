#!/usr/bin/env python3
"""Setup DataCapture camera to look forward."""

from vantagecv.ue5_bridge import UE5Bridge

def main():
    b = UE5Bridge()
    path = '/Game/automobile.automobile:PersistentLevel.DataCapture_1'
    
    print("Setting DataCapture camera to look forward...")
    
    # Set DataCapture to look straight forward (Yaw=0, Pitch=0)
    b.call_function(path, 'K2_SetActorRotation', {
        'NewRotation': {'Pitch': 0, 'Yaw': 0, 'Roll': 0},
        'bTeleportPhysics': True
    })
    
    # Verify
    rot = b.call_function(path, 'K2_GetActorRotation', {})['ReturnValue']
    loc = b.call_function(path, 'K2_GetActorLocation', {})['ReturnValue']
    
    print(f"DataCapture position: ({loc['X']:.0f}, {loc['Y']:.0f}, {loc['Z']:.0f}) cm")
    print(f"DataCapture rotation: Pitch={rot['Pitch']:.1f}, Yaw={rot['Yaw']:.1f}, Roll={rot['Roll']:.1f}")
    print("Camera now looking in +X direction")

if __name__ == "__main__":
    main()
