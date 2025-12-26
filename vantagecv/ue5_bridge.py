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
    
    def __init__(self, host: str = "localhost", port: int = 30010, timeout: int = 30):
        """
        Initialize UE5 bridge connection.
        
        Args:
            host: UE5 server hostname
            port: Remote Control API port
            timeout: Request timeout in seconds
            
        Raises:
            ConnectionError: If unable to connect to UE5
        """
        self.host = host
        self.port = port
        self.timeout = timeout
        self.base_url = f"http://{host}:{port}/remote/object"
        self.batch_url = f"http://{host}:{port}/remote/batch"
        
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
    
    def capture_frame(self, output_path: str = None) -> bool:
        """
        Capture a frame using the VantageCVSubsystem.
        
        Args:
            output_path: Path where to save the image (currently unused, subsystem uses fixed path)
            
        Returns:
            True if capture succeeded, False otherwise
            
        Raises:
            RuntimeError: If capture fails
        """
        result = self.call_function(
            object_path="/Script/VantageCV.Default__VantageCVSubsystem",
            function_name="CaptureFrame",
            parameters={}
        )
        
        return result.get('ReturnValue', False)
        
        try:
            response = requests.put(
                f"{self.base_url}/call",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(
                f"Failed to call {function_name} on {object_path}: {e}"
            )
    
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
        Randomize scene lighting parameters.
        
        Args:
            intensity_range: (min, max) light intensity
            color_temp_range: (min, max) color temperature in Kelvin
        """
        self.call_function(
            "/Game/VantageCV/SceneController",
            "RandomizeLighting",
            {
                "IntensityMin": intensity_range[0],
                "IntensityMax": intensity_range[1],
                "ColorTempMin": color_temp_range[0],
                "ColorTempMax": color_temp_range[1]
            }
        )
        logger.debug(f"Randomized lighting: intensity={intensity_range}, temp={color_temp_range}")
    
    def randomize_materials(self, object_types: List[str]) -> None:
        """
        Randomize materials on specified object types.
        
        Args:
            object_types: List of object type names to randomize
        """
        self.call_function(
            "/Game/VantageCV/SceneController",
            "RandomizeMaterials",
            {"ObjectTypes": object_types}
        )
        logger.debug(f"Randomized materials for: {object_types}")
    
    def spawn_objects(self, object_classes: List[str], count: int) -> None:
        """
        Spawn random objects in the scene.
        
        Args:
            object_classes: List of object class names to spawn
            count: Number of objects to spawn
        """
        self.call_function(
            "/Game/VantageCV/SceneController",
            "SpawnRandomObjects",
            {
                "ObjectClasses": object_classes,
                "Count": count
            }
        )
        logger.debug(f"Spawned {count} objects from classes: {object_classes}")
    
    def capture_frame(self, output_path: str) -> bool:
        """
        Capture current frame to disk via VantageCVSubsystem.
        
        Args:
            output_path: Filesystem path to save captured image
            
        Returns:
            True if capture succeeded
            
        Raises:
            RuntimeError: If capture fails
        """
        # Call VantageCVSubsystem which triggers DataCapture actor
        result = self.call_function(
            "/Script/VantageCV.Default__VantageCVSubsystem",
            "CaptureFrame"
        )
        
        success = result.get("ReturnValue", False)
        if not success:
            raise RuntimeError(f"Frame capture failed")
        
        logger.debug(f"Triggered frame capture via subsystem")
        return True
    
    def generate_annotations(self) -> Dict[str, Any]:
        """
        Generate annotations for the current scene.
        
        Returns:
            Dictionary containing bounding boxes, segmentation masks, etc.
            
        Raises:
            RuntimeError: If annotation generation fails
        """
        result = self.call_function(
            "/Game/VantageCV/DataCapture",
            "GenerateBoundingBoxes",
            {}
        )
        
        annotations = result.get("ReturnValue", [])
        logger.debug(f"Generated {len(annotations)} annotations")
        
        return {
            "bounding_boxes": annotations,
            "timestamp": time.time()
        }
    
    def reset_scene(self) -> None:
        """Reset scene to default state."""
        self.call_function(
            "/Game/VantageCV/SceneController",
            "ResetScene",
            {}
        )
        logger.debug("Scene reset to default state")
    
    def close(self) -> None:
        """Close connection and cleanup resources."""
        logger.info("Closing UE5 bridge connection")
