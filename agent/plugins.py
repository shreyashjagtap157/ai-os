"""
AI-OS Plugin Architecture
Extensible plugin system for adding new capabilities
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, field
import importlib
import os
from pathlib import Path


@dataclass
class PluginInfo:
    """Plugin metadata"""
    name: str
    version: str
    description: str
    author: str = ""
    dependencies: List[str] = field(default_factory=list)
    commands: List[str] = field(default_factory=list)
    

class Plugin(ABC):
    """
    Base class for AI-OS plugins.
    Extend this class to create custom plugins.
    """
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin information"""
        pass
    
    @abstractmethod
    def initialize(self, context: Dict[str, Any]) -> bool:
        """
        Initialize the plugin.
        Called when the plugin is loaded.
        
        Args:
            context: Dictionary containing system_api, llm_manager, etc.
            
        Returns:
            True if initialization successful
        """
        pass
    
    @abstractmethod
    def get_commands(self) -> Dict[str, Callable]:
        """
        Return available commands.
        
        Returns:
            Dictionary mapping command names to handler functions
        """
        pass
    
    def shutdown(self):
        """Called when the plugin is unloaded"""
        pass
    
    def on_startup(self):
        """Called when AI-OS starts"""
        pass
    
    def on_command(self, command: str, args: str) -> Optional[str]:
        """
        Hook for processing commands.
        Return None to pass to next handler.
        """
        return None


class PluginManager:
    """
    Manages plugin lifecycle and discovery.
    """
    
    def __init__(self, plugins_dir: str = "plugins"):
        self.plugins_dir = Path(plugins_dir)
        self._plugins: Dict[str, Plugin] = {}
        self._commands: Dict[str, Callable] = {}
        self._context: Dict[str, Any] = {}
    
    def set_context(self, context: Dict[str, Any]):
        """Set the context passed to plugins during initialization"""
        self._context = context
    
    def discover_plugins(self) -> List[str]:
        """Discover available plugins in the plugins directory"""
        if not self.plugins_dir.exists():
            return []
        
        plugins = []
        for item in self.plugins_dir.iterdir():
            if item.is_dir() and (item / "__init__.py").exists():
                plugins.append(item.name)
            elif item.suffix == ".py" and item.name != "__init__.py":
                plugins.append(item.stem)
        
        return plugins
    
    def load_plugin(self, name: str) -> bool:
        """
        Load a plugin by name.
        
        Args:
            name: Plugin module name
            
        Returns:
            True if loaded successfully
        """
        try:
            # Import the plugin module
            module = importlib.import_module(f"plugins.{name}")
            
            # Find the Plugin subclass
            plugin_class = None
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, type) and issubclass(attr, Plugin) and attr != Plugin:
                    plugin_class = attr
                    break
            
            if not plugin_class:
                print(f"[PluginManager] No Plugin class found in {name}")
                return False
            
            # Instantiate and initialize
            plugin = plugin_class()
            if plugin.initialize(self._context):
                self._plugins[name] = plugin
                
                # Register commands
                for cmd_name, handler in plugin.get_commands().items():
                    self._commands[cmd_name] = handler
                
                print(f"[PluginManager] Loaded plugin: {plugin.info.name} v{plugin.info.version}")
                return True
            else:
                print(f"[PluginManager] Failed to initialize: {name}")
                return False
                
        except Exception as e:
            print(f"[PluginManager] Error loading {name}: {e}")
            return False
    
    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin"""
        if name not in self._plugins:
            return False
        
        plugin = self._plugins[name]
        
        # Remove commands
        for cmd_name in plugin.get_commands().keys():
            self._commands.pop(cmd_name, None)
        
        # Shutdown
        plugin.shutdown()
        del self._plugins[name]
        
        print(f"[PluginManager] Unloaded plugin: {name}")
        return True
    
    def load_all(self):
        """Load all discovered plugins"""
        for name in self.discover_plugins():
            self.load_plugin(name)
    
    def get_command(self, name: str) -> Optional[Callable]:
        """Get a command handler by name"""
        return self._commands.get(name)
    
    def list_plugins(self) -> List[PluginInfo]:
        """List all loaded plugins"""
        return [p.info for p in self._plugins.values()]
    
    def list_commands(self) -> Dict[str, str]:
        """List all available plugin commands"""
        commands = {}
        for plugin in self._plugins.values():
            for cmd in plugin.info.commands:
                commands[cmd] = f"[{plugin.info.name}] {plugin.info.description}"
        return commands


# Example plugin template
PLUGIN_TEMPLATE = '''"""
Example AI-OS Plugin
"""
from agent.plugins import Plugin, PluginInfo
from typing import Dict, Any, Callable


class ExamplePlugin(Plugin):
    """Example plugin demonstrating the plugin architecture"""
    
    @property
    def info(self) -> PluginInfo:
        return PluginInfo(
            name="Example Plugin",
            version="1.0.0",
            description="An example plugin for AI-OS",
            author="AI-OS Team",
            commands=["example", "demo"]
        )
    
    def initialize(self, context: Dict[str, Any]) -> bool:
        self.system_api = context.get("system_api")
        self.llm = context.get("llm_manager")
        return True
    
    def get_commands(self) -> Dict[str, Callable]:
        return {
            "example": self.cmd_example,
            "demo": self.cmd_demo
        }
    
    def cmd_example(self, args: str) -> str:
        return f"Example command executed with: {args}"
    
    def cmd_demo(self, args: str) -> str:
        return "This is a demo command from the example plugin!"
'''


# Global plugin manager
plugin_manager = PluginManager()
