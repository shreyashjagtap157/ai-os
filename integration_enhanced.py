"""
Integration of distributed mesh, LLM optimization, and federated learning
into the main AI-OS agent runtime.
"""

import asyncio
import logging
from pathlib import Path
from typing import Optional

from agent.distributed import DistributedAgentMesh
from agent.optimization import LLMInferenceOptimizer
from agent.federated import FederatedLearningCoordinator, DifferentialPrivacyConfig
from agent.async_agent import AsyncAgent

logger = logging.getLogger(__name__)


class EnhancedAsyncAgent(AsyncAgent):
    """
    Enhanced async agent with distributed mesh, LLM optimization, and federated learning.
    """
    
    def __init__(
        self,
        allowed_root: Path | None = None,
        rpc_host: str = "127.0.0.1",
        rpc_port: int = 8000,
        enable_distributed_mesh: bool = True,
        enable_llm_optimization: bool = True,
        enable_federated_learning: bool = True,
        consul_host: str = "localhost",
        consul_port: int = 8500,
    ):
        super().__init__(allowed_root, rpc_host, rpc_port)
        
        self.enable_distributed_mesh = enable_distributed_mesh
        self.enable_llm_optimization = enable_llm_optimization
        self.enable_federated_learning = enable_federated_learning
        
        # Initialize distributed mesh
        self.mesh: Optional[DistributedAgentMesh] = None
        if enable_distributed_mesh:
            import socket
            hostname = socket.gethostname()
            self.mesh = DistributedAgentMesh(
                node_id=f"{hostname}_node",
                hostname=hostname,
                port=rpc_port,
                consul_host=consul_host,
                consul_port=consul_port
            )
        
        # Initialize LLM optimizer
        self.llm_optimizer: Optional[LLMInferenceOptimizer] = None
        if enable_llm_optimization:
            self.llm_optimizer = LLMInferenceOptimizer(
                kv_cache_size_gb=4.0,
                batch_size=32,
                enable_speculative_decoding=True
            )
        
        # Initialize federated learning
        self.federated_coordinator: Optional[FederatedLearningCoordinator] = None
        if enable_federated_learning:
            privacy_config = DifferentialPrivacyConfig(
                enabled=True,
                epsilon=1.0,
                delta=1e-5
            )
            self.federated_coordinator = FederatedLearningCoordinator(
                node_id=f"{hostname}_federated",
                privacy_config=privacy_config,
                compression_ratio=0.1
            )
    
    async def startup_enhancements(self):
        """Start distributed mesh, LLM optimization, and federated learning."""
        if self.mesh:
            try:
                await self.mesh.start()
                logger.info("Distributed mesh started successfully")
            except Exception as e:
                logger.error(f"Failed to start distributed mesh: {e}")
        
        if self.llm_optimizer:
            logger.info(f"LLM optimizer enabled with {self.llm_optimizer.batcher.batch_size} batch size")
        
        if self.federated_coordinator:
            logger.info("Federated learning coordinator initialized")
    
    async def shutdown_enhancements(self):
        """Shutdown distributed mesh and federated learning."""
        if self.mesh:
            try:
                await self.mesh.stop()
                logger.info("Distributed mesh shutdown completed")
            except Exception as e:
                logger.error(f"Error during mesh shutdown: {e}")
    
    async def run(self):
        """Enhanced run with all optimizations."""
        # Load plugins
        self.load_plugins()
        
        # Start enhancements
        await self.startup_enhancements()
        
        # Setup tasks
        tasks = []
        
        # Start RPC server
        tasks.append(asyncio.create_task(self.start_rpc()))
        
        # Start scheduler (includes enhancement monitoring)
        tasks.append(asyncio.create_task(self.enhanced_scheduler()))
        
        # Start input loop
        tasks.append(asyncio.create_task(self.input_loop()))
        
        # Handle signals
        loop = asyncio.get_running_loop()
        import signal
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                pass
        
        await self.shutdown_event.wait()
        logger.info("Shutdown event set, cancelling tasks...")
        
        # Shutdown enhancements
        await self.shutdown_enhancements()
        
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
    
    async def enhanced_scheduler(self):
        """Scheduler with enhancement monitoring."""
        while not self.shutdown_event.is_set():
            logger.debug("Heartbeat: agent running with enhancements")
            
            # Log distributed mesh status
            if self.mesh:
                logger.debug(f"Mesh peers: {len(self.mesh.peers)}, Role: {self.mesh.node.role.value}")
            
            # Log LLM optimizer stats
            if self.llm_optimizer:
                stats = self.llm_optimizer.get_statistics()
                if stats['total_requests'] > 0:
                    logger.debug(f"LLM: {stats['total_requests']} requests, "
                               f"cache hit rate: {stats['cache_hit_rate']:.2%}")
            
            # Log federated learning status
            if self.federated_coordinator:
                fed_stats = self.federated_coordinator.get_statistics()
                logger.debug(f"Federated: Round {fed_stats['round_number']}, "
                           f"Clients: {fed_stats['registered_clients']}")
            
            await asyncio.sleep(30)


async def main():
    """Main entry point with enhanced agent."""
    agent = EnhancedAsyncAgent(
        allowed_root=Path.cwd(),
        rpc_port=8000,
        enable_distributed_mesh=True,
        enable_llm_optimization=True,
        enable_federated_learning=True
    )
    
    try:
        await agent.run()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.exception(f"Agent failed: {e}")
    finally:
        logger.info("Agent shutdown complete")


if __name__ == "__main__":
    import logging.config
    from agent.logging_config import LOGGING
    
    logging.config.dictConfig(LOGGING)
    asyncio.run(main())
