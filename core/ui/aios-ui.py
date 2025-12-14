#!/usr/bin/env python3
"""
AI-OS Wayland UI Compositor
Custom Wayland-based user interface for AI-OS.
Uses wlroots for Wayland compositor functionality.
"""

import os
import sys
import signal
import asyncio
import logging
import json
import socket
import struct
import subprocess
from pathlib import Path
from dataclasses import dataclass
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime

# Use PyWLRoots/pywayland if available, otherwise fall back to weston
try:
    HAS_WLROOTS = True
    from pywayland.server import Display
    from pywlroots.wlroots import wlr_compositor, wlr_backend, wlr_output_layout
except ImportError:
    HAS_WLROOTS = False

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/aios/ui.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('aios-ui')


@dataclass
class UIConfig:
    """UI configuration"""
    theme: str = "dark"
    font_family: str = "Inter"
    font_size: int = 14
    accent_color: str = "#667eea"
    background_color: str = "#1a1a2e"
    agent_socket: str = "/run/aios/agent.sock"
    show_clock: bool = True
    clock_format: str = "%H:%M"
    wallpaper: Optional[str] = None
    
    @classmethod
    def load(cls, path: str = "/etc/aios/ui.conf") -> 'UIConfig':
        config = cls()
        if os.path.exists(path):
            try:
                with open(path) as f:
                    data = json.load(f)
                    for key, value in data.items():
                        if hasattr(config, key):
                            setattr(config, key, value)
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
        return config


class AgentClient:
    """Client for AI-OS Agent daemon"""
    
    def __init__(self, socket_path: str):
        self.socket_path = socket_path
    
    def send(self, request: dict) -> dict:
        """Send request to agent"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect(self.socket_path)
            
            data = json.dumps(request).encode('utf-8')
            sock.sendall(struct.pack('!I', len(data)))
            sock.sendall(data)
            
            length_data = sock.recv(4)
            length = struct.unpack('!I', length_data)[0]
            response_data = sock.recv(length)
            
            sock.close()
            return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            logger.error(f"Agent error: {e}")
            return {'status': 'error', 'message': str(e)}
    
    def chat(self, text: str) -> dict:
        return self.send({'cmd': 'chat', 'text': text})
    
    def status(self) -> dict:
        return self.send({'cmd': 'status'})
    
    def action(self, action: dict) -> dict:
        return self.send({'cmd': 'action', 'action': action})


class GTKFallbackUI:
    """
    GTK-based fallback UI when wlroots is not available.
    This provides a simple but functional UI.
    """
    
    def __init__(self, config: UIConfig):
        self.config = config
        self.agent = AgentClient(config.agent_socket)
        
    def run(self):
        """Run the GTK UI"""
        try:
            import gi
            gi.require_version('Gtk', '4.0')
            gi.require_version('Adw', '1')
            from gi.repository import Gtk, Adw, Gdk, GLib, Pango
            
            class AIosWindow(Adw.ApplicationWindow):
                def __init__(self, app, config, agent):
                    super().__init__(application=app)
                    self.config = config
                    self.agent = agent
                    self._setup_ui()
                    
                def _setup_ui(self):
                    self.set_title("AI-OS")
                    self.set_default_size(1024, 768)
                    self.fullscreen()
                    
                    # Main container
                    main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
                    self.set_content(main_box)
                    
                    # Apply dark theme
                    css = b"""
                    window {
                        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%);
                    }
                    .clock {
                        font-size: 72px;
                        font-weight: 300;
                        color: white;
                    }
                    .date {
                        font-size: 18px;
                        color: rgba(255,255,255,0.7);
                    }
                    .agent-button {
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 50px;
                        padding: 24px 48px;
                        color: white;
                        font-size: 18px;
                        font-weight: 600;
                    }
                    .agent-entry {
                        background: rgba(255,255,255,0.1);
                        border-radius: 25px;
                        padding: 16px 24px;
                        color: white;
                        font-size: 16px;
                        border: 2px solid transparent;
                    }
                    .agent-entry:focus {
                        border-color: #667eea;
                    }
                    .response-text {
                        color: white;
                        font-size: 16px;
                        padding: 20px;
                    }
                    """
                    
                    css_provider = Gtk.CssProvider()
                    css_provider.load_from_data(css)
                    Gtk.StyleContext.add_provider_for_display(
                        Gdk.Display.get_default(),
                        css_provider,
                        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
                    )
                    
                    # Spacer
                    main_box.append(Gtk.Box(vexpand=True))
                    
                    # Clock
                    self.clock_label = Gtk.Label()
                    self.clock_label.add_css_class('clock')
                    main_box.append(self.clock_label)
                    
                    # Date
                    self.date_label = Gtk.Label()
                    self.date_label.add_css_class('date')
                    main_box.append(self.date_label)
                    
                    main_box.append(Gtk.Box(vexpand=True))
                    
                    # Agent input area
                    input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
                    input_box.set_halign(Gtk.Align.CENTER)
                    input_box.set_margin_bottom(100)
                    
                    self.entry = Gtk.Entry()
                    self.entry.set_placeholder_text("Ask AI-OS anything...")
                    self.entry.add_css_class('agent-entry')
                    self.entry.set_size_request(400, -1)
                    self.entry.connect('activate', self._on_submit)
                    input_box.append(self.entry)
                    
                    submit_btn = Gtk.Button(label="Ask AI")
                    submit_btn.add_css_class('agent-button')
                    submit_btn.connect('clicked', self._on_submit)
                    input_box.append(submit_btn)
                    
                    main_box.append(input_box)
                    
                    # Response area
                    self.response_label = Gtk.Label()
                    self.response_label.add_css_class('response-text')
                    self.response_label.set_wrap(True)
                    self.response_label.set_max_width_chars(60)
                    self.response_label.set_margin_bottom(50)
                    main_box.append(self.response_label)
                    
                    # Update clock every second
                    GLib.timeout_add_seconds(1, self._update_clock)
                    self._update_clock()
                
                def _update_clock(self):
                    now = datetime.now()
                    self.clock_label.set_text(now.strftime(self.config.clock_format))
                    self.date_label.set_text(now.strftime("%A, %B %d"))
                    return True
                
                def _on_submit(self, widget):
                    text = self.entry.get_text().strip()
                    if text:
                        self.entry.set_text("")
                        self.response_label.set_text("Processing...")
                        
                        # Process in background
                        import threading
                        def process():
                            response = self.agent.chat(text)
                            from gi.repository import GLib
                            GLib.idle_add(self._show_response, response)
                        
                        thread = threading.Thread(target=process)
                        thread.start()
                
                def _show_response(self, response):
                    if response.get('status') == 'ok':
                        text = response.get('response', '')
                        # Clean up JSON blocks
                        import re
                        clean_text = re.sub(r'```json\s*\{[^`]+\}\s*```', '[Action executed]', text)
                        self.response_label.set_text(clean_text)
                    else:
                        self.response_label.set_text(f"Error: {response.get('message')}")
                    return False
            
            class AIosApp(Adw.Application):
                def __init__(self, config, agent):
                    super().__init__(application_id='com.aios.ui')
                    self.config = config
                    self.agent = agent
                
                def do_activate(self):
                    win = AIosWindow(self, self.config, self.agent)
                    win.present()
            
            app = AIosApp(self.config, self.agent)
            app.run(None)
            
        except Exception as e:
            logger.error(f"GTK UI failed: {e}")
            self._run_terminal_ui()
    
    def _run_terminal_ui(self):
        """Fallback terminal UI"""
        logger.info("Running terminal UI fallback")
        
        print("\n" + "=" * 60)
        print("  AI-OS - Terminal Interface")
        print("=" * 60)
        print("\nType 'help' for commands, 'exit' to quit.\n")
        
        while True:
            try:
                user_input = input("AI-OS> ").strip()
                
                if user_input.lower() == 'exit':
                    break
                elif user_input.lower() == 'help':
                    print("Commands: help, status, exit")
                    print("Or just type a question for the AI assistant.")
                elif user_input.lower() == 'status':
                    status = self.agent.status()
                    print(json.dumps(status, indent=2))
                elif user_input:
                    response = self.agent.chat(user_input)
                    if response.get('status') == 'ok':
                        print(f"\nAI: {response.get('response', '')}\n")
                    else:
                        print(f"\nError: {response.get('message')}\n")
                        
            except EOFError:
                break
            except KeyboardInterrupt:
                break


class WestonLauncher:
    """
    Launch Weston compositor with AI-OS shell.
    """
    
    def __init__(self, config: UIConfig):
        self.config = config
        
    def run(self):
        """Start Weston with AI-OS configuration"""
        # Create weston.ini for AI-OS
        weston_config = f"""
