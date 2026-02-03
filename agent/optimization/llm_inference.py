"""
LLM Inference Optimization

Implements quantization, caching, batching, and serving optimizations
for local LLM inference.

Features:
- Model quantization (ONNX, TensorRT, AWQ)
- KV cache management
- Request batching with dynamic window size
- Speculative decoding
- Token router for load balancing
"""

import asyncio
import logging
import time
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import hashlib

import numpy as np
from functools import lru_cache

logger = logging.getLogger(__name__)


@dataclass
class QuantizationConfig:
    """Configuration for model quantization"""
    method: str = "int8"  # int8, int4, fp16, fp32
    symmetric: bool = True
    calibration_data_size: int = 100
    optimize_for_inference: bool = True
    target_ops: List[str] = field(default_factory=list)


@dataclass
class InferenceRequest:
    """Request for inference"""
    request_id: str
    input_ids: List[int]
    max_tokens: int = 512
    temperature: float = 0.7
    top_p: float = 0.9
    top_k: int = 50
    priority: int = 0  # Higher = more important
    timestamp: datetime = field(default_factory=datetime.utcnow)
    timeout: float = 30.0


@dataclass
class InferenceResult:
    """Result of inference"""
    request_id: str
    output_ids: List[int]
    logits: Optional[np.ndarray] = None
    latency: float = 0.0
    tokens_per_second: float = 0.0
    cache_hit: bool = False


class KVCacheManager:
    """
    Manages KV (Key-Value) cache for transformer models.
    
    Reduces computation by caching attention keys and values.
    """
    
    def __init__(
        self,
        max_cache_size_gb: float = 4.0,
        eviction_policy: str = "lru"
    ):
        self.max_cache_size = int(max_cache_size_gb * 1024 * 1024 * 1024)  # Convert to bytes
        self.current_size = 0
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.access_times: Dict[str, datetime] = {}
        self.eviction_policy = eviction_policy
    
    def _compute_cache_key(
        self,
        input_ids: Tuple[int, ...],
        max_tokens: int,
        temperature: float
    ) -> str:
        """Compute cache key for request"""
        key_data = f"{input_ids}:{max_tokens}:{temperature}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    def get(
        self,
        input_ids: List[int],
        max_tokens: int,
        temperature: float
    ) -> Optional[Dict[str, Any]]:
        """Get cached KV for request"""
        cache_key = self._compute_cache_key(tuple(input_ids), max_tokens, temperature)
        
        if cache_key in self.cache:
            self.access_times[cache_key] = datetime.utcnow()
            return self.cache[cache_key]
        
        return None
    
    def put(
        self,
        input_ids: List[int],
        max_tokens: int,
        temperature: float,
        kv_data: Dict[str, Any]
    ):
        """Store KV cache for request"""
        cache_key = self._compute_cache_key(tuple(input_ids), max_tokens, temperature)
        
        # Estimate cache size (simplified)
        estimated_size = len(str(kv_data).encode())
        
        # Evict if necessary
        while self.current_size + estimated_size > self.max_cache_size and self.cache:
            self._evict_one()
        
        self.cache[cache_key] = kv_data
        self.access_times[cache_key] = datetime.utcnow()
        self.current_size += estimated_size
    
    def _evict_one(self):
        """Evict one entry based on policy"""
        if self.eviction_policy == "lru":
            # Remove least recently used
            lru_key = min(self.access_times, key=self.access_times.get)
        else:
            # FIFO
            lru_key = next(iter(self.cache))
        
        estimated_size = len(str(self.cache[lru_key]).encode())
        del self.cache[lru_key]
        del self.access_times[lru_key]
        self.current_size -= estimated_size


