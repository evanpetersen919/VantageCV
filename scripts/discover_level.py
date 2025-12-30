#!/usr/bin/env python3
"""
VantageCV - Level Discovery Tool

File: discover_level.py
Description: Automatically discover VantageCV actors in the current UE5 level.
             Outputs the correct paths for config files.
Author: Evan Petersen
Date: December 2025

Usage:
    python scripts/discover_level.py
    python scripts/discover_level.py --update-config configs/automotive.yaml
"""

import sys
import json
import argparse
import requests
from pathlib import Path
from typing import Dict, List, Optional, Tuple

sys.path.insert(0, str(Path(__file__).parent.parent))


class LevelDiscovery:
    """
    Discovers VantageCV actors in the current UE5 level.
    
    This solves the problem of camera/actor paths breaking when
    switching between levels or creating new ones.
    """
    
    def __init__(self, host: str = "localhost", port: int = 30010):
        self.base_url = f"http://{host}:{port}"
        self.discovered_actors: Dict[str, str] = {}
        
    def connect(self) -> bool:
        """Test connection to UE5."""
        try:
            response = requests.get(f"{self.base_url}/remote/info", timeout=5)
            return response.status_code == 200
        except:
            return False
    
    def get_current_level(self) -> Optional[str]:
        """Get the name of the currently loaded level."""
        try:
            # Use Remote Control to query world
            response = requests.put(
                f"{self.base_url}/remote/object/call",
                json={
                    "objectPath": "/Script/Engine.GameplayStatics",
                    "functionName": "GetCurrentLevelName",
                    "parameters": {"WorldContextObject": None}
                },
                timeout=5
            )
            # This may not work - try alternative
        except:
            pass
        return None
    
    def search_actors(self, class_filter: str = "") -> List[Dict]:
        """
        Search for actors in the current level.
        
        Args:
            class_filter: Filter by class name (e.g., "DataCapture")
        """
        try:
            payload = {
                "Query": class_filter,
                "Class": "/Script/Engine.Actor",
                "Limit": 100
            }
            
            response = requests.put(
                f"{self.base_url}/remote/search/assets",
                json=payload,
                timeout=10
            )
            
            if response.status_code == 200:
                return response.json().get('Assets', [])
        except Exception as e:
            print(f"  Search error: {e}")
        return []
    
    def find_vantagecv_actors(self) -> Dict[str, str]:
        """
        Find all VantageCV-related actors in the level.
        
        Returns:
            Dictionary mapping actor type to full path
        """
        print("\nSearching for VantageCV actors...")
        print("-" * 50)
        
        # Actor types we're looking for
        target_actors = [
            ("DataCapture", "data_capture_path"),
            ("SceneController", "scene_controller_path"),
            ("DomainRandomization", "domain_randomization_path"),
        ]
        
        for actor_class, config_key in target_actors:
            print(f"\n  Looking for {actor_class}...")
            
            # Try multiple search patterns
            found_path = self._try_find_actor(actor_class)
            
            if found_path:
                self.discovered_actors[config_key] = found_path
                print(f"  ✓ Found: {found_path}")
            else:
                print(f"  ✗ Not found in level")
        
        return self.discovered_actors
    
    def _try_find_actor(self, actor_class: str) -> Optional[str]:
        """Try various methods to find an actor."""
        
        # Method 1: Search by class name in assets
        assets = self.search_actors(actor_class)
        for asset in assets:
            path = asset.get('Path', '')
            if actor_class.lower() in path.lower():
                # Verify it's accessible
                if self._verify_actor_path(path):
                    return path
        
        # Method 2: Try common naming patterns
        patterns = [
            f"/Game/{{level}}.{{level}}:PersistentLevel.{actor_class}",
            f"/Game/{{level}}.{{level}}:PersistentLevel.{actor_class}_1",
            f"/Game/{{level}}.{{level}}:PersistentLevel.BP_{actor_class}",
            f"/Game/{{level}}.{{level}}:PersistentLevel.BP_{actor_class}_C_0",
        ]
        
        # Try common level names
        common_levels = ["automobile", "automotive", "industrial", "main", "test"]
        
        for level in common_levels:
            for pattern in patterns:
                path = pattern.format(level=level)
                if self._verify_actor_path(path):
                    return path
        
        return None
    
    def _verify_actor_path(self, path: str) -> bool:
        """Verify that an actor path is valid and accessible."""
        try:
            response = requests.put(
                f"{self.base_url}/remote/object/describe",
                json={"objectPath": path},
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def test_actor_functions(self) -> Dict[str, bool]:
        """Test that each discovered actor's functions work."""
        print("\nTesting actor functions...")
        print("-" * 50)
        
        results = {}
        
        # Test DataCapture
        if 'data_capture_path' in self.discovered_actors:
            path = self.discovered_actors['data_capture_path']
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": path,
                        "functionName": "SetResolution",
                        "parameters": {"Width": 1920, "Height": 1080}
                    },
                    timeout=5
                )
                results['DataCapture.SetResolution'] = response.status_code == 200
                print(f"  DataCapture.SetResolution: {'✓' if results['DataCapture.SetResolution'] else '✗'}")
            except:
                results['DataCapture.SetResolution'] = False
        
        # Test SceneController
        if 'scene_controller_path' in self.discovered_actors:
            path = self.discovered_actors['scene_controller_path']
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": path,
                        "functionName": "RandomizeLighting",
                        "parameters": {
                            "MinIntensity": 5.0,
                            "MaxIntensity": 10.0,
                            "MinTemperature": 5000.0,
                            "MaxTemperature": 6500.0
                        }
                    },
                    timeout=5
                )
                results['SceneController.RandomizeLighting'] = response.status_code == 200
                print(f"  SceneController.RandomizeLighting: {'✓' if results['SceneController.RandomizeLighting'] else '✗'}")
            except:
                results['SceneController.RandomizeLighting'] = False
        
        # Test DomainRandomization
        if 'domain_randomization_path' in self.discovered_actors:
            path = self.discovered_actors['domain_randomization_path']
            try:
                response = requests.put(
                    f"{self.base_url}/remote/object/call",
                    json={
                        "objectPath": path,
                        "functionName": "ApplyRandomization",
                        "parameters": {}
                    },
                    timeout=5
                )
                results['DomainRandomization.ApplyRandomization'] = response.status_code == 200
                print(f"  DomainRandomization.ApplyRandomization: {'✓' if results['DomainRandomization.ApplyRandomization'] else '✗'}")
            except:
                results['DomainRandomization.ApplyRandomization'] = False
        
        return results
    
    def generate_config_snippet(self) -> str:
        """Generate YAML config snippet for discovered actors."""
        lines = [
            "#==============================================================================",
            "# UE5 Integration Settings (Auto-discovered)",
            "#==============================================================================",
            "ue5:",
            "  # Remote Control API settings",
            "  remote_control_port: 30010",
            "  ",
            "  # Actor paths in your UE5 level",
        ]
        
        if 'scene_controller_path' in self.discovered_actors:
            lines.append(f'  scene_controller_path: "{self.discovered_actors["scene_controller_path"]}"')
        else:
            lines.append('  # scene_controller_path: "<not found>"')
        
        if 'data_capture_path' in self.discovered_actors:
            lines.append(f'  data_capture_path: "{self.discovered_actors["data_capture_path"]}"')
        else:
            lines.append('  # data_capture_path: "<not found>"')
        
        if 'domain_randomization_path' in self.discovered_actors:
            lines.append(f'  domain_randomization_path: "{self.discovered_actors["domain_randomization_path"]}"')
        else:
            lines.append('  # domain_randomization_path: "<not found>"')
        
        lines.extend([
            "  ",
            "  # Output settings",
            "  default_resolution: [1920, 1080]",
        ])
        
        return '\n'.join(lines)
    
    def update_config_file(self, config_path: str) -> bool:
        """Update an existing config file with discovered paths."""
        config_file = Path(config_path)
        
        if not config_file.exists():
            print(f"Config file not found: {config_path}")
            return False
        
        content = config_file.read_text()
        
        # Update each path
        updates = []
        for config_key, actor_path in self.discovered_actors.items():
            # Find and replace the line
            import re
            pattern = rf'(\s*{config_key}:\s*)"[^"]*"'
            replacement = rf'\1"{actor_path}"'
            new_content, count = re.subn(pattern, replacement, content)
            if count > 0:
                content = new_content
                updates.append(config_key)
        
        if updates:
            config_file.write_text(content)
            print(f"\nUpdated {config_path}:")
            for key in updates:
                print(f"  - {key}")
            return True
        else:
            print(f"\nNo updates needed for {config_path}")
            return False


