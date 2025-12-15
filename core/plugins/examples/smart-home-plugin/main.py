"""
AI-OS Smart Home Plugin
Control smart home devices via Home Assistant or similar hubs
"""

import json
import logging
import asyncio
from typing import Dict, Any, List, Optional
from dataclasses import dataclass
from enum import Enum
import aiohttp

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    LIGHT = "light"
    SWITCH = "switch"
    THERMOSTAT = "climate"
    FAN = "fan"
    COVER = "cover"
    MEDIA_PLAYER = "media_player"
    UNKNOWN = "unknown"


@dataclass
class SmartDevice:
    entity_id: str
    name: str
    device_type: DeviceType
    state: str
    attributes: Dict[str, Any]


class SmartHomePlugin:
    """Smart home control plugin for AI-OS"""
    
    def __init__(self, config: Dict[str, Any]):
        self.hub_type = config.get("hub_type", "home_assistant")
        self.hub_url = config.get("hub_url", "http://localhost:8123")
        self.api_token = config.get("api_token", "")
        self.devices: Dict[str, SmartDevice] = {}
        self._session: Optional[aiohttp.ClientSession] = None
    
    async def initialize(self) -> bool:
        """Initialize connection to smart home hub"""
        try:
            self._session = aiohttp.ClientSession(
                headers={"Authorization": f"Bearer {self.api_token}"}
            )
            await self._refresh_devices()
            logger.info(f"Connected to {self.hub_type} at {self.hub_url}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to smart home hub: {e}")
            return False
    
    async def shutdown(self):
        """Cleanup resources"""
        if self._session:
            await self._session.close()
    
    async def _refresh_devices(self):
        """Refresh device list from hub"""
        if not self._session:
            return
            
        try:
            async with self._session.get(f"{self.hub_url}/api/states") as resp:
                if resp.status == 200:
                    states = await resp.json()
                    for state in states:
                        entity_id = state["entity_id"]
                        domain = entity_id.split(".")[0]
                        
                        device_type = {
                            "light": DeviceType.LIGHT,
                            "switch": DeviceType.SWITCH,
                            "climate": DeviceType.THERMOSTAT,
                            "fan": DeviceType.FAN,
                            "cover": DeviceType.COVER,
                            "media_player": DeviceType.MEDIA_PLAYER,
                        }.get(domain, DeviceType.UNKNOWN)
                        
                        self.devices[entity_id] = SmartDevice(
                            entity_id=entity_id,
                            name=state["attributes"].get("friendly_name", entity_id),
                            device_type=device_type,
                            state=state["state"],
                            attributes=state["attributes"]
                        )
        except Exception as e:
            logger.error(f"Failed to refresh devices: {e}")
    
    def _find_device(self, name: str) -> Optional[SmartDevice]:
        """Find device by name (fuzzy match)"""
        name_lower = name.lower()
        
        # Exact match first
        for device in self.devices.values():
            if device.name.lower() == name_lower:
                return device
        
        # Partial match
        for device in self.devices.values():
            if name_lower in device.name.lower():
                return device
        
        return None
    
    async def _call_service(self, domain: str, service: str, entity_id: str, 
                           data: Optional[Dict] = None) -> bool:
        """Call Home Assistant service"""
        if not self._session:
            return False
            
        try:
            payload = {"entity_id": entity_id}
            if data:
                payload.update(data)
                
            async with self._session.post(
                f"{self.hub_url}/api/services/{domain}/{service}",
                json=payload
            ) as resp:
                return resp.status == 200
        except Exception as e:
            logger.error(f"Service call failed: {e}")
            return False
    
    # ==================== Intent Handlers ====================
    
    async def handle_intent(self, intent: str, entities: Dict[str, str]) -> str:
        """Route intent to appropriate handler"""
        handlers = {
            "device_on": self._handle_device_on,
            "device_off": self._handle_device_off,
            "set_brightness": self._handle_set_brightness,
            "set_temperature": self._handle_set_temperature,
            "get_status": self._handle_get_status,
            "list_devices": self._handle_list_devices,
        }
        
        handler = handlers.get(intent)
        if handler:
            return await handler(entities)
        return "I don't know how to do that."
    
    async def _handle_device_on(self, entities: Dict[str, str]) -> str:
        device_name = entities.get("device", "")
        device = self._find_device(device_name)
        
        if not device:
            return f"I couldn't find a device called {device_name}"
        
        domain = device.entity_id.split(".")[0]
        success = await self._call_service(domain, "turn_on", device.entity_id)
        
        if success:
            return f"Turned on {device.name}"
        return f"Failed to turn on {device.name}"
    
    async def _handle_device_off(self, entities: Dict[str, str]) -> str:
        device_name = entities.get("device", "")
        device = self._find_device(device_name)
        
        if not device:
            return f"I couldn't find a device called {device_name}"
        
        domain = device.entity_id.split(".")[0]
        success = await self._call_service(domain, "turn_off", device.entity_id)
        
        if success:
            return f"Turned off {device.name}"
        return f"Failed to turn off {device.name}"
    
    async def _handle_set_brightness(self, entities: Dict[str, str]) -> str:
        device_name = entities.get("device", "")
        value = entities.get("value", "50")
        
        device = self._find_device(device_name)
        if not device:
            return f"I couldn't find a device called {device_name}"
        
        if device.device_type != DeviceType.LIGHT:
            return f"{device.name} doesn't support brightness control"
        
        try:
            brightness = int(float(value) * 2.55)  # Convert 0-100 to 0-255
            success = await self._call_service(
                "light", "turn_on", device.entity_id,
                {"brightness": brightness}
            )
            
            if success:
                return f"Set {device.name} brightness to {value}%"
        except ValueError:
            return "Invalid brightness value"
        
        return f"Failed to set brightness for {device.name}"
    
    async def _handle_set_temperature(self, entities: Dict[str, str]) -> str:
        device_name = entities.get("device", "thermostat")
        value = entities.get("value", "72")
        
        device = self._find_device(device_name)
        if not device:
            return f"I couldn't find a device called {device_name}"
        
        if device.device_type != DeviceType.THERMOSTAT:
            return f"{device.name} is not a thermostat"
        
        try:
            temperature = float(value)
            success = await self._call_service(
                "climate", "set_temperature", device.entity_id,
                {"temperature": temperature}
            )
            
            if success:
                return f"Set {device.name} to {value} degrees"
        except ValueError:
            return "Invalid temperature value"
        
        return f"Failed to set temperature for {device.name}"
    
    async def _handle_get_status(self, entities: Dict[str, str]) -> str:
        device_name = entities.get("device", "")
        device = self._find_device(device_name)
        
        if not device:
            return f"I couldn't find a device called {device_name}"
        
        await self._refresh_devices()
        device = self.devices.get(device.entity_id)
        
        if device:
            status_parts = [f"{device.name} is {device.state}"]
            
            if device.device_type == DeviceType.LIGHT:
                brightness = device.attributes.get("brightness")
                if brightness:
                    status_parts.append(f"at {int(brightness / 2.55)}% brightness")
            
            if device.device_type == DeviceType.THERMOSTAT:
                temp = device.attributes.get("current_temperature")
                target = device.attributes.get("temperature")
                if temp:
                    status_parts.append(f"current temperature is {temp} degrees")
                if target:
                    status_parts.append(f"set to {target} degrees")
            
            return ", ".join(status_parts)
        
        return f"Unable to get status for {device_name}"
    
    async def _handle_list_devices(self, entities: Dict[str, str]) -> str:
        await self._refresh_devices()
        
        if not self.devices:
            return "No smart devices found"
        
        # Group by type
        by_type: Dict[DeviceType, List[str]] = {}
        for device in self.devices.values():
            if device.device_type not in by_type:
                by_type[device.device_type] = []
            by_type[device.device_type].append(device.name)
        
        parts = []
        for device_type, names in by_type.items():
            if device_type != DeviceType.UNKNOWN:
                parts.append(f"{device_type.value}s: {', '.join(names[:5])}")
        
        return "Found " + "; ".join(parts)


# ==================== Plugin Entry Point ====================

plugin_instance: Optional[SmartHomePlugin] = None


async def initialize(config: Dict[str, Any]) -> bool:
    """Plugin initialization"""
    global plugin_instance
    plugin_instance = SmartHomePlugin(config)
    return await plugin_instance.initialize()


async def shutdown():
    """Plugin shutdown"""
    if plugin_instance:
        await plugin_instance.shutdown()


async def handle_intent(intent: str, entities: Dict[str, str]) -> str:
    """Handle incoming intent"""
    if plugin_instance:
        return await plugin_instance.handle_intent(intent, entities)
    return "Smart home plugin not initialized"
