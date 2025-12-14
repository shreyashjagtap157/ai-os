#!/usr/bin/env python3
"""
AI-OS Network Manager
Handles WiFi, Ethernet, Bluetooth, and VPN configuration.
"""

import os
import subprocess
import json
from dataclasses import dataclass
from typing import List, Dict, Optional, Any
from pathlib import Path
import logging

logger = logging.getLogger('aios-network')


@dataclass
class NetworkInterface:
    """Network interface information"""
    name: str
    type: str  # ethernet, wifi, loopback
    state: str  # up, down, dormant
    mac_address: str = ""
    ip_address: str = ""
    gateway: str = ""
    dns: List[str] = None


@dataclass
class WifiNetwork:
    """WiFi network information"""
    ssid: str
    signal: int
    security: str
    connected: bool = False
    saved: bool = False


@dataclass
class BluetoothDevice:
    """Bluetooth device information"""
    address: str
    name: str
    paired: bool
    connected: bool
    device_type: str = "unknown"


class NetworkManager:
    """AI-OS Network Manager"""
    
    def __init__(self):
        self._check_tools()
    
    def _check_tools(self):
        """Check for required tools"""
        self.has_nmcli = self._cmd_exists('nmcli')
        self.has_iw = self._cmd_exists('iw')
        self.has_bluetoothctl = self._cmd_exists('bluetoothctl')
    
    def _cmd_exists(self, cmd: str) -> bool:
        """Check if a command exists"""
        return subprocess.run(['which', cmd], capture_output=True).returncode == 0
    
    def _run(self, cmd: List[str], timeout: int = 10) -> Optional[str]:
        """Run a command and return output"""
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return result.stdout
        except Exception as e:
            logger.error(f"Command failed: {' '.join(cmd)}: {e}")
            return None
    
    # ==================== General ====================
    
    def get_interfaces(self) -> List[NetworkInterface]:
        """Get all network interfaces"""
        interfaces = []
        
        try:
            for iface in Path('/sys/class/net').iterdir():
                name = iface.name
                
                # Get type
                if (iface / 'wireless').exists():
                    itype = 'wifi'
                elif name.startswith('eth') or name.startswith('en'):
                    itype = 'ethernet'
                elif name == 'lo':
                    itype = 'loopback'
                else:
                    itype = 'unknown'
                
                # Get state
                state = (iface / 'operstate').read_text().strip()
                
                # Get MAC
                mac = (iface / 'address').read_text().strip()
                
                interfaces.append(NetworkInterface(
                    name=name,
                    type=itype,
                    state=state,
                    mac_address=mac
                ))
        except Exception as e:
            logger.error(f"Failed to get interfaces: {e}")
        
        return interfaces
    
    def get_connection_status(self) -> Dict[str, Any]:
        """Get overall connection status"""
        if self.has_nmcli:
            output = self._run(['nmcli', '-t', '-f', 'TYPE,STATE,CONNECTION', 'device'])
            if output:
                for line in output.strip().split('\n'):
                    parts = line.split(':')
                    if len(parts) >= 3 and parts[1] == 'connected':
                        return {
                            'connected': True,
                            'type': parts[0],
                            'connection': parts[2]
                        }
        
        return {'connected': False}
    
    # ==================== WiFi ====================
    
    def scan_wifi(self) -> List[WifiNetwork]:
        """Scan for WiFi networks"""
        networks = []
        
        if self.has_nmcli:
            # Trigger rescan
            self._run(['nmcli', 'device', 'wifi', 'rescan'])
            
            output = self._run(['nmcli', '-t', '-f', 'ACTIVE,SSID,SIGNAL,SECURITY', 'device', 'wifi', 'list'])
            if output:
                for line in output.strip().split('\n'):
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[1]:  # Has SSID
                        networks.append(WifiNetwork(
                            ssid=parts[1],
                            signal=int(parts[2]) if parts[2].isdigit() else 0,
                            security=parts[3],
                            connected=parts[0] == 'yes'
                        ))
        
        return networks
    
    def connect_wifi(self, ssid: str, password: Optional[str] = None) -> bool:
        """Connect to a WiFi network"""
        if not self.has_nmcli:
            return False
        
        cmd = ['nmcli', 'device', 'wifi', 'connect', ssid]
        if password:
            cmd.extend(['password', password])
        
        result = subprocess.run(cmd, capture_output=True)
        return result.returncode == 0
    
    def disconnect_wifi(self) -> bool:
        """Disconnect from current WiFi"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run(['nmcli', 'device', 'disconnect', 'wlan0'], capture_output=True)
        return result.returncode == 0
    
    def wifi_enabled(self) -> bool:
        """Check if WiFi is enabled"""
        if self.has_nmcli:
            output = self._run(['nmcli', 'radio', 'wifi'])
            return output and 'enabled' in output.lower()
        return False
    
    def set_wifi_enabled(self, enabled: bool) -> bool:
        """Enable/disable WiFi"""
        if not self.has_nmcli:
            return False
        
        state = 'on' if enabled else 'off'
        result = subprocess.run(['nmcli', 'radio', 'wifi', state], capture_output=True)
        return result.returncode == 0
    
    def get_saved_networks(self) -> List[str]:
        """Get list of saved WiFi networks"""
        if not self.has_nmcli:
            return []
        
        output = self._run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection'])
        if output:
            return [
                line.split(':')[0]
                for line in output.strip().split('\n')
                if ':802-11-wireless' in line
            ]
        return []
    
    def forget_network(self, name: str) -> bool:
        """Forget a saved network"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run(['nmcli', 'connection', 'delete', name], capture_output=True)
        return result.returncode == 0
    
    # ==================== Bluetooth ====================
    
    def scan_bluetooth(self, duration: int = 5) -> List[BluetoothDevice]:
        """Scan for Bluetooth devices"""
        devices = []
        
        if not self.has_bluetoothctl:
            return devices
        
        # Start scan
        subprocess.run(['bluetoothctl', 'scan', 'on'], capture_output=True, timeout=2)
        import time
        time.sleep(duration)
        subprocess.run(['bluetoothctl', 'scan', 'off'], capture_output=True, timeout=2)
        
        # Get devices
        output = self._run(['bluetoothctl', 'devices'])
        if output:
            for line in output.strip().split('\n'):
                if line.startswith('Device'):
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        devices.append(BluetoothDevice(
                            address=parts[1],
                            name=parts[2],
                            paired=False,
                            connected=False
                        ))
        
        return devices
    
    def get_paired_devices(self) -> List[BluetoothDevice]:
        """Get paired Bluetooth devices"""
        devices = []
        
        if not self.has_bluetoothctl:
            return devices
        
        output = self._run(['bluetoothctl', 'paired-devices'])
        if output:
            for line in output.strip().split('\n'):
                if line.startswith('Device'):
                    parts = line.split(' ', 2)
                    if len(parts) >= 3:
                        devices.append(BluetoothDevice(
                            address=parts[1],
                            name=parts[2],
                            paired=True,
                            connected=False  # Would need to check
                        ))
        
        return devices
    
    def connect_bluetooth(self, address: str) -> bool:
        """Connect to a Bluetooth device"""
        if not self.has_bluetoothctl:
            return False
        
        result = subprocess.run(['bluetoothctl', 'connect', address], capture_output=True, timeout=10)
        return result.returncode == 0
    
    def disconnect_bluetooth(self, address: str) -> bool:
        """Disconnect from a Bluetooth device"""
        if not self.has_bluetoothctl:
            return False
        
        result = subprocess.run(['bluetoothctl', 'disconnect', address], capture_output=True)
        return result.returncode == 0
    
    def pair_bluetooth(self, address: str) -> bool:
        """Pair with a Bluetooth device"""
        if not self.has_bluetoothctl:
            return False
        
        # Trust first
        subprocess.run(['bluetoothctl', 'trust', address], capture_output=True)
        
        result = subprocess.run(['bluetoothctl', 'pair', address], capture_output=True, timeout=30)
        return result.returncode == 0
    
    def bluetooth_enabled(self) -> bool:
        """Check if Bluetooth is enabled"""
        if not self.has_bluetoothctl:
            return False
        
        output = self._run(['bluetoothctl', 'show'])
        return output and 'Powered: yes' in output
    
    def set_bluetooth_enabled(self, enabled: bool) -> bool:
        """Enable/disable Bluetooth"""
        if not self.has_bluetoothctl:
            return False
        
        state = 'on' if enabled else 'off'
        result = subprocess.run(['bluetoothctl', 'power', state], capture_output=True)
        return result.returncode == 0
    
    # ==================== VPN ====================
    
    def get_vpn_connections(self) -> List[str]:
        """Get available VPN connections"""
        if not self.has_nmcli:
            return []
        
        output = self._run(['nmcli', '-t', '-f', 'NAME,TYPE', 'connection'])
        if output:
            return [
                line.split(':')[0]
                for line in output.strip().split('\n')
                if ':vpn' in line
            ]
        return []
    
    def connect_vpn(self, name: str) -> bool:
        """Connect to a VPN"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run(['nmcli', 'connection', 'up', name], capture_output=True)
        return result.returncode == 0
    
    def disconnect_vpn(self, name: str) -> bool:
        """Disconnect from a VPN"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run(['nmcli', 'connection', 'down', name], capture_output=True)
        return result.returncode == 0
    
    # ==================== Hotspot ====================
    
    def create_hotspot(self, ssid: str, password: str) -> bool:
        """Create a WiFi hotspot"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run([
            'nmcli', 'device', 'wifi', 'hotspot',
            'ssid', ssid,
            'password', password
        ], capture_output=True)
        return result.returncode == 0
    
    def stop_hotspot(self) -> bool:
        """Stop the WiFi hotspot"""
        if not self.has_nmcli:
            return False
        
        result = subprocess.run(['nmcli', 'connection', 'down', 'Hotspot'], capture_output=True)
        return result.returncode == 0


# Example usage
if __name__ == '__main__':
    nm = NetworkManager()
    
    print("Network Interfaces:")
    for iface in nm.get_interfaces():
        print(f"  {iface.name}: {iface.type} ({iface.state})")
    
    print("\nConnection Status:", nm.get_connection_status())
    
    print("\nWiFi Networks:")
    for net in nm.scan_wifi():
        status = "●" if net.connected else "○"
        print(f"  {status} {net.ssid} ({net.signal}%) [{net.security}]")
    
    print("\nBluetooth Paired Devices:")
    for dev in nm.get_paired_devices():
        print(f"  {dev.name} ({dev.address})")
