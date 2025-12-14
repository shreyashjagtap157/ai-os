#!/usr/bin/env python3
"""
AI-OS Input Service
Handles keyboard shortcuts, gestures, and input device management.
"""

import os
import sys
import signal
import logging
import asyncio
import json
import struct
import socket
from pathlib import Path
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass
from enum import Enum, auto

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger('aios-input')


class KeyCode(Enum):
    """Common key codes"""
    ESCAPE = 1
    KEY_1 = 2
    KEY_2 = 3
    KEY_3 = 4
    KEY_4 = 5
    KEY_5 = 6
    KEY_6 = 7
    KEY_7 = 8
    KEY_8 = 9
    KEY_9 = 10
    KEY_0 = 11
    BACKSPACE = 14
    TAB = 15
    Q = 16
    W = 17
    E = 18
    R = 19
    T = 20
    ENTER = 28
    LEFTCTRL = 29
    A = 30
    S = 31
    D = 32
    F = 33
    LEFTSHIFT = 42
    LEFTALT = 56
    SPACE = 57
    F1 = 59
    F2 = 60
    F3 = 61
    F4 = 62
    F5 = 63
    F6 = 64
    F7 = 65
    F8 = 66
    F9 = 67
    F10 = 68
    F11 = 87
    F12 = 88
    LEFTMETA = 125  # Super/Windows key


@dataclass
class Hotkey:
    """Hotkey definition"""
    modifiers: List[str]  # ctrl, alt, shift, super
    key: str
    action: str
    description: str


