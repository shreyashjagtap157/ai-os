#!/usr/bin/env python3
"""
AI-OS Hardware Abstraction Layer (HAL)
Provides unified interface to hardware across different platforms.
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import subprocess

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aios-hal')


class Platform(Enum):
    """Supported platforms"""
    GENERIC_X86_64 = "x86_64"
    GENERIC_ARM64 = "aarch64"
    RASPBERRY_PI = "rpi"
    ROCK_PI = "rockpi"
    JETSON = "jetson"
    UNKNOWN = "unknown"


@dataclass
class GPUInfo:
    """GPU information"""
    vendor: str
    model: str
    driver: str
    memory_mb: int = 0


@dataclass
class DisplayInfo:
    """Display information"""
    name: str
    resolution: tuple
    refresh_rate: int
    connected: bool
    primary: bool = False


class HAL:
    """
    Hardware Abstraction Layer.
    Provides platform-independent hardware access.
    """
    
    def __init__(self):
        self._platform = self._detect_platform()
        self._gpu = self._detect_gpu()
        logger.info(f"HAL initialized on platform: {self._platform.value}")
    
    @property
    def platform(self) -> Platform:
        return self._platform
    
    def _detect_platform(self) -> Platform:
        """Detect the hardware platform"""
        # Check architecture
        import platform as plat
        arch = plat.machine()
        
        # Check for specific platforms
        if os.path.exists('/sys/firmware/devicetree/base/model'):
            with open('/sys/firmware/devicetree/base/model') as f:
                model = f.read().strip('\x00')
                
                if 'Raspberry Pi' in model:
                    return Platform.RASPBERRY_PI
                elif 'NVIDIA Jetson' in model:
                    return Platform.JETSON
                elif 'Rock' in model:
                    return Platform.ROCK_PI
        
        if arch == 'x86_64':
            return Platform.GENERIC_X86_64
        elif arch == 'aarch64':
            return Platform.GENERIC_ARM64
        
        return Platform.UNKNOWN
    
    def _detect_gpu(self) -> Optional[GPUInfo]:
        """Detect GPU"""
        try:
            # Try using DRM
            drm_path = Path('/sys/class/drm')
            if drm_path.exists():
                for card in drm_path.iterdir():
                    if card.name.startswith('card') and not '-' in card.name:
                        uevent = card / 'device' / 'uevent'
                        if uevent.exists():
                            with open(uevent) as f:
                                content = f.read()
                                
                            vendor = 'Unknown'
                            model = 'Unknown'
                            driver = 'Unknown'
                            
                            for line in content.split('\n'):
                                if line.startswith('DRIVER='):
                                    driver = line.split('=')[1]
                            
                            return GPUInfo(
                                vendor=vendor,
                                model=model,
                                driver=driver
                            )
        except Exception as e:
            logger.warning(f"GPU detection failed: {e}")
        
        return None
    
    # ==================== Display ====================
    
    def get_displays(self) -> List[DisplayInfo]:
        """Get connected displays"""
        displays = []
        
        try:
            drm_path = Path('/sys/class/drm')
            for connector in drm_path.iterdir():
                if '-' in connector.name:  # e.g., card0-HDMI-A-1
                    status_file = connector / 'status'
                    if status_file.exists():
                        with open(status_file) as f:
                            connected = f.read().strip() == 'connected'
                        
                        modes_file = connector / 'modes'
                        resolution = (0, 0)
                        if modes_file.exists():
                            with open(modes_file) as f:
                                first_mode = f.readline().strip()
                                if 'x' in first_mode:
                                    parts = first_mode.split('x')
                                    resolution = (int(parts[0]), int(parts[1].split('i')[0].split('p')[0]))
                        
                        displays.append(DisplayInfo(
                            name=connector.name,
                            resolution=resolution,
                            refresh_rate=60,
                            connected=connected
                        ))
        except Exception as e:
            logger.warning(f"Display detection failed: {e}")
        
        return displays
    
    def set_display_brightness(self, level: int, display: str = None) -> bool:
        """Set display brightness"""
        try:
            backlight_path = Path('/sys/class/backlight')
            if not backlight_path.exists():
                return False
            
            for device in backlight_path.iterdir():
                max_file = device / 'max_brightness'
                brightness_file = device / 'brightness'
                
                if not max_file.exists() or not brightness_file.exists():
                    continue
                
                with open(max_file) as f:
                    max_val = int(f.read().strip())
                
                new_val = int(max_val * level / 100)
                with open(brightness_file, 'w') as f:
                    f.write(str(new_val))
                
                return True
        except Exception as e:
            logger.error(f"Brightness control failed: {e}")
        
        return False
    
    # ==================== Audio ====================
    
    def get_audio_devices(self) -> List[Dict[str, Any]]:
        """Get audio devices"""
        devices = []
        
        try:
            result = subprocess.run(
                ['aplay', '-l'],
                capture_output=True, text=True
            )
            
            for line in result.stdout.split('\n'):
                if line.startswith('card '):
                    parts = line.split(':')
                    if len(parts) >= 2:
                        devices.append({
                            'name': parts[1].strip().split(',')[0],
                            'type': 'output'
                        })
        except:
            pass
        
        return devices
    
    def set_volume(self, level: int, device: str = 'Master') -> bool:
        """Set audio volume"""
        try:
            subprocess.run(
                ['amixer', 'set', device, f'{level}%'],
                capture_output=True, check=True
            )
            return True
        except:
            return False
    
    def mute(self, mute: bool = True, device: str = 'Master') -> bool:
        """Mute/unmute audio"""
        try:
            state = 'mute' if mute else 'unmute'
            subprocess.run(
                ['amixer', 'set', device, state],
                capture_output=True, check=True
            )
            return True
        except:
            return False
    
    # ==================== Input ====================
    
    def get_input_devices(self) -> List[Dict[str, Any]]:
        """Get input devices"""
        devices = []
        
        try:
            input_path = Path('/sys/class/input')
            for device in input_path.iterdir():
                if device.name.startswith('event'):
                    name_file = device / 'device' / 'name'
                    if name_file.exists():
                        with open(name_file) as f:
                            name = f.read().strip()
                        
                        device_type = 'unknown'
                        lower_name = name.lower()
                        if 'keyboard' in lower_name:
                            device_type = 'keyboard'
                        elif 'mouse' in lower_name or 'trackpad' in lower_name or 'touchpad' in lower_name:
                            device_type = 'pointer'
                        elif 'touch' in lower_name:
                            device_type = 'touch'
                        
                        devices.append({
                            'name': name,
                            'path': f'/dev/input/{device.name}',
                            'type': device_type
                        })
        except Exception as e:
            logger.warning(f"Input device detection failed: {e}")
        
        return devices
    
    # ==================== Network ====================
    
    def get_network_interfaces(self) -> List[Dict[str, Any]]:
        """Get network interfaces"""
        interfaces = []
        
        try:
            net_path = Path('/sys/class/net')
            for iface in net_path.iterdir():
                if iface.name == 'lo':
                    continue
                
                iface_type = 'ethernet'
                if iface.name.startswith('wl'):
                    iface_type = 'wifi'
                elif iface.name.startswith('docker') or iface.name.startswith('br-'):
                    iface_type = 'virtual'
                
                carrier = False
                carrier_file = iface / 'carrier'
                if carrier_file.exists():
                    try:
                        with open(carrier_file) as f:
                            carrier = f.read().strip() == '1'
                    except:
                        pass
                
                interfaces.append({
                    'name': iface.name,
                    'type': iface_type,
                    'up': carrier
                })
        except Exception as e:
            logger.warning(f"Network detection failed: {e}")
        
        return interfaces
    
    def set_wifi(self, enable: bool) -> bool:
        """Enable/disable WiFi"""
        try:
            state = 'on' if enable else 'off'
            subprocess.run(['nmcli', 'radio', 'wifi', state], check=True)
            return True
        except:
            # Try rfkill as fallback
            try:
                action = 'unblock' if enable else 'block'
                subprocess.run(['rfkill', action, 'wifi'], check=True)
                return True
            except:
                return False
    
    def set_bluetooth(self, enable: bool) -> bool:
        """Enable/disable Bluetooth"""
        try:
            action = 'power' if enable else 'power'
            state = 'on' if enable else 'off'
            subprocess.run(['bluetoothctl', action, state], check=True)
            return True
        except:
            try:
                action = 'unblock' if enable else 'block'
                subprocess.run(['rfkill', action, 'bluetooth'], check=True)
                return True
            except:
                return False
    
    # ==================== Power ====================
    
    def get_power_status(self) -> Dict[str, Any]:
        """Get power/battery status"""
        status = {
            'ac_connected': True,
            'battery_present': False,
            'battery_level': 100,
            'battery_status': 'unknown'
        }
        
        try:
            power_path = Path('/sys/class/power_supply')
            
            for supply in power_path.iterdir():
                type_file = supply / 'type'
                if type_file.exists():
                    with open(type_file) as f:
                        supply_type = f.read().strip()
                    
                    if supply_type == 'Battery':
                        status['battery_present'] = True
                        
                        capacity_file = supply / 'capacity'
                        if capacity_file.exists():
                            with open(capacity_file) as f:
                                status['battery_level'] = int(f.read().strip())
                        
                        status_file = supply / 'status'
                        if status_file.exists():
                            with open(status_file) as f:
                                status['battery_status'] = f.read().strip()
                    
                    elif supply_type == 'Mains':
                        online_file = supply / 'online'
                        if online_file.exists():
                            with open(online_file) as f:
                                status['ac_connected'] = f.read().strip() == '1'
        except Exception as e:
            logger.warning(f"Power status detection failed: {e}")
        
        return status
    
    def shutdown(self, reboot: bool = False) -> bool:
        """Shutdown or reboot"""
        try:
            cmd = 'reboot' if reboot else 'poweroff'
            subprocess.run(['systemctl', cmd], check=True)
            return True
        except:
            return False
    
    def suspend(self) -> bool:
        """Suspend to RAM"""
        try:
            subprocess.run(['systemctl', 'suspend'], check=True)
            return True
        except:
            return False
    
    # ==================== System Info ====================
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        import platform as plat
        
        info = {
            'platform': self._platform.value,
            'arch': plat.machine(),
            'kernel': plat.release(),
            'hostname': plat.node()
        }
        
        # CPU info
        try:
            with open('/proc/cpuinfo') as f:
                for line in f:
                    if line.startswith('model name'):
                        info['cpu'] = line.split(':')[1].strip()
                        break
            
            info['cpu_cores'] = os.cpu_count()
        except:
            pass
        
        # Memory info
        try:
            with open('/proc/meminfo') as f:
                for line in f:
                    if line.startswith('MemTotal'):
                        info['memory_mb'] = int(line.split()[1]) // 1024
                    elif line.startswith('MemAvailable'):
                        info['memory_available_mb'] = int(line.split()[1]) // 1024
        except:
            pass
        
        # Disk info
        try:
            stat = os.statvfs('/')
            info['disk_total_gb'] = (stat.f_blocks * stat.f_frsize) // (1024**3)
            info['disk_free_gb'] = (stat.f_bfree * stat.f_frsize) // (1024**3)
        except:
            pass
        
        # GPU
        if self._gpu:
            info['gpu'] = {
                'driver': self._gpu.driver,
                'vendor': self._gpu.vendor,
                'model': self._gpu.model
            }
        
        return info


# Global HAL instance
hal = HAL()


def main():
    """CLI for HAL testing"""
    import argparse
    
    parser = argparse.ArgumentParser(description='AI-OS Hardware Abstraction Layer')
    parser.add_argument('command', choices=[
        'info', 'displays', 'audio', 'input', 'network', 'power'
    ])
    
    args = parser.parse_args()
    
    if args.command == 'info':
        print(json.dumps(hal.get_system_info(), indent=2))
    elif args.command == 'displays':
        for d in hal.get_displays():
            print(f"{d.name}: {d.resolution} @ {d.refresh_rate}Hz (connected: {d.connected})")
    elif args.command == 'audio':
        for d in hal.get_audio_devices():
            print(f"{d['name']} ({d['type']})")
    elif args.command == 'input':
        for d in hal.get_input_devices():
            print(f"{d['name']} ({d['type']}): {d['path']}")
    elif args.command == 'network':
        for i in hal.get_network_interfaces():
            print(f"{i['name']} ({i['type']}): {'up' if i['up'] else 'down'}")
    elif args.command == 'power':
        print(json.dumps(hal.get_power_status(), indent=2))


if __name__ == '__main__':
    main()
