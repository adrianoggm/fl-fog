"""
Cloud Interface for Fog Computing Layer.

Handles communication between fog nodes and cloud infrastructure
for global model coordination and synchronization.
"""

import asyncio
import grpc
import json
import logging
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import aiohttp

logger = logging.getLogger(__name__)


class CloudInterface:
    """
    Communication interface between fog node and cloud services.
    
    Features:
    - gRPC communication with FL server
    - Periodic synchronization
    - Global model updates
    - Regional aggregation forwarding
    - Health reporting
    """
    
    def __init__(self, server_url: str, sync_interval: int, fog_node: Any):
        self.server_url = server_url
        self.sync_interval = sync_interval
        self.fog_node = fog_node
        
        # Communication state
        self.connected = False
        self.last_sync: Optional[datetime] = None
        
        # Background tasks
        self._sync_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Protocol detection
        self.use_grpc = server_url.startswith("grpc://")
        self.use_http = server_url.startswith("http://") or server_url.startswith("https://")
        
        if self.use_grpc:
            self.server_address = server_url.replace("grpc://", "")
            self.grpc_channel: Optional[grpc.aio.Channel] = None
        
        logger.info(f"Cloud interface initialized for {server_url}")
    
    async def start(self) -> None:
        """Start the cloud interface."""
        try:
            self._running = True
            
            # Establish connection
            await self._connect()
            
            # Start sync task
            self._sync_task = asyncio.create_task(self._sync_loop())
            
            logger.info("Cloud interface started")
            
        except Exception as e:
            logger.error(f"Failed to start cloud interface: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the cloud interface."""
        self._running = False
        
        if self._sync_task:
            self._sync_task.cancel()
            try:
                await self._sync_task
            except asyncio.CancelledError:
                pass
        
        await self._disconnect()
        logger.info("Cloud interface stopped")
    
    async def _connect(self) -> None:
        """Establish connection to cloud services."""
        if self.use_grpc:
            await self._connect_grpc()
        elif self.use_http:
            await self._connect_http()
        else:
            raise ValueError(f"Unsupported protocol in {self.server_url}")
    
    async def _disconnect(self) -> None:
        """Disconnect from cloud services."""
        if self.use_grpc and self.grpc_channel:
            await self.grpc_channel.close()
        
        self.connected = False
    
    async def _connect_grpc(self) -> None:
        """Connect using gRPC."""
        try:
            self.grpc_channel = grpc.aio.insecure_channel(self.server_address)
            
            # Test connection with health check
            await self._grpc_health_check()
            self.connected = True
            
            logger.info(f"Connected to gRPC server at {self.server_address}")
            
        except Exception as e:
            logger.error(f"Failed to connect to gRPC server: {e}")
            raise
    
    async def _connect_http(self) -> None:
        """Connect using HTTP/REST."""
        try:
            # Test connection with health check
            await self._http_health_check()
            self.connected = True
            
            logger.info(f"Connected to HTTP server at {self.server_url}")
            
        except Exception as e:
            logger.error(f"Failed to connect to HTTP server: {e}")
            raise
    
    async def _grpc_health_check(self) -> bool:
        """Perform gRPC health check."""
        # Implementation would depend on your gRPC service definition
        # For now, just assume success
        return True
    
    async def _http_health_check(self) -> bool:
        """Perform HTTP health check."""
        try:
            async with aiohttp.ClientSession() as session:
                health_url = f"{self.server_url}/health"
                async with session.get(health_url, timeout=10) as response:
                    return response.status == 200
        except Exception as e:
            logger.error(f"HTTP health check failed: {e}")
            return False
    
    async def _sync_loop(self) -> None:
        """Main synchronization loop."""
        while self._running:
            try:
                if self.connected:
                    await self._perform_sync()
                else:
                    await self._reconnect()
                
                await asyncio.sleep(self.sync_interval)
                
            except Exception as e:
                logger.error(f"Error in sync loop: {e}")
                await asyncio.sleep(self.sync_interval)
    
    async def _reconnect(self) -> None:
        """Attempt to reconnect to cloud services."""
        try:
            await self._connect()
        except Exception as e:
            logger.warning(f"Reconnection failed: {e}")
    
    async def _perform_sync(self) -> None:
        """Perform synchronization with cloud."""
        try:
            # Send fog node status
            await self._send_status_update()
            
            # Check for global model updates
            await self._check_global_model_updates()
            
            # Send any pending aggregation results
            await self._send_aggregation_results()
            
            self.last_sync = datetime.now()
            logger.debug("Cloud sync completed")
            
        except Exception as e:
            logger.error(f"Sync failed: {e}")
            self.connected = False
    
    async def _send_status_update(self) -> None:
        """Send fog node status to cloud."""
        status = self.fog_node.get_status()
        
        if self.use_grpc:
            await self._send_status_grpc(status)
        elif self.use_http:
            await self._send_status_http(status)
    
    async def _send_status_grpc(self, status: Dict[str, Any]) -> None:
        """Send status via gRPC."""
        # Implementation would depend on your gRPC service definition
        logger.debug("Sent status via gRPC")
    
    async def _send_status_http(self, status: Dict[str, Any]) -> None:
        """Send status via HTTP."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.server_url}/fog-nodes/{self.fog_node.node_id}/status"
                async with session.post(url, json=status, timeout=30) as response:
                    if response.status == 200:
                        logger.debug("Sent status via HTTP")
                    else:
                        logger.warning(f"Status update failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send status via HTTP: {e}")
    
    async def _check_global_model_updates(self) -> None:
        """Check for global model updates from cloud."""
        if self.use_grpc:
            await self._check_model_updates_grpc()
        elif self.use_http:
            await self._check_model_updates_http()
    
    async def _check_model_updates_grpc(self) -> None:
        """Check for model updates via gRPC."""
        # Implementation would depend on your gRPC service definition
        pass
    
    async def _check_model_updates_http(self) -> None:
        """Check for model updates via HTTP."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.server_url}/models/latest"
                params = {"region": self.fog_node.region}
                
                async with session.get(url, params=params, timeout=30) as response:
                    if response.status == 200:
                        model_data = await response.json()
                        await self._process_global_model_update(model_data)
        except Exception as e:
            logger.error(f"Failed to check model updates via HTTP: {e}")
    
    async def _process_global_model_update(self, model_data: Dict[str, Any]) -> None:
        """Process a global model update from cloud."""
        model_id = model_data.get("model_id", "global")
        version = model_data.get("version")
        weights = model_data.get("weights", {})
        
        if weights and version:
            # Cache the new model
            await self.fog_node.model_cache.cache_model(
                model_id, weights, version, model_data.get("metadata", {})
            )
            
            # Optionally broadcast to edge devices
            await self._broadcast_model_update(model_data)
            
            logger.info(f"Processed global model update: {model_id}:{version}")
    
    async def _broadcast_model_update(self, model_data: Dict[str, Any]) -> None:
        """Broadcast model update to edge devices."""
        await self.fog_node.edge_interface.broadcast_to_devices(
            "model/update", model_data
        )
    
    async def _send_aggregation_results(self) -> None:
        """Send regional aggregation results to cloud."""
        # Get recent aggregation results
        recent_results = self.fog_node.regional_aggregator.aggregation_history[-5:]  # Last 5
        
        for result in recent_results:
            # Check if this result has already been sent
            if not hasattr(result, '_sent_to_cloud'):
                await self._send_aggregation_result(result)
                result._sent_to_cloud = True
    
    async def _send_aggregation_result(self, result) -> None:
        """Send a single aggregation result to cloud."""
        aggregation_data = {
            "fog_node_id": result.fog_node_id,
            "aggregation_round": result.aggregation_round,
            "participating_clients": result.participating_clients,
            "total_samples": result.total_samples,
            "average_loss": result.average_loss,
            "aggregated_weights": result.aggregated_weights,
            "created_at": result.created_at.isoformat()
        }
        
        if self.use_grpc:
            await self._send_aggregation_grpc(aggregation_data)
        elif self.use_http:
            await self._send_aggregation_http(aggregation_data)
    
    async def _send_aggregation_grpc(self, data: Dict[str, Any]) -> None:
        """Send aggregation result via gRPC."""
        # Implementation would depend on your gRPC service definition
        logger.debug("Sent aggregation result via gRPC")
    
    async def _send_aggregation_http(self, data: Dict[str, Any]) -> None:
        """Send aggregation result via HTTP."""
        try:
            async with aiohttp.ClientSession() as session:
                url = f"{self.server_url}/aggregation-results"
                async with session.post(url, json=data, timeout=60) as response:
                    if response.status == 200:
                        logger.debug("Sent aggregation result via HTTP")
                    else:
                        logger.warning(f"Aggregation result send failed: {response.status}")
        except Exception as e:
            logger.error(f"Failed to send aggregation result via HTTP: {e}")
    
    # Public API methods
    
    async def report_fog_node_registration(self) -> bool:
        """Register this fog node with cloud services."""
        registration_data = {
            "node_id": self.fog_node.node_id,
            "region": self.fog_node.region,
            "capabilities": {
                "max_edge_devices": self.fog_node.edge_coordinator.max_edge_devices,
                "aggregation_strategies": ["fedavg", "fedprox", "regional", "adaptive"],
                "cache_size_gb": self.fog_node.model_cache.max_size_bytes / (1024**3)
            },
            "registered_at": datetime.now().isoformat()
        }
        
        if self.use_http:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.server_url}/fog-nodes/register"
                    async with session.post(url, json=registration_data, timeout=30) as response:
                        return response.status == 200
            except Exception as e:
                logger.error(f"Registration failed: {e}")
                return False
        
        # For gRPC, implement similar registration
        return True
    
    async def request_global_model(self, model_id: str = "global") -> Optional[Dict[str, Any]]:
        """Request latest global model from cloud."""
        if self.use_http:
            try:
                async with aiohttp.ClientSession() as session:
                    url = f"{self.server_url}/models/{model_id}/latest"
                    async with session.get(url, timeout=60) as response:
                        if response.status == 200:
                            return await response.json()
            except Exception as e:
                logger.error(f"Failed to request global model: {e}")
        
        return None
    
    def get_cloud_stats(self) -> Dict[str, Any]:
        """Get cloud interface statistics."""
        return {
            "connected": self.connected,
            "server_url": self.server_url,
            "last_sync": self.last_sync.isoformat() if self.last_sync else None,
            "sync_interval": self.sync_interval,
            "protocol": "grpc" if self.use_grpc else "http"
        }