class InputService:
    """Main input handling service"""
    
    DEFAULT_HOTKEYS = [
        Hotkey(['super'], 'space', 'agent_activate', 'Activate AI Agent'),
        Hotkey(['super'], 'a', 'app_launcher', 'Open App Launcher'),
        Hotkey(['super'], 't', 'terminal', 'Open Terminal'),
        Hotkey(['super'], 'l', 'lock', 'Lock Screen'),
        Hotkey(['super'], 'q', 'close_window', 'Close Current Window'),
        Hotkey(['ctrl', 'alt'], 't', 'terminal', 'Open Terminal'),
        Hotkey(['ctrl', 'alt'], 'delete', 'system_menu', 'System Menu'),
        Hotkey(['alt'], 'f4', 'close_window', 'Close Window'),
        Hotkey(['alt'], 'tab', 'switch_window', 'Switch Windows'),
        Hotkey([], 'Print', 'screenshot', 'Take Screenshot'),
        # Volume keys
        Hotkey([], 'XF86AudioRaiseVolume', 'volume_up', 'Volume Up'),
        Hotkey([], 'XF86AudioLowerVolume', 'volume_down', 'Volume Down'),
        Hotkey([], 'XF86AudioMute', 'volume_mute', 'Mute'),
        # Brightness keys
        Hotkey([], 'XF86MonBrightnessUp', 'brightness_up', 'Brightness Up'),
        Hotkey([], 'XF86MonBrightnessDown', 'brightness_down', 'Brightness Down'),
    ]
    
    def __init__(self):
        self.hotkeys = self.DEFAULT_HOTKEYS.copy()
        self.running = False
        self._input_devices: List[str] = []
        self._pressed_keys: set = set()
        
        # Load custom hotkeys
        self._load_config()
    
    def _load_config(self):
        """Load hotkey configuration"""
        config_path = Path('/etc/aios/input.json')
        if config_path.exists():
            try:
                with open(config_path) as f:
                    data = json.load(f)
                for hk in data.get('hotkeys', []):
                    self.hotkeys.append(Hotkey(
                        modifiers=hk.get('modifiers', []),
                        key=hk['key'],
                        action=hk['action'],
                        description=hk.get('description', '')
                    ))
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
    
    def _discover_devices(self) -> List[str]:
        """Discover input devices"""
        devices = []
        input_path = Path('/dev/input')
        
        for event in input_path.glob('event*'):
            # Check if it's a keyboard
            try:
                sysfs = Path(f'/sys/class/input/{event.name}/device/capabilities/key')
                if sysfs.exists():
                    caps = sysfs.read_text().strip()
                    # Has keyboard keys
                    if caps and int(caps.replace(' ', ''), 16) > 0:
                        devices.append(str(event))
            except:
                pass
        
        return devices
    
    async def start(self):
        """Start input service"""
        logger.info("Starting AI-OS Input Service...")
        
        self._input_devices = self._discover_devices()
        logger.info(f"Found input devices: {self._input_devices}")
        
        if not self._input_devices:
            logger.warning("No input devices found")
            return
        
        self.running = True
        
        # Start device readers
        tasks = [self._read_device(dev) for dev in self._input_devices]
        await asyncio.gather(*tasks)
    
    async def _read_device(self, device_path: str):
        """Read events from input device"""
        try:
            # Open device
            fd = os.open(device_path, os.O_RDONLY | os.O_NONBLOCK)
            
            while self.running:
                try:
                    # Read input event (24 bytes: timeval + type + code + value)
                    data = os.read(fd, 24)
                    if len(data) == 24:
                        # Parse event
                        tv_sec, tv_usec, ev_type, code, value = struct.unpack('qqHHi', data)
                        
                        # Key event (type 1)
                        if ev_type == 1:
                            if value == 1:  # Key press
                                self._pressed_keys.add(code)
                                await self._check_hotkey(code)
                            elif value == 0:  # Key release
                                self._pressed_keys.discard(code)
                
                except BlockingIOError:
                    await asyncio.sleep(0.01)
                except Exception as e:
                    logger.debug(f"Read error: {e}")
                    await asyncio.sleep(0.1)
                    
        except Exception as e:
            logger.error(f"Failed to open {device_path}: {e}")
        finally:
            try:
                os.close(fd)
            except:
                pass
    
    async def _check_hotkey(self, key_code: int):
        """Check if current key state matches a hotkey"""
        # Check modifiers
        ctrl = KeyCode.LEFTCTRL.value in self._pressed_keys
        alt = KeyCode.LEFTALT.value in self._pressed_keys
        shift = KeyCode.LEFTSHIFT.value in self._pressed_keys
        super_key = KeyCode.LEFTMETA.value in self._pressed_keys
        
        for hotkey in self.hotkeys:
            # Check modifiers match
            mods_match = (
                ('ctrl' in hotkey.modifiers) == ctrl and
                ('alt' in hotkey.modifiers) == alt and
                ('shift' in hotkey.modifiers) == shift and
                ('super' in hotkey.modifiers) == super_key
            )
            
            if not mods_match:
                continue
            
            # Check key (this is simplified - would need proper key name mapping)
            # For now, just trigger on specific codes
            if self._key_matches(hotkey.key, key_code):
                logger.info(f"Triggered hotkey: {hotkey.action}")
                await self._execute_action(hotkey.action)
                break
    
    def _key_matches(self, key_name: str, code: int) -> bool:
        """Check if key name matches code"""
        key_map = {
            'space': KeyCode.SPACE.value,
            'a': KeyCode.A.value,
            't': KeyCode.T.value,
            'l': 38,  # L key
            'q': KeyCode.Q.value,
            'escape': KeyCode.ESCAPE.value,
            'f1': KeyCode.F1.value,
            'f2': KeyCode.F2.value,
            'f3': KeyCode.F3.value,
            'f4': KeyCode.F4.value,
            'tab': KeyCode.TAB.value,
        }
        return key_map.get(key_name.lower()) == code
    
    async def _execute_action(self, action: str):
        """Execute hotkey action"""
        try:
            if action == 'agent_activate':
                await self._send_to_agent('{"cmd": "activate"}')
            
            elif action == 'terminal':
                os.system('weston-terminal &')
            
            elif action == 'lock':
                os.system('loginctl lock-session')
            
            elif action == 'screenshot':
                os.system('grim /tmp/screenshot-$(date +%s).png &')
            
            elif action == 'volume_up':
                os.system('amixer set Master 5%+')
            
            elif action == 'volume_down':
                os.system('amixer set Master 5%-')
            
            elif action == 'volume_mute':
                os.system('amixer set Master toggle')
            
            elif action == 'brightness_up':
                await self._adjust_brightness(10)
            
            elif action == 'brightness_down':
                await self._adjust_brightness(-10)
            
            elif action == 'close_window':
                # Would need compositor integration
                pass
            
            elif action == 'switch_window':
                # Would need compositor integration
                pass
            
        except Exception as e:
            logger.error(f"Action error: {e}")
    
    async def _send_to_agent(self, message: str):
        """Send message to agent daemon"""
        try:
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            sock.connect('/run/aios/agent.sock')
            data = message.encode()
            sock.send(struct.pack('!I', len(data)) + data)
            sock.close()
        except:
            pass
    
    async def _adjust_brightness(self, delta: int):
        """Adjust screen brightness"""
        try:
            for device in Path('/sys/class/backlight').iterdir():
                current = int((device / 'brightness').read_text().strip())
                max_val = int((device / 'max_brightness').read_text().strip())
                
                new_val = current + (max_val * delta // 100)
                new_val = max(0, min(max_val, new_val))
                
                (device / 'brightness').write_text(str(new_val))
                break
        except Exception as e:
            logger.error(f"Brightness error: {e}")
    
    def stop(self):
        """Stop service"""
        self.running = False


def main():
    service = InputService()
    
    def signal_handler(sig, frame):
        service.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    asyncio.run(service.start())


if __name__ == '__main__':
    main()
