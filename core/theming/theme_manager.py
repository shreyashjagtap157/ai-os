#!/usr/bin/env python3
"""
AI-OS Theming Engine
Visual customization and theme management.
"""

import os
import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from enum import Enum
import logging

logger = logging.getLogger('aios-theme')


class ColorScheme(Enum):
    DARK = "dark"
    LIGHT = "light"
    AUTO = "auto"


@dataclass
class Color:
    """RGBA color"""
    r: int
    g: int
    b: int
    a: float = 1.0
    
    def to_hex(self) -> str:
        return f"#{self.r:02x}{self.g:02x}{self.b:02x}"
    
    def to_rgba(self) -> str:
        return f"rgba({self.r}, {self.g}, {self.b}, {self.a})"
    
    @classmethod
    def from_hex(cls, hex_str: str) -> 'Color':
        hex_str = hex_str.lstrip('#')
        if len(hex_str) == 6:
            return cls(
                r=int(hex_str[0:2], 16),
                g=int(hex_str[2:4], 16),
                b=int(hex_str[4:6], 16)
            )
        elif len(hex_str) == 8:
            return cls(
                r=int(hex_str[0:2], 16),
                g=int(hex_str[2:4], 16),
                b=int(hex_str[4:6], 16),
                a=int(hex_str[6:8], 16) / 255
            )
        raise ValueError(f"Invalid hex color: {hex_str}")


@dataclass
class ThemeColors:
    """Theme color palette"""
    # Background colors
    background: Color = field(default_factory=lambda: Color(26, 26, 46))
    surface: Color = field(default_factory=lambda: Color(22, 33, 62))
    surface_variant: Color = field(default_factory=lambda: Color(42, 53, 82))
    
    # Text colors
    text_primary: Color = field(default_factory=lambda: Color(255, 255, 255))
    text_secondary: Color = field(default_factory=lambda: Color(180, 180, 200))
    text_disabled: Color = field(default_factory=lambda: Color(100, 100, 120))
    
    # Accent colors
    primary: Color = field(default_factory=lambda: Color(102, 126, 234))
    primary_variant: Color = field(default_factory=lambda: Color(118, 75, 162))
    secondary: Color = field(default_factory=lambda: Color(3, 218, 197))
    
    # Status colors
    success: Color = field(default_factory=lambda: Color(76, 175, 80))
    warning: Color = field(default_factory=lambda: Color(255, 193, 7))
    error: Color = field(default_factory=lambda: Color(244, 67, 54))
    info: Color = field(default_factory=lambda: Color(33, 150, 243))
    
    # UI colors
    border: Color = field(default_factory=lambda: Color(60, 70, 100))
    divider: Color = field(default_factory=lambda: Color(50, 60, 80))
    shadow: Color = field(default_factory=lambda: Color(0, 0, 0, 0.3))


@dataclass
class ThemeTypography:
    """Theme typography settings"""
    font_family: str = "Inter, system-ui, sans-serif"
    font_family_mono: str = "JetBrains Mono, monospace"
    
    # Font sizes
    size_xs: int = 10
    size_sm: int = 12
    size_md: int = 14
    size_lg: int = 16
    size_xl: int = 20
    size_xxl: int = 24
    size_display: int = 48
    
    # Font weights
    weight_light: int = 300
    weight_normal: int = 400
    weight_medium: int = 500
    weight_bold: int = 700


@dataclass
class ThemeSpacing:
    """Theme spacing values"""
    xs: int = 4
    sm: int = 8
    md: int = 16
    lg: int = 24
    xl: int = 32
    xxl: int = 48


@dataclass
class ThemeEffects:
    """Theme visual effects"""
    border_radius_sm: int = 4
    border_radius_md: int = 8
    border_radius_lg: int = 16
    border_radius_xl: int = 24
    border_radius_full: int = 9999
    
    blur_sm: int = 4
    blur_md: int = 8
    blur_lg: int = 16
    
    animation_fast: str = "150ms ease"
    animation_normal: str = "250ms ease"
    animation_slow: str = "400ms ease"


