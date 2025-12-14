"""
AI-OS Modern Shell Interface
Rich, interactive terminal UI with AI assistance
"""
import asyncio
from typing import Optional, Callable, List
from dataclasses import dataclass
from enum import Enum


class ShellTheme(Enum):
    """Shell color themes"""
    DARK = "dark"
    LIGHT = "light"
    CYBERPUNK = "cyberpunk"
    MINIMAL = "minimal"


@dataclass
class ShellConfig:
    """Shell configuration"""
    theme: ShellTheme = ShellTheme.DARK
    show_suggestions: bool = True
    show_time: bool = True
    animation_enabled: bool = True
    prompt_style: str = "arrow"  # arrow, classic, minimal


class ModernShell:
    """
    AI-OS Modern Shell with rich terminal interface.
    Features: Command history, auto-complete, syntax highlighting, and AI integration.
    """
    
    BANNER = r"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║     _    ___       ___  ____                                   ║
    ║    / \  |_ _|     / _ \/ ___|                                  ║
    ║   / _ \  | |_____| | | \___ \                                  ║
    ║  / ___ \ | |_____| |_| |___) |                                 ║
    ║ /_/   \_\___|     \___/|____/                                  ║
    ║                                                                ║
    ║  AI-Native Operating System Shell                              ║
    ║  Type 'help' for commands, 'ai <query>' for AI assistance      ║
    ╚═══════════════════════════════════════════════════════════════╝
    """
    
    def __init__(self, config: Optional[ShellConfig] = None):
        self.config = config or ShellConfig()
        self._history: List[str] = []
        self._running = False
        self._llm_manager = None
        self._system_api = None
        
    def _setup_dependencies(self):
        """Setup LLM and System API"""
        try:
            from agent.llm import llm_manager
            from agent.system_api import system_api
            self._llm_manager = llm_manager
            self._system_api = system_api
        except ImportError as e:
            print(f"[Shell] Warning: {e}")
    
    def _get_prompt(self) -> str:
        """Generate the shell prompt"""
        import datetime
        
        cwd = self._system_api.get_current_directory() if self._system_api else "~"
        
        # Shorten path if too long
        if len(cwd) > 40:
            parts = cwd.split(os.sep)
            cwd = os.sep.join([".."] + parts[-2:])
        
        time_str = datetime.datetime.now().strftime("%H:%M") if self.config.show_time else ""
        
        if self.config.prompt_style == "arrow":
            return f"\n┌─[AI-OS]─[{cwd}]" + (f"─[{time_str}]" if time_str else "") + f"\n└─▶ "
        elif self.config.prompt_style == "classic":
            return f"[AI-OS {cwd}]$ "
        else:
            return f"{cwd} ▶ "
    
    def _print_styled(self, text: str, style: str = ""):
        """Print with optional styling (uses Rich if available)"""
        try:
            from rich.console import Console
            from rich.markdown import Markdown
            console = Console()
            
            if style == "markdown":
                console.print(Markdown(text))
            elif style == "success":
                console.print(f"[green]{text}[/green]")
            elif style == "error":
                console.print(f"[red]{text}[/red]")
            elif style == "warning":
                console.print(f"[yellow]{text}[/yellow]")
            elif style == "info":
                console.print(f"[blue]{text}[/blue]")
            else:
                console.print(text)
        except ImportError:
            print(text)
    
    async def _handle_ai_command(self, query: str):
        """Handle AI commands"""
        if not self._llm_manager:
            self._print_styled("AI not available. Check your API keys.", "error")
            return
        
        self._print_styled(f"\n🤖 AI ({self._llm_manager.provider_name}):", "info")
        
        try:
            response = await self._llm_manager.chat(query, stream=True)
        except Exception as e:
            self._print_styled(f"AI Error: {e}", "error")
    
    def _handle_system_command(self, command: str) -> bool:
        """Handle system commands. Returns True if command was handled."""
        if not self._system_api:
            return False
        
        parts = command.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        result = None
        
        if cmd == "ls" or cmd == "dir":
            result = self._system_api.list_files(args or ".")
        elif cmd == "cd":
            result = self._system_api.change_directory(args or "~")
        elif cmd == "pwd":
            self._print_styled(self._system_api.get_current_directory(), "info")
            return True
        elif cmd == "cat" or cmd == "type":
            result = self._system_api.read_file(args)
        elif cmd == "mkdir":
            result = self._system_api.create_directory(args)
        elif cmd == "rm" or cmd == "del":
            result = self._system_api.delete(args)
        elif cmd == "cp" or cmd == "copy":
            src, dst = args.split(maxsplit=1) if " " in args else (args, "")
            result = self._system_api.copy(src, dst)
        elif cmd == "mv" or cmd == "move":
            src, dst = args.split(maxsplit=1) if " " in args else (args, "")
            result = self._system_api.move(src, dst)
        elif cmd == "time":
            self._print_styled(f"🕐 {self._system_api.get_time()}", "info")
            return True
        elif cmd == "sysinfo":
            info = self._system_api.get_system_info()
            for key, value in info.items():
                self._print_styled(f"  {key}: {value}")
            return True
        elif cmd == "ps":
            procs = self._system_api.get_processes()
            for p in procs:
                self._print_styled(f"  {p['pid']:6} {p['name'][:30]:30} CPU: {p['cpu_percent']:.1f}%")
            return True
        elif cmd == "find":
            result = self._system_api.search_files(args)
        elif cmd == "history":
            for i, h in enumerate(self._system_api.get_history(), 1):
                self._print_styled(f"  {i}. {h}")
            return True
        elif cmd == "echo":
            self._print_styled(args)
            return True
        else:
            return False
        
        if result:
            if result.success:
                self._print_styled(result.output, "success" if "Created" in result.output or "Copied" in result.output else "")
            else:
                self._print_styled(f"Error: {result.error}", "error")
            return True
        
        return False
    
    def _show_help(self):
        """Display help information"""
        help_text = """
