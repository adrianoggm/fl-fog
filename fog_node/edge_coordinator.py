"""
Edge Device Coordinator for Fog Computing Layer.

Manages connections, workload distribution, and resource optimization
for edge devices connected to this fog node.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Callable, Any
from enum import Enum
import logging
from datetime import datetime, timedelta
import json

logger = logging.getLogger(__name__)


class EdgeDeviceStatus(Enum):
    """Status of edge devices."""
    ONLINE = "online"
    OFFLINE = "offline"
    BUSY = "busy"
    IDLE = "idle"
    OVERLOADED = "overloaded"
    LOW_BATTERY = "low_battery"


@dataclass
class EdgeDeviceInfo:
    """Information about an edge device."""
    device_id: str
    device_type: str  # smartphone, raspberry_pi, smartwatch, etc.
    capabilities: Dict[str, Any]
    status: EdgeDeviceStatus
    last_seen: datetime
    connected_at: datetime
    current_workload: Optional[str] = None
    performance_metrics: Dict[str, float] = field(default_factory=dict)
    location: Optional[Dict[str, float]] = None  # lat, lng if available


@dataclass
class WorkloadAssignment:
    """Workload assignment to an edge device."""
    workload_id: str
    device_id: str
    workload_type: str  # "training", "inference", "data_collection"
    parameters: Dict[str, Any]
    assigned_at: datetime
    expected_completion: datetime
    status: str = "assigned"  # assigned, running, completed, failed


class EdgeCoordinator:
    """
    Coordinates edge devices connected to the fog node.
    
    Features:
    - Device registration and health monitoring
    - Intelligent workload distribution
    - Resource-aware task assignment
    - Load balancing across devices
    - Fault tolerance and recovery
    """
    
    def __init__(
        self,
        fog_node_id: str,
        max_edge_devices: int = 50,
        health_check_interval: float = 30.0,
        device_timeout: float = 300.0
    ):
        self.fog_node_id = fog_node_id
        self.max_edge_devices = max_edge_devices
        self.health_check_interval = health_check_interval
        self.device_timeout = device_timeout
        
        # Device management
        self.connected_devices: Dict[str, EdgeDeviceInfo] = {}
        self.workload_assignments: Dict[str, WorkloadAssignment] = {}
        self.device_groups: Dict[str, Set[str]] = {}  # Group devices by type/capability
        
        # Monitoring and coordination
        self._monitoring_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Callbacks for events
        self.event_callbacks: Dict[str, List[Callable]] = {
            "device_connected": [],
            "device_disconnected": [],
            "workload_completed": [],
            "device_overloaded": []
        }
        
        logger.info(f"Edge coordinator initialized for fog node {fog_node_id}")
    
    async def start(self) -> None:
        """Start the edge coordinator."""
        if self._running:
            return
        
        self._running = True
        self._monitoring_task = asyncio.create_task(self._monitoring_loop())
        logger.info("Edge coordinator started")
    
    async def stop(self) -> None:
        """Stop the edge coordinator."""
        self._running = False
        if self._monitoring_task:
            self._monitoring_task.cancel()
            try:
                await self._monitoring_task
            except asyncio.CancelledError:
                pass
        logger.info("Edge coordinator stopped")
    
    async def register_device(
        self,
        device_id: str,
        device_type: str,
        capabilities: Dict[str, Any],
        location: Optional[Dict[str, float]] = None
    ) -> bool:
        """Register a new edge device."""
        if len(self.connected_devices) >= self.max_edge_devices:
            logger.warning(f"Maximum device limit reached, rejecting {device_id}")
            return False
        
        if device_id in self.connected_devices:
            logger.warning(f"Device {device_id} already registered")
            return False
        
        now = datetime.now()
        device_info = EdgeDeviceInfo(
            device_id=device_id,
            device_type=device_type,
            capabilities=capabilities,
            status=EdgeDeviceStatus.ONLINE,
            last_seen=now,
            connected_at=now,
            location=location
        )
        
        self.connected_devices[device_id] = device_info
        
        # Add to appropriate groups
        self._update_device_groups(device_id, device_type)
        
        logger.info(f"Registered edge device {device_id} ({device_type})")
        
        # Notify callbacks
        await self._notify_callbacks("device_connected", device_info)
        
        return True
    
    async def unregister_device(self, device_id: str) -> bool:
        """Unregister an edge device."""
        if device_id not in self.connected_devices:
            return False
        
        device_info = self.connected_devices[device_id]
        
        # Cancel any active workloads
        await self._cancel_device_workloads(device_id)
        
        # Remove from groups
        self._remove_from_device_groups(device_id)
        
        # Remove from connected devices
        del self.connected_devices[device_id]
        
        logger.info(f"Unregistered edge device {device_id}")
        
        # Notify callbacks
        await self._notify_callbacks("device_disconnected", device_info)
        
        return True
    
    async def update_device_status(
        self,
        device_id: str,
        status: EdgeDeviceStatus,
        metrics: Optional[Dict[str, float]] = None
    ) -> bool:
        """Update device status and performance metrics."""
        if device_id not in self.connected_devices:
            return False
        
        device_info = self.connected_devices[device_id]
        device_info.status = status
        device_info.last_seen = datetime.now()
        
        if metrics:
            device_info.performance_metrics.update(metrics)
        
        # Handle status-specific actions
        if status == EdgeDeviceStatus.OVERLOADED:
            await self._handle_overloaded_device(device_id)
        elif status == EdgeDeviceStatus.LOW_BATTERY:
            await self._handle_low_battery_device(device_id)
        
        return True
    
    async def assign_workload(
        self,
        workload_type: str,
        parameters: Dict[str, Any],
        device_filter: Optional[Callable[[EdgeDeviceInfo], bool]] = None,
        priority: int = 0
    ) -> Optional[str]:
        """Assign a workload to the best available edge device."""
        
        # Find suitable devices
        candidates = self._find_suitable_devices(workload_type, device_filter)
        
        if not candidates:
            logger.warning(f"No suitable devices found for workload {workload_type}")
            return None
        
        # Select best device using multi-criteria optimization
        best_device = self._select_optimal_device(candidates, workload_type, parameters)
        
        if not best_device:
            return None
        
        # Create workload assignment
        workload_id = f"workload_{int(time.time())}_{best_device}"
        assignment = WorkloadAssignment(
            workload_id=workload_id,
            device_id=best_device,
            workload_type=workload_type,
            parameters=parameters,
            assigned_at=datetime.now(),
            expected_completion=datetime.now() + timedelta(seconds=300)  # Default 5 min
        )
        
        self.workload_assignments[workload_id] = assignment
        self.connected_devices[best_device].current_workload = workload_id
        self.connected_devices[best_device].status = EdgeDeviceStatus.BUSY
        
        logger.info(f"Assigned workload {workload_id} to device {best_device}")
        return workload_id
    
    def _find_suitable_devices(
        self,
        workload_type: str,
        device_filter: Optional[Callable[[EdgeDeviceInfo], bool]] = None
    ) -> List[str]:
        """Find devices suitable for the given workload."""
        candidates = []
        
        for device_id, device_info in self.connected_devices.items():
            # Check basic availability
            if device_info.status not in [EdgeDeviceStatus.ONLINE, EdgeDeviceStatus.IDLE]:
                continue
            
            # Check if device can handle this workload type
            if not self._can_handle_workload(device_info, workload_type):
                continue
            
            # Apply custom filter if provided
            if device_filter and not device_filter(device_info):
                continue
            
            candidates.append(device_id)
        
        return candidates
    
    def _can_handle_workload(self, device_info: EdgeDeviceInfo, workload_type: str) -> bool:
        """Check if device can handle the specified workload type."""
        capabilities = device_info.capabilities
        
        # Basic capability checks based on workload type
        if workload_type == "training":
            min_memory = capabilities.get("memory_gb", 0)
            min_cpu = capabilities.get("cpu_cores", 0)
            return min_memory >= 1.0 and min_cpu >= 1
        
        elif workload_type == "inference":
            return capabilities.get("cpu_cores", 0) >= 1
        
        elif workload_type == "data_collection":
            return capabilities.get("sensors", []) != []
        
        return True  # Default: assume device can handle unknown workload types
    
    def _select_optimal_device(
        self,
        candidates: List[str],
        workload_type: str,
        parameters: Dict[str, Any]
    ) -> Optional[str]:
        """Select the optimal device from candidates using multi-criteria scoring."""
        if not candidates:
            return None
        
        best_device = None
        best_score = -1
        
        for device_id in candidates:
            device_info = self.connected_devices[device_id]
            score = self._calculate_device_score(device_info, workload_type, parameters)
            
            if score > best_score:
                best_score = score
                best_device = device_id
        
        return best_device
    
    def _calculate_device_score(
        self,
        device_info: EdgeDeviceInfo,
        workload_type: str,
        parameters: Dict[str, Any]
    ) -> float:
        """Calculate a score for device suitability."""
        score = 0.0
        capabilities = device_info.capabilities
        metrics = device_info.performance_metrics
        
        # Resource availability (0-40 points)
        cpu_score = min(capabilities.get("cpu_cores", 1) / 2.0, 1.0) * 20
        memory_score = min(capabilities.get("memory_gb", 1) / 4.0, 1.0) * 20
        score += cpu_score + memory_score
        
        # Performance history (0-30 points)
        if metrics:
            avg_cpu = metrics.get("avg_cpu_usage", 50) / 100.0
            avg_memory = metrics.get("avg_memory_usage", 50) / 100.0
            # Prefer devices with moderate resource usage (not too high, not too low)
            performance_score = (1.0 - abs(avg_cpu - 0.6) - abs(avg_memory - 0.6)) * 30
            score += max(performance_score, 0)
        
        # Battery level (0-20 points) for mobile devices
        battery_level = capabilities.get("battery_level", 100)
        if battery_level < 100:  # Mobile device
            battery_score = min(battery_level / 50.0, 1.0) * 20
            score += battery_score
        else:
            score += 20  # Fixed power devices get full points
        
        # Network quality (0-10 points)
        network_quality = capabilities.get("network_bandwidth_mbps", 10)
        network_score = min(network_quality / 50.0, 1.0) * 10
        score += network_score
        
        return score
    
    async def complete_workload(self, workload_id: str, result: Dict[str, Any]) -> bool:
        """Mark a workload as completed."""
        if workload_id not in self.workload_assignments:
            return False
        
        assignment = self.workload_assignments[workload_id]
        assignment.status = "completed"
        
        device_id = assignment.device_id
        if device_id in self.connected_devices:
            self.connected_devices[device_id].current_workload = None
            self.connected_devices[device_id].status = EdgeDeviceStatus.IDLE
        
        logger.info(f"Workload {workload_id} completed on device {device_id}")
        
        # Notify callbacks
        await self._notify_callbacks("workload_completed", {"assignment": assignment, "result": result})
        
        return True
    
    async def _monitoring_loop(self) -> None:
        """Main monitoring loop for device health and workload status."""
        while self._running:
            try:
                await self._check_device_health()
                await self._check_workload_timeouts()
                await asyncio.sleep(self.health_check_interval)
            except Exception as e:
                logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(self.health_check_interval)
    
    async def _check_device_health(self) -> None:
        """Check health of all connected devices."""
        now = datetime.now()
        disconnected_devices = []
        
        for device_id, device_info in self.connected_devices.items():
            time_since_last_seen = (now - device_info.last_seen).total_seconds()
            
            if time_since_last_seen > self.device_timeout:
                disconnected_devices.append(device_id)
                logger.warning(f"Device {device_id} timed out")
        
        # Remove timed out devices
        for device_id in disconnected_devices:
            await self.unregister_device(device_id)
    
    async def _check_workload_timeouts(self) -> None:
        """Check for timed out workloads."""
        now = datetime.now()
        timed_out_workloads = []
        
        for workload_id, assignment in self.workload_assignments.items():
            if assignment.status == "running" and now > assignment.expected_completion:
                timed_out_workloads.append(workload_id)
        
        for workload_id in timed_out_workloads:
            logger.warning(f"Workload {workload_id} timed out")
            assignment = self.workload_assignments[workload_id]
            assignment.status = "failed"
            
            # Free up the device
            device_id = assignment.device_id
            if device_id in self.connected_devices:
                self.connected_devices[device_id].current_workload = None
                self.connected_devices[device_id].status = EdgeDeviceStatus.IDLE
    
    async def _handle_overloaded_device(self, device_id: str) -> None:
        """Handle an overloaded device."""
        logger.warning(f"Device {device_id} is overloaded")
        
        # Cancel non-critical workloads if any
        await self._cancel_device_workloads(device_id, critical_only=False)
        
        # Notify callbacks
        await self._notify_callbacks("device_overloaded", self.connected_devices[device_id])
    
    async def _handle_low_battery_device(self, device_id: str) -> None:
        """Handle a device with low battery."""
        logger.warning(f"Device {device_id} has low battery")
        
        # Reduce workload or migrate to other devices
        await self._cancel_device_workloads(device_id, critical_only=True)
    
    async def _cancel_device_workloads(self, device_id: str, critical_only: bool = False) -> None:
        """Cancel workloads for a specific device."""
        cancelled_workloads = []
        
        for workload_id, assignment in self.workload_assignments.items():
            if assignment.device_id == device_id and assignment.status in ["assigned", "running"]:
                if critical_only and assignment.parameters.get("priority", 0) > 5:
                    continue  # Keep critical workloads
                
                assignment.status = "cancelled"
                cancelled_workloads.append(workload_id)
        
        if cancelled_workloads:
            logger.info(f"Cancelled {len(cancelled_workloads)} workloads for device {device_id}")
        
        # Update device status
        if device_id in self.connected_devices:
            self.connected_devices[device_id].current_workload = None
            self.connected_devices[device_id].status = EdgeDeviceStatus.IDLE
    
    def _update_device_groups(self, device_id: str, device_type: str) -> None:
        """Update device groups for efficient lookup."""
        if device_type not in self.device_groups:
            self.device_groups[device_type] = set()
        self.device_groups[device_type].add(device_id)
    
    def _remove_from_device_groups(self, device_id: str) -> None:
        """Remove device from all groups."""
        for group_devices in self.device_groups.values():
            group_devices.discard(device_id)
    
    async def _notify_callbacks(self, event_type: str, data: Any) -> None:
        """Notify registered callbacks about events."""
        for callback in self.event_callbacks.get(event_type, []):
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(data)
                else:
                    callback(data)
            except Exception as e:
                logger.error(f"Error in callback for {event_type}: {e}")
    
    def add_event_callback(self, event_type: str, callback: Callable) -> None:
        """Add a callback for specific events."""
        if event_type in self.event_callbacks:
            self.event_callbacks[event_type].append(callback)
    
    def get_coordinator_stats(self) -> Dict[str, Any]:
        """Get coordinator statistics for monitoring."""
        online_devices = sum(1 for d in self.connected_devices.values() 
                           if d.status == EdgeDeviceStatus.ONLINE)
        busy_devices = sum(1 for d in self.connected_devices.values() 
                          if d.status == EdgeDeviceStatus.BUSY)
        
        active_workloads = sum(1 for w in self.workload_assignments.values() 
                             if w.status in ["assigned", "running"])
        
        device_types = {}
        for device_info in self.connected_devices.values():
            device_type = device_info.device_type
            device_types[device_type] = device_types.get(device_type, 0) + 1
        
        return {
            "total_devices": len(self.connected_devices),
            "online_devices": online_devices,
            "busy_devices": busy_devices,
            "active_workloads": active_workloads,
            "device_types": device_types,
            "fog_node_id": self.fog_node_id
        }
