"""
Peer Interface for Fog-to-Fog Communication
==========================================

Handles communication between fog nodes for collaboration,
resource sharing, and distributed coordination.
"""

import asyncio
import logging
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Callable, Dict, Optional

import aiohttp
from aiohttp import ClientSession, web


@dataclass
class PeerNode:
    """Information about a peer fog node."""

    node_id: str
    region: str
    endpoint: str
    capabilities: Dict[str, Any]
    last_seen: datetime
    status: str = "active"  # active, inactive, unreachable


@dataclass
class CollaborationRequest:
    """Request for inter-fog collaboration."""

    request_id: str
    source_node: str
    target_node: str
    request_type: str  # resource_sharing, model_sharing, load_balancing
    data: Dict[str, Any]
    timestamp: datetime
    priority: int = 1  # 1=low, 5=high


class PeerInterface:
    """
    Interface for fog-to-fog communication.

    Enables:
    - Peer discovery and registration
    - Resource sharing between fog nodes
    - Model sharing and collaborative training
    - Load balancing and task migration
    - Distributed consensus for coordination
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize peer interface."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Configuration
        self.port = config.get("port", 8080)
        self.host = config.get("host", "0.0.0.0")
        self.discovery_enabled = config.get("discovery_enabled", True)
        self.heartbeat_interval = config.get("heartbeat_interval", 30)

        # State management
        self.peer_nodes: Dict[str, PeerNode] = {}
        self.message_handlers: Dict[str, Callable] = {}
        self.collaboration_requests: Dict[str, CollaborationRequest] = {}

        # HTTP server and client
        self.app = web.Application()
        self.server = None
        self.client_session: Optional[ClientSession] = None

        # Running state
        self.is_running = False

        # Setup HTTP routes
        self._setup_routes()

        self.logger.info("Peer interface initialized")

    def _setup_routes(self):
        """Setup HTTP routes for peer communication."""
        self.app.router.add_post("/peer/register", self._handle_peer_registration)
        self.app.router.add_post("/peer/heartbeat", self._handle_heartbeat)
        self.app.router.add_post(
            "/peer/collaborate", self._handle_collaboration_request
        )
        self.app.router.add_post("/peer/resource_share", self._handle_resource_sharing)
        self.app.router.add_post("/peer/model_share", self._handle_model_sharing)
        self.app.router.add_get("/peer/status", self._handle_status_request)
        self.app.router.add_get("/peer/peers", self._handle_peers_list)
        self.app.router.add_get("/health", self._handle_health_check)

    async def start(self):
        """Start peer interface services."""
        if self.is_running:
            return

        self.logger.info(f"Starting peer interface on {self.host}:{self.port}")

        # Start HTTP client session
        self.client_session = aiohttp.ClientSession(
            timeout=aiohttp.ClientTimeout(total=30)
        )

        # Start HTTP server
        self.server = await aiohttp.web.create_server(self.app, self.host, self.port)

        self.is_running = True

        # Start background tasks
        if self.discovery_enabled:
            asyncio.create_task(self._peer_discovery_loop())

        asyncio.create_task(self._heartbeat_loop())
        asyncio.create_task(self._cleanup_inactive_peers())

        self.logger.info("Peer interface started successfully")

    async def stop(self):
        """Stop peer interface services."""
        if not self.is_running:
            return

        self.logger.info("Stopping peer interface")

        self.is_running = False

        # Close client session
        if self.client_session:
            await self.client_session.close()

        # Stop server
        if self.server:
            self.server.close()
            await self.server.wait_closed()

        self.logger.info("Peer interface stopped")

    def set_message_handler(self, message_type: str, handler: Callable):
        """Set handler for specific message type."""
        self.message_handlers[message_type] = handler
        self.logger.debug(f"Registered handler for message type: {message_type}")

    async def register_peer(self, peer_info: Dict[str, Any]) -> bool:
        """Register a new peer fog node."""
        try:
            peer = PeerNode(
                node_id=peer_info["node_id"],
                region=peer_info["region"],
                endpoint=peer_info["endpoint"],
                capabilities=peer_info.get("capabilities", {}),
                last_seen=datetime.now(),
                status="active",
            )

            self.peer_nodes[peer.node_id] = peer
            self.logger.info(f"Registered peer node: {peer.node_id} in {peer.region}")

            return True
        except Exception as e:
            self.logger.error(f"Failed to register peer: {e}")
            return False

    async def send_collaboration_request(
        self,
        target_node: str,
        request_type: str,
        data: Dict[str, Any],
        priority: int = 1,
    ) -> Optional[str]:
        """Send collaboration request to peer node."""
        if target_node not in self.peer_nodes:
            self.logger.error(f"Unknown peer node: {target_node}")
            return None

        peer = self.peer_nodes[target_node]
        request_id = f"req_{datetime.now().timestamp():.0f}"

        request = CollaborationRequest(
            request_id=request_id,
            source_node="self",  # Will be filled with actual node ID
            target_node=target_node,
            request_type=request_type,
            data=data,
            timestamp=datetime.now(),
            priority=priority,
        )

        try:
            async with self.client_session.post(
                f"{peer.endpoint}/peer/collaborate",
                json=asdict(request),
                headers={"Content-Type": "application/json"},
            ) as response:
                if response.status == 200:
                    self.collaboration_requests[request_id] = request
                    self.logger.info(
                        f"Sent collaboration request {request_id} to {target_node}"
                    )
                    return request_id
                else:
                    self.logger.error(
                        f"Failed to send request to {target_node}: {response.status}"
                    )
                    return None

        except Exception as e:
            self.logger.error(f"Error sending collaboration request: {e}")
            return None

    async def share_resource(
        self, target_node: str, resource_type: str, resource_data: Dict[str, Any]
    ) -> bool:
        """Share computational resource with peer node."""
        return (
            await self.send_collaboration_request(
                target_node,
                "resource_sharing",
                {
                    "resource_type": resource_type,
                    "resource_data": resource_data,
                    "action": "offer",
                },
                priority=3,
            )
            is not None
        )

    async def share_model(self, target_node: str, model_data: Dict[str, Any]) -> bool:
        """Share model or model updates with peer node."""
        return (
            await self.send_collaboration_request(
                target_node,
                "model_sharing",
                {"model_data": model_data, "action": "share"},
                priority=2,
            )
            is not None
        )

    async def request_load_balancing(
        self, target_node: str, workload: Dict[str, Any]
    ) -> bool:
        """Request load balancing assistance from peer node."""
        return (
            await self.send_collaboration_request(
                target_node,
                "load_balancing",
                {"workload": workload, "action": "migrate"},
                priority=4,
            )
            is not None
        )

    async def broadcast_to_region(
        self, region: str, message_type: str, data: Dict[str, Any]
    ):
        """Broadcast message to all peers in a specific region."""
        region_peers = [
            peer
            for peer in self.peer_nodes.values()
            if peer.region == region and peer.status == "active"
        ]

        tasks = []
        for peer in region_peers:
            task = self.send_collaboration_request(peer.node_id, message_type, data)
            tasks.append(task)

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            successful = sum(
                1 for r in results if r is not None and not isinstance(r, Exception)
            )
            self.logger.info(
                f"Broadcast to {region}: {successful}/{len(tasks)} successful"
            )

    async def get_peer_status(self, peer_id: str) -> Optional[Dict[str, Any]]:
        """Get status information from peer node."""
        if peer_id not in self.peer_nodes:
            return None

        peer = self.peer_nodes[peer_id]

        try:
            async with self.client_session.get(
                f"{peer.endpoint}/peer/status"
            ) as response:
                if response.status == 200:
                    status_data = await response.json()
                    peer.last_seen = datetime.now()
                    peer.status = "active"
                    return status_data
                else:
                    peer.status = "unreachable"
                    return None

        except Exception as e:
            self.logger.error(f"Error getting peer status: {e}")
            peer.status = "unreachable"
            return None

    # HTTP Request Handlers

    async def _handle_peer_registration(self, request: web.Request) -> web.Response:
        """Handle peer registration request."""
        try:
            data = await request.json()
            success = await self.register_peer(data)

            if success:
                return web.json_response(
                    {"status": "success", "message": "Peer registered"}
                )
            else:
                return web.json_response(
                    {"status": "error", "message": "Registration failed"}, status=400
                )

        except Exception as e:
            self.logger.error(f"Error in peer registration: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_heartbeat(self, request: web.Request) -> web.Response:
        """Handle heartbeat from peer node."""
        try:
            data = await request.json()
            peer_id = data.get("node_id")

            if peer_id in self.peer_nodes:
                self.peer_nodes[peer_id].last_seen = datetime.now()
                self.peer_nodes[peer_id].status = "active"

                return web.json_response({"status": "success"})
            else:
                return web.json_response(
                    {"status": "error", "message": "Unknown peer"}, status=404
                )

        except Exception as e:
            self.logger.error(f"Error in heartbeat handling: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_collaboration_request(self, request: web.Request) -> web.Response:
        """Handle collaboration request from peer."""
        try:
            data = await request.json()
            collaboration_req = CollaborationRequest(**data)

            # Store request
            self.collaboration_requests[collaboration_req.request_id] = (
                collaboration_req
            )

            # Call appropriate handler
            handler = self.message_handlers.get("peer_collaboration")
            if handler:
                await handler(data)

            return web.json_response(
                {"status": "success", "request_id": collaboration_req.request_id}
            )

        except Exception as e:
            self.logger.error(f"Error handling collaboration request: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_resource_sharing(self, request: web.Request) -> web.Response:
        """Handle resource sharing request."""
        try:
            data = await request.json()

            # Call resource sharing handler
            handler = self.message_handlers.get("resource_sharing")
            if handler:
                result = await handler(data)
                return web.json_response({"status": "success", "result": result})
            else:
                return web.json_response(
                    {"status": "error", "message": "No handler for resource sharing"},
                    status=501,
                )

        except Exception as e:
            self.logger.error(f"Error handling resource sharing: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_model_sharing(self, request: web.Request) -> web.Response:
        """Handle model sharing request."""
        try:
            data = await request.json()

            # Call model sharing handler
            handler = self.message_handlers.get("model_sharing")
            if handler:
                result = await handler(data)
                return web.json_response({"status": "success", "result": result})
            else:
                return web.json_response(
                    {"status": "error", "message": "No handler for model sharing"},
                    status=501,
                )

        except Exception as e:
            self.logger.error(f"Error handling model sharing: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_status_request(self, request: web.Request) -> web.Response:
        """Handle status request from peer."""
        try:
            status = {
                "node_id": "self",  # Will be filled with actual node ID
                "timestamp": datetime.now().isoformat(),
                "peer_count": len(self.peer_nodes),
                "active_requests": len(self.collaboration_requests),
                "status": "active",
            }

            return web.json_response(status)

        except Exception as e:
            self.logger.error(f"Error handling status request: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_peers_list(self, request: web.Request) -> web.Response:
        """Handle request for peers list."""
        try:
            peers_list = [
                {
                    "node_id": peer.node_id,
                    "region": peer.region,
                    "status": peer.status,
                    "last_seen": peer.last_seen.isoformat(),
                }
                for peer in self.peer_nodes.values()
            ]

            return web.json_response({"peers": peers_list})

        except Exception as e:
            self.logger.error(f"Error handling peers list request: {e}")
            return web.json_response({"status": "error", "message": str(e)}, status=500)

    async def _handle_health_check(self, request: web.Request) -> web.Response:
        """Handle health check request."""
        return web.json_response(
            {
                "status": "healthy",
                "timestamp": datetime.now().isoformat(),
                "peers": len(self.peer_nodes),
            }
        )

    # Background Tasks

    async def _peer_discovery_loop(self):
        """Periodic peer discovery and health checks."""
        while self.is_running:
            try:
                # Check health of known peers
                for peer_id in list(self.peer_nodes.keys()):
                    await self.get_peer_status(peer_id)

                await asyncio.sleep(60)  # Discovery every minute

            except Exception as e:
                self.logger.error(f"Error in peer discovery: {e}")
                await asyncio.sleep(30)

    async def _heartbeat_loop(self):
        """Send heartbeat to all active peers."""
        while self.is_running:
            try:
                heartbeat_data = {
                    "node_id": "self",  # Will be filled with actual node ID
                    "timestamp": datetime.now().isoformat(),
                    "status": "active",
                }

                for peer in self.peer_nodes.values():
                    if peer.status == "active":
                        try:
                            async with self.client_session.post(
                                f"{peer.endpoint}/peer/heartbeat", json=heartbeat_data
                            ) as response:
                                if response.status != 200:
                                    peer.status = "unreachable"

                        except Exception:
                            peer.status = "unreachable"

                await asyncio.sleep(self.heartbeat_interval)

            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
                await asyncio.sleep(self.heartbeat_interval)

    async def _cleanup_inactive_peers(self):
        """Clean up inactive peers and old requests."""
        while self.is_running:
            try:
                now = datetime.now()

                # Remove peers that haven't been seen for too long
                inactive_threshold = 300  # 5 minutes
                inactive_peers = [
                    peer_id
                    for peer_id, peer in self.peer_nodes.items()
                    if (now - peer.last_seen).total_seconds() > inactive_threshold
                ]

                for peer_id in inactive_peers:
                    del self.peer_nodes[peer_id]
                    self.logger.info(f"Removed inactive peer: {peer_id}")

                # Remove old collaboration requests
                old_threshold = 3600  # 1 hour
                old_requests = [
                    req_id
                    for req_id, req in self.collaboration_requests.items()
                    if (now - req.timestamp).total_seconds() > old_threshold
                ]

                for req_id in old_requests:
                    del self.collaboration_requests[req_id]

                await asyncio.sleep(300)  # Cleanup every 5 minutes

            except Exception as e:
                self.logger.error(f"Error in cleanup: {e}")
                await asyncio.sleep(60)
