# AI-OS System Library (libaios)
# Python bindings for AI-OS system functionality

"""
libaios - AI-OS System Library
Provides unified access to AI-OS functionality.
"""

import os
import json
import socket
import struct
from pathlib import Path
from typing import Dict, Any, Optional, List


__version__ = "1.0.0"


class AgentConnection:
    """Connection to AI agent daemon"""
    
    SOCKET_PATH = "/run/aios/agent.sock"
    
    def __init__(self):
        self._socket = None
    
    def connect(self):
        """Connect to agent"""
        self._socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._socket.connect(self.SOCKET_PATH)
    
    def disconnect(self):
        """Disconnect from agent"""
        if self._socket:
            self._socket.close()
            self._socket = None
    
    def send(self, message: Dict[str, Any]) -> Dict[str, Any]:
        """Send message and get response"""
        if not self._socket:
            self.connect()
        
        data = json.dumps(message).encode()
        self._socket.sendall(struct.pack('!I', len(data)))
        self._socket.sendall(data)
        
        length_data = self._socket.recv(4)
        length = struct.unpack('!I', length_data)[0]
        
        response_data = b''
        while len(response_data) < length:
            chunk = self._socket.recv(min(4096, length - len(response_data)))
            if not chunk:
                break
            response_data += chunk
        
        return json.loads(response_data.decode())
    
    def __enter__(self):
        self.connect()
        return self
    
    def __exit__(self, *args):
        self.disconnect()


def chat(message: str) -> str:
    """Send message to AI agent and get response"""
    with AgentConnection() as agent:
        result = agent.send({'cmd': 'chat', 'text': message})
        return result.get('response', '')


def execute_action(action: str, **params) -> Dict[str, Any]:
    """Execute a system action"""
    with AgentConnection() as agent:
        return agent.send({
            'cmd': 'action',
            'action': {'action': action, **params}
        })


def get_status() -> Dict[str, Any]:
    """Get system status"""
    with AgentConnection() as agent:
        return agent.send({'cmd': 'status'})


# Hardware control shortcuts
def set_brightness(level: int) -> bool:
    """Set screen brightness (0-100)"""
    result = execute_action('brightness', level=level)
    return result.get('result', {}).get('success', False)


def get_brightness() -> int:
    """Get current brightness"""
    for device in Path("/sys/class/backlight").iterdir():
        try:
            current = int((device / "brightness").read_text().strip())
            max_val = int((device / "max_brightness").read_text().strip())
            return int(current * 100 / max_val)
        except:
            pass
    return -1


def set_volume(level: int) -> bool:
    """Set volume (0-100)"""
    result = execute_action('volume', level=level)
    return result.get('result', {}).get('success', False)


def get_battery() -> Optional[Dict[str, Any]]:
    """Get battery status"""
    for bat in Path("/sys/class/power_supply").glob("BAT*"):
        try:
            return {
                'level': int((bat / "capacity").read_text().strip()),
                'status': (bat / "status").read_text().strip()
            }
        except:
            pass
    return None


# Notification helper
def notify(summary: str, body: str = "", urgency: str = "normal") -> int:
    """Send a notification"""
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect("/run/aios/notify.sock")
        
        msg = json.dumps({
            'cmd': 'notify',
            'summary': summary,
            'body': body,
            'urgency': urgency
        }).encode()
        
        sock.sendall(struct.pack('!I', len(msg)))
        sock.sendall(msg)
        
        length = struct.unpack('!I', sock.recv(4))[0]
        response = json.loads(sock.recv(length).decode())
        sock.close()
        
        return response.get('id', 0)
    except:
        # Fallback to notify-send
        os.system(f'notify-send -u {urgency} "{summary}" "{body}"')
        return 0


# Config helpers
def get_config(name: str) -> Dict[str, Any]:
    """Load configuration file"""
    path = Path(f"/etc/aios/{name}.json")
    if path.exists():
        return json.loads(path.read_text())
    return {}


def set_config(name: str, data: Dict[str, Any]):
    """Save configuration file"""
    path = Path(f"/etc/aios/{name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
