"""
Regional FL Aggregator for Fog Computing Layer.

Provides partial aggregation of federated learning updates from edge devices
before forwarding to cloud aggregation services.
"""

import asyncio
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from enum import Enum
import logging
import numpy as np
import torch
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class AggregationStrategy(Enum):
    """Available aggregation strategies for fog layer."""
    FEDAVG = "fedavg"           # Simple weighted average
    FEDPROX = "fedprox"         # FedProx with proximal term
    REGIONAL = "regional"       # Region-aware aggregation
    ADAPTIVE = "adaptive"       # Adaptive based on device characteristics


@dataclass
class EdgeUpdate:
    """Represents an update from an edge device."""
    client_id: str
    model_weights: Dict[str, torch.Tensor]
    sample_count: int
    training_loss: float
    timestamp: datetime
    device_tier: str = "edge"
    privacy_budget: float = 1.0
    compression_ratio: float = 1.0


@dataclass
class AggregationResult:
    """Result of regional aggregation."""
    aggregated_weights: Dict[str, torch.Tensor]
    participating_clients: List[str]
    total_samples: int
    average_loss: float
    aggregation_round: int
    fog_node_id: str
    created_at: datetime = field(default_factory=datetime.now)


class RegionalAggregator:
    """
    Regional FL aggregator for fog computing layer.
    
    Features:
    - Partial aggregation of edge updates
    - Multiple aggregation strategies
    - Resource-aware aggregation timing
    - Privacy-preserving computations
    """
    
    def __init__(
        self,
        fog_node_id: str,
        strategy: AggregationStrategy = AggregationStrategy.FEDAVG,
        min_clients: int = 3,
        max_wait_time: float = 120.0,
        aggregation_threshold: float = 0.7
    ):
        self.fog_node_id = fog_node_id
        self.strategy = strategy
        self.min_clients = min_clients
        self.max_wait_time = max_wait_time
        self.aggregation_threshold = aggregation_threshold
        
        # Aggregation state
        self.current_round = 0
        self.pending_updates: List[EdgeUpdate] = []
        self.aggregation_history: List[AggregationResult] = []
        
        # Timing and coordination
        self.round_start_time: Optional[datetime] = None
        self.aggregation_task: Optional[asyncio.Task] = None
        
        # Strategy-specific parameters
        self.fedprox_mu = 0.1  # Proximal term weight
        self.regional_weights = {}  # Region-specific weights
        
        logger.info(f"Regional aggregator initialized for fog node {fog_node_id}")
    
    async def start_aggregation_round(self) -> None:
        """Start a new aggregation round."""
        if self.aggregation_task and not self.aggregation_task.done():
            logger.warning("Aggregation round already in progress")
            return
        
        self.current_round += 1
        self.round_start_time = datetime.now()
        self.pending_updates.clear()
        
        logger.info(f"Started aggregation round {self.current_round}")
        
        # Start the aggregation coordination task
        self.aggregation_task = asyncio.create_task(self._coordinate_aggregation())
    
    async def _coordinate_aggregation(self) -> None:
        """Coordinate the aggregation process with timing constraints."""
        try:
            start_time = time.time()
            
            while time.time() - start_time < self.max_wait_time:
                # Check if we have enough clients
                if len(self.pending_updates) >= self.min_clients:
                    # Check if we should trigger early aggregation
                    if await self._should_trigger_aggregation():
                        break
                
                await asyncio.sleep(1.0)  # Check every second
            
            # Perform aggregation if we have any updates
            if self.pending_updates:
                result = await self._perform_aggregation()
                await self._handle_aggregation_result(result)
            else:
                logger.warning(f"No updates received for round {self.current_round}")
                
        except Exception as e:
            logger.error(f"Error in aggregation coordination: {e}")
    
    async def add_edge_update(self, update: EdgeUpdate) -> bool:
        """Add an edge device update to the current aggregation round."""
        if not self.round_start_time:
            logger.warning("No active aggregation round")
            return False
        
        # Validate update
        if not self._validate_update(update):
            logger.warning(f"Invalid update from client {update.client_id}")
            return False
        
        # Add to pending updates
        self.pending_updates.append(update)
        logger.debug(f"Added update from {update.client_id} ({len(self.pending_updates)} total)")
        
        return True
    
    def _validate_update(self, update: EdgeUpdate) -> bool:
        """Validate an incoming edge update."""
        # Check timestamp
        if self.round_start_time and update.timestamp < self.round_start_time:
            return False
        
        # Check model weights structure
        if not update.model_weights or not isinstance(update.model_weights, dict):
            return False
        
        # Check sample count
        if update.sample_count <= 0:
            return False
        
        # Check for duplicate client in this round
        client_ids = [u.client_id for u in self.pending_updates]
        if update.client_id in client_ids:
            logger.warning(f"Duplicate update from client {update.client_id}")
            return False
        
        return True
    
    async def _should_trigger_aggregation(self) -> bool:
        """Determine if aggregation should be triggered early."""
        if len(self.pending_updates) < self.min_clients:
            return False
        
        # Strategy-specific trigger conditions
        if self.strategy == AggregationStrategy.ADAPTIVE:
            return await self._adaptive_trigger_condition()
        
        # Default: trigger when we have enough clients
        return len(self.pending_updates) >= self.min_clients
    
    async def _adaptive_trigger_condition(self) -> bool:
        """Adaptive trigger condition based on client characteristics."""
        if not self.pending_updates:
            return False
        
        # Calculate diversity of updates
        total_samples = sum(u.sample_count for u in self.pending_updates)
        sample_threshold = total_samples >= 100  # Minimum sample threshold
        
        # Check loss convergence
        losses = [u.training_loss for u in self.pending_updates]
        loss_variance = np.var(losses) if len(losses) > 1 else 1.0
        convergence_threshold = loss_variance < 0.1  # Low variance indicates convergence
        
        return sample_threshold and (convergence_threshold or len(self.pending_updates) >= self.min_clients * 2)
    
    async def _perform_aggregation(self) -> AggregationResult:
        """Perform the actual aggregation based on selected strategy."""
        logger.info(f"Performing {self.strategy.value} aggregation with {len(self.pending_updates)} updates")
        
        if self.strategy == AggregationStrategy.FEDAVG:
            aggregated_weights = self._fedavg_aggregation()
        elif self.strategy == AggregationStrategy.FEDPROX:
            aggregated_weights = self._fedprox_aggregation()
        elif self.strategy == AggregationStrategy.REGIONAL:
            aggregated_weights = self._regional_aggregation()
        elif self.strategy == AggregationStrategy.ADAPTIVE:
            aggregated_weights = self._adaptive_aggregation()
        else:
            raise ValueError(f"Unknown aggregation strategy: {self.strategy}")
        
        # Calculate statistics
        total_samples = sum(u.sample_count for u in self.pending_updates)
        average_loss = sum(u.training_loss * u.sample_count for u in self.pending_updates) / total_samples
        participating_clients = [u.client_id for u in self.pending_updates]
        
        result = AggregationResult(
            aggregated_weights=aggregated_weights,
            participating_clients=participating_clients,
            total_samples=total_samples,
            average_loss=average_loss,
            aggregation_round=self.current_round,
            fog_node_id=self.fog_node_id
        )
        
        self.aggregation_history.append(result)
        return result
    
    def _fedavg_aggregation(self) -> Dict[str, torch.Tensor]:
        """Standard FedAvg aggregation: weighted average by sample count."""
        total_samples = sum(u.sample_count for u in self.pending_updates)
        aggregated_weights = {}
        
        # Get all parameter names from first update
        param_names = list(self.pending_updates[0].model_weights.keys())
        
        for param_name in param_names:
            weighted_sum = None
            
            for update in self.pending_updates:
                weight = update.sample_count / total_samples
                param_tensor = update.model_weights[param_name]
                
                if weighted_sum is None:
                    weighted_sum = weight * param_tensor
                else:
                    weighted_sum += weight * param_tensor
            
            aggregated_weights[param_name] = weighted_sum
        
        return aggregated_weights
    
    def _fedprox_aggregation(self) -> Dict[str, torch.Tensor]:
        """FedProx aggregation with proximal term."""
        # For fog layer, we use modified FedProx that considers device heterogeneity
        total_samples = sum(u.sample_count for u in self.pending_updates)
        aggregated_weights = {}
        
        param_names = list(self.pending_updates[0].model_weights.keys())
        
        for param_name in param_names:
            weighted_sum = None
            
            for update in self.pending_updates:
                # Adjust weight based on device characteristics
                base_weight = update.sample_count / total_samples
                
                # Apply proximal adjustment (reduce weight for outliers)
                # This is a simplified version - full FedProx would need global model
                prox_adjustment = 1.0 / (1.0 + self.fedprox_mu * update.training_loss)
                adjusted_weight = base_weight * prox_adjustment
                
                param_tensor = update.model_weights[param_name]
                
                if weighted_sum is None:
                    weighted_sum = adjusted_weight * param_tensor
                else:
                    weighted_sum += adjusted_weight * param_tensor
            
            aggregated_weights[param_name] = weighted_sum
        
        return aggregated_weights
    
    def _regional_aggregation(self) -> Dict[str, torch.Tensor]:
        """Region-aware aggregation considering geographic locality."""
        # For now, this is similar to FedAvg but could incorporate
        # geographic information, network topology, etc.
        return self._fedavg_aggregation()
    
    def _adaptive_aggregation(self) -> Dict[str, torch.Tensor]:
        """Adaptive aggregation based on runtime characteristics."""
        total_samples = sum(u.sample_count for u in self.pending_updates)
        aggregated_weights = {}
        
        param_names = list(self.pending_updates[0].model_weights.keys())
        
        for param_name in param_names:
            weighted_sum = None
            
            for update in self.pending_updates:
                # Adaptive weight based on multiple factors
                base_weight = update.sample_count / total_samples
                
                # Quality factor based on training loss
                loss_factor = 1.0 / (1.0 + update.training_loss)
                
                # Privacy factor (higher privacy budget = lower weight)
                privacy_factor = 1.0 / (1.0 + update.privacy_budget)
                
                # Compression factor
                compression_factor = update.compression_ratio
                
                # Combine factors
                adaptive_weight = base_weight * loss_factor * privacy_factor * compression_factor
                
                param_tensor = update.model_weights[param_name]
                
                if weighted_sum is None:
                    weighted_sum = adaptive_weight * param_tensor
                else:
                    weighted_sum += adaptive_weight * param_tensor
            
            aggregated_weights[param_name] = weighted_sum
        
        return aggregated_weights
    
    async def _handle_aggregation_result(self, result: AggregationResult) -> None:
        """Handle the aggregation result (logging, forwarding, etc.)."""
        logger.info(
            f"Aggregation round {result.aggregation_round} completed: "
            f"{len(result.participating_clients)} clients, "
            f"{result.total_samples} samples, "
            f"avg_loss={result.average_loss:.4f}"
        )
        
        # Here you would typically:
        # 1. Forward result to cloud layer
        # 2. Cache result locally
        # 3. Notify edge devices of completion
        # 4. Update local statistics
    
    def get_aggregation_stats(self) -> Dict[str, Any]:
        """Get aggregation statistics for monitoring."""
        if not self.aggregation_history:
            return {"rounds_completed": 0}
        
        recent_results = self.aggregation_history[-10:]  # Last 10 rounds
        
        return {
            "rounds_completed": len(self.aggregation_history),
            "current_round": self.current_round,
            "avg_clients_per_round": np.mean([len(r.participating_clients) for r in recent_results]),
            "avg_samples_per_round": np.mean([r.total_samples for r in recent_results]),
            "avg_loss": np.mean([r.average_loss for r in recent_results]),
            "last_aggregation": self.aggregation_history[-1].created_at.isoformat() if self.aggregation_history else None
        }
    
    async def cleanup(self) -> None:
        """Cleanup resources and cancel ongoing tasks."""
        if self.aggregation_task and not self.aggregation_task.done():
            self.aggregation_task.cancel()
            try:
                await self.aggregation_task
            except asyncio.CancelledError:
                pass
        
        logger.info(f"Regional aggregator for {self.fog_node_id} cleaned up")