def main():
    parser = argparse.ArgumentParser(
        description="Discover VantageCV actors in current UE5 level"
    )
    parser.add_argument(
        '--port',
        type=int,
        default=30010,
        help='Remote Control API port'
    )
    parser.add_argument(
        '--update-config',
        type=str,
        help='Update config file with discovered paths'
    )
    
    args = parser.parse_args()
    
    print("="*60)
    print("VantageCV Level Discovery")
    print("="*60)
    
    discovery = LevelDiscovery(port=args.port)
    
    # Test connection
    print("\nConnecting to UE5...")
    if not discovery.connect():
        print("✗ Failed to connect to UE5 Remote Control API")
        print("  Make sure UE5 is running with Remote Control enabled")
        sys.exit(1)
    print("✓ Connected to UE5")
    
    # Find actors
    actors = discovery.find_vantagecv_actors()
    
    if not actors:
        print("\n❌ No VantageCV actors found in current level")
        print("\nMake sure you have placed these actors in your level:")
        print("  - DataCapture (from VantageCV plugin)")
        print("  - SceneController (from VantageCV plugin)")
        print("  - DomainRandomization (from VantageCV plugin)")
        sys.exit(1)
    
    # Test functions
    discovery.test_actor_functions()
    
    # Generate config
    print("\n" + "="*60)
    print("CONFIG SNIPPET")
    print("="*60)
    print(discovery.generate_config_snippet())
    print("="*60)
    
    # Update config if requested
    if args.update_config:
        discovery.update_config_file(args.update_config)
    
    print("\n✓ Discovery complete\n")


if __name__ == "__main__":
    main()
