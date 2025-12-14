# AI-OS: Android-Based AI Operating System

<p align="center">
  <strong>A complete Android OS with deep AI agent control for every aspect of the device</strong>
</p>

<p align="center">
  <a href="#features">Features</a> •
  <a href="#architecture">Architecture</a> •
  <a href="#capabilities">Capabilities</a> •
  <a href="#building">Building</a> •
  <a href="#usage">Usage</a>
</p>

---

## 🌟 Overview

AI-OS is an **Android-based operating system** that puts AI at the center of the user experience. Unlike regular Android launchers, AI-OS provides **deep system integration** enabling the AI agent to truly control every aspect of the device - from tapping buttons in any app to managing system settings, reading notifications, and automating complex workflows.

### Key Differentiators

| Feature | Regular Launcher | AI-OS |
|---------|-----------------|-------|
| Home Screen | ✅ | ✅ |
| Open Apps | ✅ | ✅ |
| Control Settings | ❌ | ✅ |
| See Screen Content | ❌ | ✅ |
| Tap UI Elements | ❌ | ✅ |
| Type in Any App | ❌ | ✅ |
| Read Notifications | ❌ | ✅ |
| Automate Apps | ❌ | ✅ |
| Voice Control | Limited | ✅ Full |
| Visual Understanding | ❌ | ✅ |

---

## 🤖 Features

### 1. Deep UI Automation (Accessibility Service)
- **Screen Analysis**: AI sees all UI elements on screen
- **Touch Injection**: Tap, long press, swipe anywhere
- **Gesture Control**: Scroll, pinch, custom gestures
- **Text Input**: Type into any text field
- **Navigation**: Back, Home, Recents, Lock

### 2. Visual Understanding
- **Screen Capture**: Take screenshots for AI analysis
- **Element Recognition**: Identify buttons, text, images
- **Context Awareness**: Understand which app is active
- **GPT-4 Vision**: Send screenshots to AI for analysis

### 3. System Control
- **Display**: Brightness, timeout, rotation
- **Audio**: Volume, ringer mode, DND
- **Connectivity**: WiFi, Bluetooth, Airplane mode
- **Hardware**: Flashlight, camera, vibration
- **Power**: Lock screen, screenshot, power menu

### 4. App Management
- **Launch Any App**: By name or package
- **List Apps**: Installed, system, recent
- **App Actions**: Settings, Play Store, uninstall
- **Inter-app Control**: Navigate within apps

### 5. Notification Intelligence
- **Read All Notifications**: Title, text, actions
- **Dismiss Notifications**: Individual or all
- **Click Actions**: Reply, mark read, etc.
- **Summarize**: Get AI summary of notifications

### 6. Communication Control
- **Calls**: Make, answer, reject
- **SMS**: Send, read
- **Contacts**: Search, add

### 7. Voice Assistant
- **Wake Word**: "Hey AI" activation
- **Continuous Listening**: Always-on mode
- **Text-to-Speech**: Spoken responses
- **Offline Fallback**: Basic commands work offline

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AI-OS Android                                 │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                    User Interface Layer                       │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │   │
│  │  │ Home Screen │  │ Quick Panel │  │  Agent Overlay      │   │   │
│  │  │ (Compose)   │  │ (SystemUI)  │  │  (Floating Button)  │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────────┘   │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  Agent Orchestrator                           │   │
│  │  - Coordinates all components                                 │   │
│  │  - Manages agent state                                        │   │
│  │  - Executes action sequences                                  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                Enhanced AI Agent                              │   │
│  │  - GPT-4 / Claude integration                                │   │
│  │  - Visual understanding (GPT-4 Vision)                       │   │
│  │  - 40+ action types                                          │   │
│  │  - Local fallback processing                                 │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │              System Control Layer                             │   │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  │   │
│  │  │ DeepSystem     │  │ SystemSettings   │  │ AppManager   │  │   │
│  │  │ Controller     │  │ Controller       │  │              │  │   │
│  │  │ - Screen       │  │ - Brightness     │  │ - List apps  │  │   │
│  │  │ - Touch        │  │ - Volume         │  │ - Launch     │  │   │
│  │  │ - Gestures     │  │ - Connectivity   │  │ - Search     │  │   │
│  │  └────────────────┘  └──────────────────┘  └──────────────┘  │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                │                                     │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                   Services Layer                              │   │
│  │  ┌────────────────┐  ┌──────────────────┐  ┌──────────────┐  │   │
│  │  │ AgentService   │  │ Accessibility    │  │ Notification │  │   │
│  │  │ (Foreground)   │  │ Service          │  │ Listener     │  │   │
│  │  └────────────────┘  └──────────────────┘  └──────────────┘  │   │
│  │  ┌────────────────┐  ┌──────────────────┐                    │   │
│  │  │ VoiceService   │  │ Device Admin     │                    │   │
│  │  │ (Wake Word)    │  │ Receiver         │                    │   │
│  │  └────────────────┘  └──────────────────┘                    │   │
│  └──────────────────────────────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Project Structure

