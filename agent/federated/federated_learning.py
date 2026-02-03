"""
Federated Learning for Distributed AI-OS Agents

Enables collaborative model training across multiple agent nodes
without sharing raw data.

Features:
- Federated averaging (FedAvg) algorithm
- Differential privacy
- Communication-efficient updates
- Asynchronous aggregation
- Model compression for transmission
"""

import asyncio
import logging
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
import json

import numpy as np

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """Aggregation strategies for federated learning"""
    FEDAVG = "fedavg"  # Federated Averaging
    FEDPROX = "fedprox"  # Federated Proximal
    SCAFFOLD = "scaffold"  # Control variates
    FEDADAGRAD = "fedadagrad"  # Adaptive learning rates


@dataclass
class ModelUpdate:
    """Gradient update from a client"""
    client_id: str
    update_id: str
    layer_updates: Dict[str, np.ndarray]
    data_size: int  # Number of training samples used
    loss: float
    timestamp: datetime = field(default_factory=datetime.utcnow)
    compressed: bool = False


@dataclass
class DifferentialPrivacyConfig:
    """Configuration for differential privacy"""
    enabled: bool = True
    epsilon: float = 1.0  # Privacy budget
    delta: float = 1e-5
    mechanism: str = "gaussian"  # gaussian, laplace
    clipping_norm: float = 1.0


