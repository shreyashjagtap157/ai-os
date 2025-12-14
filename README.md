# AI-OS: Standalone AI Operating System

<p align="center">
  <strong>A complete, bootable Linux-based operating system with AI at its core</strong>
</p>

---

## 🌟 What is AI-OS?

AI-OS is a **standalone operating system** - not an app, not a launcher, but a complete bootable OS. It boots directly on hardware (or VM) and provides full AI agent control over the entire device.

### This is an OS if:
✅ It has a custom Linux kernel  
✅ It has an init system  
✅ It has system daemons/services  
✅ It has a display compositor  
✅ It can boot directly on bare metal  
✅ It creates bootable images (ISO, USB, SD card)  

### Project Structure

```
ai-os/
│
├── core/                              # Core OS Components
│   ├── init/
│   │   └── init                      # Early boot init script
│   │
│   ├── services/                     # System Daemons
│   │   ├── aios-agent/
│   │   │   ├── agent.py             # AI Agent daemon (800+ LOC)
│   │   │   └── aios-agent.service   # Systemd unit
│   │   │
│   │   ├── aios-display/
│   │   │   ├── compositor.py        # Wayland compositor
│   │   │   └── aios-display.service
│   │   │
│   │   └── aios-voice/
│   │       ├── voice.py             # Voice recognition
│   │       └── aios-voice.service
│   │
│   └── ui/
│       └── shell.py                  # GTK-based shell UI
│
├── build/                             # Build System
│   ├── scripts/
│   │   └── build.sh                 # Main build script
│   ├── configs/
│   │   ├── aios_defconfig           # Base Buildroot config
│   │   ├── aios_rpi4_defconfig      # Raspberry Pi 4
│   │   └── aios_x86_64_defconfig    # PC/x86_64
│   ├── board/
│   │   └── aios/
│   │       └── linux-config         # Kernel configuration
│   └── external/                     # Buildroot external tree
│
├── rootfs/                            # Root Filesystem Overlay
│   ├── etc/
│   │   └── aios/
│   │       ├── agent.json           # Agent configuration
│   │       └── agent.env            # Environment variables
│   └── init
│
├── tools/                             # Development Tools
│
└── ports/                             # Optional Platform Ports
    └── android/                      # Android port (separate)
```

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI-OS                                        │
├─────────────────────────────────────────────────────────────────────┤
│  User Space                                                          │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    AI-OS Shell (GTK)                         │    │
│  │  - Home screen with clock                                    │    │
│  │  - AI input field                                            │    │
│  │  - Voice control                                             │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                │                                     │
│  ┌──────────────┐  ┌───────────┴──────────┐  ┌──────────────┐       │
│  │ aios-display │  │    aios-agent        │  │ aios-voice   │       │
│  │  (Weston)    │  │  - AI Engine         │  │ - Wake word  │       │
│  │              │  │  - Action Executor   │  │ - STT/TTS    │       │
│  │              │  │  - HAL Integration   │  │              │       │
│  └──────────────┘  └──────────────────────┘  └──────────────┘       │
│                                │                                     │
│  ┌─────────────────────────────┴───────────────────────────────┐    │
│  │                   Hardware Abstraction Layer                 │    │
│  │  Display | Audio | Network | Power | Input | System Info    │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
├──────────────────────────────── systemd ────────────────────────────┤
│                                                                      │
│  Kernel Space                                                        │
│  ┌─────────────────────────────────────────────────────────────┐    │
│  │                    Linux Kernel (6.6 LTS)                    │    │
│  │  - DRM/KMS graphics                                          │    │
│  │  - ALSA audio                                                │    │
│  │  - NetworkManager                                            │    │
│  │  - Input subsystem                                           │    │
│  └─────────────────────────────────────────────────────────────┘    │
│                                                                      │
└──────────────────────────────── Hardware ───────────────────────────┘
```

---

## 🔧 Building

### Prerequisites

```bash
# Ubuntu/Debian
sudo apt-get install build-essential git wget cpio unzip rsync bc \
    python3 libssl-dev libncurses-dev flex bison

# Fedora
sudo dnf install @development-tools git wget cpio unzip rsync bc \
    python3 openssl-devel ncurses-devel flex bison
