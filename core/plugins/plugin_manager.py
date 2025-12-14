#!/usr/bin/env python3
"""
AI-OS Plugin System
Extensible plugin architecture for adding new capabilities.
"""

import os
import sys
import json
import importlib
import importlib.util
from pathlib import Path
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Callable
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aios-plugins')


class PluginType(Enum):
    """Types of plugins"""
    AGENT_SKILL = "agent_skill"      # New AI capabilities
    ACTION = "action"                 # New action types
    SERVICE = "service"               # Background service
    UI_WIDGET = "ui_widget"           # UI component
    HAL_DRIVER = "hal_driver"         # Hardware driver
    INPUT_METHOD = "input_method"     # Input handling
    THEME = "theme"                   # Visual theme


@dataclass
class PluginInfo:
    """Plugin metadata"""
    id: str
    name: str
    version: str
    description: str
    author: str
    plugin_type: PluginType
    dependencies: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    config_schema: Dict[str, Any] = field(default_factory=dict)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PluginInfo':
        return cls(
            id=data['id'],
            name=data['name'],
            version=data.get('version', '1.0.0'),
            description=data.get('description', ''),
            author=data.get('author', ''),
            plugin_type=PluginType(data.get('type', 'action')),
            dependencies=data.get('dependencies', []),
            permissions=data.get('permissions', []),
            config_schema=data.get('config_schema', {})
        )


class Plugin(ABC):
    """Base class for all plugins"""
    
    def __init__(self, info: PluginInfo, config: Dict[str, Any] = None):
        self.info = info
        self.config = config or {}
        self.enabled = False
    
    @abstractmethod
    def activate(self) -> bool:
        """Called when plugin is enabled"""
        pass
    
    @abstractmethod
    def deactivate(self) -> bool:
        """Called when plugin is disabled"""
        pass
    
    def get_config(self, key: str, default: Any = None) -> Any:
        """Get configuration value"""
        return self.config.get(key, default)
    
    def set_config(self, key: str, value: Any):
        """Set configuration value"""
        self.config[key] = value


