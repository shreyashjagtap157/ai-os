#!/usr/bin/env python3
"""
AI-OS Notification Daemon
System notification service with action support.
"""

import os
import sys
import json
import asyncio
import socket
import struct
import signal
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Callable
from datetime import datetime
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aios-notify')


class Urgency(Enum):
    LOW = 0
    NORMAL = 1
    CRITICAL = 2


@dataclass
class Notification:
    """Notification data"""
    id: int
    app_name: str
    summary: str
    body: str = ""
    icon: str = ""
    urgency: Urgency = Urgency.NORMAL
    timeout: int = 5000  # milliseconds, -1 for persistent
    actions: List[Dict[str, str]] = field(default_factory=list)
    hints: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    read: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'app_name': self.app_name,
            'summary': self.summary,
            'body': self.body,
            'icon': self.icon,
            'urgency': self.urgency.name,
            'timeout': self.timeout,
            'actions': self.actions,
            'timestamp': self.timestamp.isoformat(),
            'read': self.read
        }


class NotificationDaemon:
    """Main notification daemon"""
    
    SOCKET_PATH = "/run/aios/notify.sock"
    HISTORY_PATH = "/var/lib/aios/notifications.json"
    MAX_HISTORY = 100
    
    def __init__(self):
        self.notifications: Dict[int, Notification] = {}
        self.history: List[Dict[str, Any]] = []
        self.next_id = 1
        self.running = False
        self._callbacks: List[Callable[[Notification], None]] = []
        
        self._load_history()
    
    def _load_history(self):
        """Load notification history"""
        try:
            path = Path(self.HISTORY_PATH)
            if path.exists():
                with open(path) as f:
                    self.history = json.load(f)
                # Get next ID
                if self.history:
                    self.next_id = max(n.get('id', 0) for n in self.history) + 1
        except Exception as e:
            logger.warning(f"Failed to load history: {e}")
    
    def _save_history(self):
        """Save notification history"""
        try:
            path = Path(self.HISTORY_PATH)
            path.parent.mkdir(parents=True, exist_ok=True)
            with open(path, 'w') as f:
                json.dump(self.history[-self.MAX_HISTORY:], f)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
    
    def notify(
        self,
        app_name: str,
        summary: str,
        body: str = "",
        icon: str = "",
        urgency: Urgency = Urgency.NORMAL,
        timeout: int = 5000,
        actions: List[Dict[str, str]] = None,
        hints: Dict[str, Any] = None,
        replace_id: int = 0
    ) -> int:
        """Create a new notification"""
        
        # Use existing ID if replacing
        if replace_id and replace_id in self.notifications:
            notif_id = replace_id
        else:
            notif_id = self.next_id
            self.next_id += 1
        
        notification = Notification(
            id=notif_id,
            app_name=app_name,
            summary=summary,
            body=body,
            icon=icon,
            urgency=urgency,
            timeout=timeout,
            actions=actions or [],
            hints=hints or {}
        )
        
        self.notifications[notif_id] = notification
        self.history.append(notification.to_dict())
        self._save_history()
        
        # Display notification
        self._display_notification(notification)
        
        # Call callbacks
        for callback in self._callbacks:
            try:
                callback(notification)
            except Exception as e:
                logger.error(f"Notification callback error: {e}")
        
        logger.info(f"Notification {notif_id}: {summary}")
        return notif_id
    
    def _display_notification(self, notification: Notification):
        """Display notification to user"""
        # Try to use native notification display
        try:
            # Construct notify-send command
            cmd = ['notify-send']
            
            if notification.icon:
                cmd.extend(['-i', notification.icon])
            
            if notification.urgency == Urgency.LOW:
                cmd.extend(['-u', 'low'])
            elif notification.urgency == Urgency.CRITICAL:
                cmd.extend(['-u', 'critical'])
            
            if notification.timeout > 0:
                cmd.extend(['-t', str(notification.timeout)])
            
            cmd.append(notification.summary)
            if notification.body:
                cmd.append(notification.body)
            
            os.spawnvp(os.P_NOWAIT, 'notify-send', cmd)
            
        except Exception as e:
            logger.debug(f"notify-send failed: {e}")
            # Fallback: print to console
            print(f"\n📢 [{notification.app_name}] {notification.summary}")
            if notification.body:
                print(f"   {notification.body}")
    
    def close_notification(self, notif_id: int) -> bool:
        """Close a notification"""
        if notif_id in self.notifications:
            del self.notifications[notif_id]
            return True
        return False
    
    def invoke_action(self, notif_id: int, action_key: str) -> bool:
        """Invoke a notification action"""
        if notif_id not in self.notifications:
            return False
        
        notification = self.notifications[notif_id]
        
        for action in notification.actions:
            if action.get('key') == action_key:
                callback = action.get('callback')
                if callback:
                    try:
                        # Execute callback
                        os.system(callback)
                        return True
                    except Exception as e:
                        logger.error(f"Action callback failed: {e}")
                break
        
        return False
    
    def get_notifications(self, include_read: bool = False) -> List[Dict[str, Any]]:
        """Get active notifications"""
        result = []
        for notif in self.notifications.values():
            if include_read or not notif.read:
                result.append(notif.to_dict())
        return result
    
    def get_history(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get notification history"""
        return self.history[-limit:]
    
    def mark_read(self, notif_id: int) -> bool:
        """Mark notification as read"""
        if notif_id in self.notifications:
            self.notifications[notif_id].read = True
            return True
        return False
    
    def mark_all_read(self):
        """Mark all notifications as read"""
        for notif in self.notifications.values():
            notif.read = True
    
    def clear_all(self):
        """Clear all notifications"""
        self.notifications.clear()
    
    def add_callback(self, callback: Callable[[Notification], None]):
        """Add notification callback"""
        self._callbacks.append(callback)
    
    async def start_server(self):
        """Start IPC server"""
        logger.info("Starting notification daemon...")
        
        # Ensure directory
        os.makedirs(os.path.dirname(self.SOCKET_PATH), exist_ok=True)
        
        # Remove old socket
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
        
        self.running = True
        
        server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.SOCKET_PATH
        )
        
        os.chmod(self.SOCKET_PATH, 0o666)
        
        logger.info(f"Listening on {self.SOCKET_PATH}")
        
        async with server:
            await server.serve_forever()
    
    async def _handle_client(self, reader, writer):
        """Handle IPC client"""
        try:
            while True:
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                length = struct.unpack('!I', length_data)[0]
                data = await reader.read(length)
                
                request = json.loads(data.decode())
                response = self._process_request(request)
                
                response_data = json.dumps(response).encode()
                writer.write(struct.pack('!I', len(response_data)))
                writer.write(response_data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process IPC request"""
        cmd = request.get('cmd')
        
        if cmd == 'notify':
            notif_id = self.notify(
                app_name=request.get('app_name', 'AI-OS'),
                summary=request.get('summary', ''),
                body=request.get('body', ''),
                icon=request.get('icon', ''),
                urgency=Urgency[request.get('urgency', 'NORMAL')],
                timeout=request.get('timeout', 5000),
                actions=request.get('actions', []),
                replace_id=request.get('replace_id', 0)
            )
            return {'status': 'ok', 'id': notif_id}
        
        elif cmd == 'close':
            success = self.close_notification(request.get('id', 0))
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'invoke':
            success = self.invoke_action(
                request.get('id', 0),
                request.get('action_key', '')
            )
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'list':
            return {
                'status': 'ok',
                'notifications': self.get_notifications(
                    include_read=request.get('include_read', False)
                )
            }
        
        elif cmd == 'history':
            return {
                'status': 'ok',
                'history': self.get_history(request.get('limit', 50))
            }
        
        elif cmd == 'mark_read':
            self.mark_read(request.get('id', 0))
            return {'status': 'ok'}
        
        elif cmd == 'mark_all_read':
            self.mark_all_read()
            return {'status': 'ok'}
        
        elif cmd == 'clear':
            self.clear_all()
            return {'status': 'ok'}
        
        else:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
    
    def stop(self):
        """Stop the daemon"""
        self.running = False
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)


# Client helper
class NotifyClient:
    """Client for notification daemon"""
    
    SOCKET_PATH = "/run/aios/notify.sock"
    
    def send(self, msg: Dict[str, Any]) -> Dict[str, Any]:
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.connect(self.SOCKET_PATH)
                data = json.dumps(msg).encode()
                sock.sendall(struct.pack('!I', len(data)))
                sock.sendall(data)
                
                length_data = sock.recv(4)
                length = struct.unpack('!I', length_data)[0]
                response = sock.recv(length)
                return json.loads(response.decode())
        except Exception as e:
            return {'error': str(e)}
    
    def notify(self, summary: str, body: str = "", **kwargs) -> int:
        result = self.send({
            'cmd': 'notify',
            'summary': summary,
            'body': body,
            **kwargs
        })
        return result.get('id', 0)
    
    def list(self) -> List[Dict]:
        result = self.send({'cmd': 'list'})
        return result.get('notifications', [])


def main():
    daemon = NotificationDaemon()
    
    def signal_handler(sig, frame):
        daemon.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    asyncio.run(daemon.start_server())


if __name__ == '__main__':
    main()
