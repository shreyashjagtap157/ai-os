#!/usr/bin/env python3
"""
AI-OS Agent Daemon
The core AI agent service that runs as a system daemon.
Handles user input, AI processing, and device control.
"""

import os
import sys
import signal
import asyncio
import logging
import json
import socket
import struct
from pathlib import Path
from typing import Optional, Dict, Any, Callable, List
from dataclasses import dataclass, field
from datetime import datetime
import subprocess

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/aios-agent.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('aios-agent')


@dataclass
class AgentConfig:
    """Agent configuration"""
    socket_path: str = "/run/aios/agent.sock"
    config_dir: str = "/etc/aios"
    data_dir: str = "/var/lib/aios"
    log_dir: str = "/var/log/aios"
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    voice_enabled: bool = True
    wake_word: str = "hey ai"
    
    @classmethod
    def load(cls, path: str = "/etc/aios/agent.conf") -> 'AgentConfig':
        """Load configuration from file"""
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
        
        # Override with environment variables
        config.openai_api_key = os.environ.get('OPENAI_API_KEY', config.openai_api_key)
        config.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY', config.anthropic_api_key)
        
        return config


class DeviceController:
    """
    Low-level device control for AI-OS.
    Direct hardware and system control.
    """
    
    def __init__(self):
        self._display = None
        self._audio = None
        
    # ==================== Display Control ====================
    
    def set_brightness(self, level: int) -> bool:
        """Set display brightness (0-100)"""
        try:
            brightness_path = "/sys/class/backlight"
            if not os.path.exists(brightness_path):
                return False
            
            # Find first backlight device
            devices = os.listdir(brightness_path)
            if not devices:
                return False
            
            device = devices[0]
            max_brightness_file = f"{brightness_path}/{device}/max_brightness"
            brightness_file = f"{brightness_path}/{device}/brightness"
            
            with open(max_brightness_file) as f:
                max_val = int(f.read().strip())
            
            new_val = int(max_val * level / 100)
            with open(brightness_file, 'w') as f:
                f.write(str(new_val))
            
            return True
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            return False
    
    def get_brightness(self) -> int:
        """Get current display brightness"""
        try:
            brightness_path = "/sys/class/backlight"
            devices = os.listdir(brightness_path)
            if not devices:
                return -1
            
            device = devices[0]
            with open(f"{brightness_path}/{device}/brightness") as f:
                current = int(f.read().strip())
            with open(f"{brightness_path}/{device}/max_brightness") as f:
                max_val = int(f.read().strip())
            
            return int(current * 100 / max_val)
        except:
            return -1
    
    # ==================== Audio Control ====================
    
    def set_volume(self, level: int) -> bool:
        """Set audio volume (0-100)"""
        try:
            subprocess.run(
                ['amixer', 'set', 'Master', f'{level}%'],
                capture_output=True, check=True
            )
            return True
        except Exception as e:
            logger.error(f"Failed to set volume: {e}")
            return False
    
    def get_volume(self) -> int:
        """Get current audio volume"""
        try:
            result = subprocess.run(
                ['amixer', 'get', 'Master'],
                capture_output=True, text=True
            )
            # Parse output to find percentage
            for line in result.stdout.split('\n'):
                if '%' in line:
                    import re
                    match = re.search(r'\[(\d+)%\]', line)
                    if match:
                        return int(match.group(1))
            return -1
        except:
            return -1
    
    def mute(self, mute: bool = True) -> bool:
        """Mute/unmute audio"""
        try:
            state = 'mute' if mute else 'unmute'
            subprocess.run(
                ['amixer', 'set', 'Master', state],
                capture_output=True, check=True
            )
            return True
        except:
            return False
    
    # ==================== Network Control ====================
    
    def get_wifi_status(self) -> Dict[str, Any]:
        """Get WiFi status"""
        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,SECURITY', 'dev', 'wifi'],
                capture_output=True, text=True
            )
            networks = []
            for line in result.stdout.strip().split('\n'):
                if line:
                    parts = line.split(':')
                    if len(parts) >= 4:
                        networks.append({
                            'active': parts[0] == 'yes',
                            'ssid': parts[1],
                            'signal': int(parts[2]) if parts[2].isdigit() else 0,
                            'security': parts[3]
                        })
            return {'networks': networks}
        except Exception as e:
            return {'error': str(e)}
    
    def connect_wifi(self, ssid: str, password: Optional[str] = None) -> bool:
        """Connect to WiFi network"""
        try:
            cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
            if password:
                cmd.extend(['password', password])
            subprocess.run(cmd, capture_output=True, check=True)
            return True
        except:
            return False
    
    def toggle_wifi(self, enable: bool) -> bool:
        """Enable/disable WiFi"""
        try:
            state = 'on' if enable else 'off'
            subprocess.run(['nmcli', 'radio', 'wifi', state], check=True)
            return True
        except:
            return False
    
    def toggle_bluetooth(self, enable: bool) -> bool:
        """Enable/disable Bluetooth"""
        try:
            state = 'on' if enable else 'off'
            subprocess.run(['bluetoothctl', 'power', state], check=True)
            return True
        except:
            return False
    
    # ==================== Power Management ====================
    
    def get_battery_status(self) -> Dict[str, Any]:
        """Get battery status"""
        try:
            battery_path = "/sys/class/power_supply/BAT0"
            if not os.path.exists(battery_path):
                return {'available': False}
            
            with open(f"{battery_path}/capacity") as f:
                capacity = int(f.read().strip())
            with open(f"{battery_path}/status") as f:
                status = f.read().strip()
            
            return {
                'available': True,
                'capacity': capacity,
                'status': status,
                'charging': status == 'Charging'
            }
        except Exception as e:
            return {'available': False, 'error': str(e)}
    
    def shutdown(self, reboot: bool = False) -> bool:
        """Shutdown or reboot the system"""
        try:
            cmd = 'reboot' if reboot else 'poweroff'
            subprocess.run(['systemctl', cmd], check=True)
            return True
        except:
            return False
    
    def suspend(self) -> bool:
        """Suspend the system"""
        try:
            subprocess.run(['systemctl', 'suspend'], check=True)
            return True
        except:
            return False
    
    # ==================== Application Control ====================
    
    def launch_app(self, app_name: str) -> bool:
        """Launch an application"""
        try:
            # Try common app locations
            desktop_dirs = [
                '/usr/share/applications',
                '/usr/local/share/applications',
                os.path.expanduser('~/.local/share/applications')
            ]
            
            for dir_path in desktop_dirs:
                desktop_file = os.path.join(dir_path, f'{app_name}.desktop')
                if os.path.exists(desktop_file):
                    subprocess.Popen(['gtk-launch', f'{app_name}.desktop'])
                    return True
            
            # Try direct execution
            subprocess.Popen([app_name], start_new_session=True)
            return True
        except:
            return False
    
    def list_apps(self) -> List[Dict[str, str]]:
        """List installed applications"""
        apps = []
        desktop_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications'
        ]
        
        for dir_path in desktop_dirs:
            if os.path.exists(dir_path):
                for filename in os.listdir(dir_path):
                    if filename.endswith('.desktop'):
                        try:
                            desktop_path = os.path.join(dir_path, filename)
                            app_info = self._parse_desktop_file(desktop_path)
                            if app_info:
                                apps.append(app_info)
                        except:
                            pass
        
        return apps
    
    def _parse_desktop_file(self, path: str) -> Optional[Dict[str, str]]:
        """Parse a .desktop file"""
        with open(path) as f:
            content = f.read()
        
        name = None
        exec_cmd = None
        icon = None
        
        for line in content.split('\n'):
            if line.startswith('Name='):
                name = line[5:]
            elif line.startswith('Exec='):
                exec_cmd = line[5:]
            elif line.startswith('Icon='):
                icon = line[5:]
        
        if name:
            return {'name': name, 'exec': exec_cmd, 'icon': icon}
        return None
    
    # ==================== System Information ====================
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get system information"""
        info = {}
        
        # CPU info
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith('model name'):
                        info['cpu'] = line.split(':')[1].strip()
                        break
        except:
            pass
        
        # Memory info
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        total = int(line.split()[1]) // 1024
                        info['memory_mb'] = total
                    elif line.startswith('MemAvailable'):
                        available = int(line.split()[1]) // 1024
                        info['memory_available_mb'] = available
        except:
            pass
        
        # Disk info
        try:
            stat = os.statvfs('/')
            total_gb = (stat.f_blocks * stat.f_frsize) // (1024**3)
            free_gb = (stat.f_bfree * stat.f_frsize) // (1024**3)
            info['disk_total_gb'] = total_gb
            info['disk_free_gb'] = free_gb
        except:
            pass
        
        # Uptime
        try:
            with open('/proc/uptime') as f:
                uptime_seconds = float(f.read().split()[0])
                info['uptime_hours'] = round(uptime_seconds / 3600, 2)
        except:
            pass
        
        return info


class AIEngine:
    """
    AI processing engine with LLM integration.
    """
    
    SYSTEM_PROMPT = """You are AI-OS, an intelligent operating system assistant.
