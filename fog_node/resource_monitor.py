"""
Resource Monitor for Fog Node
============================

Monitors and manages computational resources, memory usage,
and performance metrics for the fog node.
"""

import asyncio
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import psutil


@dataclass
class ResourceMetrics:
    """Resource usage metrics."""

    timestamp: datetime
    cpu_percent: float
    memory_percent: float
    memory_available_gb: float
    disk_usage_percent: float
    disk_free_gb: float
    network_bytes_sent: int
    network_bytes_recv: int
    active_connections: int
    load_average: List[float]


@dataclass
class DeviceMetrics:
    """Metrics from edge devices."""

    device_id: str
    timestamp: datetime
    training_time: float
    model_accuracy: float
    data_samples: int
    cpu_usage: float
    memory_usage: float
    battery_level: Optional[float] = None


class ResourceMonitor:
    """
    Monitor and manage fog node resources.

    Tracks:
    - System resource usage (CPU, memory, disk, network)
    - Performance metrics
    - Edge device metrics
    - Resource allocation and optimization
    """

    def __init__(self, config: Dict[str, Any]):
        """Initialize resource monitor."""
        self.config = config
        self.logger = logging.getLogger(__name__)

        # Resource limits from config
        self.max_cpu_usage = config.get("max_cpu_usage", 0.8)
        self.max_memory_usage = config.get("max_memory_usage", 0.75)
        self.max_storage_gb = config.get("max_storage_gb", 100)

        # Monitoring state
        self.is_monitoring = False
        self.metrics_history: List[ResourceMetrics] = []
        self.device_metrics: Dict[str, List[DeviceMetrics]] = {}

        # Resource alerts
        self.alert_thresholds = {
            "cpu_high": 0.9,
            "memory_high": 0.85,
            "disk_high": 0.9,
            "temperature_high": 85.0,  # Celsius
        }

        # Performance tracking
        self.performance_baselines = {}
        self.optimization_suggestions = []

        self.logger.info("Resource monitor initialized")

    async def start(self):
        """Start resource monitoring."""
        if self.is_monitoring:
            return

        self.is_monitoring = True
        self.logger.info("Starting resource monitoring")

        # Start monitoring tasks
        asyncio.create_task(self._monitor_resources())
        asyncio.create_task(self._analyze_performance())
        asyncio.create_task(self._cleanup_old_metrics())

    async def stop(self):
        """Stop resource monitoring."""
        self.is_monitoring = False
        self.logger.info("Resource monitoring stopped")

    async def get_capabilities(self) -> Dict[str, Any]:
        """Get fog node capabilities."""
        # CPU information
        cpu_count = psutil.cpu_count()
        cpu_freq = psutil.cpu_freq()

        # Memory information
        memory = psutil.virtual_memory()

        # Disk information
        disk = psutil.disk_usage("/")

        capabilities = {
            "compute": {
                "cpu_cores": cpu_count,
                "cpu_frequency_mhz": cpu_freq.current if cpu_freq else None,
                "memory_gb": round(memory.total / (1024**3), 2),
                "architecture": psutil.cpu_count(logical=False),
            },
            "storage": {
                "total_gb": round(disk.total / (1024**3), 2),
                "available_gb": round(disk.free / (1024**3), 2),
            },
            "network": {
                "interfaces": list(psutil.net_if_addrs().keys()),
                "bandwidth_estimate": await self._estimate_bandwidth(),
            },
            "limits": {
                "max_cpu_usage": self.max_cpu_usage,
                "max_memory_usage": self.max_memory_usage,
                "max_storage_gb": self.max_storage_gb,
            },
        }

        return capabilities

    async def update_metrics(self):
        """Update current resource metrics."""
        try:
            metrics = await self._collect_metrics()
            self.metrics_history.append(metrics)

            # Keep only recent metrics (last 24 hours)
            cutoff_time = datetime.now() - timedelta(hours=24)
            self.metrics_history = [
                m for m in self.metrics_history if m.timestamp > cutoff_time
            ]

            # Check for alerts
            await self._check_resource_alerts(metrics)

        except Exception as e:
            self.logger.error(f"Error updating metrics: {e}")

    async def log_device_metrics(self, device_id: str, metrics: Dict[str, Any]):
        """Log metrics from edge device."""
        device_metric = DeviceMetrics(
            device_id=device_id,
            timestamp=datetime.now(),
            training_time=metrics.get("training_time", 0.0),
            model_accuracy=metrics.get("accuracy", 0.0),
            data_samples=metrics.get("data_samples", 0),
            cpu_usage=metrics.get("cpu_usage", 0.0),
            memory_usage=metrics.get("memory_usage", 0.0),
            battery_level=metrics.get("battery_level"),
        )

        if device_id not in self.device_metrics:
            self.device_metrics[device_id] = []

        self.device_metrics[device_id].append(device_metric)

        # Keep only recent metrics per device
        cutoff_time = datetime.now() - timedelta(hours=12)
        self.device_metrics[device_id] = [
            m for m in self.device_metrics[device_id] if m.timestamp > cutoff_time
        ]

    async def get_current_usage(self) -> Dict[str, float]:
        """Get current resource usage percentages."""
        return {
            "cpu": psutil.cpu_percent(interval=1),
            "memory": psutil.virtual_memory().percent,
            "disk": psutil.disk_usage("/").percent,
        }

    async def get_available_resources(self) -> Dict[str, float]:
        """Get available resources for new tasks."""
        current_usage = await self.get_current_usage()

        return {
            "cpu_available": max(0, self.max_cpu_usage * 100 - current_usage["cpu"]),
            "memory_available": max(
                0, self.max_memory_usage * 100 - current_usage["memory"]
            ),
            "disk_available": psutil.disk_usage("/").free / (1024**3),  # GB
        }

    async def can_handle_task(self, task_requirements: Dict[str, float]) -> bool:
        """Check if fog node can handle a new task."""
        available = await self.get_available_resources()

        cpu_ok = task_requirements.get("cpu", 0) <= available["cpu_available"]
        memory_ok = task_requirements.get("memory_gb", 0) <= (
            available["memory_available"]
            / 100
            * psutil.virtual_memory().total
            / (1024**3)
        )
        disk_ok = task_requirements.get("disk_gb", 0) <= available["disk_available"]

        return cpu_ok and memory_ok and disk_ok

    async def get_device_performance_summary(
        self, device_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get performance summary for a specific device."""
        if device_id not in self.device_metrics:
            return None

        metrics = self.device_metrics[device_id]
        if not metrics:
            return None

        # Calculate averages and trends
        recent_metrics = [
            m for m in metrics if m.timestamp > datetime.now() - timedelta(hours=2)
        ]

        if not recent_metrics:
            return None

        avg_training_time = sum(m.training_time for m in recent_metrics) / len(
            recent_metrics
        )
        avg_accuracy = sum(m.model_accuracy for m in recent_metrics) / len(
            recent_metrics
        )
        total_samples = sum(m.data_samples for m in recent_metrics)
        avg_cpu = sum(m.cpu_usage for m in recent_metrics) / len(recent_metrics)
        avg_memory = sum(m.memory_usage for m in recent_metrics) / len(recent_metrics)

        return {
            "device_id": device_id,
            "metrics_count": len(recent_metrics),
            "avg_training_time": avg_training_time,
            "avg_accuracy": avg_accuracy,
            "total_samples": total_samples,
            "avg_cpu_usage": avg_cpu,
            "avg_memory_usage": avg_memory,
            "last_update": recent_metrics[-1].timestamp.isoformat(),
        }

    async def get_optimization_suggestions(self) -> List[Dict[str, Any]]:
        """Get optimization suggestions based on current metrics."""
        suggestions = []

        if not self.metrics_history:
            return suggestions

        recent_metrics = self.metrics_history[-10:]  # Last 10 measurements

        # High CPU usage suggestion
        avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(recent_metrics)
        if avg_cpu > 70:
            suggestions.append(
                {
                    "type": "cpu_optimization",
                    "priority": "high" if avg_cpu > 85 else "medium",
                    "message": (
                        f"High CPU usage detected ({avg_cpu:.1f}%). "
                        "Consider load balancing."
                    ),
                    "actions": ["redistribute_tasks", "scale_horizontally"],
                }
            )

        # High memory usage suggestion
        avg_memory = sum(m.memory_percent for m in recent_metrics) / len(recent_metrics)
        if avg_memory > 75:
            suggestions.append(
                {
                    "type": "memory_optimization",
                    "priority": "high" if avg_memory > 90 else "medium",
                    "message": (
                        f"High memory usage detected ({avg_memory:.1f}%). "
                        "Consider cache cleanup."
                    ),
                    "actions": ["cleanup_cache", "optimize_model_storage"],
                }
            )

        # Device performance suggestions
        for device_id, device_metrics in self.device_metrics.items():
            if device_metrics:
                recent_device_metrics = [
                    m
                    for m in device_metrics
                    if m.timestamp > datetime.now() - timedelta(hours=1)
                ]

                if recent_device_metrics:
                    avg_training_time = sum(
                        m.training_time for m in recent_device_metrics
                    ) / len(recent_device_metrics)

                    if avg_training_time > 300:  # 5 minutes
                        suggestions.append(
                            {
                                "type": "device_optimization",
                                "priority": "medium",
                                "message": (
                                    f"Device {device_id} has slow training "
                                    f"({avg_training_time:.1f}s)"
                                ),
                                "actions": [
                                    "reduce_model_complexity",
                                    "adjust_batch_size",
                                ],
                            }
                        )

        return suggestions

    async def _collect_metrics(self) -> ResourceMetrics:
        """Collect current system metrics."""
        # CPU metrics
        cpu_percent = psutil.cpu_percent(interval=1)

        # Memory metrics
        memory = psutil.virtual_memory()

        # Disk metrics
        disk = psutil.disk_usage("/")

        # Network metrics
        network = psutil.net_io_counters()

        # Load average (Linux/Mac only)
        try:
            load_avg = list(psutil.getloadavg())
        except AttributeError:
            load_avg = [0.0, 0.0, 0.0]  # Windows doesn't have load average

        # Active connections
        connections = len(psutil.net_connections())

        return ResourceMetrics(
            timestamp=datetime.now(),
            cpu_percent=cpu_percent,
            memory_percent=memory.percent,
            memory_available_gb=memory.available / (1024**3),
            disk_usage_percent=disk.percent,
            disk_free_gb=disk.free / (1024**3),
            network_bytes_sent=network.bytes_sent,
            network_bytes_recv=network.bytes_recv,
            active_connections=connections,
            load_average=load_avg,
        )

    async def _check_resource_alerts(self, metrics: ResourceMetrics):
        """Check for resource usage alerts."""
        alerts = []

        if metrics.cpu_percent > self.alert_thresholds["cpu_high"] * 100:
            alerts.append(f"High CPU usage: {metrics.cpu_percent:.1f}%")

        if metrics.memory_percent > self.alert_thresholds["memory_high"] * 100:
            alerts.append(f"High memory usage: {metrics.memory_percent:.1f}%")

        if metrics.disk_usage_percent > self.alert_thresholds["disk_high"] * 100:
            alerts.append(f"High disk usage: {metrics.disk_usage_percent:.1f}%")

        for alert in alerts:
            self.logger.warning(f"Resource alert: {alert}")

    async def _estimate_bandwidth(self) -> Optional[float]:
        """Estimate network bandwidth (simplified)."""
        try:
            # This is a simplified bandwidth estimation
            # In production, you might want to use iperf or similar tools
            network_before = psutil.net_io_counters()
            await asyncio.sleep(1)
            network_after = psutil.net_io_counters()

            bytes_sent = network_after.bytes_sent - network_before.bytes_sent
            bytes_recv = network_after.bytes_recv - network_before.bytes_recv

            # Estimate in Mbps
            total_bytes = bytes_sent + bytes_recv
            bandwidth_mbps = (total_bytes * 8) / (1024 * 1024)  # Convert to Mbps

            return bandwidth_mbps
        except Exception:
            return None

    async def _monitor_resources(self):
        """Continuous resource monitoring loop."""
        while self.is_monitoring:
            try:
                await self.update_metrics()
                await asyncio.sleep(10)  # Update every 10 seconds
            except Exception as e:
                self.logger.error(f"Error in resource monitoring: {e}")
                await asyncio.sleep(5)

    async def _analyze_performance(self):
        """Analyze performance trends and generate insights."""
        while self.is_monitoring:
            try:
                # Generate optimization suggestions
                self.optimization_suggestions = (
                    await self.get_optimization_suggestions()
                )

                # Log performance summary every 5 minutes
                if len(self.metrics_history) > 0:
                    recent_metrics = self.metrics_history[-30:]  # Last 5 minutes
                    avg_cpu = sum(m.cpu_percent for m in recent_metrics) / len(
                        recent_metrics
                    )
                    avg_memory = sum(m.memory_percent for m in recent_metrics) / len(
                        recent_metrics
                    )

                    self.logger.info(
                        f"Performance summary - CPU: {avg_cpu:.1f}%, "
                        f"Memory: {avg_memory:.1f}%, "
                        f"Devices: {len(self.device_metrics)}"
                    )

                await asyncio.sleep(300)  # Analyze every 5 minutes
            except Exception as e:
                self.logger.error(f"Error in performance analysis: {e}")
                await asyncio.sleep(60)

    async def _cleanup_old_metrics(self):
        """Clean up old metrics to prevent memory bloat."""
        while self.is_monitoring:
            try:
                # Clean up old system metrics (keep last 24 hours)
                cutoff_time = datetime.now() - timedelta(hours=24)
                self.metrics_history = [
                    m for m in self.metrics_history if m.timestamp > cutoff_time
                ]

                # Clean up old device metrics (keep last 12 hours)
                device_cutoff = datetime.now() - timedelta(hours=12)
                for device_id in self.device_metrics:
                    self.device_metrics[device_id] = [
                        m
                        for m in self.device_metrics[device_id]
                        if m.timestamp > device_cutoff
                    ]

                await asyncio.sleep(3600)  # Cleanup every hour
            except Exception as e:
                self.logger.error(f"Error in metrics cleanup: {e}")
                await asyncio.sleep(600)

    def export_metrics(self, format: str = "json") -> str:
        """Export metrics in specified format."""
        data = {
            "system_metrics": [asdict(m) for m in self.metrics_history],
            "device_metrics": {
                device_id: [asdict(m) for m in metrics]
                for device_id, metrics in self.device_metrics.items()
            },
            "optimization_suggestions": self.optimization_suggestions,
            "export_timestamp": datetime.now().isoformat(),
        }

        if format.lower() == "json":
            return json.dumps(data, indent=2, default=str)
        else:
            raise ValueError(f"Unsupported export format: {format}")
