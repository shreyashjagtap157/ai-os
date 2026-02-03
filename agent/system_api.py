"""
System API stubs with simple safety checks.
"""
from pathlib import Path
import datetime
import logging

logger = logging.getLogger(__name__)


class SystemAPI:
    """Secure system API for agent operations."""
    def __init__(self, allowed_root: Path | None = None):
        self.allowed_root = allowed_root.resolve() if allowed_root else None

    def _safe_path(self, path: str | Path) -> Path:
        p = Path(path).resolve()
        if self.allowed_root and self.allowed_root not in p.parents and p != self.allowed_root:
            logger.warning(f"Path access denied: {p} (outside {self.allowed_root})")
            raise PermissionError(f"Path not allowed: {p}")
        return p

    def list_files(self, path: str | Path = ".") -> list[str]:
        """List files in a directory."""
        try:
            p = self._safe_path(path)
            if not p.is_dir():
                raise NotADirectoryError(f"{p} is not a directory")
            return sorted([f.name for f in p.iterdir()])
        except FileNotFoundError as e:
            logger.error(f"Directory not found: {p}")
            raise
        except OSError as e:
            logger.error(f"Error listing {p}: {e}")
            raise

    def get_time(self) -> str:
        """Get current system time in ISO format."""
        return datetime.datetime.now().isoformat()

    def echo(self, msg: str) -> str:
        """Echo a message."""
        return msg
import os
import subprocess
import datetime
import platform
import shutil
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from pathlib import Path
import json


@dataclass
class CommandResult:
    """Result of a system command execution"""
    success: bool
    output: str
    error: str = ""
    return_code: int = 0