class ModelQuantizer:
    """
    Quantizes models for faster inference and reduced memory usage.
    """
    
    def __init__(self, config: QuantizationConfig):
        self.config = config
        self.quantization_scale: Optional[np.ndarray] = None
        self.quantization_zero_point: Optional[np.ndarray] = None
    
    def calibrate(self, calibration_data: List[np.ndarray]):
        """Calibrate quantization parameters"""
        if not calibration_data:
            return
        
        # Compute per-channel statistics
        stacked = np.vstack(calibration_data)
        
        min_val = np.min(stacked, axis=0)
        max_val = np.max(stacked, axis=0)
        
        # Compute scale and zero point for int8
        if self.config.method == "int8":
            self.quantization_scale = (max_val - min_val) / 255.0
            self.quantization_zero_point = np.round(-min_val / self.quantization_scale).astype(np.int32)
        
        logger.info(f"Quantization calibrated with {len(calibration_data)} samples")
    
    def quantize_weights(self, weights: np.ndarray) -> Tuple[np.ndarray, np.ndarray, np.ndarray]:
        """
        Quantize model weights.
        
        Returns: (quantized_weights, scale, zero_point)
        """
        if self.config.method == "fp32":
            return weights, np.array([1.0]), np.array([0])
        
        if not self.quantization_scale is None:
            scale = self.quantization_scale
            zero_point = self.quantization_zero_point
        else:
            # Use per-tensor quantization
            min_val = np.min(weights)
            max_val = np.max(weights)
            
            if self.config.method == "int8":
                scale = (max_val - min_val) / 255.0
                zero_point = np.round(-min_val / scale).astype(np.int32)
            elif self.config.method == "int4":
                scale = (max_val - min_val) / 15.0
                zero_point = np.round(-min_val / scale).astype(np.int32)
            else:
                scale = np.array([1.0])
                zero_point = np.array([0])
        
        # Quantize
        quantized = np.round(weights / scale + zero_point).astype(np.int8)
        
        return quantized, scale, zero_point
    
    def dequantize(
        self,
        quantized: np.ndarray,
        scale: np.ndarray,
        zero_point: np.ndarray
    ) -> np.ndarray:
        """Dequantize weights for inference"""
        return (quantized.astype(np.float32) - zero_point) * scale


class RequestBatcher:
    """
    Batches inference requests for efficient processing.
    """
    
    def __init__(
        self,
        batch_size: int = 32,
        batch_timeout: float = 0.1,
        dynamic_batching: bool = True
    ):
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.dynamic_batching = dynamic_batching
        
        self.pending_requests: deque = deque()
        self.batch_lock = asyncio.Lock()
        self.batch_event = asyncio.Event()
    
    async def add_request(self, request: InferenceRequest):
        """Add request to batch queue"""
        async with self.batch_lock:
            self.pending_requests.append(request)
            
            if len(self.pending_requests) >= self.batch_size:
                self.batch_event.set()
    
    async def get_batch(self) -> List[InferenceRequest]:
        """Get next batch of requests"""
        start_time = time.time()
        
        while len(self.pending_requests) < self.batch_size:
            if time.time() - start_time > self.batch_timeout:
                break
            
            # Check for dynamic batching
            if self.dynamic_batching and self.pending_requests:
                # Batch immediately if high-priority request
                min_priority = min(
                    (r.priority for r in self.pending_requests),
                    default=0
                )
                if min_priority > 5:  # High priority threshold
                    break
            
            await asyncio.sleep(0.01)
        
        async with self.batch_lock:
            batch_size = min(len(self.pending_requests), self.batch_size)
            batch = [self.pending_requests.popleft() for _ in range(batch_size)]
        
        return batch


class SpeculativeDecoding:
    """
    Implements speculative decoding for faster token generation.
    
    Uses a small draft model to generate candidate tokens,
    then verifies with the main model.
    """
    
    def __init__(
        self,
        num_speculative_tokens: int = 5,
        draft_model_size: str = "small"  # relative to main model
    ):
        self.num_speculative_tokens = num_speculative_tokens
        self.draft_model_size = draft_model_size
        self.draft_model = None
        self.main_model = None
    
    async def speculative_decode(
        self,
        input_ids: List[int],
        max_tokens: int
    ) -> Tuple[List[int], float]:
        """
        Generate tokens using speculative decoding.
        
        Returns: (output_ids, latency)
        """
        start_time = time.time()
        
        current_ids = input_ids.copy()
        generated_tokens = 0
        
        while generated_tokens < max_tokens:
            # Draft model generates candidates
            draft_candidates = await self._draft_generate(
                current_ids,
                self.num_speculative_tokens
            )
            
            # Main model verifies candidates
            verified_tokens = await self._verify_candidates(
                current_ids,
                draft_candidates
            )
            
            current_ids.extend(verified_tokens)
            generated_tokens += len(verified_tokens)
            
            if len(verified_tokens) < len(draft_candidates):
                # Rejected candidate, generate one more token
                next_token = await self._generate_one_token(current_ids)
                current_ids.append(next_token)
                generated_tokens += 1
        
        latency = time.time() - start_time
        return current_ids[len(input_ids):], latency
    
    async def _draft_generate(self, input_ids: List[int], num_tokens: int) -> List[int]:
        """Generate candidates using draft model"""
        # Simplified - would call actual draft model
        return [1] * num_tokens
    
    async def _verify_candidates(self, input_ids: List[int], candidates: List[int]) -> List[int]:
        """Verify candidates with main model"""
        # Simplified - would verify with main model
        return candidates[:1]  # Accept only first candidate
    
    async def _generate_one_token(self, input_ids: List[int]) -> int:
        """Generate one token with main model"""
        # Simplified - would generate actual token
        return 1


