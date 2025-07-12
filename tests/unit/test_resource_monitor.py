"""
Unit tests for ResourceMonitor class.
"""

import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime, timedelta

from fog_node.resource_monitor import ResourceMonitor, ResourceMetrics, DeviceMetrics


class TestResourceMonitor:
    """Test suite for ResourceMonitor."""
    
    @pytest.fixture
    def resource_config(self):
        """Configuration for resource monitor."""
        return {
            "max_cpu_usage": 0.8,
            "max_memory_usage": 0.75,
            "max_storage_gb": 100
        }
    
    @pytest.fixture
    def resource_monitor(self, resource_config):
        """Create ResourceMonitor instance."""
        return ResourceMonitor(resource_config)
    
    def test_init(self, resource_monitor, resource_config):
        """Test ResourceMonitor initialization."""
        assert resource_monitor.max_cpu_usage == resource_config["max_cpu_usage"]
        assert resource_monitor.max_memory_usage == resource_config["max_memory_usage"]
        assert resource_monitor.max_storage_gb == resource_config["max_storage_gb"]
        assert not resource_monitor.is_monitoring
        assert len(resource_monitor.metrics_history) == 0
        assert len(resource_monitor.device_metrics) == 0
    
    @pytest.mark.asyncio
    async def test_start_stop(self, resource_monitor):
        """Test starting and stopping resource monitoring."""
        assert not resource_monitor.is_monitoring
        
        await resource_monitor.start()
        assert resource_monitor.is_monitoring
        
        await resource_monitor.stop()
        assert not resource_monitor.is_monitoring
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_count')
    @patch('psutil.cpu_freq')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_get_capabilities(self, mock_disk, mock_memory, mock_cpu_freq, mock_cpu_count, resource_monitor):
        """Test getting node capabilities."""
        # Mock system information
        mock_cpu_count.return_value = 8
        mock_cpu_freq.return_value = Mock(current=2400.0)
        mock_memory.return_value = Mock(total=16 * 1024**3)  # 16GB
        mock_disk.return_value = Mock(total=500 * 1024**3, free=200 * 1024**3)  # 500GB total, 200GB free
        
        capabilities = await resource_monitor.get_capabilities()
        
        assert capabilities["compute"]["cpu_cores"] == 8
        assert capabilities["compute"]["cpu_frequency_mhz"] == 2400.0
        assert capabilities["compute"]["memory_gb"] == 16.0
        assert capabilities["storage"]["total_gb"] == 500.0
        assert capabilities["storage"]["available_gb"] == 200.0
    
    @pytest.mark.asyncio
    @patch('psutil.cpu_percent')
    @patch('psutil.virtual_memory')
    @patch('psutil.disk_usage')
    async def test_get_current_usage(self, mock_disk, mock_memory, mock_cpu, resource_monitor):
        """Test getting current resource usage."""
        # Mock system usage
        mock_cpu.return_value = 50.0
        mock_memory.return_value = Mock(percent=60.0)
        mock_disk.return_value = Mock(percent=70.0)
        
        usage = await resource_monitor.get_current_usage()
        
        assert usage["cpu"] == 50.0
        assert usage["memory"] == 60.0
        assert usage["disk"] == 70.0
    
    @pytest.mark.asyncio
    async def test_log_device_metrics(self, resource_monitor):
        """Test logging device metrics."""
        device_id = "test_device_001"
        metrics = {
            "training_time": 120.5,
            "accuracy": 0.85,
            "data_samples": 1000,
            "cpu_usage": 75.0,
            "memory_usage": 60.0,
            "battery_level": 85.0
        }
        
        await resource_monitor.log_device_metrics(device_id, metrics)
        
        assert device_id in resource_monitor.device_metrics
        device_metrics_list = resource_monitor.device_metrics[device_id]
        assert len(device_metrics_list) == 1
        
        device_metric = device_metrics_list[0]
        assert device_metric.device_id == device_id
        assert device_metric.training_time == 120.5
        assert device_metric.model_accuracy == 0.85
        assert device_metric.data_samples == 1000
        assert device_metric.cpu_usage == 75.0
        assert device_metric.memory_usage == 60.0
        assert device_metric.battery_level == 85.0
    
    @pytest.mark.asyncio
    async def test_can_handle_task(self, resource_monitor):
        """Test task handling capability check."""
        with patch.object(resource_monitor, 'get_available_resources') as mock_available:
            mock_available.return_value = {
                "cpu_available": 40.0,  # 40% CPU available
                "memory_available": 50.0,  # 50% memory available  
                "disk_available": 100.0  # 100GB disk available
            }
            
            # Task that fits within available resources
            task_small = {
                "cpu": 30.0,
                "memory_gb": 4.0,
                "disk_gb": 10.0
            }
            assert await resource_monitor.can_handle_task(task_small)
            
            # Task that exceeds available resources
            task_large = {
                "cpu": 50.0,  # Exceeds available CPU
                "memory_gb": 4.0,
                "disk_gb": 10.0
            }
            assert not await resource_monitor.can_handle_task(task_large)
    
    @pytest.mark.asyncio
    async def test_get_device_performance_summary(self, resource_monitor):
        """Test getting device performance summary."""
        device_id = "test_device_001"
        
        # Add some test metrics
        for i in range(3):
            metrics = {
                "training_time": 100.0 + i * 10,
                "accuracy": 0.8 + i * 0.05,
                "data_samples": 1000,
                "cpu_usage": 70.0 + i * 5,
                "memory_usage": 60.0 + i * 5
            }
            await resource_monitor.log_device_metrics(device_id, metrics)
        
        summary = await resource_monitor.get_device_performance_summary(device_id)
        
        assert summary is not None
        assert summary["device_id"] == device_id
        assert summary["metrics_count"] == 3
        assert summary["avg_training_time"] == 110.0  # (100 + 110 + 120) / 3
        assert summary["avg_accuracy"] == 0.85  # (0.8 + 0.85 + 0.9) / 3
        assert summary["total_samples"] == 3000  # 1000 * 3
    
    @pytest.mark.asyncio
    async def test_get_optimization_suggestions(self, resource_monitor):
        """Test getting optimization suggestions."""
        # Add metrics indicating high CPU usage
        for _ in range(5):
            metric = ResourceMetrics(
                timestamp=datetime.now(),
                cpu_percent=90.0,  # High CPU usage
                memory_percent=50.0,
                memory_available_gb=8.0,
                disk_usage_percent=60.0,
                disk_free_gb=100.0,
                network_bytes_sent=1000,
                network_bytes_recv=1000,
                active_connections=10,
                load_average=[2.0, 1.5, 1.0]
            )
            resource_monitor.metrics_history.append(metric)
        
        suggestions = await resource_monitor.get_optimization_suggestions()
        
        # Should suggest CPU optimization
        cpu_suggestions = [s for s in suggestions if s["type"] == "cpu_optimization"]
        assert len(cpu_suggestions) > 0
        assert cpu_suggestions[0]["priority"] == "high"
    
    def test_resource_metrics_creation(self):
        """Test ResourceMetrics dataclass creation."""
        timestamp = datetime.now()
        metrics = ResourceMetrics(
            timestamp=timestamp,
            cpu_percent=75.0,
            memory_percent=60.0,
            memory_available_gb=8.0,
            disk_usage_percent=50.0,
            disk_free_gb=200.0,
            network_bytes_sent=1000000,
            network_bytes_recv=2000000,
            active_connections=25,
            load_average=[1.5, 1.2, 1.0]
        )
        
        assert metrics.timestamp == timestamp
        assert metrics.cpu_percent == 75.0
        assert metrics.memory_percent == 60.0
        assert metrics.active_connections == 25
    
    def test_device_metrics_creation(self):
        """Test DeviceMetrics dataclass creation."""
        timestamp = datetime.now()
        device_metrics = DeviceMetrics(
            device_id="test_device",
            timestamp=timestamp,
            training_time=120.5,
            model_accuracy=0.92,
            data_samples=1500,
            cpu_usage=80.0,
            memory_usage=65.0,
            battery_level=75.0
        )
        
        assert device_metrics.device_id == "test_device"
        assert device_metrics.timestamp == timestamp
        assert device_metrics.training_time == 120.5
        assert device_metrics.model_accuracy == 0.92
        assert device_metrics.battery_level == 75.0
    
    @pytest.mark.asyncio
    async def test_metrics_cleanup(self, resource_monitor):
        """Test that old metrics are cleaned up properly."""
        # Add old metrics
        old_time = datetime.now() - timedelta(hours=25)  # Older than 24 hours
        recent_time = datetime.now() - timedelta(hours=1)  # Recent
        
        old_metric = ResourceMetrics(
            timestamp=old_time,
            cpu_percent=50.0,
            memory_percent=50.0,
            memory_available_gb=8.0,
            disk_usage_percent=50.0,
            disk_free_gb=100.0,
            network_bytes_sent=1000,
            network_bytes_recv=1000,
            active_connections=10,
            load_average=[1.0, 1.0, 1.0]
        )
        
        recent_metric = ResourceMetrics(
            timestamp=recent_time,
            cpu_percent=60.0,
            memory_percent=60.0,
            memory_available_gb=8.0,
            disk_usage_percent=60.0,
            disk_free_gb=100.0,
            network_bytes_sent=2000,
            network_bytes_recv=2000,
            active_connections=15,
            load_average=[1.5, 1.5, 1.5]
        )
        
        resource_monitor.metrics_history = [old_metric, recent_metric]
        
        # Update metrics (which should trigger cleanup)
        await resource_monitor.update_metrics()
        
        # Old metric should be cleaned up, recent one should remain
        # Plus the new one from update_metrics
        assert len(resource_monitor.metrics_history) >= 1
        assert all(m.timestamp > old_time for m in resource_monitor.metrics_history)