class SystemAPI:
    """
    Enhanced System API for AI-OS Agent.
    Provides secure, sandboxed access to system resources.
    """
    
    def __init__(self, sandbox_mode: bool = True):
        self.sandbox_mode = sandbox_mode
        self.home_dir = Path.home()
        self.current_dir = Path.cwd()
        self._history: List[str] = []
        
        # Allowed commands in sandbox mode
        self._safe_commands = {
            "ls", "dir", "pwd", "cd", "cat", "head", "tail", "echo",
            "date", "time", "whoami", "hostname", "uname", "uptime",
            "ps", "curl", "ping", "python", "pip"
        }
        
        # Dangerous patterns to block
        self._dangerous_patterns = [
            "rm -rf /", "rm -rf ~", ":(){ :|:& };:",  # Fork bomb
            "mkfs", "dd if=", "> /dev/", "chmod 777 /",
            "sudo rm", "sudo mkfs", "sudo dd"
        ]
    
    def _is_safe_command(self, command: str) -> Tuple[bool, str]:
        """Check if a command is safe to execute"""
        if not self.sandbox_mode:
            return True, ""
        
        # Check for dangerous patterns
        for pattern in self._dangerous_patterns:
            if pattern in command:
                return False, f"Blocked dangerous pattern: {pattern}"
        
        # Check command whitelist
        cmd_parts = command.split()
        if not cmd_parts:
            return False, "Empty command"
        
        base_cmd = cmd_parts[0]
        if base_cmd not in self._safe_commands:
            return False, f"Command '{base_cmd}' not in allowed list"
        
        return True, ""
    
    # === File System Operations ===
    
    def list_files(self, path: str = ".") -> CommandResult:
        """List files in a directory"""
        try:
            target = Path(path).expanduser().resolve()
            if not target.exists():
                return CommandResult(False, "", f"Path does not exist: {path}")
            
            files = []
            for item in target.iterdir():
                icon = "📁 " if item.is_dir() else "📄 "
                size = f" ({item.stat().st_size} bytes)" if item.is_file() else ""
                files.append(f"{icon}{item.name}{size}")
            
            return CommandResult(True, "\n".join(files) if files else "(empty directory)")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def read_file(self, path: str, lines: int = 50) -> CommandResult:
        """Read file contents"""
        try:
            target = Path(path).expanduser().resolve()
            if not target.is_file():
                return CommandResult(False, "", f"Not a file: {path}")
            
            with open(target, "r", encoding="utf-8", errors="replace") as f:
                content = "".join(f.readlines()[:lines])
            
            return CommandResult(True, content)
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def write_file(self, path: str, content: str) -> CommandResult:
        """Write content to a file"""
        try:
            target = Path(path).expanduser().resolve()
            with open(target, "w", encoding="utf-8") as f:
                f.write(content)
            return CommandResult(True, f"Written to {target}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def create_directory(self, path: str) -> CommandResult:
        """Create a directory"""
        try:
            target = Path(path).expanduser().resolve()
            target.mkdir(parents=True, exist_ok=True)
            return CommandResult(True, f"Created directory: {target}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def delete(self, path: str, recursive: bool = False) -> CommandResult:
        """Delete a file or directory"""
        try:
            target = Path(path).expanduser().resolve()
            
            if target.is_file():
                target.unlink()
                return CommandResult(True, f"Deleted file: {target}")
            elif target.is_dir():
                if recursive:
                    shutil.rmtree(target)
                else:
                    target.rmdir()
                return CommandResult(True, f"Deleted directory: {target}")
            else:
                return CommandResult(False, "", f"Path not found: {path}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def copy(self, src: str, dst: str) -> CommandResult:
        """Copy a file or directory"""
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()
            
            if src_path.is_file():
                shutil.copy2(src_path, dst_path)
            else:
                shutil.copytree(src_path, dst_path)
            
            return CommandResult(True, f"Copied {src_path} to {dst_path}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def move(self, src: str, dst: str) -> CommandResult:
        """Move a file or directory"""
        try:
            src_path = Path(src).expanduser().resolve()
            dst_path = Path(dst).expanduser().resolve()
            shutil.move(str(src_path), str(dst_path))
            return CommandResult(True, f"Moved {src_path} to {dst_path}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    # === System Information ===
    
    def get_time(self) -> str:
        """Get current date and time"""
        return datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        import psutil
        
        return {
            "platform": platform.system(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "hostname": platform.node(),
            "python_version": platform.python_version(),
            "cpu_count": os.cpu_count(),
            "cpu_percent": psutil.cpu_percent(interval=0.1),
            "memory_total_gb": round(psutil.virtual_memory().total / (1024**3), 2),
            "memory_used_percent": psutil.virtual_memory().percent,
            "disk_total_gb": round(psutil.disk_usage("/").total / (1024**3), 2),
            "disk_used_percent": psutil.disk_usage("/").percent,
        }
    
    def get_processes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get running processes"""
        import psutil
        
        processes = []
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
            try:
                processes.append(proc.info)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        
        # Sort by CPU usage
        processes.sort(key=lambda x: x.get('cpu_percent', 0), reverse=True)
        return processes[:limit]
    
    # === Command Execution ===
    
    def execute(self, command: str, timeout: int = 30) -> CommandResult:
        """Execute a shell command safely"""
        is_safe, reason = self._is_safe_command(command)
        if not is_safe:
            return CommandResult(False, "", f"Command blocked: {reason}")
        
        self._history.append(command)
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.current_dir)
            )
            
            return CommandResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode
            )
        except subprocess.TimeoutExpired:
            return CommandResult(False, "", f"Command timed out after {timeout}s")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    # === Navigation ===
    
    def change_directory(self, path: str) -> CommandResult:
        """Change current directory"""
        try:
            target = Path(path).expanduser().resolve()
            if not target.is_dir():
                return CommandResult(False, "", f"Not a directory: {path}")
            
            self.current_dir = target
            os.chdir(target)
            return CommandResult(True, f"Changed to: {target}")
        except Exception as e:
            return CommandResult(False, "", str(e))
    
    def get_current_directory(self) -> str:
        """Get current working directory"""
        return str(self.current_dir)
    
    # === Utilities ===
    
    def echo(self, message: str) -> str:
        """Echo a message"""
        return message
    
    def get_history(self, limit: int = 20) -> List[str]:
        """Get command history"""
        return self._history[-limit:]
    
    def search_files(self, pattern: str, path: str = ".") -> CommandResult:
        """Search for files matching a pattern"""
        try:
            target = Path(path).expanduser().resolve()
            matches = list(target.rglob(pattern))
            
            if matches:
                return CommandResult(True, "\n".join(str(m) for m in matches[:50]))
            else:
                return CommandResult(True, f"No files matching '{pattern}'")
        except Exception as e:
            return CommandResult(False, "", str(e))


# Global instance
system_api = SystemAPI()
