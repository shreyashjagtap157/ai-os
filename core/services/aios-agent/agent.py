#!/usr/bin/env python3
"""
AI-OS Agent Service
Core AI agent daemon that runs as a system service.
This is the central intelligence of AI-OS.
"""

import os
import sys
import json
import signal
import asyncio
import logging
import socket
import struct
import subprocess
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import threading

# Logging setup
LOG_PATH = "/var/log/aios/agent.log"
os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('aios-agent')


# ==============================================================================
# Configuration
# ==============================================================================

@dataclass
class AgentConfig:
    """AI-OS Agent configuration"""
    # Paths
    socket_path: str = "/run/aios/agent.sock"
    config_dir: str = "/etc/aios"
    data_dir: str = "/var/lib/aios"
    
    # AI Provider
    ai_provider: str = "openai"  # openai, anthropic, local
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    model: str = "gpt-4"
    
    # Voice
    voice_enabled: bool = True
    wake_word: str = "hey ai"
    tts_enabled: bool = True
    
    # Behavior
    confirm_dangerous: bool = True
    max_actions_per_command: int = 20
    action_timeout: float = 30.0
    
    @classmethod
    def load(cls) -> 'AgentConfig':
        """Load configuration from file and environment"""
        config = cls()
        
        # Load from file
        config_file = Path(config.config_dir) / "agent.json"
        if config_file.exists():
            try:
                with open(config_file) as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(config, key):
                        setattr(config, key, value)
            except Exception as e:
                logger.warning(f"Failed to load config file: {e}")
        
        # Override with environment
        config.openai_api_key = os.environ.get('OPENAI_API_KEY', config.openai_api_key)
        config.anthropic_api_key = os.environ.get('ANTHROPIC_API_KEY', config.anthropic_api_key)
        
        return config


# ==============================================================================
# Hardware Abstraction Layer
# ==============================================================================

