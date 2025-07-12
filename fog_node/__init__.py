"""
Main Fog Node Implementation.

Central orchestrator for the fog computing layer that coordinates
edge devices, regional aggregation, and cloud communication.
"""

__version__ = "0.1.0"
__author__ = "TFM Federated Learning Team"
__email__ = "fl-fog@project.com"

import asyncio
import signal
import sys
from typing import Dict, Any, Optional, List
import logging
from datetime import datetime
import yaml
from pathlib import Path

from .aggregator import RegionalAggregator, AggregationStrategy, EdgeUpdate
from .edge_coordinator import EdgeCoordinator, EdgeDeviceStatus
from .model_cache import ModelCache
from ..communication.edge_interface import EdgeInterface
from ..communication.cloud_interface import CloudInterface

logger = logging.getLogger(__name__)


class FogNode:
    """
    Main Fog Node implementation.
    
    Orchestrates all fog computing services:
    - Edge device coordination
    - Regional FL aggregation  
    - Model caching and versioning
    - Cloud communication
    - Resource management
    """
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.node_id = config["fog_node"]["id"]
        self.region = config["fog_node"]["region"]
        
        # Core components
        self.edge_coordinator = EdgeCoordinator(
            fog_node_id=self.node_id,
            max_edge_devices=config["edge_interface"]["max_edge_clients"],
            health_check_interval=config.get("monitoring", {}).get("health_check_interval", 30.0)
        )
        
        self.regional_aggregator = RegionalAggregator(
            fog_node_id=self.node_id,
            strategy=AggregationStrategy(config.get("aggregation", {}).get("strategy", "fedavg")),
            min_clients=config.get("aggregation", {}).get("min_clients", 3),
            max_wait_time=config.get("aggregation", {}).get("max_wait_time", 120.0)
        )
        
        self.model_cache = ModelCache(
            cache_size=config.get("caching", {}).get("max_size_gb", 10.0),
            ttl_hours=config.get("caching", {}).get("ttl_hours", 24)
        )
        
        # Communication interfaces
        self.edge_interface = EdgeInterface(
            mqtt_broker=config["edge_interface"]["mqtt_broker"],
            fog_node=self
        )
        
        self.cloud_interface = CloudInterface(
            server_url=config["cloud_interface"]["server_url"],
            sync_interval=config["cloud_interface"]["sync_interval"],
            fog_node=self
        )
        
        # State management
        self._running = False
        self._startup_time: Optional[datetime] = None
        self._tasks: List[asyncio.Task] = []
        
        # Statistics and monitoring
        self.stats = {
            "aggregation_rounds": 0,
            "devices_served": 0,
            "models_cached": 0,
            "uptime_seconds": 0
        }
        
        logger.info(f"Fog node {self.node_id} initialized for region {self.region}")
    
    async def start(self) -> None:
        """Start the fog node and all its services."""
        if self._running:
            logger.warning("Fog node is already running")
            return
        
        try:
            self._running = True
            self._startup_time = datetime.now()
            
            logger.info(f"Starting fog node {self.node_id}...")
            
            # Start core components
            await self.edge_coordinator.start()
            await self.model_cache.start()
            
            # Start communication interfaces
            await self.edge_interface.start()
            await self.cloud_interface.start()
            
            # Setup event handlers
            self._setup_event_handlers()
            
            # Start monitoring tasks
            self._tasks.append(asyncio.create_task(self._monitoring_loop()))
            self._tasks.append(asyncio.create_task(self._stats_update_loop()))
            
            logger.info(f"Fog node {self.node_id} started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start fog node: {e}")
            await self.stop()
            raise
    
    async def stop(self) -> None:
        """Stop the fog node and cleanup resources."""
        if not self._running:
            return
        
        logger.info(f"Stopping fog node {self.node_id}...")
        self._running = False
        
        # Cancel all tasks
        for task in self._tasks:
            task.cancel()
        
        # Wait for tasks to complete
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        
        # Stop components
        try:
            await self.cloud_interface.stop()
            await self.edge_interface.stop()
            await self.model_cache.stop()
            await self.edge_coordinator.stop()
            await self.regional_aggregator.cleanup()
        except Exception as e:
            logger.error(f"Error during shutdown: {e}")
        
        logger.info(f"Fog node {self.node_id} stopped")
    
    def _setup_event_handlers(self) -> None:
        """Setup event handlers for component communication."""
        
        # Edge coordinator events
        self.edge_coordinator.add_event_callback(
            "device_connected", 
            self._on_device_connected
        )
        self.edge_coordinator.add_event_callback(
            "device_disconnected", 
            self._on_device_disconnected
        )
        self.edge_coordinator.add_event_callback(
            "workload_completed", 
            self._on_workload_completed
        )
        
        # Aggregation events would be added here
        # Cloud sync events would be added here
    
    async def _on_device_connected(self, device_info) -> None:
        """Handle device connection event."""
        logger.info(f"Device connected: {device_info.device_id}")
        self.stats["devices_served"] += 1
        
        # Potentially send cached models to new device
        await self._send_cached_models_to_device(device_info.device_id)
    
    async def _on_device_disconnected(self, device_info) -> None:
        """Handle device disconnection event."""
        logger.info(f"Device disconnected: {device_info.device_id}")
    
    async def _on_workload_completed(self, event_data) -> None:
        """Handle workload completion event."""
        assignment = event_data["assignment"]
        result = event_data["result"]
        
        logger.info(f"Workload completed: {assignment.workload_id}")
        
        # If it's a training workload, process the update
        if assignment.workload_type == "training" and "model_update" in result:
            await self._process_training_update(assignment.device_id, result["model_update"])
    
    async def _send_cached_models_to_device(self, device_id: str) -> None:
        """Send relevant cached models to a newly connected device."""
        try:
            # Get latest cached model
            latest_model = await self.model_cache.get_latest_model()
            if latest_model:
                await self.edge_interface.send_model_to_device(device_id, latest_model)
        except Exception as e:
            logger.error(f"Failed to send cached model to {device_id}: {e}")
    
    async def _process_training_update(self, device_id: str, model_update: Dict[str, Any]) -> None:
        """Process a training update from an edge device."""
        try:
            # Convert to EdgeUpdate format
            edge_update = EdgeUpdate(
                client_id=device_id,
                model_weights=model_update["weights"],
                sample_count=model_update["sample_count"],
                training_loss=model_update["loss"],
                timestamp=datetime.now()
            )
            
            # Add to regional aggregator
            await self.regional_aggregator.add_edge_update(edge_update)
            
            logger.debug(f"Processed training update from {device_id}")
            
        except Exception as e:
            logger.error(f"Failed to process training update from {device_id}: {e}")
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring and coordination loop."""
        while self._running:
            try:
                # Check system health
                await self._check_system_health()
                
                # Trigger aggregation if needed
                await self._check_aggregation_triggers()
                
                # Sync with cloud if needed
                await self._check_cloud_sync()
                
                # Cleanup old data
                await self._cleanup_old_data()
                
                await asyncio.sleep(30)  # Check every 30 seconds
                
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(30)
    
    async def _stats_update_loop(self) -> None:
        """Update statistics periodically."""
        while self._running:
            try:
                if self._startup_time:
                    self.stats["uptime_seconds"] = (
                        datetime.now() - self._startup_time
                    ).total_seconds()
                
                # Update component stats
                coordinator_stats = self.edge_coordinator.get_coordinator_stats()
                aggregator_stats = self.regional_aggregator.get_aggregation_stats()
                cache_stats = await self.model_cache.get_cache_stats()
                
                self.stats.update({
                    "connected_devices": coordinator_stats["total_devices"],
                    "active_workloads": coordinator_stats["active_workloads"],
                    "aggregation_rounds": aggregator_stats["rounds_completed"],
                    "cache_hit_rate": cache_stats.get("hit_rate", 0.0)
                })
                
                await asyncio.sleep(60)  # Update every minute
                
            except Exception as e:
                logger.error(f"Error updating stats: {e}")
                await asyncio.sleep(60)
    
    async def _check_system_health(self) -> None:
        """Check overall system health."""
        # Implement health checks for all components
        pass
    
    async def _check_aggregation_triggers(self) -> None:
        """Check if aggregation should be triggered."""
        # Check if we have enough updates for aggregation
        if len(self.regional_aggregator.pending_updates) >= self.regional_aggregator.min_clients:
            if not self.regional_aggregator.aggregation_task or self.regional_aggregator.aggregation_task.done():
                await self.regional_aggregator.start_aggregation_round()
    
    async def _check_cloud_sync(self) -> None:
        """Check if cloud synchronization is needed."""
        # Implement cloud sync logic
        pass
    
    async def _cleanup_old_data(self) -> None:
        """Cleanup old data and expired cache entries."""
        await self.model_cache.cleanup_expired()
    
    # API methods for external interaction
    
    async def register_edge_device(
        self,
        device_id: str,
        device_type: str,
        capabilities: Dict[str, Any]
    ) -> bool:
        """Register a new edge device."""
        return await self.edge_coordinator.register_device(
            device_id, device_type, capabilities
        )
    
    async def submit_training_update(
        self,
        device_id: str,
        model_update: Dict[str, Any]
    ) -> bool:
        """Submit a training update from an edge device."""
        await self._process_training_update(device_id, model_update)
        return True
    
    async def request_model(self, device_id: str, model_version: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Request a model for an edge device."""
        if model_version:
            return await self.model_cache.get_model(model_version)
        else:
            return await self.model_cache.get_latest_model()
    
    async def assign_task(
        self,
        task_type: str,
        parameters: Dict[str, Any],
        device_filter: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """Assign a task to an edge device."""
        filter_func = None
        if device_filter:
            # Convert device_filter dict to a callable filter function
            # This is a simplified implementation
            filter_func = lambda device: all(
                device.capabilities.get(k) == v for k, v in device_filter.items()
            )
        
        return await self.edge_coordinator.assign_workload(
            task_type, parameters, filter_func
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get current fog node status."""
        return {
            "node_id": self.node_id,
            "region": self.region,
            "running": self._running,
            "startup_time": self._startup_time.isoformat() if self._startup_time else None,
            "stats": self.stats.copy()
        }


async def create_fog_node_from_config(config_path: str) -> FogNode:
    """Create a fog node from configuration file."""
    config_file = Path(config_path)
    
    if not config_file.exists():
        raise FileNotFoundError(f"Configuration file not found: {config_path}")
    
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    
    return FogNode(config)


async def main():
    """Main entry point for fog node."""
    import argparse
    
    parser = argparse.ArgumentParser(description="FL Fog Node")
    parser.add_argument("--config", default="config/fog_config.yaml", help="Configuration file")
    parser.add_argument("--log-level", default="INFO", help="Logging level")
    args = parser.parse_args()
    
    # Setup logging
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Create and start fog node
    try:
        fog_node = await create_fog_node_from_config(args.config)
        
        # Setup signal handlers for graceful shutdown
        def signal_handler():
            logger.info("Received shutdown signal")
            asyncio.create_task(fog_node.stop())
        
        for sig in [signal.SIGTERM, signal.SIGINT]:
            signal.signal(sig, lambda s, f: signal_handler())
        
        # Start fog node
        await fog_node.start()
        
        # Keep running until stopped
        while fog_node._running:
            await asyncio.sleep(1)
            
    except Exception as e:
        logger.error(f"Failed to run fog node: {e}")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