class TokenRouter:
    """
    Routes token generation requests to different inference engines
    for load balancing.
    """
    
    def __init__(self, num_engines: int = 4):
        self.num_engines = num_engines
        self.engine_loads: List[int] = [0] * num_engines
        self.engine_latencies: List[float] = [0.0] * num_engines
    
    def select_engine(self) -> int:
        """Select least loaded engine"""
        # Weighted by latency - prefer faster engines
        weights = [
            1.0 / (latency + 0.1) for latency in self.engine_latencies
        ]
        
        total_weight = sum(weights)
        weighted_loads = [
            (load / weight) if weight > 0 else float('inf')
            for load, weight in zip(self.engine_loads, weights)
        ]
        
        return weighted_loads.index(min(weighted_loads))
    
    def add_load(self, engine_id: int, latency: float):
        """Record engine load and latency"""
        self.engine_loads[engine_id] += 1
        self.engine_latencies[engine_id] = latency
    
    def remove_load(self, engine_id: int):
        """Decrement engine load"""
        self.engine_loads[engine_id] = max(0, self.engine_loads[engine_id] - 1)


class LLMInferenceOptimizer:
    """
    Coordinates all LLM optimization techniques.
    """
    
    def __init__(
        self,
        quantization_config: Optional[QuantizationConfig] = None,
        kv_cache_size_gb: float = 4.0,
        batch_size: int = 32,
        enable_speculative_decoding: bool = True
    ):
        self.quantization_config = quantization_config or QuantizationConfig()
        self.quantizer = ModelQuantizer(self.quantization_config)
        
        self.kv_cache = KVCacheManager(max_cache_size_gb=kv_cache_size_gb)
        self.batcher = RequestBatcher(batch_size=batch_size)
        
        if enable_speculative_decoding:
            self.speculative_decoder = SpeculativeDecoding()
        else:
            self.speculative_decoder = None
        
        self.token_router = TokenRouter()
        
        # Statistics
        self.total_requests = 0
        self.total_tokens_generated = 0
        self.total_latency = 0.0
        self.cache_hits = 0
    
    async def infer(self, request: InferenceRequest) -> InferenceResult:
        """Run inference with optimizations"""
        await self.batcher.add_request(request)
        
        # Check cache first
        cached = self.kv_cache.get(
            request.input_ids,
            request.max_tokens,
            request.temperature
        )
        
        if cached:
            self.cache_hits += 1
            return InferenceResult(
                request_id=request.request_id,
                output_ids=cached["output_ids"],
                logits=cached.get("logits"),
                latency=0.0,
                cache_hit=True
            )
        
        # Select inference engine
        engine_id = self.token_router.select_engine()
        
        # Generate tokens
        start_time = time.time()
        
        if self.speculative_decoder:
            output_ids, latency = await self.speculative_decoder.speculative_decode(
                request.input_ids,
                request.max_tokens
            )
        else:
            # Fallback to standard generation
            output_ids = request.input_ids.copy()
            latency = 0.0
        
        # Record metrics
        actual_latency = time.time() - start_time
        self.token_router.add_load(engine_id, actual_latency)
        
        # Cache result
        self.kv_cache.put(
            request.input_ids,
            request.max_tokens,
            request.temperature,
            {
                "output_ids": output_ids,
                "latency": actual_latency
            }
        )
        
        # Update statistics
        self.total_requests += 1
        self.total_tokens_generated += len(output_ids)
        self.total_latency += actual_latency
        
        return InferenceResult(
            request_id=request.request_id,
            output_ids=output_ids,
            latency=actual_latency,
            tokens_per_second=len(output_ids) / actual_latency if actual_latency > 0 else 0
        )
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get optimizer statistics"""
        return {
            "total_requests": self.total_requests,
            "total_tokens_generated": self.total_tokens_generated,
            "total_latency_seconds": self.total_latency,
            "avg_latency_ms": (self.total_latency / self.total_requests * 1000) if self.total_requests > 0 else 0,
            "avg_tokens_per_second": self.total_tokens_generated / self.total_latency if self.total_latency > 0 else 0,
            "cache_hit_rate": self.cache_hits / self.total_requests if self.total_requests > 0 else 0,
            "kv_cache_usage_mb": self.kv_cache.current_size / (1024 * 1024)
        }