[core]
shell=desktop-shell.so
backend=drm-backend.so
modules=systemd-notify.so

[shell]
background-color=0x{self.config.background_color[1:]}
background-type=solid
panel-position=none
locking=false

[libinput]
enable-tap=true
natural-scroll=true

[output]
name=*
mode=current
transform=normal

[keyboard]
keymap_layout=us

[launcher]
icon=/usr/share/aios/icons/terminal.png
path=/usr/lib/aios/ui/aios-terminal
"""
        
        # Write config
        config_dir = os.path.expanduser("~/.config/weston")
        os.makedirs(config_dir, exist_ok=True)
        
        with open(os.path.join(config_dir, "weston.ini"), "w") as f:
            f.write(weston_config)
        
        # Set environment
        os.environ['XDG_SESSION_TYPE'] = 'wayland'
        os.environ['XDG_RUNTIME_DIR'] = '/run/user/0'
        
        # Start weston
        logger.info("Starting Weston compositor...")
        subprocess.run(['weston', '--tty=1'], check=True)


def main():
    """Main entry point"""
    config = UIConfig.load()
    
    # Signal handlers
    def signal_handler(sig, frame):
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # Try different UI backends
    if os.environ.get('AIOS_UI_MODE') == 'terminal':
        ui = GTKFallbackUI(config)
        ui._run_terminal_ui()
    elif HAS_WLROOTS:
        logger.info("Using wlroots compositor")
        # Direct wlroots implementation would go here
        ui = GTKFallbackUI(config)
        ui.run()
    elif os.path.exists('/usr/bin/weston'):
        logger.info("Using Weston compositor")
        launcher = WestonLauncher(config)
        launcher.run()
    else:
        logger.info("Using GTK fallback UI")
        ui = GTKFallbackUI(config)
        ui.run()


if __name__ == '__main__':
    main()
