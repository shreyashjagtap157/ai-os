# AI-OS Ports

This directory contains platform-specific ports of AI-OS.

## Available Ports

### Android (`android/`)
Android implementation of the AI agent as a launcher/overlay app.
This allows running AI-OS agent capabilities on existing Android devices.

**Note**: The Android port is a separate implementation, not the main AI-OS.
The main AI-OS is a standalone Linux-based operating system in `/core/`.

## Future Ports

- **iOS**: Companion app for Apple devices
- **Web**: Browser-based interface
- **Windows**: Desktop agent

## Port Structure

Each port should contain:
```
port-name/
├── README.md          # Port-specific documentation
├── src/               # Source code
├── build/             # Build configuration
└── docs/              # Documentation
```