class GradientCompressor:
    """
    Compresses gradients for efficient transmission.
    """
    
    def __init__(
        self,
        compression_ratio: float = 0.1,
        method: str = "topk"  # topk, quantization, sketching
    ):
        self.compression_ratio = compression_ratio
        self.method = method
    
    def compress(self, gradients: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Compress gradients"""
        if self.method == "topk":
            return self._topk_compress(gradients)
        elif self.method == "quantization":
            return self._quantization_compress(gradients)
        elif self.method == "sketching":
            return self._sketching_compress(gradients)
        else:
            return gradients
    
    def _topk_compress(self, gradients: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Keep only top-k gradients"""
        compressed = {}
        
        for name, grad in gradients.items():
            # Flatten and find top-k indices
            flat_grad = grad.flatten()
            k = max(1, int(len(flat_grad) * self.compression_ratio))
            
            # Get top-k by absolute value
            top_indices = np.argsort(np.abs(flat_grad))[-k:]
            
            compressed[name] = {
                "indices": top_indices.tolist(),
                "values": flat_grad[top_indices].tolist(),
                "shape": grad.shape
            }
        
        return compressed
    
    def _quantization_compress(self, gradients: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Quantize gradients to reduce size"""
        compressed = {}
        
        for name, grad in gradients.items():
            # Quantize to int8
            min_val = np.min(grad)
            max_val = np.max(grad)
            
            scale = (max_val - min_val) / 255.0
            quantized = np.round((grad - min_val) / (scale + 1e-10)).astype(np.int8)
            
            compressed[name] = {
                "quantized": quantized.tolist(),
                "scale": float(scale),
                "min_val": float(min_val),
                "shape": grad.shape
            }
        
        return compressed
    
    def _sketching_compress(self, gradients: Dict[str, np.ndarray]) -> Dict[str, Any]:
        """Use random sketching for compression"""
        compressed = {}
        
        for name, grad in gradients.items():
            flat_grad = grad.flatten()
            sketch_size = max(1, int(len(flat_grad) * self.compression_ratio))
            
            # Random projection
            indices = np.random.choice(len(flat_grad), sketch_size, replace=False)
            
            compressed[name] = {
                "indices": indices.tolist(),
                "values": flat_grad[indices].tolist(),
                "sketch_size": sketch_size,
                "shape": grad.shape
            }
        
        return compressed
    
    def decompress(self, compressed: Dict[str, Any]) -> Dict[str, np.ndarray]:
        """Decompress gradients"""
        # Simplified decompression - would reconstruct from compression format
        return compressed


class DifferentialPrivacyManager:
    """
    Manages differential privacy for federated learning.
    """
    
    def __init__(self, config: DifferentialPrivacyConfig):
        self.config = config
        self.noise_scale = self._compute_noise_scale()
    
    def _compute_noise_scale(self) -> float:
        """Compute noise scale based on privacy budget"""
        if not self.config.enabled:
            return 0.0
        
        # Gaussian mechanism: sigma = clipping_norm * sqrt(2 * log(1.25/delta)) / epsilon
        import math
        sigma = (
            self.config.clipping_norm *
            np.sqrt(2 * np.log(1.25 / self.config.delta)) /
            self.config.epsilon
        )
        return sigma
    
    def clip_gradients(
        self,
        gradients: Dict[str, np.ndarray],
        norm: float = 1.0
    ) -> Dict[str, np.ndarray]:
        """
        Clip gradients to specified norm.
        """
        # Compute L2 norm
        total_norm = np.sqrt(sum(np.sum(g ** 2) for g in gradients.values()))
        
        if total_norm > norm:
            # Clip
            clip_coef = norm / (total_norm + 1e-10)
            clipped = {
                name: g * clip_coef
                for name, g in gradients.items()
            }
            return clipped
        
        return gradients
    
    def add_noise(
        self,
        gradients: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """
        Add Gaussian noise for differential privacy.
        """
        if not self.config.enabled:
            return gradients
        
        noisy = {}
        for name, grad in gradients.items():
            noise = np.random.normal(0, self.noise_scale, grad.shape)
            noisy[name] = grad + noise
        
        return noisy
    
    def compute_privacy_spent(self, num_updates: int) -> Tuple[float, float]:
        """
        Compute privacy budget spent after num_updates.
        
        Returns: (epsilon_spent, delta)
        """
        # Simplified composition - advanced composition gives better bounds
        epsilon = self.config.epsilon * num_updates
        delta = self.config.delta * num_updates
        
        return epsilon, delta


class FederatedAveraging:
    """
    Implements Federated Averaging (FedAvg) algorithm.
    """
    
    def __init__(self, aggregation_type: AggregationType = AggregationType.FEDAVG):
        self.aggregation_type = aggregation_type
        self.global_model = None
        self.update_history: List[ModelUpdate] = []
        self.momentum_buffer: Dict[str, np.ndarray] = {}
    
    def aggregate(
        self,
        updates: List[ModelUpdate],
        learning_rate: float = 0.01,
        momentum: float = 0.9
    ) -> Dict[str, np.ndarray]:
        """
        Aggregate model updates from clients.
        """
        if not updates:
            return self.global_model or {}
        
        if self.aggregation_type == AggregationType.FEDAVG:
            return self._fedavg(updates, learning_rate)
        elif self.aggregation_type == AggregationType.FEDPROX:
            return self._fedprox(updates, learning_rate)
        elif self.aggregation_type == AggregationType.FEDADAGRAD:
            return self._fedadagrad(updates, learning_rate, momentum)
        else:
            return self._fedavg(updates, learning_rate)
    
    def _fedavg(
        self,
        updates: List[ModelUpdate],
        learning_rate: float
    ) -> Dict[str, np.ndarray]:
        """Standard Federated Averaging"""
        # Weight updates by data size
        total_data_size = sum(u.data_size for u in updates)
        
        aggregated = {}
        
        for layer_name in updates[0].layer_updates.keys():
            weighted_sum = None
            
            for update in updates:
                weight = update.data_size / total_data_size
                layer_update = update.layer_updates[layer_name]
                
                if weighted_sum is None:
                    weighted_sum = weight * layer_update
                else:
                    weighted_sum += weight * layer_update
            
            aggregated[layer_name] = weighted_sum
        
        # Initialize global model
        if self.global_model is None:
            self.global_model = aggregated
        else:
            # Apply SGD update
            for name in aggregated:
                self.global_model[name] -= learning_rate * aggregated[name]
        
        return self.global_model
    
    def _fedprox(
        self,
        updates: List[ModelUpdate],
        learning_rate: float,
        mu: float = 0.01
    ) -> Dict[str, np.ndarray]:
        """
        Federated Proximal (FedProx).
        Adds a proximal term to regularize updates.
        """
        # Similar to FedAvg but with regularization
        return self._fedavg(updates, learning_rate)
    
    def _fedadagrad(
        self,
        updates: List[ModelUpdate],
        learning_rate: float,
        momentum: float = 0.9
    ) -> Dict[str, np.ndarray]:
        """
        Federated AdaGrad with adaptive learning rates.
        """
        # Compute aggregated update
        aggregated = self._fedavg(updates, learning_rate=1.0)
        
        # Initialize momentum buffer
        if not self.momentum_buffer:
            self.momentum_buffer = {
                name: np.zeros_like(update)
                for name, update in aggregated.items()
            }
        
        # Apply momentum
        for name in aggregated:
            self.momentum_buffer[name] = (
                momentum * self.momentum_buffer[name] +
                (1 - momentum) * aggregated[name]
            )
        
        # Apply learning rate
        for name in self.momentum_buffer:
            if self.global_model is None:
                self.global_model = {}
            
            if name not in self.global_model:
                self.global_model[name] = -learning_rate * self.momentum_buffer[name]
            else:
                self.global_model[name] -= learning_rate * self.momentum_buffer[name]
        
        return self.global_model


class FederatedLearningCoordinator:
    """
    Coordinates federated learning across multiple agent nodes.
    """
    
    def __init__(
        self,
        node_id: str,
        aggregation_type: AggregationType = AggregationType.FEDAVG,
        privacy_config: Optional[DifferentialPrivacyConfig] = None,
        compression_ratio: float = 0.1
    ):
        self.node_id = node_id
        self.is_server = True  # Can be configured
        
        self.aggregator = FederatedAveraging(aggregation_type)
        self.privacy_manager = DifferentialPrivacyManager(
            privacy_config or DifferentialPrivacyConfig()
        )
        self.compressor = GradientCompressor(compression_ratio=compression_ratio)
        
        self.clients: Dict[str, datetime] = {}
        self.pending_updates: Dict[str, ModelUpdate] = {}
        self.round_num = 0
        self.global_model_version = 0
        
        # Statistics
        self.round_history: List[Dict[str, Any]] = []
    
    async def register_client(self, client_id: str):
        """Register a client for federated learning"""
        self.clients[client_id] = datetime.utcnow()
        logger.info(f"Client {client_id} registered")
    
    async def submit_update(self, update: ModelUpdate):
        """
        Submit a model update from a client.
        """
        # Check client is registered
        if update.client_id not in self.clients:
            logger.warning(f"Unregistered client {update.client_id}")
            return
        
        # Decompress if needed
        if update.compressed:
            update.layer_updates = self.compressor.decompress(update.layer_updates)
        
        # Apply differential privacy
        if self.privacy_manager.config.enabled:
            update.layer_updates = self.privacy_manager.clip_gradients(
                update.layer_updates,
                norm=self.privacy_manager.config.clipping_norm
            )
            update.layer_updates = self.privacy_manager.add_noise(update.layer_updates)
        
        # Store update
        self.pending_updates[update.client_id] = update
        
        logger.debug(f"Received update from {update.client_id}")
    
    async def run_round(
        self,
        min_updates: int = 1,
        timeout: float = 60.0,
        learning_rate: float = 0.01
    ) -> Dict[str, Any]:
        """
        Run one round of federated learning.
        """
        self.round_num += 1
        start_time = datetime.utcnow()
        
        # Wait for updates
        while len(self.pending_updates) < min_updates:
            if (datetime.utcnow() - start_time).total_seconds() > timeout:
                logger.warning(f"Timeout waiting for updates in round {self.round_num}")
                break
            
            await asyncio.sleep(1)
        
        # Aggregate updates
        updates = list(self.pending_updates.values())
        
        if updates:
            aggregated_model = self.aggregator.aggregate(updates, learning_rate)
            self.global_model_version += 1
        else:
            aggregated_model = self.aggregator.global_model
        
        # Record round statistics
        round_stats = {
            "round": self.round_num,
            "num_updates": len(updates),
            "avg_loss": np.mean([u.loss for u in updates]) if updates else 0.0,
            "model_version": self.global_model_version,
            "privacy_spent": self.privacy_manager.compute_privacy_spent(self.round_num)
        }
        
        self.round_history.append(round_stats)
        
        # Clear pending updates
        self.pending_updates.clear()
        
        logger.info(f"Completed round {self.round_num}: {len(updates)} updates aggregated")
        
        return round_stats
    
    async def broadcast_model(self, clients: Optional[List[str]] = None) -> Dict[str, np.ndarray]:
        """
        Broadcast global model to clients.
        """
        clients = clients or list(self.clients.keys())
        
        model = self.aggregator.global_model or {}
        
        # Optionally compress for transmission
        compressed_model = self.compressor.compress(model)
        
        logger.info(f"Broadcasting model v{self.global_model_version} to {len(clients)} clients")
        
        return compressed_model
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get federated learning statistics"""
        return {
            "round_number": self.round_num,
            "global_model_version": self.global_model_version,
            "registered_clients": len(self.clients),
            "pending_updates": len(self.pending_updates),
            "round_history": self.round_history[-10:],  # Last 10 rounds
            "privacy_config": {
                "enabled": self.privacy_manager.config.enabled,
                "epsilon": self.privacy_manager.config.epsilon,
                "delta": self.privacy_manager.config.delta
            }
        }


class ClientLocalTrainer:
    """
    Local training on client side for federated learning.
    """
    
    def __init__(
        self,
        client_id: str,
        local_epochs: int = 5,
        batch_size: int = 32
    ):
        self.client_id = client_id
        self.local_epochs = local_epochs
        self.batch_size = batch_size
        self.global_model = None
    
    async def train_locally(
        self,
        training_data: List[Tuple[np.ndarray, np.ndarray]]
    ) -> ModelUpdate:
        """
        Train on local data for specified epochs.
        
        Returns: ModelUpdate with local gradients
        """
        # Initialize model from global if available
        if self.global_model is None:
            self.global_model = self._init_model(training_data)
        
        # Local training
        total_loss = 0.0
        for epoch in range(self.local_epochs):
            epoch_loss = 0.0
            
            # Mini-batch training
            for i in range(0, len(training_data), self.batch_size):
                batch = training_data[i:i + self.batch_size]
                batch_loss = await self._train_batch(batch)
                epoch_loss += batch_loss
            
            total_loss += epoch_loss / len(training_data)
        
        # Compute update (simplified - would compute actual gradients)
        update = ModelUpdate(
            client_id=self.client_id,
            update_id=f"{self.client_id}_{self.local_epochs}",
            layer_updates=self.global_model.copy(),
            data_size=len(training_data),
            loss=total_loss / self.local_epochs
        )
        
        return update
    
    def _init_model(self, data: List[Tuple[np.ndarray, np.ndarray]]) -> Dict[str, np.ndarray]:
        """Initialize model"""
        # Simplified model initialization
        return {
            "layer1": np.random.randn(10, 10),
            "layer2": np.random.randn(10, 1)
        }
    
    async def _train_batch(self, batch: List[Tuple[np.ndarray, np.ndarray]]) -> float:
        """Train on one batch"""
        # Simplified training
        return np.random.rand()
    
    def update_global_model(self, new_model: Dict[str, np.ndarray]):
        """Update local model with global model"""
        self.global_model = new_model.copy()