```
android/
├── app/src/main/
│   ├── java/com/aios/launcher/
│   │   ├── AIosApplication.kt           # Application class
│   │   │
│   │   ├── agent/
│   │   │   ├── AIAgent.kt               # Basic AI agent
│   │   │   ├── EnhancedAIAgent.kt       # Full agent with vision
│   │   │   ├── AgentOrchestrator.kt     # Master coordinator
│   │   │   └── DeviceController.kt      # Device control
│   │   │
│   │   ├── system/
│   │   │   ├── DeepSystemController.kt  # Screen & touch control
│   │   │   ├── SystemSettingsController.kt # Settings control
│   │   │   ├── AppManager.kt            # App management
│   │   │   └── DevicePolicyManager.kt   # Enterprise control
│   │   │
│   │   ├── services/
│   │   │   ├── AgentService.kt          # Main foreground service
│   │   │   ├── VoiceRecognitionService.kt # Voice input
│   │   │   ├── AgentAccessibilityService.kt # UI automation
│   │   │   └── AIosNotificationListener.kt # Notifications
│   │   │
│   │   ├── ui/
│   │   │   ├── MainActivity.kt          # Launcher activity
│   │   │   ├── home/
│   │   │   │   ├── HomeScreen.kt        # Home screen UI
│   │   │   │   └── HomeViewModel.kt
│   │   │   ├── overlay/
│   │   │   │   └── AgentOverlay.kt      # Floating AI button
│   │   │   ├── systemui/
│   │   │   │   └── SystemUI.kt          # Status/nav bars
│   │   │   └── theme/
│   │   │       └── Theme.kt             # Material3 theme
│   │   │
│   │   ├── receivers/
│   │   │   └── BootReceiver.kt          # Boot autostart
│   │   │
│   │   └── di/
│   │       └── AppModule.kt             # Hilt DI
│   │
│   ├── res/
│   │   ├── values/
│   │   │   ├── strings.xml
│   │   │   ├── colors.xml
│   │   │   └── themes.xml
│   │   └── xml/
│   │       ├── accessibility_service_config.xml
│   │       ├── device_admin.xml
│   │       └── widget_info.xml
│   │
│   └── AndroidManifest.xml
│
├── build.gradle
├── settings.gradle
└── gradle.properties
```

---

## 🎯 Capabilities

### AI Agent Actions (40+)

**Touch Actions:**
- `tap(x, y)` - Tap at coordinates
- `tap_element(text)` - Tap element by text
- `tap_id(viewId)` - Tap element by ID
- `long_press(x, y, duration)` - Long press
- `swipe(startX, startY, endX, endY)` - Swipe gesture
- `scroll(direction)` - Scroll up/down/left/right
- `type_text(text)` - Type text
- `clear_text()` - Clear focused field