class HAL:
    """Hardware Abstraction Layer for AI-OS"""
    
    # ---------- Display ----------
    
    @staticmethod
    def get_brightness() -> int:
        """Get display brightness (0-100)"""
        try:
            for device in Path("/sys/class/backlight").iterdir():
                current = int((device / "brightness").read_text().strip())
                max_val = int((device / "max_brightness").read_text().strip())
                return int(current * 100 / max_val)
        except:
            return -1
    
    @staticmethod
    def set_brightness(level: int) -> bool:
        """Set display brightness (0-100)"""
        try:
            for device in Path("/sys/class/backlight").iterdir():
                max_val = int((device / "max_brightness").read_text().strip())
                value = int(max_val * level / 100)
                (device / "brightness").write_text(str(value))
                return True
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            return False
    
    # ---------- Audio ----------
    
    @staticmethod
    def get_volume() -> int:
        """Get audio volume (0-100)"""
        try:
            result = subprocess.run(
                ['amixer', 'get', 'Master'],
                capture_output=True, text=True
            )
            import re
            match = re.search(r'\[(\d+)%\]', result.stdout)
            if match:
                return int(match.group(1))
        except:
            pass
        return -1
    
    @staticmethod
    def set_volume(level: int) -> bool:
        """Set audio volume (0-100)"""
        try:
            subprocess.run(['amixer', 'set', 'Master', f'{level}%'], check=True)
            return True
        except:
            return False
    
    @staticmethod
    def set_mute(mute: bool) -> bool:
        """Mute/unmute audio"""
        try:
            state = 'mute' if mute else 'unmute'
            subprocess.run(['amixer', 'set', 'Master', state], check=True)
            return True
        except:
            return False
    
    # ---------- Network ----------
    
    @staticmethod
    def get_wifi_status() -> Dict[str, Any]:
        """Get WiFi status"""
        try:
            result = subprocess.run(
                ['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL', 'dev', 'wifi'],
                capture_output=True, text=True
            )
            for line in result.stdout.strip().split('\n'):
                parts = line.split(':')
                if len(parts) >= 3 and parts[0] == 'yes':
                    return {
                        'connected': True,
                        'ssid': parts[1],
                        'signal': int(parts[2]) if parts[2].isdigit() else 0
                    }
            return {'connected': False}
        except:
            return {'error': 'Unable to get WiFi status'}
    
    @staticmethod
    def set_wifi(enable: bool) -> bool:
        """Enable/disable WiFi"""
        try:
            state = 'on' if enable else 'off'
            subprocess.run(['nmcli', 'radio', 'wifi', state], check=True)
            return True
        except:
            return False
    
    @staticmethod
    def connect_wifi(ssid: str, password: Optional[str] = None) -> bool:
        """Connect to WiFi network"""
        try:
            cmd = ['nmcli', 'dev', 'wifi', 'connect', ssid]
            if password:
                cmd.extend(['password', password])
            subprocess.run(cmd, check=True)
            return True
        except:
            return False
    
    @staticmethod
    def set_bluetooth(enable: bool) -> bool:
        """Enable/disable Bluetooth"""
        try:
            state = 'on' if enable else 'off'
            subprocess.run(['bluetoothctl', 'power', state], check=True)
            return True
        except:
            return False
    
    # ---------- Power ----------
    
    @staticmethod
    def get_battery() -> Dict[str, Any]:
        """Get battery status"""
        try:
            bat_path = Path("/sys/class/power_supply/BAT0")
            if not bat_path.exists():
                return {'available': False}
            
            capacity = int((bat_path / "capacity").read_text().strip())
            status = (bat_path / "status").read_text().strip()
            
            return {
                'available': True,
                'level': capacity,
                'status': status,
                'charging': status == 'Charging'
            }
        except:
            return {'available': False}
    
    @staticmethod
    def shutdown(reboot: bool = False) -> bool:
        """Shutdown or reboot"""
        try:
            cmd = 'reboot' if reboot else 'poweroff'
            subprocess.run(['systemctl', cmd], check=True)
            return True
        except:
            return False
    
    @staticmethod
    def suspend() -> bool:
        """Suspend to RAM"""
        try:
            subprocess.run(['systemctl', 'suspend'], check=True)
            return True
        except:
            return False
    
    # ---------- Input ----------
    
    @staticmethod
    def get_input_devices() -> List[Dict[str, str]]:
        """Get input devices"""
        devices = []
        input_path = Path("/sys/class/input")
        
        for device in input_path.iterdir():
            if device.name.startswith('event'):
                name_file = device / 'device' / 'name'
                if name_file.exists():
                    name = name_file.read_text().strip()
                    devices.append({
                        'name': name,
                        'path': f'/dev/input/{device.name}'
                    })
        
        return devices
    
    # ---------- System Info ----------
    
    @staticmethod
    def get_system_info() -> Dict[str, Any]:
        """Get system information"""
        import platform
        info = {
            'hostname': platform.node(),
            'kernel': platform.release(),
            'arch': platform.machine()
        }
        
        # CPU
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith('model name'):
                        info['cpu'] = line.split(':')[1].strip()
                        break
            info['cpu_count'] = os.cpu_count()
        except:
            pass
        
        # Memory
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        info['memory_mb'] = int(line.split()[1]) // 1024
                    elif line.startswith('MemAvailable'):
                        info['memory_free_mb'] = int(line.split()[1]) // 1024
        except:
            pass
        
        # Disk
        try:
            stat = os.statvfs('/')
            info['disk_total_gb'] = (stat.f_blocks * stat.f_frsize) // (1024**3)
            info['disk_free_gb'] = (stat.f_bfree * stat.f_frsize) // (1024**3)
        except:
            pass
        
        # Uptime
        try:
            with open('/proc/uptime') as f:
                uptime_sec = float(f.read().split()[0])
                info['uptime_hours'] = round(uptime_sec / 3600, 1)
        except:
            pass
        
        return info
    
    # ---------- Applications ----------
    
    @staticmethod
    def list_applications() -> List[Dict[str, str]]:
        """List installed applications"""
        apps = []
        app_dirs = [
            '/usr/share/applications',
            '/usr/local/share/applications',
            os.path.expanduser('~/.local/share/applications')
        ]
        
        for app_dir in app_dirs:
            dir_path = Path(app_dir)
            if dir_path.exists():
                for desktop_file in dir_path.glob('*.desktop'):
                    try:
                        content = desktop_file.read_text()
                        name = None
                        exec_cmd = None
                        for line in content.split('\n'):
                            if line.startswith('Name='):
                                name = line[5:]
                            elif line.startswith('Exec='):
                                exec_cmd = line[5:]
                        if name:
                            apps.append({'name': name, 'exec': exec_cmd})
                    except:
                        pass
        
        return apps
    
    @staticmethod
    def launch_app(name: str) -> bool:
        """Launch an application"""
        apps = HAL.list_applications()
        
        for app in apps:
            if name.lower() in app['name'].lower():
                if app['exec']:
                    try:
                        # Remove field codes like %f, %u
                        import re
                        cmd = re.sub(r'%[a-zA-Z]', '', app['exec']).strip()
                        subprocess.Popen(cmd.split(), start_new_session=True)
                        return True
                    except:
                        pass
        
        # Try direct execution
        try:
            subprocess.Popen([name], start_new_session=True)
            return True
        except:
            return False


