"""
AI-OS Agent: Main event loop with command registry and system API.
"""
import logging
from pathlib import Path
from typing import Callable
from agent.input.text_input import get_text_input
from agent.input.voice_input import get_voice_input
from agent.input.gesture_input import get_gesture_input
from agent.system_api import SystemAPI

logger = logging.getLogger(__name__)


def parse_command(raw: str) -> tuple[str, list[str]]:
    """Parse raw command string into command and args."""
    parts = raw.strip().split()
    if not parts:
        return "", []
    return parts[0], parts[1:]


class CommandRegistry:
    """Registry of available commands."""
    def __init__(self, api: SystemAPI):
        self.api = api
        self.commands: dict[str, tuple[Callable, str]] = {
            "exit": (self._cmd_exit, "Exit the agent"),
            "quit": (self._cmd_exit, "Alias for exit"),
            "help": (self._cmd_help, "Show this help message"),
            "time": (self._cmd_time, "Show system time"),
            "ls": (self._cmd_ls, "List files (usage: ls [path])"),
            "echo": (self._cmd_echo, "Echo a message (usage: echo <text>)"),
        }

    def _cmd_exit(self, args: list[str]) -> bool:
        logger.info("Agent exit requested")
        return False

    def _cmd_help(self, args: list[str]) -> bool:
        print("[AI-OS] Available commands:")
        for name, (_, desc) in self.commands.items():
            print(f"  {name:10} - {desc}")
        return True

    def _cmd_time(self, args: list[str]) -> bool:
        print(f"[AI-OS] System time: {self.api.get_time()}")
        return True

    def _cmd_ls(self, args: list[str]) -> bool:
        path = args[0] if args else "."
        try:
            files = self.api.list_files(path)
            print(f"[AI-OS] Files in {path}: {files}")
        except FileNotFoundError:
            print(f"[AI-OS] Error: Directory not found: {path}")
        except NotADirectoryError as e:
            print(f"[AI-OS] Error: {e}")
        except PermissionError as e:
            print(f"[AI-OS] Error: {e}")
        except Exception as e:
            logger.exception("Unexpected error in ls command")
            print(f"[AI-OS] Error: {e}")
        return True

    def _cmd_echo(self, args: list[str]) -> bool:
        msg = " ".join(args)
        print(f"[AI-OS] {self.api.echo(msg)}")
        return True

    def execute(self, cmd: str, args: list[str]) -> bool:
        """Execute a command. Return False to exit agent."""
        if not cmd:
            return True
        # log command for audit
        try:
            from agent.session import log_command_signed
            from agent.config import load_config

            cfg = load_config()
            hmac_key = cfg.session_hmac_key
            log_command_signed(cmd, args, hmac_key)
        except Exception:
            logger.exception("Failed to write session log")

        if cmd not in self.commands:
            print(f"[AI-OS] Unknown command: {cmd}. Type 'help' for available commands.")
            return True
        handler, _ = self.commands[cmd]
        try:
            return handler(args)
        except Exception as e:
            logger.exception(f"Error executing {cmd}")
            print(f"[AI-OS] Error: {e}")
            return True


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="[%(name)s] %(levelname)s: %(message)s"
    )
    allowed_root = Path.cwd()
    api = SystemAPI(allowed_root=allowed_root)
    registry = CommandRegistry(api)
    # plugin loading
    try:
        from agent.plugins import __init__ as plugin_loader
        from importlib import import_module
        plugin_dir = Path(__file__).parent / "plugins"
        discovered = plugin_loader.discover_plugins(plugin_dir)
        for name in discovered:
            mod = plugin_loader.load_plugin(f"agent.plugins.{name}")
            if mod and hasattr(mod, 'register'):
                try:
                    mod.register(registry)
                    logger.info(f"Loaded plugin: {name}")
                except Exception:
                    logger.exception(f"Plugin {name} failed to register")
    except Exception:
        logger.exception("Plugin loading failed")
    logger.info("AI-OS Agent starting...")
    print("[AI-OS Agent] Starting event loop (type 'help' for commands)")
    while True:
        raw = get_text_input()
        cmd, args = parse_command(raw)
        if not registry.execute(cmd, args):
            break
        # Future hooks for voice/gesture input
        # voice = get_voice_input()
        # gesture = get_gesture_input()


if __name__ == "__main__":
    main()
