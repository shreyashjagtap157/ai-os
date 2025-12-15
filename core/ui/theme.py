"""
AI-OS Theme Manager
Handles theme loading and application
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Any

logger = logging.getLogger('aios-shell')

@dataclass
class Theme:
    name: str
    bg_gradient_start: str
    bg_gradient_end: str
    text_primary: str
    text_secondary: str
    accent_color: str
    input_bg: str
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Theme':
        return cls(
            name=data.get('name', 'Default'),
            bg_gradient_start=data.get('bg_gradient_start', '#1a1a2e'),
            bg_gradient_end=data.get('bg_gradient_end', '#16213e'),
            text_primary=data.get('text_primary', 'white'),
            text_secondary=data.get('text_secondary', 'rgba(255, 255, 255, 0.7)'),
            accent_color=data.get('accent_color', '#667eea'),
            input_bg=data.get('input_bg', 'rgba(255, 255, 255, 0.1)')
        )
    
    def to_css(self) -> bytes:
        css = f"""
            window {{
                background: linear-gradient(180deg, {self.bg_gradient_start} 0%, {self.bg_gradient_end} 100%);
            }}
            .time-label {{
                font-size: 72px;
                font-weight: 300;
                color: {self.text_primary};
            }}
            .date-label {{
                font-size: 24px;
                color: {self.text_secondary};
            }}
            .agent-input {{
                font-size: 18px;
                padding: 16px 24px;
                border-radius: 30px;
                background: {self.input_bg};
                border: none;
                color: {self.text_primary};
                caret-color: {self.accent_color};
            }}
            .agent-input:focus {{
                outline: none;
                background: rgba(255, 255, 255, 0.15);
            }}
            .response-label {{
                font-size: 16px;
                color: rgba(255, 255, 255, 0.8);
                padding: 20px;
            }}
            .status-bar {{
                background: rgba(0, 0, 0, 0.3);
                padding: 8px 16px;
            }}
            .status-text {{
                font-size: 14px;
                color: {self.text_primary};
            }}
        """
        return css.encode('utf-8')

class ThemeManager:
    def __init__(self, theme_dir: str = "themes"):
        self.theme_dir = Path(theme_dir)
        self.current_theme = Theme.from_dict({})
        
    def load_theme(self, name: str) -> Theme:
        try:
            theme_path = self.theme_dir / f"{name}.json"
            if theme_path.exists():
                with open(theme_path) as f:
                    data = json.load(f)
                    self.current_theme = Theme.from_dict(data)
            else:
                logger.warning(f"Theme {name} not found, using default")
        except Exception as e:
            logger.error(f"Failed to load theme: {e}")
            
        return self.current_theme