# ==============================================================================
# AI Engine
# ==============================================================================

class AIEngine:
    """AI processing engine with LLM integration"""
    
    SYSTEM_PROMPT = """You are AI-OS, an intelligent operating system.
You have COMPLETE CONTROL over this device through the following actions.

## Available Actions (respond with JSON)

### Display Control
- {"action": "brightness", "level": 0-100}

### Audio Control
- {"action": "volume", "level": 0-100}
- {"action": "mute", "mute": true/false}

### Network Control
- {"action": "wifi", "enabled": true/false}
- {"action": "wifi_connect", "ssid": "name", "password": "optional"}
- {"action": "bluetooth", "enabled": true/false}

### Power Control
- {"action": "shutdown", "reboot": false}
- {"action": "suspend"}

### Application Control
- {"action": "launch", "app": "app_name"}

### Information
- {"action": "info", "type": "system|battery|wifi|apps"}

When responding, output your action as JSON wrapped in ```json blocks.
For dangerous actions (shutdown, reboot), always confirm first.
Be helpful and conversational while executing commands."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.history = [{"role": "system", "content": self.SYSTEM_PROMPT}]
    
    async def process(self, user_input: str) -> str:
        """Process user input and return response"""
        self.history.append({"role": "user", "content": user_input})
        
        try:
            if self.config.openai_api_key:
                response = await self._call_openai()
            elif self.config.anthropic_api_key:
                response = await self._call_anthropic()
            else:
                response = self._process_local(user_input)
        except Exception as e:
            logger.error(f"AI processing error: {e}")
            response = f"I encountered an error: {e}"
        
        self.history.append({"role": "assistant", "content": response})
        
        # Keep history manageable
        if len(self.history) > 20:
            self.history = [self.history[0]] + self.history[-10:]
        
        return response
    
    async def _call_openai(self) -> str:
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
                    "model": self.config.model,
                    "messages": self.history,
                    "temperature": 0.7,
                    "max_tokens": 1024
                },
                timeout=60.0
            )
            
            data = response.json()
            return data["choices"][0]["message"]["content"]
    
    async def _call_anthropic(self) -> str:
        """Call Anthropic API"""
        import httpx
        
        system_msg = self.history[0]["content"]
        messages = [{"role": m["role"], "content": m["content"]} for m in self.history[1:]]
        
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
                    "messages": messages
                },
                timeout=60.0
            )
            
            data = response.json()
            return data["content"][0]["text"]
    
    def _process_local(self, user_input: str) -> str:
        """Local processing without AI provider"""
        lower = user_input.lower()
        
        # Time/Date
        if 'time' in lower:
            return f"The current time is {datetime.now().strftime('%H:%M:%S')}"
        if 'date' in lower:
            return f"Today is {datetime.now().strftime('%A, %B %d, %Y')}"
        
        # Brightness
        if 'brightness' in lower:
            if 'up' in lower or 'higher' in lower or 'increase' in lower:
                return '```json\n{"action": "brightness", "level": 80}\n```'
            if 'down' in lower or 'lower' in lower or 'decrease' in lower:
                return '```json\n{"action": "brightness", "level": 40}\n```'
            if 'max' in lower or 'full' in lower:
                return '```json\n{"action": "brightness", "level": 100}\n```'
            if 'min' in lower or 'low' in lower:
                return '```json\n{"action": "brightness", "level": 10}\n```'
        
        # Volume
        if 'volume' in lower:
            if 'up' in lower or 'higher' in lower or 'increase' in lower:
                return '```json\n{"action": "volume", "level": 70}\n```'
            if 'down' in lower or 'lower' in lower or 'decrease' in lower:
                return '```json\n{"action": "volume", "level": 30}\n```'
            if 'mute' in lower:
                return '```json\n{"action": "mute", "mute": true}\n```'
            if 'unmute' in lower:
                return '```json\n{"action": "mute", "mute": false}\n```'
        
        # WiFi
        if 'wifi' in lower:
            if 'on' in lower or 'enable' in lower:
                return '```json\n{"action": "wifi", "enabled": true}\n```'
            if 'off' in lower or 'disable' in lower:
                return '```json\n{"action": "wifi", "enabled": false}\n```'
            if 'status' in lower:
                return '```json\n{"action": "info", "type": "wifi"}\n```'
        
        # Bluetooth
        if 'bluetooth' in lower:
            if 'on' in lower or 'enable' in lower:
                return '```json\n{"action": "bluetooth", "enabled": true}\n```'
            if 'off' in lower or 'disable' in lower:
                return '```json\n{"action": "bluetooth", "enabled": false}\n```'
        
        # Power
        if 'shutdown' in lower or 'power off' in lower or 'turn off' in lower:
            return 'Are you sure you want to shutdown? Say "confirm shutdown" to proceed.'
        if 'confirm shutdown' in lower:
            return '```json\n{"action": "shutdown", "reboot": false}\n```'
        if 'reboot' in lower or 'restart' in lower:
            return '```json\n{"action": "shutdown", "reboot": true}\n```'
        if 'suspend' in lower or 'sleep' in lower:
            return '```json\n{"action": "suspend"}\n```'
        
        # System info
        if 'battery' in lower:
            return '```json\n{"action": "info", "type": "battery"}\n```'
        if 'system' in lower and ('info' in lower or 'status' in lower):
            return '```json\n{"action": "info", "type": "system"}\n```'
        
        # Launch apps
        if 'open' in lower or 'launch' in lower or 'start' in lower:
            words = user_input.split()
            for i, word in enumerate(words):
                if word.lower() in ('open', 'launch', 'start'):
                    if i + 1 < len(words):
                        app = ' '.join(words[i+1:])
                        return f'```json\n{{"action": "launch", "app": "{app}"}}\n```'
        
        return "I'm running in local mode without an AI provider. Try commands like 'turn up brightness', 'mute volume', 'show battery status', 'open firefox'."
    
    def extract_action(self, response: str) -> Optional[Dict[str, Any]]:
        """Extract action from AI response"""
        import re
        
        pattern = r'```json\s*(\{[^`]+\})\s*```'
        match = re.search(pattern, response)
        
        if match:
            try:
                return json.loads(match.group(1))
            except:
                pass
        
        return None
    
    def clear(self):
        """Clear conversation history"""
        self.history = [self.history[0]]


# ==============================================================================
# Action Executor
# ==============================================================================

class ActionExecutor:
    """Executes actions from AI responses"""
    
    def execute(self, action: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an action and return result"""
        action_type = action.get('action')
        
        try:
            if action_type == 'brightness':
                level = action.get('level', 50)
                success = HAL.set_brightness(level)
                return {'success': success, 'message': f'Brightness set to {level}%'}
            
            elif action_type == 'volume':
                level = action.get('level', 50)
                success = HAL.set_volume(level)
                return {'success': success, 'message': f'Volume set to {level}%'}
            
            elif action_type == 'mute':
                mute = action.get('mute', True)
                success = HAL.set_mute(mute)
                return {'success': success, 'message': 'Muted' if mute else 'Unmuted'}
            
            elif action_type == 'wifi':
                enabled = action.get('enabled', True)
                success = HAL.set_wifi(enabled)
                return {'success': success, 'message': f'WiFi {"enabled" if enabled else "disabled"}'}
            
            elif action_type == 'wifi_connect':
                ssid = action.get('ssid', '')
                password = action.get('password')
                success = HAL.connect_wifi(ssid, password)
                return {'success': success, 'message': f'Connected to {ssid}' if success else 'Connection failed'}
            
            elif action_type == 'bluetooth':
                enabled = action.get('enabled', True)
                success = HAL.set_bluetooth(enabled)
                return {'success': success, 'message': f'Bluetooth {"enabled" if enabled else "disabled"}'}
            
            elif action_type == 'shutdown':
                reboot = action.get('reboot', False)
                success = HAL.shutdown(reboot)
                return {'success': success, 'message': 'Rebooting...' if reboot else 'Shutting down...'}
            
            elif action_type == 'suspend':
                success = HAL.suspend()
                return {'success': success, 'message': 'Suspending...'}
            
            elif action_type == 'launch':
                app = action.get('app', '')
                success = HAL.launch_app(app)
                return {'success': success, 'message': f'Launched {app}' if success else f'Could not find {app}'}
            
            elif action_type == 'info':
                info_type = action.get('type', 'system')
                if info_type == 'system':
                    data = HAL.get_system_info()
                elif info_type == 'battery':
                    data = HAL.get_battery()
                elif info_type == 'wifi':
                    data = HAL.get_wifi_status()
                elif info_type == 'apps':
                    data = {'apps': [a['name'] for a in HAL.list_applications()[:20]]}
                else:
                    data = {}
                return {'success': True, 'data': data}
            
            else:
                return {'success': False, 'message': f'Unknown action: {action_type}'}
                
        except Exception as e:
            logger.error(f"Action execution error: {e}")
            return {'success': False, 'message': str(e)}


