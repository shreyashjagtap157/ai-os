#!/usr/bin/env python3
"""
AI-OS Display Compositor & Shell
Wayland-based compositor with integrated AI interface.
"""

import os
import sys
import signal
import logging
import subprocess
import threading
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='[%(levelname)s] %(message)s')
logger = logging.getLogger('aios-compositor')


class AIosCompositor:
    """Wayland compositor for AI-OS"""
    
    def __init__(self):
        self.weston_process = None
        self.shell_process = None
        
    def start(self):
        """Start the compositor"""
        logger.info("Starting AI-OS Compositor...")
        
        # Set environment
        os.environ['XDG_RUNTIME_DIR'] = os.environ.get('XDG_RUNTIME_DIR', '/run/user/0')
        
        # Ensure runtime directory
        runtime_dir = Path(os.environ['XDG_RUNTIME_DIR'])
        runtime_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(runtime_dir, 0o700)
        
        # Create Weston config
        self._create_config()
        
        # Determine backend
        backend = self._detect_backend()
        
        # Start Weston
        self._start_weston(backend)
        
        # Wait for Weston to initialize
        import time
        time.sleep(1)
        
        # Start AI-OS Shell
        self._start_shell()
        
    def _detect_backend(self) -> str:
        """Detect appropriate backend"""
        # Check for DRM
        if Path('/dev/dri').exists():
            return 'drm'
        # Check for framebuffer
        elif Path('/dev/fb0').exists():
            return 'fbdev'
        # Fallback to headless/pixman
        else:
            return 'headless'
    
    def _create_config(self):
        """Create Weston configuration"""
        config_path = Path('/etc/aios/weston.ini')
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        config = """
[core]
idle-time=0
require-input=false

[shell]
background-color=0xff1a1a2e
panel-position=top
clock-format=24h
locking=false

[output]
name=*
mode=preferred
transform=normal

[terminal]
font=monospace
font-size=14

[keyboard]
numlock-on=true

[input-method]
path=/usr/libexec/weston-keyboard
"""
        config_path.write_text(config)
        logger.info("Created Weston configuration")
    
    def _start_weston(self, backend: str):
        """Start Weston compositor"""
        cmd = [
            'weston',
            f'--backend={backend}-backend.so',
            '--log=/var/log/aios/weston.log',
            '--config=/etc/aios/weston.ini'
        ]
        
        # Add DRM-specific options
        if backend == 'drm':
            cmd.extend(['--current-mode', '--use-pixman'])
        
        logger.info(f"Starting Weston with backend: {backend}")
        
        try:
            self.weston_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            logger.info(f"Weston started with PID {self.weston_process.pid}")
        except Exception as e:
            logger.error(f"Failed to start Weston: {e}")
            raise
    
    def _start_shell(self):
        """Start AI-OS shell UI"""
        # Set Wayland display
        os.environ['WAYLAND_DISPLAY'] = 'wayland-0'
        
        shell_script = """#!/bin/bash
# AI-OS Shell Launcher

# Wait for display
sleep 2

# Try GTK-based shell first
if command -v python3 &> /dev/null; then
    exec python3 /usr/lib/aios/ui/shell.py
fi

# Fallback to terminal
exec weston-terminal --login
"""
        
        shell_path = Path('/tmp/aios-shell.sh')
        shell_path.write_text(shell_script)
        os.chmod(shell_path, 0o755)
        
        try:
            self.shell_process = subprocess.Popen(
                [shell_path],
                env=os.environ.copy()
            )
            logger.info("AI-OS Shell started")
        except Exception as e:
            logger.error(f"Failed to start shell: {e}")
    
    def stop(self):
        """Stop compositor"""
        if self.shell_process:
            self.shell_process.terminate()
        if self.weston_process:
            self.weston_process.terminate()
        logger.info("Compositor stopped")
    
    def wait(self):
        """Wait for compositor to exit"""
        if self.weston_process:
            self.weston_process.wait()


def main():
    compositor = AIosCompositor()
    
    def signal_handler(sig, frame):
        compositor.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    compositor.start()
    compositor.wait()


if __name__ == '__main__':
    main()
