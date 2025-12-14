#!/usr/bin/env python3
"""
AI-OS Shell Interface
GTK-based graphical shell for AI-OS.
"""

import os
import sys
import json
import socket
import struct
import threading
from datetime import datetime

# Try GTK first
try:
    import gi
    gi.require_version('Gtk', '4.0')
    from gi.repository import Gtk, Gdk, GLib, Pango
    HAS_GTK = True
except ImportError:
    HAS_GTK = False


class AgentClient:
    """Client for communicating with AI Agent daemon"""
    
    SOCKET_PATH = "/run/aios/agent.sock"
    
    def send(self, message: dict) -> dict:
        """Send message to agent and get response"""
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.SOCKET_PATH)
                
                # Send message
                data = json.dumps(message).encode('utf-8')
                sock.sendall(struct.pack('!I', len(data)))
                sock.sendall(data)
                
                # Read response
                length_data = sock.recv(4)
                if not length_data:
                    return {'error': 'No response'}
                
                length = struct.unpack('!I', length_data)[0]
                response_data = sock.recv(length)
                
                return json.loads(response_data.decode('utf-8'))
        except Exception as e:
            return {'error': str(e)}
    
    def chat(self, text: str) -> dict:
        return self.send({'cmd': 'chat', 'text': text})
    
    def status(self) -> dict:
        return self.send({'cmd': 'status'})


if HAS_GTK:
    
    class AIosShell(Gtk.Application):
        """Main AI-OS Shell application"""
        
        def __init__(self):
            super().__init__(application_id='com.aios.shell')
            self.agent = AgentClient()
            self.window = None
            
        def do_activate(self):
            if not self.window:
                self.window = ShellWindow(self)
            self.window.present()
    
    
    class ShellWindow(Gtk.ApplicationWindow):
        """Main shell window"""
        
        def __init__(self, app):
            super().__init__(application=app, title="AI-OS")
            self.agent = app.agent
            
            # Make fullscreen
            self.set_decorated(False)
            self.fullscreen()
            
            # Set dark theme
            self.apply_theme()
            
            # Build UI
            self.build_ui()
            
            # Start clock update
            GLib.timeout_add_seconds(1, self.update_clock)
        
        def apply_theme(self):
            """Apply AI-OS theme"""
            css_provider = Gtk.CssProvider()
            css_provider.load_from_data(b"""
                window {
                    background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
                }
                .time-label {
                    font-size: 72px;
                    font-weight: 300;
                    color: white;
                }
                .date-label {
                    font-size: 24px;
                    color: rgba(255, 255, 255, 0.7);
                }
                .agent-input {
                    font-size: 18px;
                    padding: 16px 24px;
                    border-radius: 30px;
                    background: rgba(255, 255, 255, 0.1);
                    border: none;
                    color: white;
                    caret-color: #667eea;
                }
                .agent-input:focus {
                    outline: none;
                    background: rgba(255, 255, 255, 0.15);
                }
                .response-label {
                    font-size: 16px;
                    color: rgba(255, 255, 255, 0.8);
                    padding: 20px;
                }
                .status-bar {
                    background: rgba(0, 0, 0, 0.3);
                    padding: 8px 16px;
                }
                .status-text {
                    font-size: 14px;
                    color: white;
                }
            """)
            
            Gtk.StyleContext.add_provider_for_display(
                Gdk.Display.get_default(),
                css_provider,
                Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
            )
        
        def build_ui(self):
            """Build the UI"""
            # Main container
            main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            self.set_child(main_box)
            
            # Status bar
            status_bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            status_bar.add_css_class('status-bar')
            
            self.status_label = Gtk.Label(label="AI-OS")
            self.status_label.add_css_class('status-text')
            status_bar.append(self.status_label)
            
            status_bar_spacer = Gtk.Box()
            status_bar_spacer.set_hexpand(True)
            status_bar.append(status_bar_spacer)
            
            self.clock_mini = Gtk.Label()
            self.clock_mini.add_css_class('status-text')
            status_bar.append(self.clock_mini)
            
            main_box.append(status_bar)
            
            # Center content
            center_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
            center_box.set_valign(Gtk.Align.CENTER)
            center_box.set_halign(Gtk.Align.CENTER)
            center_box.set_vexpand(True)
            center_box.set_spacing(20)
            
            # Time display
            self.time_label = Gtk.Label()
            self.time_label.add_css_class('time-label')
            center_box.append(self.time_label)
            
            # Date display
            self.date_label = Gtk.Label()
            self.date_label.add_css_class('date-label')
            center_box.append(self.date_label)
            
            # Spacer
            spacer = Gtk.Box()
            spacer.set_size_request(-1, 50)
            center_box.append(spacer)
            
            # Agent input
            input_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
            input_box.set_halign(Gtk.Align.CENTER)
            input_box.set_size_request(500, -1)
            
            self.input_entry = Gtk.Entry()
            self.input_entry.set_placeholder_text("Ask AI-OS anything...")
            self.input_entry.add_css_class('agent-input')
            self.input_entry.set_hexpand(True)
            self.input_entry.connect('activate', self.on_input_activate)
            input_box.append(self.input_entry)
            
            center_box.append(input_box)
            
            # Response area
            self.response_label = Gtk.Label()
            self.response_label.add_css_class('response-label')
            self.response_label.set_wrap(True)
            self.response_label.set_max_width_chars(60)
            center_box.append(self.response_label)
            
            main_box.append(center_box)
            
            # Update clock immediately
            self.update_clock()
        
        def update_clock(self):
            """Update clock display"""
            now = datetime.now()
            self.time_label.set_text(now.strftime("%H:%M"))
            self.date_label.set_text(now.strftime("%A, %B %d, %Y"))
            self.clock_mini.set_text(now.strftime("%H:%M:%S"))
            return True
        
        def on_input_activate(self, entry):
            """Handle input entry"""
            text = entry.get_text().strip()
            if not text:
                return
            
            entry.set_text("")
            self.response_label.set_text("Processing...")
            
            # Process in background
            def process():
                response = self.agent.chat(text)
                
                if 'error' in response:
                    result = f"Error: {response['error']}"
                else:
                    result = response.get('response', 'No response')
                    
                    # Show action result if any
                    action_result = response.get('action_result')
                    if action_result:
                        if action_result.get('success'):
                            result += f"\n✓ {action_result.get('message', 'Action completed')}"
                        else:
                            result += f"\n✗ {action_result.get('message', 'Action failed')}"
                
                GLib.idle_add(self.response_label.set_text, result)
            
            thread = threading.Thread(target=process)
            thread.daemon = True
            thread.start()