# ==============================================================================
# Agent Daemon
# ==============================================================================

class AgentDaemon:
    """Main AI-OS Agent Daemon"""
    
    def __init__(self, config: AgentConfig):
        self.config = config
        self.ai = AIEngine(config)
        self.executor = ActionExecutor()
        self.running = False
        self._server = None
        
        # Ensure directories
        os.makedirs(os.path.dirname(config.socket_path), exist_ok=True)
        os.makedirs(config.data_dir, exist_ok=True)
    
    async def start(self):
        """Start the agent daemon"""
        logger.info("Starting AI-OS Agent Daemon...")
        
        self.running = True
        
        # Remove old socket
        if os.path.exists(self.config.socket_path):
            os.unlink(self.config.socket_path)
        
        # Start IPC server
        self._server = await asyncio.start_unix_server(
            self._handle_client,
            path=self.config.socket_path
        )
        
        os.chmod(self.config.socket_path, 0o666)
        
        logger.info(f"Agent listening on {self.config.socket_path}")
        
        async with self._server:
            await self._server.serve_forever()
    
    async def stop(self):
        """Stop the daemon"""
        logger.info("Stopping AI-OS Agent Daemon...")
        self.running = False
        
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        
        if os.path.exists(self.config.socket_path):
            os.unlink(self.config.socket_path)
    
    async def _handle_client(self, reader, writer):
        """Handle IPC client connection"""
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
        """Process IPC request"""
        cmd = request.get('cmd')
        
        if cmd == 'chat':
            # Process through AI
            text = request.get('text', '')
            response = await self.ai.process(text)
            
            # Check for actions
            action = self.ai.extract_action(response)
            action_result = None
            
            if action:
                action_result = self.executor.execute(action)
            
            return {
                'status': 'ok',
                'response': response,
                'action': action,
                'action_result': action_result
            }
        
        elif cmd == 'action':
            # Direct action
            action = request.get('action', {})
            result = self.executor.execute(action)
            return {'status': 'ok', 'result': result}
        
        elif cmd == 'status':
            return {
                'status': 'ok',
                'running': self.running,
                'ai_configured': bool(self.config.openai_api_key or self.config.anthropic_api_key),
                'system': HAL.get_system_info()
            }
        
        elif cmd == 'clear':
            self.ai.clear()
            return {'status': 'ok', 'message': 'Conversation cleared'}
        
        else:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}


# ==============================================================================
# Main
# ==============================================================================

def main():
    """Main entry point"""
    logger.info("=" * 60)
    logger.info("AI-OS Agent Service Starting")
    logger.info("=" * 60)
    
    config = AgentConfig.load()
    daemon = AgentDaemon(config)
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Signal handlers
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))
    
    try:
        loop.run_until_complete(daemon.start())
    except KeyboardInterrupt:
        pass
    finally:
        loop.run_until_complete(daemon.stop())
        loop.close()
    
    logger.info("AI-OS Agent Service Stopped")


if __name__ == '__main__':
    main()
