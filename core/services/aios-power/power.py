#!/usr/bin/env python3
"""
AI-OS Power Manager
Handles power states, battery monitoring, and power profiles.
"""

import os
import sys
import asyncio
import signal
import json
import socket
import struct
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from enum import Enum
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aios-power')


class PowerProfile(Enum):
    PERFORMANCE = "performance"
    BALANCED = "balanced"
    POWERSAVE = "powersave"


class PowerState(Enum):
    RUNNING = "running"
    SUSPENDED = "suspended"
    HIBERNATED = "hibernated"


@dataclass
class BatteryInfo:
    present: bool
    level: int  # 0-100
    status: str  # Charging, Discharging, Full, Not charging
    time_to_empty: int  # minutes
    time_to_full: int  # minutes
    health: str
    technology: str


@dataclass
class PowerConfig:
    low_battery_threshold: int = 15
    critical_battery_threshold: int = 5
    auto_suspend_ac_minutes: int = 0  # 0 = disabled
    auto_suspend_battery_minutes: int = 15
    dim_screen_on_battery: bool = True
    power_button_action: str = "suspend"  # suspend, hibernate, poweroff, nothing
    lid_close_action: str = "suspend"
    default_profile: PowerProfile = PowerProfile.BALANCED


class PowerManager:
    """AI-OS Power Manager"""
    
    CONFIG_PATH = Path("/etc/aios/power.json")
    SOCKET_PATH = "/run/aios/power.sock"
    
    def __init__(self):
        self.config = PowerConfig()
        self.current_profile = PowerProfile.BALANCED
        self.running = False
        self._load_config()
    
    def _load_config(self):
        """Load power configuration"""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH) as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(self.config, key):
                        setattr(self.config, key, value)
                self.current_profile = PowerProfile(
                    data.get('default_profile', 'balanced')
                )
            except Exception as e:
                logger.warning(f"Failed to load config: {e}")
    
    def _save_config(self):
        """Save power configuration"""
        try:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                'low_battery_threshold': self.config.low_battery_threshold,
                'critical_battery_threshold': self.config.critical_battery_threshold,
                'auto_suspend_ac_minutes': self.config.auto_suspend_ac_minutes,
                'auto_suspend_battery_minutes': self.config.auto_suspend_battery_minutes,
                'dim_screen_on_battery': self.config.dim_screen_on_battery,
                'power_button_action': self.config.power_button_action,
                'lid_close_action': self.config.lid_close_action,
                'default_profile': self.current_profile.value
            }
            with open(self.CONFIG_PATH, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")
    
    # ==================== Battery ====================
    
    def get_battery_info(self) -> Optional[BatteryInfo]:
        """Get battery information"""
        bat_paths = list(Path("/sys/class/power_supply").glob("BAT*"))
        
        if not bat_paths:
            return None
        
        bat_path = bat_paths[0]
        
        try:
            def read_file(name: str, default: str = "") -> str:
                path = bat_path / name
                if path.exists():
                    return path.read_text().strip()
                return default
            
            present = read_file("present", "0") == "1"
            if not present:
                return BatteryInfo(
                    present=False, level=0, status="Unknown",
                    time_to_empty=0, time_to_full=0, health="Unknown", technology=""
                )
            
            # Get capacity
            level = int(read_file("capacity", "0"))
            
            # Get status
            status = read_file("status", "Unknown")
            
            # Get time estimates
            energy_now = int(read_file("energy_now", "0"))
            energy_full = int(read_file("energy_full", "0"))
            power_now = int(read_file("power_now", "1"))
            
            time_to_empty = 0
            time_to_full = 0
            
            if power_now > 0:
                if status == "Discharging":
                    time_to_empty = (energy_now * 60) // power_now
                elif status == "Charging":
                    time_to_full = ((energy_full - energy_now) * 60) // power_now
            
            return BatteryInfo(
                present=True,
                level=level,
                status=status,
                time_to_empty=time_to_empty,
                time_to_full=time_to_full,
                health=read_file("health", "Unknown"),
                technology=read_file("technology", "Unknown")
            )
            
        except Exception as e:
            logger.error(f"Failed to get battery info: {e}")
            return None
    
    def is_on_battery(self) -> bool:
        """Check if running on battery"""
        ac_paths = list(Path("/sys/class/power_supply").glob("AC*")) + \
                   list(Path("/sys/class/power_supply").glob("ADP*"))
        
        for ac_path in ac_paths:
            online_file = ac_path / "online"
            if online_file.exists():
                if online_file.read_text().strip() == "1":
                    return False
        
        # No AC adapter found or all offline
        battery = self.get_battery_info()
        return battery is not None and battery.present
    
    # ==================== Power Profiles ====================
    
    def set_profile(self, profile: PowerProfile) -> bool:
        """Set power profile"""
        self.current_profile = profile
        
        try:
            # Try powerprofiles daemon
            result = os.system(f'powerprofilesctl set {profile.value}')
            if result == 0:
                logger.info(f"Set power profile: {profile.value}")
                return True
        except:
            pass
        
        try:
            # Try CPU governor directly
            if profile == PowerProfile.PERFORMANCE:
                governor = "performance"
            elif profile == PowerProfile.POWERSAVE:
                governor = "powersave"
            else:
                governor = "schedutil"
            
            for cpu in Path("/sys/devices/system/cpu").glob("cpu[0-9]*"):
                governor_path = cpu / "cpufreq/scaling_governor"
                if governor_path.exists():
                    governor_path.write_text(governor)
            
            logger.info(f"Set CPU governor: {governor}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to set profile: {e}")
            return False
    
    def get_profile(self) -> PowerProfile:
        """Get current power profile"""
        try:
            # Try powerprofiles daemon
            import subprocess
            result = subprocess.run(['powerprofilesctl', 'get'], capture_output=True, text=True)
            if result.returncode == 0:
                profile_str = result.stdout.strip()
                return PowerProfile(profile_str)
        except:
            pass
        
        return self.current_profile
    
    # ==================== Power Actions ====================
    
    def suspend(self) -> bool:
        """Suspend to RAM"""
        logger.info("Suspending system...")
        return os.system('systemctl suspend') == 0
    
    def hibernate(self) -> bool:
        """Hibernate to disk"""
        logger.info("Hibernating system...")
        return os.system('systemctl hibernate') == 0
    
    def poweroff(self) -> bool:
        """Power off the system"""
        logger.info("Powering off...")
        return os.system('systemctl poweroff') == 0
    
    def reboot(self) -> bool:
        """Reboot the system"""
        logger.info("Rebooting...")
        return os.system('systemctl reboot') == 0
    
    def lock_screen(self) -> bool:
        """Lock the screen"""
        # Try various lock mechanisms
        for cmd in ['loginctl lock-session', 'swaylock', 'i3lock', 'xdg-screensaver lock']:
            if os.system(cmd) == 0:
                return True
        return False
    
    # ==================== Screen/Backlight ====================
    
    def get_brightness(self) -> int:
        """Get screen brightness (0-100)"""
        try:
            for device in Path("/sys/class/backlight").iterdir():
                current = int((device / "brightness").read_text().strip())
                max_val = int((device / "max_brightness").read_text().strip())
                return int(current * 100 / max_val)
        except:
            return -1
    
    def set_brightness(self, level: int) -> bool:
        """Set screen brightness (0-100)"""
        try:
            for device in Path("/sys/class/backlight").iterdir():
                max_val = int((device / "max_brightness").read_text().strip())
                value = int(max_val * level / 100)
                (device / "brightness").write_text(str(value))
                return True
        except Exception as e:
            logger.error(f"Failed to set brightness: {e}")
            return False
    
    def dim_screen(self, percent: int = 50):
        """Dim screen by percentage"""
        current = self.get_brightness()
        if current > 0:
            new_level = max(5, current - percent)
            self.set_brightness(new_level)
    
    # ==================== Monitoring ====================
    
    async def _battery_monitor(self):
        """Monitor battery and take action on low battery"""
        while self.running:
            battery = self.get_battery_info()
            
            if battery and battery.present and battery.status == "Discharging":
                if battery.level <= self.config.critical_battery_threshold:
                    logger.critical(f"Critical battery: {battery.level}%")
                    # Show critical notification
                    self._notify("Critical Battery", 
                               f"Battery at {battery.level}%. System will suspend soon.",
                               "critical")
                    await asyncio.sleep(30)
                    if battery.level <= self.config.critical_battery_threshold:
                        self.suspend()
                        
                elif battery.level <= self.config.low_battery_threshold:
                    logger.warning(f"Low battery: {battery.level}%")
                    self._notify("Low Battery", 
                               f"Battery at {battery.level}%. Please connect charger.",
                               "normal")
            
            await asyncio.sleep(60)  # Check every minute
    
    def _notify(self, title: str, message: str, urgency: str = "normal"):
        """Send notification"""
        try:
            os.system(f'notify-send -u {urgency} "{title}" "{message}"')
        except:
            pass
    
    async def start_server(self):
        """Start power manager daemon"""
        logger.info("Starting AI-OS Power Manager...")
        
        os.makedirs(os.path.dirname(self.SOCKET_PATH), exist_ok=True)
        
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)
        
        self.running = True
        
        # Start battery monitor
        asyncio.create_task(self._battery_monitor())
        
        # Apply default profile
        self.set_profile(self.current_profile)
        
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
        
        if cmd == 'battery':
            battery = self.get_battery_info()
            if battery:
                return {
                    'status': 'ok',
                    'battery': {
                        'present': battery.present,
                        'level': battery.level,
                        'status': battery.status,
                        'time_to_empty': battery.time_to_empty,
                        'time_to_full': battery.time_to_full
                    }
                }
            return {'status': 'ok', 'battery': None}
        
        elif cmd == 'profile':
            if 'set' in request:
                profile = PowerProfile(request['set'])
                success = self.set_profile(profile)
                return {'status': 'ok' if success else 'error'}
            else:
                return {'status': 'ok', 'profile': self.get_profile().value}
        
        elif cmd == 'suspend':
            success = self.suspend()
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'hibernate':
            success = self.hibernate()
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'poweroff':
            success = self.poweroff()
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'reboot':
            success = self.reboot()
            return {'status': 'ok' if success else 'error'}
        
        elif cmd == 'brightness':
            if 'set' in request:
                success = self.set_brightness(request['set'])
                return {'status': 'ok' if success else 'error'}
            else:
                return {'status': 'ok', 'brightness': self.get_brightness()}
        
        else:
            return {'status': 'error', 'message': f'Unknown command: {cmd}'}
    
    def stop(self):
        self.running = False
        if os.path.exists(self.SOCKET_PATH):
            os.unlink(self.SOCKET_PATH)


def main():
    manager = PowerManager()
    
    def signal_handler(sig, frame):
        manager.stop()
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    asyncio.run(manager.start_server())


if __name__ == '__main__':
    main()
