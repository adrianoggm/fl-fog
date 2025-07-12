"""
Test configuration and fixtures for FL-Fog tests.
"""

import asyncio
import os
import tempfile
from typing import Any, Dict

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_config() -> Dict[str, Any]:
    """Test configuration for fog node."""
    return {
        "fog_node": {
            "node_id": "test_fog_node_001",
            "region": "test_region",
            "location": {
                "latitude": 52.5200,
                "longitude": 13.4050,
                "city": "Berlin",
                "country": "Germany",
            },
        },
        "resources": {
            "max_cpu_usage": 0.8,
            "max_memory_usage": 0.75,
            "max_storage_gb": 10,
        },
        "network": {
            "edge_interface": {
                "protocol": "mqtt",
                "host": "localhost",
                "port": 1883,
                "topic_prefix": "fl/test",
                "qos": 1,
            },
            "cloud_interface": {
                "protocol": "grpc",
                "host": "localhost",
                "port": 50051,
                "tls_enabled": False,
            },
            "peer_interface": {
                "protocol": "http",
                "port": 8080,
                "discovery_enabled": False,
            },
        },
        "aggregation": {
            "strategy": "fedavg",
            "min_clients": 2,
            "max_clients": 10,
            "wait_timeout": 30,
        },
        "cache": {
            "model_cache": {
                "max_size_gb": 1,
                "ttl_hours": 1,
                "compression_enabled": False,
            }
        },
        "security": {
            "encryption": {"enabled": False},
            "authentication": {"enabled": False},
        },
        "logging": {"level": "DEBUG", "file": "test_fog_node.log"},
        "monitoring": {"prometheus": {"enabled": False}},
    }


@pytest.fixture
def temp_config_file(test_config):
    """Create a temporary configuration file."""
    import yaml

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        yaml.dump(test_config, f)
        config_file = f.name

    yield config_file

    # Cleanup
    if os.path.exists(config_file):
        os.unlink(config_file)


@pytest.fixture
def mock_edge_device():
    """Mock edge device data."""
    return {
        "device_id": "test_edge_001",
        "device_type": "raspberry_pi",
        "capabilities": {
            "cpu_cores": 4,
            "memory_gb": 4,
            "storage_gb": 32,
            "gpu_available": False,
        },
        "location": {"latitude": 52.5200, "longitude": 13.4050},
        "status": "active",
    }


@pytest.fixture
def mock_model_update():
    """Mock model update data."""
    return {
        "device_id": "test_edge_001",
        "round_id": "round_001",
        "model_data": {
            "weights": [1.0, 2.0, 3.0],  # Simplified weights
            "loss": 0.5,
            "accuracy": 0.85,
            "samples": 1000,
        },
        "timestamp": "2024-01-01T10:00:00Z",
    }


# Async test helpers
@pytest.mark.asyncio
async def async_test():
    """Marker for async tests."""
    pass
