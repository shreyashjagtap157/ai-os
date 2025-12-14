#!/usr/bin/env python3
"""
Weather Plugin for AI-OS
Example plugin that adds weather skill to the AI agent.
"""

import os
import json
from typing import Dict, Any, Optional

# Import from AI-OS plugin system
try:
    from aios.plugins import AgentSkillPlugin, PluginInfo
except ImportError:
    # Fallback for standalone testing
    class AgentSkillPlugin:
        def __init__(self, info, config):
            self.info = info
            self.config = config
    PluginInfo = None


class PluginMain(AgentSkillPlugin):
    """Weather plugin that adds weather queries to AI-OS"""
    
    def activate(self) -> bool:
        """Called when plugin is enabled"""
        print(f"Weather plugin activated")
        self.api_key = self.config.get('api_key', '')
        self.units = self.config.get('units', 'metric')
        return True
    
    def deactivate(self) -> bool:
        """Called when plugin is disabled"""
        print("Weather plugin deactivated")
        return True
    
    def get_skill_prompt(self) -> str:
        """Return prompt addition for AI"""
        return """You can get weather information. When asked about weather:
        - Ask for location if not specified
        - Return action: {"action": "weather", "params": {"location": "city_name"}}
        - Available data: temperature, conditions, humidity, wind
        """
    
    def process_query(self, query: str, context: Dict[str, Any]) -> Optional[str]:
        """Process a query if relevant to weather"""
        query_lower = query.lower()
        
        if 'weather' in query_lower:
            # Extract location from query
            location = self._extract_location(query)
            
            if location:
                weather = self._get_weather(location)
                if weather:
                    return self._format_weather(weather)
                return f"I couldn't get weather for {location}."
            else:
                return "Which city would you like weather for?"
        
        return None
    
    def _extract_location(self, query: str) -> Optional[str]:
        """Extract location from query"""
        # Simple extraction - look for "in <city>" or "for <city>"
        query_lower = query.lower()
        
        for prefix in ['in ', 'for ', 'at ']:
            if prefix in query_lower:
                idx = query_lower.find(prefix)
                location = query[idx + len(prefix):].strip()
                # Clean up
                location = location.split('?')[0].strip()
                if location:
                    return location
        
        return None
    
    def _get_weather(self, location: str) -> Optional[Dict[str, Any]]:
        """Fetch weather data"""
        if not self.api_key:
            # Return mock data without API key
            return {
                'location': location,
                'temp': 22,
                'conditions': 'Partly cloudy',
                'humidity': 65,
                'wind': 12
            }
        
        try:
            import urllib.request
            
            url = f"https://api.openweathermap.org/data/2.5/weather?q={location}&appid={self.api_key}&units={self.units}"
            
            with urllib.request.urlopen(url, timeout=10) as response:
                data = json.loads(response.read().decode())
                
            return {
                'location': data['name'],
                'temp': round(data['main']['temp']),
                'conditions': data['weather'][0]['description'],
                'humidity': data['main']['humidity'],
                'wind': round(data['wind']['speed'])
            }
            
        except Exception as e:
            print(f"Weather API error: {e}")
            return None
    
    def _format_weather(self, weather: Dict[str, Any]) -> str:
        """Format weather data as response"""
        unit = '°C' if self.units == 'metric' else '°F'
        wind_unit = 'm/s' if self.units == 'metric' else 'mph'
        
        return f"""Weather for {weather['location']}:
🌡️ Temperature: {weather['temp']}{unit}
☁️ Conditions: {weather['conditions'].capitalize()}
💧 Humidity: {weather['humidity']}%
💨 Wind: {weather['wind']} {wind_unit}"""


# Standalone testing
if __name__ == '__main__':
    class MockInfo:
        name = "Weather Plugin"
    
    plugin = PluginMain(MockInfo(), {'units': 'metric'})
    plugin.activate()
    
    result = plugin.process_query("What's the weather in London?", {})
    print(result)
