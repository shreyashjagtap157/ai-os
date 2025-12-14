# AI-OS Project Structure

## Overview
AI-OS is a standalone Linux-based operating system with AI agent control at its core.
This is NOT an Android app - it's a complete bootable operating system.

## Directory Structure

```
ai-os/
│
├── core/                          # Core OS Components
│   ├── kernel/                    # Kernel patches & config
│   ├── init/                      # Init system
│   ├── services/                  # System services (daemons)
│   │   ├── aios-agent/           # AI Agent daemon
│   │   ├── aios-voice/           # Voice recognition daemon
│   │   ├── aios-input/           # Input handling daemon
│   │   └── aios-display/         # Display management daemon
│   ├── hal/                      # Hardware Abstraction Layer
│   ├── ui/                       # User Interface (Wayland compositor)
│   └── cli/                      # Command line tools
│
├── system/                        # System Libraries & APIs
│   ├── libaios/                  # Core AI-OS library
│   ├── libagent/                 # Agent API library
│   └── libui/                    # UI library
│
├── build/                         # Build System
│   ├── scripts/                  # Build scripts
│   ├── configs/                  # Target configurations
│   ├── external/                 # Buildroot external tree
│   └── board/                    # Board-specific files
│
├── rootfs/                        # Root Filesystem Overlay
│   ├── etc/                      # Configuration files
│   ├── usr/                      # User programs
│   └── var/                      # Variable data
│
├── tools/                         # Development Tools
│   ├── emulator/                 # QEMU scripts
│   └── flash/                    # Flashing utilities
│
├── docs/                          # Documentation
│
└── ports/                         # Platform Ports (Optional)
    └── android/                  # Android port (separate)
```

## What Makes This an OS (Not an App)

1. **Custom Kernel** - Linux kernel with AI-OS patches
2. **Init System** - systemd-based with AI-OS services
3. **Core Daemons** - Always-running system services
4. **HAL** - Direct hardware access
5. **Compositor** - Own display server (Wayland)
6. **Build System** - Creates bootable images
7. **Boots Directly** - No underlying OS required
