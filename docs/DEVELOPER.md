# AI-OS Developer Guide

## Creating Plugins

Plugins extend AI-OS with new capabilities.

### Plugin Structure

```
my-plugin/
├── plugin.json      # Plugin manifest
└── main.py          # Plugin code
```

### Plugin Manifest (`plugin.json`)

```json
{
    "id": "my-plugin",
    "name": "My Plugin",
    "version": "1.0.0",
    "description": "Example plugin",
    "author": "Your Name",
    "type": "action",
    "dependencies": [],
    "permissions": ["network.access"]
}
```

### Plugin Types

- `agent_skill` - Add new AI capabilities
- `action` - Add new action types
- `service` - Background service
- `ui_widget` - UI component

### Example: Action Plugin

```python
from aios.plugins import ActionPlugin, PluginInfo

class PluginMain(ActionPlugin):
    def activate(self) -> bool:
        print(f"Activated: {self.info.name}")
        return True
    
    def deactivate(self) -> bool:
        return True
    
    def get_actions(self):
        return ["my_action"]
    
    def execute_action(self, action, params):
        if action == "my_action":
            # Do something
            return {"success": True, "message": "Done!"}
        return {"success": False}
```

### Installing Plugins

```bash
# Copy to user plugins directory
cp -r my-plugin ~/.local/share/aios/plugins/

# Or system-wide
sudo cp -r my-plugin /usr/lib/aios/plugins/
```

## Creating Apps

Use the AI-OS App Framework.

### GTK App Example

```python
from aios.apps import AIosGtkApp, AppInfo

class MyApp(AIosGtkApp):
    def __init__(self):
        super().__init__(AppInfo(
            name="My App",
            version="1.0.0",
            description="Example app"
        ))
    
    def build_ui(self):
        from gi.repository import Gtk
        
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        label = Gtk.Label(label="Hello from AI-OS!")
        box.append(label)
        
        # Chat with AI
        button = Gtk.Button(label="Ask AI")
        button.connect('clicked', self.on_ask)
        box.append(button)
        
        return box
    
    def on_ask(self, button):
        response = self.chat("What time is it?")
        print(response)

if __name__ == '__main__':
    MyApp().run([])
```

## Theming

### Creating a Theme

```json
{
    "id": "my-theme",
    "name": "My Theme",
    "author": "Your Name",
    "scheme": "dark",
    "colors": {
        "background": "#1a1a2e",
        "surface": "#16213e",
        "primary": "#667eea",
        "text_primary": "#ffffff"
    },
    "wallpaper": "/path/to/wallpaper.jpg"
}
```

### Installing Themes

```bash
cp my-theme.json ~/.local/share/aios/themes/
```

## Building AI-OS

### Dependencies

```bash
sudo apt install build-essential git wget cpio unzip rsync bc python3
```

### Build Commands

```bash
# Build for PC
./build/scripts/build.sh build x86_64

# Build for Raspberry Pi 4
./build/scripts/build.sh build rpi4

# Test in QEMU
./build/scripts/build.sh qemu
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request
