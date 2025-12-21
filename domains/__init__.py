#==============================================================================
# VantageCV - Domains Package
#==============================================================================
# File: __init__.py
# Description: Domain plugin system for industry-specific configurations
# Author: Evan Petersen
# Date: December 2025
#==============================================================================

"""Domain-specific configurations and plugins for VantageCV."""

from .base import BaseDomain
from .industrial import IndustrialDomain
from .automotive import AutomotiveDomain

__all__ = ['BaseDomain', 'IndustrialDomain', 'AutomotiveDomain']

