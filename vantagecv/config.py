#==============================================================================
# VantageCV - Configuration Loader
#==============================================================================
# File: config.py
# Description: Loads YAML configuration files for domain-specific settings
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

import yaml
from pathlib import Path
from typing import Dict, Any


class Config:
    """Loads and parses YAML config files for different domains."""
    
    def __init__(self, config_path: str):
        """Load configuration from YAML file."""
        self.config_path = Path(config_path)
        self.data = self._load_yaml()
    
    def _load_yaml(self) -> Dict[str, Any]:
        """Read YAML file and return as dictionary."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        
        with open(self.config_path, 'r') as f:
            return yaml.safe_load(f)
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get config value by key. Supports nested keys with dots.
        Example: config.get('camera.resolution') returns [1920, 1080]
        """
        keys = key.split('.')
        value = self.data
        
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
            else:
                return default
            
            if value is None:
                return default
        
        return value
    
    def __getitem__(self, key: str) -> Any:
        """Allow dict-style access: config['camera']"""
        return self.data[key]

