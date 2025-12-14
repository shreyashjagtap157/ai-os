# AI-OS Architecture

## System Overview

AI-OS is a standalone Linux-based operating system with an AI agent at its core.

```
┌─────────────────────────────────────────────────────────────┐
│                    AI-OS Architecture                        │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│   ┌────────────────────────────────────────────────────┐    │
│   │                 User Interface                      │    │
│   │  ┌──────────┐  ┌──────────┐  ┌────────────────┐   │    │
│   │  │   Shell  │  │   CLI    │  │  Notifications │   │    │
│   │  │  (GTK)   │  │  (aios)  │  │    Daemon      │   │    │
│   │  └──────────┘  └──────────┘  └────────────────┘   │    │
│   └────────────────────────────────────────────────────┘    │
│                            │                                 │
│   ┌────────────────────────────────────────────────────┐    │
│   │                 Agent Layer                         │    │
│   │  ┌──────────────────────────────────────────────┐  │    │
│   │  │            AI Agent Daemon                    │  │    │
│   │  │  - LLM Integration (OpenAI, Anthropic)       │  │    │
│   │  │  - Action Execution                          │  │    │
│   │  │  - Plugin System                             │  │    │
│   │  │  - Local Fallback                            │  │    │
│   │  └──────────────────────────────────────────────┘  │    │
│   └────────────────────────────────────────────────────┘    │
│                            │                                 │
│   ┌────────────────────────────────────────────────────┐    │
│   │                System Services                      │    │
│   │  ┌────────┐  ┌────────┐  ┌────────┐  ┌────────┐   │    │
│   │  │ Voice  │  │ Input  │  │ Power  │  │Network │   │    │
│   │  └────────┘  └────────┘  └────────┘  └────────┘   │    │
│   └────────────────────────────────────────────────────┘    │
│                            │                                 │
│   ┌────────────────────────────────────────────────────┐    │
│   │           Hardware Abstraction Layer               │    │
│   │  - Display    - Audio     - Network               │    │
│   │  - Power      - Input     - Storage               │    │
│   └────────────────────────────────────────────────────┘    │
│                            │                                 │
├────────────────────────────────────────────────────────────┤
│                        systemd                              │
├────────────────────────────────────────────────────────────┤
│                     Linux Kernel                            │
└─────────────────────────────────────────────────────────────┘
```

## Component Details

### AI Agent Daemon (`aios-agent`)
The central intelligence of the system.
- Receives commands via Unix socket
- Processes through LLM (OpenAI/Anthropic) or local fallback
- Executes actions through HAL
- Manages conversation history

### Voice Service (`aios-voice`)
- Wake word detection ("Hey AI")
- Speech-to-text (STT)
- Text-to-speech (TTS)
- Sends transcriptions to agent

### Display Compositor (`aios-display`)
- Wayland compositor (Weston-based)
- Manages display output
- Launches shell UI

### Input Service (`aios-input`)
- Global hotkey handling
- Volume/brightness keys
- Super+Space for AI activation

### Power Manager (`aios-power`)
- Battery monitoring
- Power profiles
- Low-battery actions
- Suspend/hibernate

### Network Manager (`aios-network`)
- WiFi management
- Bluetooth pairing
- VPN connections

### Notification Daemon (`aios-notify`)
- Desktop notifications
- Action support
- History

## IPC Protocol

All services communicate via Unix sockets using JSON:

```json
// Request
{
    "cmd": "chat",
    "text": "turn brightness to 80%"
}

// Response
{
    "status": "ok",
    "response": "Brightness set to 80%",
    "action": {"action": "brightness", "level": 80},
    "action_result": {"success": true, "message": "Done"}
}
```

## Boot Sequence

1. Bootloader (GRUB)
2. Linux Kernel
3. Init script (`/init`)
4. systemd
5. aios-agent.service
6. aios-voice.service
7. aios-input.service
8. aios-power.service
9. aios-display.service (graphical.target)
10. Shell UI
