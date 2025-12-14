#!/usr/bin/env python3
"""
AI-OS Application Framework
Framework for building AI-OS native applications.
"""

import os
import sys
import json
import socket
import struct
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List, Callable
from pathlib import Path
from enum import Enum


class AppType(Enum):
    """Application types"""
    GRAPHICAL = "graphical"
    CLI = "cli"
    DAEMON = "daemon"
    WIDGET = "widget"


@dataclass
class AppInfo:
    """Application metadata"""
    name: str
    version: str
    description: str
    author: str = ""
    icon: str = ""
    app_type: AppType = AppType.GRAPHICAL
    categories: List[str] = field(default_factory=list)
    permissions: List[str] = field(default_factory=list)
    
    def to_desktop_entry(self) -> str:
        """Generate .desktop file content"""
        return f"""[Desktop Entry]
Type=Application
Name={self.name}
Version={self.version}
Comment={self.description}
Exec=aios-app {self.name.lower().replace(' ', '-')}
Icon={self.icon or 'application-x-executable'}
Terminal={self.app_type == AppType.CLI}
Categories={';'.join(self.categories)};
"""


class AIosApp(ABC):
    """Base class for AI-OS applications"""
    
    def __init__(self, app_info: AppInfo):
        self.info = app_info
        self._agent_socket: Optional[socket.socket] = None
    
    @abstractmethod
    def run(self, args: List[str]) -> int:
        """Main application entry point"""
        pass
    
    def send_to_agent(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message to AI agent daemon"""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect('/run/aios/agent.sock')
                
                data = json.dumps(message).encode()
                sock.sendall(struct.pack('!I', len(data)))
                sock.sendall(data)
                
                length_data = sock.recv(4)
                if not length_data:
                    return {'error': 'No response'}
                
                length = struct.unpack('!I', length_data)[0]
                response_data = sock.recv(length)
                
                return json.loads(response_data.decode())
        except Exception as e:
            return {'error': str(e)}
    
    def chat(self, message: str) -> str:
        """Chat with AI agent"""
        result = self.send_to_agent({'cmd': 'chat', 'text': message})
        return result.get('response', result.get('error', 'No response'))
    
    def execute_action(self, action: str, **params) -> Dict[str, Any]:
        """Execute a system action"""
        return self.send_to_agent({
            'cmd': 'action',
            'action': {'action': action, **params}
        })
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        result = self.send_to_agent({'cmd': 'status'})
        return result.get('system', {})
    
    def notify(self, title: str, message: str, urgency: str = 'normal'):
        """Show a notification"""
        os.system(f'notify-send -u {urgency} "{title}" "{message}"')
    
    def request_permission(self, permission: str) -> bool:
        """Request a permission from user"""
        # In a full implementation, this would show a dialog
        if permission in self.info.permissions:
            return True
        return False


class AIosGtkApp(AIosApp):
    """Base class for GTK-based AI-OS applications"""
    
    def __init__(self, app_info: AppInfo):
        super().__init__(app_info)
        self._app = None
        self._window = None
    
    def run(self, args: List[str]) -> int:
        try:
            import gi
            gi.require_version('Gtk', '4.0')
            from gi.repository import Gtk
            
            self._app = Gtk.Application(application_id=f'com.aios.{self.info.name.lower()}')
            self._app.connect('activate', self._on_activate)
            
            return self._app.run(args)
        except ImportError:
            print("GTK not available")
            return 1
    
    def _on_activate(self, app):
        """Called when app is activated"""
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        
        self._window = Gtk.ApplicationWindow(application=app, title=self.info.name)
        self._window.set_default_size(800, 600)
        
        content = self.build_ui()
        if content:
            self._window.set_child(content)
        
        self._window.present()
    
    @abstractmethod
    def build_ui(self):
        """Build the application UI. Override this method."""
        pass


# ============ Example Apps ============

class SettingsApp(AIosGtkApp):
    """AI-OS Settings Application"""
    
    def __init__(self):
        super().__init__(AppInfo(
            name="Settings",
            version="1.0.0",
            description="AI-OS System Settings",
            categories=["System", "Settings"],
            permissions=["system.settings"]
        ))
    
    def build_ui(self):
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(20)
        box.set_margin_end(20)
        
        # Title
        title = Gtk.Label(label="AI-OS Settings")
        title.add_css_class('title-1')
        box.append(title)
        
        # Brightness
        bright_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bright_label = Gtk.Label(label="Brightness:")
        bright_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        bright_scale.set_value(50)
        bright_scale.set_hexpand(True)
        bright_scale.connect('value-changed', lambda s: self.execute_action('brightness', level=int(s.get_value())))
        bright_box.append(bright_label)
        bright_box.append(bright_scale)
        box.append(bright_box)
        
        # Volume
        vol_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        vol_label = Gtk.Label(label="Volume:")
        vol_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 0, 100, 5)
        vol_scale.set_value(50)
        vol_scale.set_hexpand(True)
        vol_scale.connect('value-changed', lambda s: self.execute_action('volume', level=int(s.get_value())))
        vol_box.append(vol_label)
        vol_box.append(vol_scale)
        box.append(vol_box)
        
        # WiFi toggle
        wifi_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        wifi_label = Gtk.Label(label="WiFi:")
        wifi_switch = Gtk.Switch()
        wifi_switch.set_active(True)
        wifi_switch.connect('notify::active', lambda s, p: self.execute_action('wifi', enabled=s.get_active()))
        wifi_box.append(wifi_label)
        wifi_box.append(wifi_switch)
        box.append(wifi_box)
        
        # Bluetooth toggle
        bt_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        bt_label = Gtk.Label(label="Bluetooth:")
        bt_switch = Gtk.Switch()
        bt_switch.connect('notify::active', lambda s, p: self.execute_action('bluetooth', enabled=s.get_active()))
        bt_box.append(bt_label)
        bt_box.append(bt_switch)
        box.append(bt_box)
        
        # System info
        info = self.get_system_info()
        if info:
            info_label = Gtk.Label(label=f"System: {info.get('hostname', 'Unknown')} - {info.get('kernel', 'Unknown')}")
            box.append(info_label)
        
        return box


class FileManagerApp(AIosGtkApp):
    """Simple File Manager Application"""
    
    def __init__(self):
        super().__init__(AppInfo(
            name="Files",
            version="1.0.0",
            description="AI-OS File Manager",
            categories=["System", "FileManager"],
            permissions=["filesystem.read", "filesystem.write"]
        ))
        self.current_path = Path.home()
    
    def build_ui(self):
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk, Gio
        
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        
        # Path bar
        self.path_entry = Gtk.Entry()
        self.path_entry.set_text(str(self.current_path))
        self.path_entry.connect('activate', self._on_path_activate)
        main_box.append(self.path_entry)
        
        # File list
        scroll = Gtk.ScrolledWindow()
        scroll.set_vexpand(True)
        
        self.list_box = Gtk.ListBox()
        self.list_box.connect('row-activated', self._on_row_activated)
        scroll.set_child(self.list_box)
        
        main_box.append(scroll)
        
        # Populate
        self._populate_files()
        
        return main_box
    
    def _populate_files(self):
        import gi
        gi.require_version('Gtk', '4.0')
        from gi.repository import Gtk
        
        # Clear existing
        while True:
            row = self.list_box.get_row_at_index(0)
            if row is None:
                break
            self.list_box.remove(row)
        
        try:
            # Add parent directory
            if self.current_path != Path('/'):
                row = Gtk.Label(label="📁 ..")
                row.set_halign(Gtk.Align.START)
                row.path = self.current_path.parent
                self.list_box.append(row)
            
            # List contents
            items = sorted(self.current_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))
            
            for item in items:
                if item.name.startswith('.'):
                    continue
                
                icon = "📁" if item.is_dir() else "📄"
                row = Gtk.Label(label=f"{icon} {item.name}")
                row.set_halign(Gtk.Align.START)
                row.path = item
                self.list_box.append(row)
                
        except PermissionError:
            row = Gtk.Label(label="⚠️ Permission denied")
            self.list_box.append(row)
    
    def _on_path_activate(self, entry):
        path = Path(entry.get_text())
        if path.is_dir():
            self.current_path = path
            self._populate_files()
    
    def _on_row_activated(self, list_box, row):
        child = row.get_child()
        if hasattr(child, 'path'):
            path = child.path
            if path.is_dir():
                self.current_path = path
                self.path_entry.set_text(str(path))
                self._populate_files()
            else:
                # Open file
                os.system(f'xdg-open "{path}" &')


# Application registry
APP_REGISTRY = {
    'settings': SettingsApp,
    'files': FileManagerApp,
}


def main():
    """Main entry point for aios-app command"""
    if len(sys.argv) < 2:
        print("Usage: aios-app <app-name> [args...]")
        print("Available apps:", ', '.join(APP_REGISTRY.keys()))
        return 1
    
    app_name = sys.argv[1].lower()
    
    if app_name not in APP_REGISTRY:
        print(f"Unknown app: {app_name}")
        print("Available apps:", ', '.join(APP_REGISTRY.keys()))
        return 1
    
    app_class = APP_REGISTRY[app_name]
    app = app_class()
    return app.run(sys.argv[2:])


if __name__ == '__main__':
    sys.exit(main())
