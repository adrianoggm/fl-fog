"""
FL-Fog: Fog Computing Layer for Federated Learning
==================================================

Main module providing fog computing capabilities for
continuum computing in federated learning.
"""

from .fog_node import FogNode
from .communication import EdgeInterface, CloudInterface, PeerInterface

__version__ = "0.1.0"
__author__ = "FL-Fog Development Team"

__all__ = [
    "FogNode",
    "EdgeInterface", 
    "CloudInterface",
    "PeerInterface"
]
