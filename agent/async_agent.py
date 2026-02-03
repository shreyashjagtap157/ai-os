"""
Async agent runner with scheduler and embedded RPC server.
Enhanced with distributed mesh, LLM optimization, and federated learning.
"""
import asyncio
import signal
import logging
from pathlib import Path
from agent.system_api import SystemAPI
from agent.agent import CommandRegistry
from agent.plugins import discover_plugins, load_plugin
from agent.input.text_input import get_text_input
from agent import rpc

# Import enhancements
from agent.distributed import DistributedAgentMesh
from agent.optimization import LLMInferenceOptimizer
from agent.federated import FederatedLearningCoordinator, DifferentialPrivacyConfig

import uvicorn
import socket
import yaml

logger = logging.getLogger(__name__)


class AsyncAgent:
    def __init__(self, allowed_root: Path | None = None, rpc_host: str = "127.0.0.1", rpc_port: int = 8000):
        self.allowed_root = allowed_root or Path.cwd()
        self.api = SystemAPI(allowed_root=self.allowed_root)
        self.registry = CommandRegistry(self.api)
        self.shutdown_event = asyncio.Event()
        self.rpc_host = rpc_host
        self.rpc_port = rpc_port
        
        # Initialize enhancements
        self.mesh = None
        self.llm_optimizer = None
        self.federated_coordinator = None
        self._load_config_enhancements()

    async def start_rpc(self):
        # attach registry to app state
        rpc.app.state.registry = self.registry
        # attach api key if configured
        try:
            from agent.config import load_config

            cfg = load_config()
            if cfg.api_key:
                rpc.app.state.api_key = cfg.api_key
        except Exception:
            logger.exception("Failed to load config for RPC API key")
        
        # Attach enhancement references to app state
        rpc.app.state.mesh = self.mesh
        rpc.app.state.llm_optimizer = self.llm_optimizer
        rpc.app.state.federated_coordinator = self.federated_coordinator
        
        config = uvicorn.Config(rpc.app, host=self.rpc_host, port=self.rpc_port, loop="asyncio", lifespan="on")
        server = uvicorn.Server(config)
        logger.info(f"Starting RPC on {self.rpc_host}:{self.rpc_port}")
        # run server in background
        await server.serve()

    def load_plugins(self):
        plugin_dir = Path(__file__).parent / "plugins"
        discovered = discover_plugins(plugin_dir)
        for name in discovered:
            mod = load_plugin(f"agent.plugins.{name}")
            if mod and hasattr(mod, "register"):
                try:
                    mod.register(self.registry)
                    logger.info(f"Loaded plugin: {name}")
                except Exception:
                    logger.exception(f"Plugin {name} failed to register")

    async def scheduler(self):
        # simple periodic task example: heartbeat
        while not self.shutdown_event.is_set():
            logger.debug("Heartbeat: agent running")
            
            # Log distributed mesh status
            if self.mesh:
                try:
                    peers = len(self.mesh.peers)
                    role = self.mesh.node.role.value if self.mesh.node else "unknown"
                    logger.debug(f"Mesh: {peers} peers, role={role}")
                except Exception as e:
                    logger.warning(f"Error getting mesh status: {e}")
            
            # Log LLM optimizer stats
            if self.llm_optimizer:
                try:
                    stats = self.llm_optimizer.get_statistics()
                    if stats['total_requests'] > 0:
                        logger.debug(f"LLM: {stats['total_requests']} requests, cache_hit={stats['cache_hit_rate']:.2%}")
                except Exception as e:
                    logger.warning(f"Error getting LLM stats: {e}")
            
            # Log federated learning status
            if self.federated_coordinator:
                try:
                    fed_stats = self.federated_coordinator.get_statistics()
                    logger.debug(f"Federated: Round {fed_stats['round_number']}, Clients: {fed_stats['registered_clients']}")
                except Exception as e:
                    logger.warning(f"Error getting federated stats: {e}")
            
            await asyncio.sleep(30)

    async def input_loop(self):
        # run text input in threadpool to avoid blocking
        loop = asyncio.get_running_loop()
        while not self.shutdown_event.is_set():
            raw = await loop.run_in_executor(None, get_text_input, "[ai-async] ")
            from agent.agent import parse_command
            cmd, args = parse_command(raw)
            cont = self.registry.execute(cmd, args)
            if not cont:
                self.shutdown_event.set()

    async def run(self):
        self.load_plugins()
        
        # Start enhancements
        await self._startup_enhancements()
        
        tasks = []
        # start RPC server
        tasks.append(asyncio.create_task(self.start_rpc()))
        # start scheduler
        tasks.append(asyncio.create_task(self.scheduler()))
        # start input loop
        tasks.append(asyncio.create_task(self.input_loop()))

        # handle signals
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.shutdown()))
            except NotImplementedError:
                # add_signal_handler may not be implemented on Windows for certain loops
                pass

        await self.shutdown_event.wait()
        logger.info("Shutdown event set, cancelling tasks...")
        for t in tasks:
            t.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def shutdown(self):
        logger.info("Shutdown requested")
        
        # Shutdown enhancements
        if self.mesh:
            try:
                await self.mesh.stop()
                logger.info("Distributed mesh stopped")
            except Exception as e:
                logger.error(f"Error stopping mesh: {e}")
        
        if self.federated_coordinator:
            try:
                logger.info("Federated learning coordinator stopped")
            except Exception as e:
                logger.error(f"Error stopping federated learning: {e}")
        
        self.shutdown_event.set()
    
    def _load_config_enhancements(self):
        """Load enhancement configuration from YAML file."""
        try:
            config_path = Path(__file__).parent.parent.parent / "ai-os" / "config" / "agent.yaml"
            if not config_path.exists():
                logger.warning(f"Config file not found at {config_path}, using defaults")
                return
            
            with open(config_path) as f:
                config = yaml.safe_load(f)
            
            if not config:
                return
            
            # Initialize distributed mesh
            if config.get("distributed_mesh", {}).get("enabled", False):
                try:
                    hostname = socket.gethostname()
                    mesh_config = config.get("distributed_mesh", {})
                    self.mesh = DistributedAgentMesh(
                        node_id=f"{hostname}_node",
                        hostname=hostname,
                        port=self.rpc_port,
                        consul_host=mesh_config.get("consul_host", "localhost"),
                        consul_port=mesh_config.get("consul_port", 8500)
                    )
                    logger.info("Distributed mesh initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize distributed mesh: {e}")
            
            # Initialize LLM optimizer
            if config.get("llm_optimization", {}).get("enabled", False):
                try:
                    llm_config = config.get("llm_optimization", {})
                    self.llm_optimizer = LLMInferenceOptimizer(
                        kv_cache_size_gb=llm_config.get("kv_cache_size_gb", 4.0),
                        batch_size=llm_config.get("batch_size", 32),
                        enable_speculative_decoding=llm_config.get("enable_speculative_decoding", True)
                    )
                    logger.info("LLM optimizer initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize LLM optimizer: {e}")
            
            # Initialize federated learning
            if config.get("federated_learning", {}).get("enabled", False):
                try:
                    fed_config = config.get("federated_learning", {})
                    privacy_config = DifferentialPrivacyConfig(
                        enabled=fed_config.get("privacy", {}).get("enabled", True),
                        epsilon=fed_config.get("privacy", {}).get("epsilon", 1.0),
                        delta=fed_config.get("privacy", {}).get("delta", 1e-5)
                    )
                    hostname = socket.gethostname()
                    self.federated_coordinator = FederatedLearningCoordinator(
                        node_id=f"{hostname}_federated",
                        privacy_config=privacy_config,
                        compression_ratio=fed_config.get("gradient_compression", {}).get("compression_ratio", 0.1)
                    )
                    logger.info("Federated learning coordinator initialized")
                except Exception as e:
                    logger.error(f"Failed to initialize federated learning: {e}")
        
        except Exception as e:
            logger.error(f"Error loading enhancement configuration: {e}")
    
    async def _startup_enhancements(self):
        """Start all enhancement services."""
        if self.mesh:
            try:
                await self.mesh.start()
                logger.info("Distributed mesh started successfully")
            except Exception as e:
                logger.error(f"Failed to start distributed mesh: {e}")


def main():
    logging.basicConfig(level=logging.INFO, format="[%(name)s] %(levelname)s: %(message)s")
    agent = AsyncAgent()
    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        logger.info("Interrupted by user")


if __name__ == "__main__":
    main()