@dataclass
class Theme:
    """Complete theme definition"""
    id: str
    name: str
    author: str = ""
    version: str = "1.0.0"
    scheme: ColorScheme = ColorScheme.DARK
    
    colors: ThemeColors = field(default_factory=ThemeColors)
    typography: ThemeTypography = field(default_factory=ThemeTypography)
    spacing: ThemeSpacing = field(default_factory=ThemeSpacing)
    effects: ThemeEffects = field(default_factory=ThemeEffects)
    
    # Wallpaper
    wallpaper: str = ""
    
    # Custom CSS
    custom_css: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert theme to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'author': self.author,
            'version': self.version,
            'scheme': self.scheme.value,
            'colors': {
                'background': self.colors.background.to_hex(),
                'surface': self.colors.surface.to_hex(),
                'primary': self.colors.primary.to_hex(),
                'secondary': self.colors.secondary.to_hex(),
                'text_primary': self.colors.text_primary.to_hex(),
                'text_secondary': self.colors.text_secondary.to_hex(),
                'success': self.colors.success.to_hex(),
                'warning': self.colors.warning.to_hex(),
                'error': self.colors.error.to_hex(),
            },
            'wallpaper': self.wallpaper,
            'custom_css': self.custom_css
        }
    
    def to_gtk_css(self) -> str:
        """Generate GTK CSS"""
        return f"""
/* AI-OS Theme: {self.name} */

@define-color bg_color {self.colors.background.to_hex()};
@define-color fg_color {self.colors.text_primary.to_hex()};
@define-color accent_color {self.colors.primary.to_hex()};
@define-color accent_bg_color {self.colors.primary.to_hex()};
@define-color accent_fg_color white;
@define-color success_color {self.colors.success.to_hex()};
@define-color warning_color {self.colors.warning.to_hex()};
@define-color error_color {self.colors.error.to_hex()};
@define-color border_color {self.colors.border.to_hex()};

window {{
    background-color: @bg_color;
    color: @fg_color;
}}

.background {{
    background-color: @bg_color;
}}

button {{
    background: {self.colors.surface.to_hex()};
    border: 1px solid @border_color;
    border-radius: {self.effects.border_radius_md}px;
    padding: {self.spacing.sm}px {self.spacing.md}px;
    transition: {self.effects.animation_fast};
}}

button:hover {{
    background: {self.colors.surface_variant.to_hex()};
}}

button.suggested-action {{
    background: @accent_color;
    color: @accent_fg_color;
}}

entry {{
    background: {self.colors.surface.to_hex()};
    border: 1px solid @border_color;
    border-radius: {self.effects.border_radius_md}px;
    padding: {self.spacing.sm}px {self.spacing.md}px;
}}

entry:focus {{
    border-color: @accent_color;
}}

.card {{
    background: {self.colors.surface.to_hex()};
    border-radius: {self.effects.border_radius_lg}px;
    padding: {self.spacing.md}px;
}}

scrollbar {{
    background: transparent;
}}

scrollbar slider {{
    background: {self.colors.border.to_hex()};
    border-radius: {self.effects.border_radius_full}px;
    min-width: 6px;
    min-height: 6px;
}}

{self.custom_css}
"""
    
    def to_shell_css(self) -> str:
        """Generate CSS for AI-OS shell"""
        return f"""
:root {{
    --bg: {self.colors.background.to_hex()};
    --surface: {self.colors.surface.to_hex()};
    --primary: {self.colors.primary.to_hex()};
    --secondary: {self.colors.secondary.to_hex()};
    --text: {self.colors.text_primary.to_hex()};
    --text-secondary: {self.colors.text_secondary.to_hex()};
    --border: {self.colors.border.to_hex()};
    --success: {self.colors.success.to_hex()};
    --warning: {self.colors.warning.to_hex()};
    --error: {self.colors.error.to_hex()};
    --radius-sm: {self.effects.border_radius_sm}px;
    --radius-md: {self.effects.border_radius_md}px;
    --radius-lg: {self.effects.border_radius_lg}px;
    --font: {self.typography.font_family};
    --font-mono: {self.typography.font_family_mono};
}}

body {{
    background: var(--bg);
    color: var(--text);
    font-family: var(--font);
}}
"""


# Built-in themes
THEMES = {
    'aios-dark': Theme(
        id='aios-dark',
        name='AI-OS Dark',
        author='AI-OS Team',
        scheme=ColorScheme.DARK
    ),
    'aios-light': Theme(
        id='aios-light',
        name='AI-OS Light',
        author='AI-OS Team',
        scheme=ColorScheme.LIGHT,
        colors=ThemeColors(
            background=Color(245, 245, 250),
            surface=Color(255, 255, 255),
            surface_variant=Color(230, 230, 240),
            text_primary=Color(30, 30, 40),
            text_secondary=Color(80, 80, 100),
            text_disabled=Color(150, 150, 170),
            border=Color(200, 200, 220)
        )
    ),
    'midnight': Theme(
        id='midnight',
        name='Midnight',
        author='AI-OS Team',
        scheme=ColorScheme.DARK,
        colors=ThemeColors(
            background=Color(10, 10, 20),
            surface=Color(20, 20, 35),
            primary=Color(100, 200, 255),
            secondary=Color(255, 100, 150)
        )
    ),
    'forest': Theme(
        id='forest',
        name='Forest',
        author='AI-OS Team',
        scheme=ColorScheme.DARK,
        colors=ThemeColors(
            background=Color(20, 30, 25),
            surface=Color(30, 45, 35),
            primary=Color(100, 200, 100),
            secondary=Color(200, 220, 100)
        )
    ),
}


