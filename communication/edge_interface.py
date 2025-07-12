"""
Edge Interface for Fog Computing Layer.

Handles communication with edge devices using MQTT and other
lightweight protocols optimized for edge environments.
"""

import asyncio
import json
import logging
from typing import Dict, Any, Optional, Callable
from datetime import datetime
import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class EdgeInterface:
    """
    Communication interface between fog node and edge devices.
    
    Features:
    - MQTT-based messaging
    - Device registration and discovery
    - Model distribution
    - Update collection
    - Health monitoring
    """
    
    def __init__(self, mqtt_broker: str, fog_node: Any):
        self.mqtt_broker = mqtt_broker
        self.fog_node = fog_node
        
        # MQTT client
        self.mqtt_client: Optional[mqtt.Client] = None
        self.connected = False
        
        # Message handlers
        self.message_handlers: Dict[str, Callable] = {
            "device/register": self._handle_device_registration,
            "device/heartbeat": self._handle_device_heartbeat,
            "training/update": self._handle_training_update,
            "model/request": self._handle_model_request,
            "task/result": self._handle_task_result
        }
        
        # Topics
        self.base_topic = f"fog/{fog_node.node_id}"
        
        logger.info(f"Edge interface initialized for broker {mqtt_broker}")
    
    async def start(self) -> None:
        """Start the edge interface."""
        try:
            # Setup MQTT client
            self.mqtt_client = mqtt.Client(client_id=f"fog_node_{self.fog_node.node_id}")
            self.mqtt_client.on_connect = self._on_mqtt_connect
            self.mqtt_client.on_disconnect = self._on_mqtt_disconnect
            self.mqtt_client.on_message = self._on_mqtt_message
            
            # Parse broker address
            if ":" in self.mqtt_broker:
                host, port = self.mqtt_broker.split(":")
                port = int(port)
            else:
                host, port = self.mqtt_broker, 1883
            
            # Connect to broker
            self.mqtt_client.connect(host, port, 60)
            self.mqtt_client.loop_start()
            
            # Wait for connection
            for _ in range(10):  # Wait up to 10 seconds
                if self.connected:
                    break
                await asyncio.sleep(1)
            
            if not self.connected:
                raise Exception("Failed to connect to MQTT broker")
            
            logger.info("Edge interface started")
            
        except Exception as e:
            logger.error(f"Failed to start edge interface: {e}")
            raise
    
    async def stop(self) -> None:
        """Stop the edge interface."""
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        self.connected = False
        logger.info("Edge interface stopped")
    
    def _on_mqtt_connect(self, client, userdata, flags, rc):
        """Handle MQTT connection."""
        if rc == 0:
            self.connected = True
            logger.info("Connected to MQTT broker")
            
            # Subscribe to relevant topics
            topics = [
                f"{self.base_topic}/device/+/register",
                f"{self.base_topic}/device/+/heartbeat",
                f"{self.base_topic}/training/+/update",
                f"{self.base_topic}/model/+/request",
                f"{self.base_topic}/task/+/result"
            ]
            
            for topic in topics:
                client.subscribe(topic)
                logger.debug(f"Subscribed to {topic}")
        else:
            logger.error(f"Failed to connect to MQTT broker: {rc}")
    
    def _on_mqtt_disconnect(self, client, userdata, rc):
        """Handle MQTT disconnection."""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker: {rc}")
    
    def _on_mqtt_message(self, client, userdata, msg):
        """Handle incoming MQTT message."""
        try:
            topic_parts = msg.topic.split('/')
            
            # Extract message type and device ID
            if len(topic_parts) >= 4:
                message_type = f"{topic_parts[-2]}/{topic_parts[-1]}"
                device_id = topic_parts[-2] if len(topic_parts) > 4 else "unknown"
                
                # Decode message payload
                payload = json.loads(msg.payload.decode())
                
                # Handle message
                asyncio.create_task(self._handle_message(message_type, device_id, payload))
        
        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")
    
    async def _handle_message(self, message_type: str, device_id: str, payload: Dict[str, Any]):
        """Handle a decoded message."""
        handler = self.message_handlers.get(message_type)
        if handler:
            try:
                await handler(device_id, payload)
            except Exception as e:
                logger.error(f"Error handling {message_type} from {device_id}: {e}")
        else:
            logger.warning(f"No handler for message type: {message_type}")
    
    async def _handle_device_registration(self, device_id: str, payload: Dict[str, Any]):
        """Handle device registration request."""
        device_type = payload.get("device_type", "unknown")
        capabilities = payload.get("capabilities", {})
        location = payload.get("location")
        
        success = await self.fog_node.register_edge_device(device_id, device_type, capabilities)
        
        # Send registration response
        response = {
            "status": "success" if success else "failed",
            "fog_node_id": self.fog_node.node_id,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._send_to_device(device_id, "register/response", response)
    
    async def _handle_device_heartbeat(self, device_id: str, payload: Dict[str, Any]):
        """Handle device heartbeat."""
        metrics = payload.get("metrics", {})
        status = payload.get("status", "online")
        
        # Update device status in coordinator
        from ..fog_node.edge_coordinator import EdgeDeviceStatus
        device_status = EdgeDeviceStatus(status)
        
        await self.fog_node.edge_coordinator.update_device_status(
            device_id, device_status, metrics
        )
    
    async def _handle_training_update(self, device_id: str, payload: Dict[str, Any]):
        """Handle training update from edge device."""
        model_update = {
            "weights": payload.get("weights", {}),
            "sample_count": payload.get("sample_count", 0),
            "loss": payload.get("loss", 0.0),
            "metadata": payload.get("metadata", {})
        }
        
        success = await self.fog_node.submit_training_update(device_id, model_update)
        
        # Send acknowledgment
        ack = {
            "status": "received" if success else "failed",
            "timestamp": datetime.now().isoformat()
        }
        
        await self._send_to_device(device_id, "training/ack", ack)
    
    async def _handle_model_request(self, device_id: str, payload: Dict[str, Any]):
        """Handle model request from edge device."""
        model_version = payload.get("version")
        
        model_data = await self.fog_node.request_model(device_id, model_version)
        
        if model_data:
            await self._send_to_device(device_id, "model/update", model_data)
        else:
            error_response = {
                "error": "Model not available",
                "timestamp": datetime.now().isoformat()
            }
            await self._send_to_device(device_id, "model/error", error_response)
    
    async def _handle_task_result(self, device_id: str, payload: Dict[str, Any]):
        """Handle task result from edge device."""
        workload_id = payload.get("workload_id")
        result = payload.get("result", {})
        
        if workload_id:
            await self.fog_node.edge_coordinator.complete_workload(workload_id, result)
    
    async def _send_to_device(self, device_id: str, message_type: str, payload: Dict[str, Any]):
        """Send message to specific edge device."""
        if not self.connected or not self.mqtt_client:
            logger.error("MQTT client not connected")
            return
        
        topic = f"{self.base_topic}/device/{device_id}/{message_type}"
        message = json.dumps(payload)
        
        self.mqtt_client.publish(topic, message)
        logger.debug(f"Sent {message_type} to {device_id}")
    
    async def broadcast_to_devices(self, message_type: str, payload: Dict[str, Any]):
        """Broadcast message to all connected devices."""
        if not self.connected or not self.mqtt_client:
            logger.error("MQTT client not connected")
            return
        
        topic = f"{self.base_topic}/broadcast/{message_type}"
        message = json.dumps(payload)
        
        self.mqtt_client.publish(topic, message)
        logger.debug(f"Broadcasted {message_type}")
    
    async def send_model_to_device(self, device_id: str, model_data: Dict[str, Any]):
        """Send model update to specific device."""
        await self._send_to_device(device_id, "model/update", model_data)
    
    async def send_task_to_device(
        self,
        device_id: str,
        task_type: str,
        parameters: Dict[str, Any]
    ):
        """Send task assignment to device."""
        task_message = {
            "task_type": task_type,
            "parameters": parameters,
            "timestamp": datetime.now().isoformat()
        }
        
        await self._send_to_device(device_id, "task/assign", task_message)