```

### Build Commands

```bash
# Clone
git clone https://github.com/yourusername/ai-os.git
cd ai-os

# Make build script executable
chmod +x build/scripts/build.sh

# Build for x86_64 PC
./build/scripts/build.sh build x86_64

# Build for Raspberry Pi 4
./build/scripts/build.sh build rpi4

# Test in QEMU
./build/scripts/build.sh qemu

# Create bootable ISO
./build/scripts/build.sh iso

# Flash to USB drive
./build/scripts/build.sh flash /dev/sdX
```

### What Happens During Build

1. Downloads Buildroot
2. Downloads Linux kernel 6.6
3. Downloads GCC toolchain
4. Compiles kernel with AI-OS config
5. Compiles all packages (Python, Wayland, GTK, etc.)
6. Installs AI-OS services and shell
7. Creates bootable image

**Build Time**: ~2-3 hours (first build)

---

## 🖥️ Boot Sequence

```
Power On
    │
    ▼
Bootloader (GRUB2 / U-Boot)
    │
    ▼
Linux Kernel
    │
    ▼
/init (early init script)
    │  - Mount filesystems
    │  - Load kernel modules
    │  - Display AI-OS banner
    │
    ▼
systemd
    │
    ├─▶ aios-agent.service     # Start AI daemon
    ├─▶ aios-voice.service     # Start voice recognition
    └─▶ aios-display.service   # Start compositor
              │
              ▼
         AI-OS Shell
         (Ready for input)
```

---

## 🤖 Agent Capabilities

### Hardware Control (HAL)

| Function | Implementation |
|----------|---------------|
| Brightness | `/sys/class/backlight/` |
| Volume | `amixer` / ALSA |
| WiFi | `nmcli` / NetworkManager |
| Bluetooth | `bluetoothctl` |
| Battery | `/sys/class/power_supply/` |
| Power | `systemctl poweroff/reboot` |
| Apps | `.desktop` files |

### AI Actions

```json
{"action": "brightness", "level": 80}
{"action": "volume", "level": 50}
{"action": "mute", "mute": true}
{"action": "wifi", "enabled": true}
{"action": "bluetooth", "enabled": false}
{"action": "launch", "app": "firefox"}
{"action": "shutdown", "reboot": false}
{"action": "info", "type": "system"}
```

---

## 💬 Usage

### Voice Commands

```
"Hey AI, turn up the brightness"
"Hey AI, what's the battery level?"
"Hey AI, connect to WiFi"
"Hey AI, open Firefox"
"Hey AI, mute the volume"
"Hey AI, what time is it?"
"Hey AI, shutdown"
```

### Terminal Shell

```bash
$ aios-shell

AI-OS> turn brightness to 80%
Brightness set to 80%

AI-OS> what's my battery status?
Battery: 75%, Charging

AI-OS> open terminal
✓ Launched terminal
```

---

## ⚙️ Configuration

### API Keys (`/etc/aios/agent.env`)

```bash
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=your-key-here
```

### Agent Config (`/etc/aios/agent.json`)

```json
{
    "ai_provider": "openai",
    "model": "gpt-4",
    "voice_enabled": true,
    "wake_word": "hey ai",
    "tts_enabled": true
}
```

---

## 🎯 Supported Hardware

| Platform | Status | Build Target |
|----------|--------|--------------|
| x86_64 PC | ✅ | `x86_64` |
| Raspberry Pi 4 | ✅ | `rpi4` |
| Generic ARM64 | ✅ | `generic_arm64` |
| QEMU (Testing) | ✅ | `qemu` |

---

## 📂 Output Files

After building, find these in `build/output/`:

| File | Description |
|------|-------------|
| `bzImage` | Linux kernel |
| `rootfs.ext4` | Root filesystem |
| `sdcard.img` | Full disk image |
| `aios.iso` | Bootable ISO |

---

## 🔒 Note About Android

The `/ports/android/` directory contains an **optional Android port** of the AI agent. This is a separate implementation that runs as an Android app, not the main AI-OS.

The main AI-OS is a **standalone Linux-based OS** in `/core/`, `/build/`, and `/rootfs/`.

---

## 📄 License

MIT License

---

<p align="center">
  <strong>AI-OS: The Operating System That Understands You</strong>
</p>
