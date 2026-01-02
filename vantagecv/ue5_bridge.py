#==============================================================================
# VantageCV - UE5 Bridge Module
#==============================================================================
# File: ue5_bridge.py
# Description: Python bridge for communicating with Unreal Engine 5 via Remote
#              Control API for synthetic data generation
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import requests
import json
import time
import logging
from typing import Dict, Any, Optional, List
from pathlib import Path

logger = logging.getLogger(__name__)


class UE5Bridge:
    """
    Bridge class for communicating with Unreal Engine 5.
    
    Uses UE5's Remote Control Web API to:
    - Control scene parameters (lighting, materials, object placement)
    - Trigger image captures
    - Retrieve annotations and metadata
    
    Attributes:
        host: UE5 server hostname
        port: UE5 Remote Control API port (default 30010)
        timeout: Request timeout in seconds
    """
    
    def __init__(self, host: str = "localhost", port: int = 30010, timeout: int = 30,
                 scene_controller_path: Optional[str] = None,
                 data_capture_path: Optional[str] = None):
        """
        Initialize UE5 bridge connection.
        
        Args:
            host: UE5 server hostname
            port: Remote Control API port
            timeout: Request timeout in seconds
            scene_controller_path: Full object path to BP_SceneController instance
            data_capture_path: Full object path to BP_DataCapture instance
            
        Raises:
            ConnectionError: If unable to connect to UE5
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}/remote/object"
        self.batch_url = f"http://{host}:{port}/remote/batch"
        
        # Store actor paths (auto-discovered from automobile level)
        self.scene_controller_path = scene_controller_path or "/Game/automobile.automobile:PersistentLevel.SceneController_1"
        self.data_capture_path = data_capture_path or "/Game/automobile.automobile:PersistentLevel.DataCapture_1"
        
        # Level name for actor path construction
        self.level_name = "automobile"  # Will be used for actor paths
        
        self._verify_connection()
    
    def _verify_connection(self) -> None:
        """
        Verify connection to UE5 Remote Control API.
        
        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Test with a minimal PUT request to verify server is responding
            response = requests.put(
                f"http://{self.host}:{self.port}/remote/object/call",
                json={"objectPath": "", "functionName": ""},
                timeout=5
            )
            # Any response (even error) means server is alive
            logger.info(f"Connected to UE5 at {self.host}:{self.port}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(
                f"Failed to connect to UE5 at {self.host}:{self.port}. "
                f"Ensure UE5 is running with Remote Control plugin enabled. Error: {e}"
            )
    
    def test_connection(self) -> bool:
        """
        Test if connection to UE5 Remote Control API is working.
        
        Returns:
            True if connection is working, False otherwise
        """
        try:
            response = requests.put(
                f"http://{self.host}:{self.port}/remote/object/call",
                json={"objectPath": "", "functionName": ""},
                timeout=5
            )
            # Any response means server is alive
            return True
        except requests.exceptions.RequestException:
            return False
    
    def call_function(self, object_path: str, function_name: str, 
                      parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Call a function on a UE5 object via Remote Control API.
        
        Args:
            object_path: Path to UE5 object (e.g., "/Script/VantageCV.Default__VantageCVSubsystem")
            function_name: Name of the function to call
            parameters: Function parameters as dictionary
            
        Returns:
            Response data from UE5
            
        Raises:
            RuntimeError: If function call fails
        """
        url = f"{self.base_url}/call"
        payload = {
            "objectPath": object_path,
            "functionName": function_name,
            "parameters": parameters or {},
            "generateTransaction": False
        }
        
        try:
            response = requests.put(url, json=payload, timeout=self.timeout)
            
            if response.status_code != 200:
                error_msg = response.json().get('errorMessage', 'Unknown error') if response.text else 'No response'
                raise RuntimeError(
                    f"UE5 function call failed: {function_name} on {object_path}. "
                    f"Status: {response.status_code}, Error: {error_msg}"
                )
            
            return response.json()
            
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Network error calling {function_name}: {e}") from e
    
    def set_capture_camera(self, x: float, y: float, z: float, 
                           pitch: float = 0, yaw: float = 0, roll: float = 0,
                           fov: float = 90.0) -> bool:
        """
        Set the DataCapture camera position and rotation.
        
        Args:
            x, y, z: Camera position in centimeters
            pitch, yaw, roll: Camera rotation in degrees
            fov: Field of view in degrees
            
        Returns:
            True if successful
        """
        try:
            # Set position
            self.call_function(
                self.data_capture_path,
                "K2_SetActorLocation",
                {
                    "NewLocation": {"X": x, "Y": y, "Z": z},
                    "bSweep": False,
                    "bTeleport": True,
                }
            )
            
            # Set rotation
            self.call_function(
                self.data_capture_path,
                "K2_SetActorRotation",
                {
                    "NewRotation": {"Pitch": pitch, "Yaw": yaw, "Roll": roll},
                    "bTeleportPhysics": True,
                }
            )
            
            logger.debug(f"Camera set: pos=({x}, {y}, {z}) rot=({pitch}, {yaw}, {roll}) fov={fov}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set camera: {e}")
            return False
    
    def capture_frame(self, output_path: str, width: int = 1920, height: int = 1080) -> bool:
        """
        Capture a frame using DataCapture actor.
        Professional approach: Custom C++ actor with full control.
        
        Args:
            output_path: Full path where image should be saved (e.g., "F:/dataset/img_0001.png")
            width: Image width in pixels
            height: Image height in pixels
            
        Returns:
            True if capture succeeded
        """
        try:
            result = self.call_function(
                self.data_capture_path,
                "CaptureFrame",
                {
                    "OutputPath": output_path,
                    "Width": width,
                    "Height": height
                }
            )
            
            # Check if function returned true
            success = result.get("ReturnValue", False)
            if success:
                logger.info(f"Frame captured: {output_path}")
            else:
                logger.warning(f"Frame capture returned false: {output_path}")
            
            return success
            
        except Exception as e:
            logger.error(f"Frame capture failed: {e}")
            return False
    
    def set_property(self, object_path: str, property_name: str, 
                     value: Any) -> None:
        """
        Set a property value on a UE5 object.
        
        Args:
            object_path: Path to UE5 object
            property_name: Name of the property
            value: New value for the property
            
        Raises:
            RuntimeError: If property update fails
        """
        payload = {
            "objectPath": object_path,
            "propertyName": property_name,
            "propertyValue": value,
            "generateTransaction": True
        }
        
        try:
            response = requests.put(
                f"{self.base_url}/property",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to set {property_name} on {object_path}: {e}"
            )
    
    def _get_actor_path(self, actor_name: str) -> str:
        """
        Construct full actor path from actor name.
        
        Args:
            actor_name: Simple actor name (e.g., "Car_1")
            
        Returns:
            Full UE5 actor path
        """
        return f"/Game/{self.level_name}.{self.level_name}:PersistentLevel.{actor_name}"
    
    def set_actor_visibility(self, actor_name: str, visible: bool) -> bool:
        """
        Set actor visibility (show/hide).
        
        Args:
            actor_name: Name of actor in level (e.g., "Car_1")
            visible: True to show, False to hide
            
        Returns:
            True if successful
        """
        try:
            actor_path = self._get_actor_path(actor_name)
            self.call_function(
                actor_path,
                "SetActorHiddenInGame",
                {"bNewHidden": not visible}  # Hidden is inverse of visible
            )
            logger.debug(f"Set visibility: {actor_name} = {visible}")
            return True
        except Exception as e:
            logger.error(f"Failed to set visibility for {actor_name}: {e}")
            return False
    
    def set_actor_transform(self, actor_name: str, 
                            location: Dict[str, float],
                            rotation: Dict[str, float] = None,
                            scale: float = 1.0) -> bool:
        """
        Set actor location, rotation, and scale.
        
        Args:
            actor_name: Name of actor in level (e.g., "Car_1")
            location: Dict with x, y, z in centimeters
            rotation: Dict with yaw, pitch, roll in degrees (optional)
            scale: Uniform scale factor (default 1.0)
            
        Returns:
            True if successful
        """
        try:
            actor_path = self._get_actor_path(actor_name)
            
            # Set location
            self.call_function(
                actor_path,
                "K2_SetActorLocation",
                {
                    "NewLocation": {
                        "X": location.get("x", 0),
                        "Y": location.get("y", 0),
                        "Z": location.get("z", 0),
                    },
                    "bSweep": False,
                    "bTeleport": True,
                }
            )
            
            # Set rotation if provided
            if rotation:
                self.call_function(
                    actor_path,
                    "K2_SetActorRotation",
                    {
                        "NewRotation": {
                            "Yaw": rotation.get("yaw", 0),
                            "Pitch": rotation.get("pitch", 0),
                            "Roll": rotation.get("roll", 0),
                        },
                        "bTeleportPhysics": True,
                    }
                )
            
            # Note: We don't modify scale - vehicles have their actual UE5 dimensions
            
            logger.debug(f"Set transform: {actor_name} at ({location['x']}, {location['y']}, {location['z']})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set transform for {actor_name}: {e}")
            return False
    
    def execute_spawn_commands(self, commands: List[Dict[str, Any]]) -> int:
        """
        Execute vehicle spawn commands (visibility + transform).
        
        Args:
            commands: List of command dicts from VehicleSpawner.get_ue5_spawn_commands()
            
        Returns:
            Number of successfully executed commands
        """
        success_count = 0
        
        for cmd in commands:
            try:
                if cmd["type"] == "set_visibility":
                    if self.set_actor_visibility(cmd["actor_name"], cmd["visible"]):
                        success_count += 1
                        
                elif cmd["type"] == "set_transform":
                    if self.set_actor_transform(
                        cmd["actor_name"],
                        cmd["location"],
                        cmd.get("rotation"),
                        cmd.get("scale", 1.0)
                    ):
                        success_count += 1
                        
            except Exception as e:
                logger.warning(f"Command failed: {cmd} - {e}")
                
        logger.info(f"Executed {success_count}/{len(commands)} spawn commands")
        return success_count
    
    def hide_all_vehicles(self, vehicle_actors: Dict[str, List[str]]) -> int:
        """
        Hide all vehicle actors.
        
        Args:
            vehicle_actors: Dict mapping class names to actor name lists
            
        Returns:
            Number of actors hidden
        """
        count = 0
        for class_name, actors in vehicle_actors.items():
            for actor_name in actors:
                if self.set_actor_visibility(actor_name, False):
                    count += 1
        logger.info(f"Hidden {count} vehicle actors")
        return count
    
    def get_actor_bounds(self, actor_name: str) -> Optional[Dict[str, float]]:
        """
        Get actor bounding box dimensions in centimeters.
        
        Args:
            actor_name: Name of actor in level
            
        Returns:
            Dict with length, width, height in cm, or None if failed
        """
        try:
            actor_path = self._get_actor_path(actor_name)
            result = self.call_function(
                actor_path,
                "GetActorBounds",
                {"bOnlyCollidingComponents": False}
            )
            
            # GetActorBounds returns Origin and BoxExtent
            # BoxExtent is half the size in each dimension
            extent = result.get("BoxExtent", {})
            return {
                "length": extent.get("X", 0) * 2,  # Full length (X axis)
                "width": extent.get("Y", 0) * 2,   # Full width (Y axis) 
                "height": extent.get("Z", 0) * 2,  # Full height (Z axis)
            }
        except Exception as e:
            logger.warning(f"Failed to get bounds for {actor_name}: {e}")
            return None

    def batch_commands(self, commands: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Execute multiple commands in a single request for better performance.
        
        Args:
            commands: List of command dictionaries
            
        Returns:
            Batch execution results
            
        Raises:
            RuntimeError: If batch execution fails
        """
        payload = {"Requests": commands}
        
        try:
            response = requests.put(
                self.batch_url,
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Batch command execution failed: {e}")
    
    def randomize_lighting(self, intensity_range: tuple, 
                          color_temp_range: tuple) -> None:
        """
        Randomize scene lighting via C++ SceneController.
        Hybrid approach: Python orchestration → C++ execution for performance.
        
        Args:
            intensity_range: (min, max) light intensity in candela
            color_temp_range: (min, max) color temperature in Kelvin
        """
        self.call_function(
            self.scene_controller_path,
            "RandomizeLighting",
            {
                "MinIntensity": intensity_range[0],
                "MaxIntensity": intensity_range[1],
                "MinTemperature": color_temp_range[0],
                "MaxTemperature": color_temp_range[1]
            }
        )
        logger.debug(f"Randomized lighting: intensity={intensity_range}, temp={color_temp_range}")
    
    def randomize_materials(self, object_types: List[str] = None) -> None:
        """
        Randomize materials via C++ SceneController.
        Hybrid approach: Python orchestration → C++ execution for performance.
        
        Args:
            object_types: List of actor name patterns to target for material randomization
        """
        if object_types is None:
            object_types = []
        
        self.call_function(
            self.scene_controller_path,
            "RandomizeMaterials",
            {"TargetTags": object_types}
        )
    
    def randomize_camera(self, distance_range: tuple, fov_range: tuple) -> None:
        """
        Randomize camera position and FOV via C++ DataCapture actor.
        Hybrid approach: Python orchestration → C++ execution for performance.
        
        Args:
            distance_range: (min, max) distance from target in cm
            fov_range: (min, max) field of view in degrees
        """
        self.call_function(
            self.data_capture_path,
            "RandomizeCamera",
            {
                "MinDistance": distance_range[0],
                "MaxDistance": distance_range[1],
                "MinFOV": fov_range[0],
                "MaxFOV": fov_range[1]
            }
        )
        logger.debug(f"Randomized camera: distance={distance_range}, fov={fov_range}")
    
    def spawn_objects(self, object_classes: List[str], count: int) -> None:
        """
        Spawn random objects in the scene.
        
        Args:
            object_classes: List of object class names to spawn
            count: Number of objects to spawn
        """
        self.call_function(
            self.scene_controller_path,
            "SpawnRandomObjects",
            {
                "NumObjects": count,
                "ObjectClasses": object_classes
            }
        )
        logger.debug(f"Spawned {count} objects from classes: {object_classes}")
    
    def generate_annotations(self, visible_actors: List[str] = None) -> Dict[str, Any]:
        """
        Generate bounding box annotations for visible vehicles.
        
        Args:
            visible_actors: List of actor names that are currently visible
            
        Returns:
            Dictionary containing bounding boxes
            
        Raises:
            RuntimeError: If annotation generation fails
        """
        try:
            # Call GenerateBoundingBoxes on DataCapture actor
            # Pass empty array - it will find all visible StaticMeshActors
            result = self.call_function(
                self.data_capture_path,
                "GenerateBoundingBoxes",
                {"TargetTags": []}
            )
            
            # Parse the JSON string returned
            json_str = result.get("ReturnValue", "{}")
            if isinstance(json_str, str):
                import json
                annotations = json.loads(json_str)
            else:
                annotations = json_str
            
            logger.debug(f"Generated annotations: {annotations}")
            
            return {
                "bounding_boxes": annotations.get("annotations", []),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Failed to generate annotations: {e}")
            return {"bounding_boxes": [], "timestamp": time.time()}
    
    def reset_scene(self) -> None:
        """Reset scene to default state."""
        self.call_function(
            self.scene_controller_path,
            "ResetScene",
            {}
        )
        logger.debug("Scene reset to default state")
    
    def close(self) -> None:
        """Close connection and cleanup resources."""
        logger.info("Closing UE5 bridge connection")
    
    def _execute_command(self, command: str) -> Dict[str, Any]:
        """
        Execute a console command in UE5.
        
        Args:
            command: Console command to execute
            
        Returns:
            Response from UE5
        """
        url = f"http://{self.host}:{self.port}/remote/exec"
        payload = {"Command": command}
        
        try:
            response = requests.post(url, json=payload, timeout=self.timeout)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.warning(f"Console command failed: {command} - {e}")
            return {}