class ThemeManager:
    """Theme manager for AI-OS"""
    
    THEMES_DIR = Path("/usr/share/aios/themes")
    USER_THEMES_DIR = Path.home() / ".local/share/aios/themes"
    CONFIG_PATH = Path("/etc/aios/theme.json")
    
    def __init__(self):
        self.themes: Dict[str, Theme] = THEMES.copy()
        self.current_theme_id: str = 'aios-dark'
        self._load_user_themes()
        self._load_config()
    
    def _load_user_themes(self):
        """Load user-installed themes"""
        for themes_dir in [self.THEMES_DIR, self.USER_THEMES_DIR]:
            if not themes_dir.exists():
                continue
            
            for theme_file in themes_dir.glob("*.json"):
                try:
                    with open(theme_file) as f:
                        data = json.load(f)
                    theme = self._parse_theme(data)
                    self.themes[theme.id] = theme
                except Exception as e:
                    logger.warning(f"Failed to load theme {theme_file}: {e}")
    
    def _parse_theme(self, data: Dict[str, Any]) -> Theme:
        """Parse theme from dictionary"""
        colors = ThemeColors()
        if 'colors' in data:
            for key, value in data['colors'].items():
                if hasattr(colors, key):
                    setattr(colors, key, Color.from_hex(value))
        
        return Theme(
            id=data['id'],
            name=data['name'],
            author=data.get('author', ''),
            version=data.get('version', '1.0.0'),
            scheme=ColorScheme(data.get('scheme', 'dark')),
            colors=colors,
            wallpaper=data.get('wallpaper', ''),
            custom_css=data.get('custom_css', '')
        )
    
    def _load_config(self):
        """Load theme configuration"""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH) as f:
                    data = json.load(f)
                self.current_theme_id = data.get('theme', 'aios-dark')
            except Exception as e:
                logger.warning(f"Failed to load theme config: {e}")
    
    def _save_config(self):
        """Save theme configuration"""
        try:
            self.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
            with open(self.CONFIG_PATH, 'w') as f:
                json.dump({'theme': self.current_theme_id}, f)
        except Exception as e:
            logger.error(f"Failed to save theme config: {e}")
    
    def get_available_themes(self) -> List[Dict[str, str]]:
        """Get list of available themes"""
        return [
            {'id': t.id, 'name': t.name, 'author': t.author, 'scheme': t.scheme.value}
            for t in self.themes.values()
        ]
    
    def get_current_theme(self) -> Theme:
        """Get current theme"""
        return self.themes.get(self.current_theme_id, THEMES['aios-dark'])
    
    def set_theme(self, theme_id: str) -> bool:
        """Set current theme"""
        if theme_id not in self.themes:
            return False
        
        self.current_theme_id = theme_id
        self._save_config()
        self._apply_theme()
        return True
    
    def _apply_theme(self):
        """Apply current theme to system"""
        theme = self.get_current_theme()
        
        # Write GTK CSS
        gtk_css_path = Path.home() / ".config/gtk-4.0/gtk.css"
        try:
            gtk_css_path.parent.mkdir(parents=True, exist_ok=True)
            gtk_css_path.write_text(theme.to_gtk_css())
        except Exception as e:
            logger.warning(f"Failed to write GTK CSS: {e}")
        
        # Set wallpaper if specified
        if theme.wallpaper and Path(theme.wallpaper).exists():
            os.system(f'gsettings set org.gnome.desktop.background picture-uri "file://{theme.wallpaper}"')
        
        logger.info(f"Applied theme: {theme.name}")
    
    def install_theme(self, theme_path: str) -> bool:
        """Install a theme from file"""
        try:
            source = Path(theme_path)
            if not source.exists():
                return False
            
            self.USER_THEMES_DIR.mkdir(parents=True, exist_ok=True)
            dest = self.USER_THEMES_DIR / source.name
            
            import shutil
            shutil.copy(source, dest)
            
            # Reload themes
            self._load_user_themes()
            return True
            
        except Exception as e:
            logger.error(f"Failed to install theme: {e}")
            return False
    
    def uninstall_theme(self, theme_id: str) -> bool:
        """Uninstall a user theme"""
        if theme_id in THEMES:
            return False  # Can't uninstall built-in themes
        
        theme_file = self.USER_THEMES_DIR / f"{theme_id}.json"
        if theme_file.exists():
            theme_file.unlink()
            del self.themes[theme_id]
            
            if self.current_theme_id == theme_id:
                self.set_theme('aios-dark')
            
            return True
        
        return False


# Global theme manager
_theme_manager: Optional[ThemeManager] = None


def get_theme_manager() -> ThemeManager:
    global _theme_manager
    if _theme_manager is None:
        _theme_manager = ThemeManager()
    return _theme_manager


if __name__ == '__main__':
    manager = get_theme_manager()
    
    print("Available themes:")
    for theme in manager.get_available_themes():
        print(f"  - {theme['name']} ({theme['id']}) by {theme['author']}")
    
    print(f"\nCurrent theme: {manager.get_current_theme().name}")
    print("\nGenerated GTK CSS:")
    print(manager.get_current_theme().to_gtk_css()[:500] + "...")