class AgentSkillPlugin(Plugin):
    """Plugin that adds new AI agent capabilities"""
    
    @abstractmethod
    def get_skill_prompt(self) -> str:
        """Return prompt addition for AI"""
        pass
    
    @abstractmethod
    def process_query(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """Process a query if relevant to this skill"""
        pass


class ActionPlugin(Plugin):
    """Plugin that adds new action types"""
    
    @abstractmethod
    def get_actions(self) -> List[str]:
        """Return list of action names provided"""
        pass
    
    @abstractmethod
    def execute_action(self, action: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action"""
        pass


class ServicePlugin(Plugin):
    """Plugin that runs as a background service"""
    
    @abstractmethod
    async def run(self):
        """Main service loop"""
        pass
    
    @abstractmethod
    async def stop(self):
        """Stop the service"""
        pass


class PluginManager:
    """Manages plugin discovery, loading, and lifecycle"""
    
    PLUGIN_DIRS = [
        "/usr/lib/aios/plugins",
        "/usr/local/lib/aios/plugins",
        os.path.expanduser("~/.local/share/aios/plugins")
    ]
    
    def __init__(self):
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_configs: Dict[str, Dict[str, Any]] = {}
        self._load_configs()
    
    def _load_configs(self):
        """Load plugin configurations"""
        config_path = Path("/etc/aios/plugins.json")
        if config_path.exists():
            try:
                with open(config_path) as f:
                    self.plugin_configs = json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load plugin configs: {e}")
    
    def _save_configs(self):
        """Save plugin configurations"""
        config_path = Path("/etc/aios/plugins.json")
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, 'w') as f:
                json.dump(self.plugin_configs, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save plugin configs: {e}")
    
    def discover_plugins(self) -> List[PluginInfo]:
        """Discover available plugins"""
        discovered = []
        
        for plugin_dir in self.PLUGIN_DIRS:
            dir_path = Path(plugin_dir)
            if not dir_path.exists():
                continue
            
            for plugin_path in dir_path.iterdir():
                if plugin_path.is_dir():
                    manifest_path = plugin_path / "plugin.json"
                    if manifest_path.exists():
                        try:
                            with open(manifest_path) as f:
                                data = json.load(f)
                            info = PluginInfo.from_dict(data)
                            discovered.append(info)
                        except Exception as e:
                            logger.warning(f"Failed to load plugin manifest: {e}")
        
        return discovered
    
    def load_plugin(self, plugin_id: str) -> bool:
        """Load a plugin by ID"""
        if plugin_id in self.plugins:
            logger.info(f"Plugin {plugin_id} already loaded")
            return True
        
        # Find plugin
        for plugin_dir in self.PLUGIN_DIRS:
            plugin_path = Path(plugin_dir) / plugin_id
            manifest_path = plugin_path / "plugin.json"
            
            if manifest_path.exists():
                try:
                    # Load manifest
                    with open(manifest_path) as f:
                        data = json.load(f)
                    info = PluginInfo.from_dict(data)
                    
                    # Load module
                    module_path = plugin_path / "main.py"
                    if not module_path.exists():
                        logger.error(f"Plugin main.py not found: {plugin_id}")
                        return False
                    
                    spec = importlib.util.spec_from_file_location(plugin_id, module_path)
                    module = importlib.util.module_from_spec(spec)
                    spec.loader.exec_module(module)
                    
                    # Get plugin class
                    if not hasattr(module, 'PluginMain'):
                        logger.error(f"Plugin missing PluginMain class: {plugin_id}")
                        return False
                    
                    # Get config
                    config = self.plugin_configs.get(plugin_id, {})
                    
                    # Instantiate
                    plugin = module.PluginMain(info, config)
                    self.plugins[plugin_id] = plugin
                    
                    logger.info(f"Loaded plugin: {plugin_id}")
                    return True
                    
                except Exception as e:
                    logger.error(f"Failed to load plugin {plugin_id}: {e}")
                    return False
        
        logger.error(f"Plugin not found: {plugin_id}")
        return False
    
    def unload_plugin(self, plugin_id: str) -> bool:
        """Unload a plugin"""
        if plugin_id not in self.plugins:
            return True
        
        plugin = self.plugins[plugin_id]
        
        if plugin.enabled:
            plugin.deactivate()
        
        del self.plugins[plugin_id]
        logger.info(f"Unloaded plugin: {plugin_id}")
        return True
    
    def enable_plugin(self, plugin_id: str) -> bool:
        """Enable a loaded plugin"""
        if plugin_id not in self.plugins:
            if not self.load_plugin(plugin_id):
                return False
        
        plugin = self.plugins[plugin_id]
        
        if plugin.enabled:
            return True
        
        try:
            success = plugin.activate()
            plugin.enabled = success
            logger.info(f"Enabled plugin: {plugin_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to enable plugin {plugin_id}: {e}")
            return False
    
    def disable_plugin(self, plugin_id: str) -> bool:
        """Disable a plugin"""
        if plugin_id not in self.plugins:
            return True
        
        plugin = self.plugins[plugin_id]
        
        if not plugin.enabled:
            return True
        
        try:
            success = plugin.deactivate()
            plugin.enabled = not success
            logger.info(f"Disabled plugin: {plugin_id}")
            return success
        except Exception as e:
            logger.error(f"Failed to disable plugin {plugin_id}: {e}")
            return False
    
    def get_plugin(self, plugin_id: str) -> Optional[Plugin]:
        """Get a loaded plugin"""
        return self.plugins.get(plugin_id)
    
    def get_enabled_plugins(self) -> List[Plugin]:
        """Get all enabled plugins"""
        return [p for p in self.plugins.values() if p.enabled]
    
    def get_plugins_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        """Get plugins of a specific type"""
        return [
            p for p in self.plugins.values()
            if p.info.plugin_type == plugin_type and p.enabled
        ]
    
    def configure_plugin(self, plugin_id: str, config: Dict[str, Any]):
        """Update plugin configuration"""
        self.plugin_configs[plugin_id] = config
        self._save_configs()
        
        if plugin_id in self.plugins:
            self.plugins[plugin_id].config = config


# ============ Example Plugin ============

class WeatherPlugin(AgentSkillPlugin):
    """Example weather plugin"""
    
    def activate(self) -> bool:
        logger.info("Weather plugin activated")
        return True
    
    def deactivate(self) -> bool:
        logger.info("Weather plugin deactivated")
        return True
    
    def get_skill_prompt(self) -> str:
        return """You can provide weather information. When asked about weather:
        1. Acknowledge the request
        2. Return action: {"action": "weather", "params": {"location": "city_name"}}
        """
    
    def process_query(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        if 'weather' in query.lower():
            return "I can check the weather for you. Which city?"
        return None


# Global plugin manager instance
_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    """Get the global plugin manager"""
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager


if __name__ == '__main__':
    manager = get_plugin_manager()
    
    print("Discovering plugins...")
    plugins = manager.discover_plugins()
    
    for plugin in plugins:
        print(f"  - {plugin.name} ({plugin.id}): {plugin.description}")