**Navigation:**
- `back()` - Press back button
- `home()` - Go to home screen
- `recents()` - Open recent apps
- `notifications()` - Open notification panel
- `quick_settings()` - Open quick settings
- `lock_screen()` - Lock the device
- `screenshot()` - Take screenshot

**Settings:**
- `brightness(value)` - Set brightness (0-255)
- `volume_media(value)` - Set media volume (0-100)
- `volume_ring(value)` - Set ring volume
- `ringer_mode(mode)` - normal/vibrate/silent
- `dnd(enabled)` - Do Not Disturb
- `flashlight(enabled)` - Toggle flashlight
- `auto_rotate(enabled)` - Auto-rotation
- `screen_timeout(ms)` - Screen timeout

**Apps:**
- `open_app(name)` - Open app by name
- `call(number)` - Make phone call
- `sms(number, message)` - Send SMS

**Utility:**
- `wait(ms)` - Wait before next action

---

## 🔧 Building

### Prerequisites

- Android Studio Hedgehog or newer
- JDK 17+
- Android SDK 34

### Build Steps

```bash
# Clone repository
git clone https://github.com/yourusername/ai-os.git
cd ai-os/android

# Set API keys (create local.properties)
echo "OPENAI_API_KEY=sk-your-key" >> local.properties
echo "ANTHROPIC_API_KEY=your-key" >> local.properties

# Build debug
./gradlew assembleDebug

# Install
adb install app/build/outputs/apk/debug/app-debug.apk
```

### Setting as Default Launcher

1. Install the app
2. Press Home button
3. Select "AI-OS" 
4. Choose "Always"

---

## 📱 Required Permissions

### Essential (for basic operation)
- **Accessibility Service**: UI reading and control
- **Overlay Permission**: Floating AI button

### Optional (for full features)
- **Notification Listener**: Read/dismiss notifications
- **Device Admin**: Lock screen, wipe device
- **Write Settings**: Brightness, timeout

Enable in Settings → AI-OS → Permissions

---

## 💬 Usage Examples

### Voice Commands
```
"Hey AI, open YouTube and search for funny cats"
"Hey AI, turn brightness to 50% and mute the phone"
"Hey AI, send a message to Mom saying I'll be home soon"
"Hey AI, what notifications do I have?"
"Hey AI, open Settings and go to WiFi"
"Hey AI, scroll down and tap on the download button"
```

### How It Works

1. **User speaks**: "Open Chrome and search for weather"
2. **AI-OS Captures**: Current screen state
3. **AI Processes**: Understands intent
4. **Generates Actions**:
   ```json
   {
     "actions": [
       {"type": "open_app", "params": {"name": "Chrome"}},
       {"type": "wait", "params": {"ms": 1000}},
       {"type": "tap_element", "params": {"text": "Search or type URL"}},
       {"type": "type_text", "params": {"text": "weather"}},
       {"type": "tap_element", "params": {"text": "Search"}}
     ]
   }
   ```
5. **Executes**: Each action in sequence
6. **Responds**: "I've opened Chrome and searched for weather"

---

## 🔒 Security

- API keys stored in BuildConfig (not in code)
- All system actions logged
- User approval required for:
  - Factory reset
  - Device wipe
  - Installing apps
  - Sending SMS (optionally)

---

## 🚀 Roadmap

### Completed ✅
- [x] Launcher replacement
- [x] Deep UI automation (Accessibility)
- [x] Screen content analysis
- [x] Touch/gesture injection
- [x] System settings control
- [x] App management
- [x] Notification reading
- [x] Voice recognition
- [x] GPT-4/Claude integration
- [x] Floating agent overlay
- [x] System UI components
- [x] Device admin support

### Planned 📋
- [ ] Multi-step workflow automation
- [ ] Custom wake word training
- [ ] On-device LLM (Llama)
- [ ] App usage learning
- [ ] Smart routines
- [ ] Cross-device sync
- [ ] Custom ROM integration

---

## 📄 License

MIT License

---

<p align="center">
  <strong>AI-OS: True AI Control for Android</strong>
</p>