╔══════════════════════════════════════════════════════════════════╗
║                        AI-OS Shell Help                           ║
╠══════════════════════════════════════════════════════════════════╣
║  AI Commands:                                                     ║
║    ai <query>       Ask AI for help or execute complex tasks     ║
║    chat             Start interactive AI chat mode               ║
║    clear-ai         Clear AI conversation history                ║
║                                                                   ║
║  File Commands:                                                   ║
║    ls, dir          List directory contents                      ║
║    cd <path>        Change directory                             ║
║    pwd              Print working directory                      ║
║    cat <file>       Display file contents                        ║
║    mkdir <dir>      Create directory                             ║
║    rm <path>        Delete file/directory                        ║
║    cp <src> <dst>   Copy file/directory                          ║
║    mv <src> <dst>   Move file/directory                          ║
║    find <pattern>   Search for files                             ║
║                                                                   ║
║  System Commands:                                                 ║
║    time             Show current time                            ║
║    sysinfo          Show system information                      ║
║    ps               List running processes                       ║
║    history          Show command history                         ║
║                                                                   ║
║  Shell Commands:                                                  ║
║    help             Show this help                               ║
║    clear            Clear screen                                 ║
║    theme <name>     Change theme (dark/light/cyberpunk)          ║
║    exit, quit       Exit shell                                   ║
╚══════════════════════════════════════════════════════════════════╝
        """
        self._print_styled(help_text)
    
    async def run(self):
        """Main shell loop"""
        self._setup_dependencies()
        self._running = True
        
        # Print banner
        self._print_styled(self.BANNER, "info")
        
        while self._running:
            try:
                # Get input
                prompt = self._get_prompt()
                user_input = input(prompt).strip()
                
                if not user_input:
                    continue
                
                # Add to history
                self._history.append(user_input)
                
                # Parse command
                lower_input = user_input.lower()
                
                # Built-in shell commands
                if lower_input in ("exit", "quit"):
                    self._print_styled("\n👋 Goodbye!", "info")
                    self._running = False
                elif lower_input == "help":
                    self._show_help()
                elif lower_input == "clear":
                    print("\033[2J\033[H")  # Clear screen
                elif lower_input == "clear-ai":
                    if self._llm_manager:
                        self._llm_manager.clear_history()
                        self._print_styled("AI conversation cleared.", "success")
                elif lower_input.startswith("theme "):
                    theme_name = user_input[6:].strip()
                    try:
                        self.config.theme = ShellTheme(theme_name)
                        self._print_styled(f"Theme changed to: {theme_name}", "success")
                    except ValueError:
                        self._print_styled(f"Unknown theme: {theme_name}", "error")
                
                # AI commands
                elif lower_input.startswith("ai "):
                    query = user_input[3:].strip()
                    await self._handle_ai_command(query)
                elif lower_input == "chat":
                    self._print_styled("🤖 Entering AI chat mode. Type 'exit' to return to shell.", "info")
                    while True:
                        chat_input = input("\n💬 You: ").strip()
                        if chat_input.lower() == "exit":
                            break
                        await self._handle_ai_command(chat_input)
                
                # System commands
                elif self._handle_system_command(user_input):
                    pass  # Command was handled
                
                # Unknown command - try AI
                else:
                    self._print_styled(f"Unknown command: {user_input}. Type 'help' for commands or 'ai <query>' for AI.", "warning")
                    
            except KeyboardInterrupt:
                self._print_styled("\n(Use 'exit' to quit)", "warning")
            except EOFError:
                self._running = False
            except Exception as e:
                self._print_styled(f"Error: {e}", "error")
        
        self._running = False


# Import os for path operations
import os


def launch_shell():
    """Launch the AI-OS shell"""
    shell = ModernShell()
    asyncio.run(shell.run())


if __name__ == "__main__":
    launch_shell()