def run_gtk_shell():
    """Run GTK-based shell"""
    app = AIosShell()
    app.run([])


def run_terminal_shell():
    """Run terminal-based shell"""
    print("=" * 50)
    print("     AI-OS Interactive Shell")
    print("=" * 50)
    print("Type 'help' for commands, 'exit' to quit.")
    print()
    
    agent = AgentClient()
    
    while True:
        try:
            user_input = input("AI-OS> ").strip()
            
            if not user_input:
                continue
            
            if user_input.lower() == 'exit':
                print("Goodbye!")
                break
            
            if user_input.lower() == 'help':
                print("""
Available Commands:
  <any text>    - Chat with AI agent
  status        - Show system status  
  clear         - Clear screen
  exit          - Exit shell
  
Examples:
  turn up brightness
  what's the battery level?
  open firefox
  set volume to 50%
""")
                continue
            
            if user_input.lower() == 'clear':
                os.system('clear' if os.name != 'nt' else 'cls')
                continue
            
            if user_input.lower() == 'status':
                response = agent.status()
                if 'error' in response:
                    print(f"Error: {response['error']}")
                else:
                    print(f"Running: {response.get('running')}")
                    print(f"AI Configured: {response.get('ai_configured')}")
                    system = response.get('system', {})
                    print(f"Hostname: {system.get('hostname')}")
                    print(f"Kernel: {system.get('kernel')}")
                    print(f"CPU: {system.get('cpu', 'Unknown')}")
                    print(f"Memory: {system.get('memory_free_mb', 0)}/{system.get('memory_mb', 0)} MB")
                continue
            
            # Send to agent
            response = agent.chat(user_input)
            
            if 'error' in response:
                print(f"Error: {response['error']}")
            else:
                print(f"\n{response.get('response', 'No response')}")
                
                action_result = response.get('action_result')
                if action_result:
                    if action_result.get('success'):
                        print(f"✓ {action_result.get('message', 'Action completed')}")
                    else:
                        print(f"✗ {action_result.get('message', 'Action failed')}")
                    
                    # Show info data if present
                    data = action_result.get('data')
                    if data:
                        for key, value in data.items():
                            print(f"  {key}: {value}")
            
            print()
            
        except KeyboardInterrupt:
            print("\nUse 'exit' to quit.")
        except EOFError:
            break


def main():
    """Main entry point"""
    # Check for display
    if os.environ.get('WAYLAND_DISPLAY') or os.environ.get('DISPLAY'):
        if HAS_GTK:
            run_gtk_shell()
        else:
            print("GTK not available, falling back to terminal")
            run_terminal_shell()
    else:
        run_terminal_shell()


if __name__ == '__main__':
    main()
