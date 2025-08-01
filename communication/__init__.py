"""
FL-Fog Communication Module
==========================

Communication interfaces for fog node interactions with:
- Edge devices (MQTT/CoAP)
- Cloud server (gRPC/HTTP)
- Peer fog nodes (HTTP/REST)
"""

from .cloud_interface import CloudInterface
from .edge_interface import EdgeInterface
from .peer_interface import PeerInterface

__all__ = ["EdgeInterface", "CloudInterface", "PeerInterface"]
