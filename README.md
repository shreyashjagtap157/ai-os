# AI-OS: Next-Gen AI-Integrated Operating System (Prototype)

This project is a research prototype for an AI-native OS, branching from Linux concepts, with a built-in agent, multimodal input, and adaptive UI.
## Development

Start the async agent: `python -m agent.async_agent`

## Plugin sandboxes and manifests

Plugins may be provided either as a single-module runner (legacy) or as
a package. The runner supports both styles:

- Legacy module: `agent/plugins/<name>_runner.py` is invoked as
	`python -m agent.plugins.<name>_runner`.
- Package: `agent/plugins/<name>/__main__.py` is invoked as
	`python -m agent.plugins.<name>` and may include a `manifest.yaml`.

Place an optional `plugin.yaml` / `manifest.yaml` next to the plugin to
declare a permission manifest. Example manifest fields:

```yaml
name: example_plugin
network: false
filesystem: false
exec: false
max_cpu_seconds: 5
max_memory_mb: 256
```

The runner enforces `max_cpu_seconds` (best-effort timeout) and `max_memory_mb`
by monitoring the subprocess using `psutil`. For robust isolation use Docker
by setting the environment variable `DOCKER_SANDBOX=1` (requires Docker).

Metrics (Prometheus) are exported at the agent `/metrics` endpoint. The
plugin runner exposes `ai_os_plugin_exec_total` and
`ai_os_plugin_exec_duration_seconds`.

## Storing secrets in OS keyring

The agent loads `api_key` and `session_hmac_key` from `config.yaml` if present,
otherwise it attempts to read them from the OS keyring (using the `keyring`
library). To store secrets using the included helper:

```powershell
cd 'd:\Project\ai-os'
python -m agent.cli.secrets set-api YOUR_API_KEY
python -m agent.cli.secrets set-hmac YOUR_HMAC_KEY
```

On Linux/Mac this will use the system keyring (e.g. Secret Service / Keychain).
On Windows it uses the Windows Credential Manager. Ensure the `keyring`
dependency is installed (`pip install -r requirements.txt`).

## Running tests

Install test dependencies and run pytest:

```powershell
cd 'd:\Project\ai-os'
python -m pip install -r requirements.txt
python -m pytest -q
```

# AI-OS: Next-Gen AI-Integrated Operating System (Prototype)

This project is a research prototype for an AI-native OS, branching from Linux concepts, with a built-in agent, multimodal input, and adaptive UI.

## Structure
- `agent/` – Python-based system agent, command registry, system API stubs
- `agent/input/` – Multimodal input handlers (text, voice, gesture)
- `ui/` – Adaptive shell interface (shared command registry with agent)
- `userland/` – Shell scripts and utilities
- `docs/` – Documentation and roadmap
- `tests/` – Unit and integration tests
- `core/`, `system/`, `build/`, `rootfs/`, `ports/` – Future expansion areas

## Key Features
- **Command Registry** – Centralized, extensible command system shared by agent and UI shell
- **System API** – Secure, sandboxed access to file operations, time, and echo
- **Multimodal Input** – Text (with EOF/interrupt handling), voice (stub), gesture (stub with data class)
- **Logging** – Structured logging via Python's logging module
- **Error Handling** – Graceful error messages and recovery for all commands
- **Shared Interfaces** – Agent and UI shell use the same command registry

## Usage

### Run the Agent
```bash
python -m agent.agent
```
Type `help` for available commands. Type `exit` or `quit` to exit.

### Run the UI Shell
```bash
python -m ui.shell
```

### Available Commands
- `help` – Show available commands
- `exit`, `quit` – Exit
- `time` – Show system time
- `ls [path]` – List files in directory
- `echo <text>` – Echo a message

## Testing
```bash
pytest -q tests/
```

## Future Work
- Integrate real voice input (SpeechRecognition, Whisper)
- Integrate gesture recognition (MediaPipe, OpenCV)
- Add more system commands (process management, networking, etc.)
- Persistent command history and session logging
- Configuration file support (YAML/TOML)
- Integration with LLM backends (OpenAI, Anthropic)

## Status
Early prototype with improved structure, command registry, and error handling. Core agent loop and UI shell functional.