You have direct control over the device and can execute system commands.

When the user asks you to perform an action, respond with the action in JSON format:
```json
{"action": "action_name", "params": {...}}
```

Available actions:
- {"action": "brightness", "params": {"level": 0-100}}
- {"action": "volume", "params": {"level": 0-100}}
- {"action": "mute", "params": {"mute": true/false}}
- {"action": "wifi", "params": {"enable": true/false}}
- {"action": "wifi_connect", "params": {"ssid": "name", "password": "pass"}}
- {"action": "bluetooth", "params": {"enable": true/false}}
- {"action": "launch", "params": {"app": "app_name"}}
- {"action": "shutdown", "params": {"reboot": false}}
- {"action": "suspend", "params": {}}
- {"action": "info", "params": {"type": "system|battery|wifi"}}

Be helpful, concise, and always confirm actions before executing dangerous ones."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.conversation = [{"role": "system", "content": self.SYSTEM_PROMPT}]
    
    async def process(self, user_input: str) -> str:
        """Process user input and generate response"""
        self.conversation.append({"role": "user", "content": user_input})
        
        try:
            if self.config.openai_api_key:
                response = await self._call_openai(self.conversation)
            elif self.config.anthropic_api_key:
                response = await self._call_anthropic(self.conversation)
            else:
                response = self._process_locally(user_input)
        except Exception as e:
            logger.error(f"AI processing error: {e}")
            response = f"I encountered an error: {e}"
        
        self.conversation.append({"role": "assistant", "content": response})
        
        # Keep conversation manageable
        if len(self.conversation) > 20:
            self.conversation = [self.conversation[0]] + self.conversation[-10:]
        
        return response
    
    async def _call_openai(self, messages: List[Dict]) -> str:
        """Call OpenAI API"""
        import httpx
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.openai.com/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.config.openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4",
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 1024
                },
                timeout=60.0
            )
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def _call_anthropic(self, messages: List[Dict]) -> str:
        """Call Anthropic API"""
        import httpx
        
        system_msg = messages[0]["content"]
        conv_messages = [
            {"role": m["role"], "content": m["content"]}
            for m in messages[1:]
        ]
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": self.config.anthropic_api_key,
                    "anthropic-version": "2023-06-01",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "claude-3-opus-20240229",
                    "max_tokens": 1024,
                    "system": system_msg,
                    "messages": conv_messages
                },
                timeout=60.0
            )
            
            data = response.json()
            return data["content"][0]["text"]
    
    def _process_locally(self, user_input: str) -> str:
        """Local processing fallback"""
        lower = user_input.lower()
        
        if 'time' in lower:
            return f"The current time is {datetime.now().strftime('%H:%M:%S')}"
        elif 'date' in lower:
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"
        elif 'brightness' in lower:
            if 'up' in lower or 'increase' in lower:
                return '```json\n{"action": "brightness", "params": {"level": 80}}\n```'
            elif 'down' in lower or 'decrease' in lower:
                return '```json\n{"action": "brightness", "params": {"level": 50}}\n```'
        elif 'volume' in lower:
            if 'up' in lower or 'increase' in lower:
                return '```json\n{"action": "volume", "params": {"level": 80}}\n```'
            elif 'down' in lower or 'decrease' in lower:
                return '```json\n{"action": "volume", "params": {"level": 30}}\n```'
            elif 'mute' in lower:
                return '```json\n{"action": "mute", "params": {"mute": true}}\n```'
        elif 'wifi' in lower:
            if 'on' in lower or 'enable' in lower:
                return '```json\n{"action": "wifi", "params": {"enable": true}}\n```'
            elif 'off' in lower or 'disable' in lower:
                return '```json\n{"action": "wifi", "params": {"enable": false}}\n```'
        elif 'bluetooth' in lower:
            if 'on' in lower or 'enable' in lower:
                return '```json\n{"action": "bluetooth", "params": {"enable": true}}\n```'
            elif 'off' in lower or 'disable' in lower:
                return '```json\n{"action": "bluetooth", "params": {"enable": false}}\n```'
        elif 'shutdown' in lower or 'power off' in lower:
            return '```json\n{"action": "shutdown", "params": {"reboot": false}}\n```'
        elif 'reboot' in lower or 'restart' in lower:
            return '```json\n{"action": "shutdown", "params": {"reboot": true}}\n```'
        elif 'suspend' in lower or 'sleep' in lower:
            return '```json\n{"action": "suspend", "params": {}}\n```'
        elif 'battery' in lower:
            return '```json\n{"action": "info", "params": {"type": "battery"}}\n```'
        elif 'system' in lower and 'info' in lower:
            return '```json\n{"action": "info", "params": {"type": "system"}}\n```'
        elif 'open' in lower or 'launch' in lower:
            # Extract app name
            words = user_input.split()
            for i, word in enumerate(words):
                if word.lower() in ('open', 'launch', 'start'):
                    if i + 1 < len(words):
                        app = words[i + 1]
                        return f'```json\n{{"action": "launch", "params": {{"app": "{app}"}}}}\n```'
        
        return "I'm running in local mode. Configure an API key for full AI capabilities. Try commands like 'turn up brightness', 'mute volume', or 'show battery status'."
    
    def extract_action(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract action from AI response"""
        import re
        
        json_pattern = r'```json\s*(\{[^`]+\})\s*```'
        match = re.search(json_pattern, response)
        
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        return None
    
    def clear_history(self):
        """Clear conversation history"""
        self.conversation = [self.conversation[0]]


class AgentDaemon:
    """
    Main AI-OS Agent Daemon.
    Handles IPC, command processing, and system events.
    """
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.device = DeviceController()
        self.ai = AIEngine(config)
        self.running = False
        self._server = None
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(config.socket_path), exist_ok=True)
        os.makedirs(config.data_dir, exist_ok=True)
        os.makedirs(config.log_dir, exist_ok=True)
    
    async def start(self):
        """Start the agent daemon"""
        logger.info("Starting AI-OS Agent Daemon...")
        
        self.running = True
        
        # Remove old socket if exists
        if os.path.exists(self.config.socket_path):
            os.unlink(self.config.socket_path)
        
        # Start Unix socket server
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.config.socket_path
        )
        
        # Set socket permissions
        os.chmod(self.config.socket_path, 0o666)
        
        logger.info(f"Agent listening on {self.config.socket_path}")
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """Stop the agent daemon"""
        logger.info("Stopping AI-OS Agent Daemon...")
        self.running = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        if os.path.exists(self.config.socket_path):
            os.unlink(self.config.socket_path)
    
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Handle client connection"""
        try:
            while True:
                # Read message length
                length_data = await reader.read(4)
                if not length_data:
                    break
                
                length = struct.unpack('!I', length_data)[0]
                
                # Read message
                data = await reader.read(length)
                if not data:
                    break
                
                request = json.loads(data.decode('utf-8'))
                response = await self._process_request(request)
                
                # Send response
                response_data = json.dumps(response).encode('utf-8')
                writer.write(struct.pack('!I', len(response_data)))
                writer.write(response_data)
                await writer.drain()
                
        except Exception as e:
            logger.error(f"Client error: {e}")
        finally:
            writer.close()
            await writer.wait_closed()
    
    async def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process an incoming request"""
        cmd = request.get('cmd')
        
        if cmd == 'chat':
            # Process through AI
            user_input = request.get('text', '')
            response_text = await self.ai.process(user_input)
            
            # Check for actions
            action = self.ai.extract_action(response_text)
            action_result = None
            
            if action:
                action_result = self._execute_action(action)
            
            return {
                'status': 'ok',
                'response': response_text,
                'action': action,
                'action_result': action_result
            }
        
        elif cmd == 'action':
            # Direct action execution
            action = request.get('action')
            result = self._execute_action(action)
            return {'status': 'ok', 'result': result}
        
        elif cmd == 'status':
            return {
                'status': 'ok',
                'running': self.running,
                'ai_configured': bool(self.config.openai_api_key or self.config.anthropic_api_key),
                'system': self.device.get_system_info()
            }
        
        else:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
    
    def _execute_action(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a device action"""
        action_type = action.get('action')
        params = action.get('params', {})
        
        try:
            if action_type == 'brightness':
                success = self.device.set_brightness(params.get('level', 50))
                return {'success': success}
            
            elif action_type == 'volume':
                success = self.device.set_volume(params.get('level', 50))
                return {'success': success}
            
            elif action_type == 'mute':
                success = self.device.mute(params.get('mute', True))
                return {'success': success}
            
            elif action_type == 'wifi':
                success = self.device.toggle_wifi(params.get('enable', True))
                return {'success': success}
            
            elif action_type == 'wifi_connect':
                success = self.device.connect_wifi(
                    params.get('ssid', ''),
                    params.get('password')
                )
                return {'success': success}
            
            elif action_type == 'bluetooth':
                success = self.device.toggle_bluetooth(params.get('enable', True))
                return {'success': success}
            
            elif action_type == 'launch':
                success = self.device.launch_app(params.get('app', ''))
                return {'success': success}
            
            elif action_type == 'shutdown':
                success = self.device.shutdown(params.get('reboot', False))
                return {'success': success}
            
            elif action_type == 'suspend':
                success = self.device.suspend()
                return {'success': success}
            
            elif action_type == 'info':
                info_type = params.get('type', 'system')
                if info_type == 'system':
                    return {'success': True, 'data': self.device.get_system_info()}
                elif info_type == 'battery':
                    return {'success': True, 'data': self.device.get_battery_status()}
                elif info_type == 'wifi':
                    return {'success': True, 'data': self.device.get_wifi_status()}
            
            else:
                return {'success': False, 'error': f'Unknown action: {action_type}'}
                
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {'success': False, 'error': str(e)}


def main():
    """Main entry point"""
    config = AgentConfig.load()
    daemon = AgentDaemon(config)
    
    # Signal handlers
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))
    
    try:
        loop.run_until_complete(daemon.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(daemon.stop())
        loop.close()


if __name__ == '__main__':
    main()
