"""
Built-in tools for AI-OS agent.
File operations, system info, process management, etc.
"""

import os
import subprocess
import shutil
import platform
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from .registry import (
    Tool,
    ToolParameter,
    ToolResult,
    ParameterType,
    tool_registry,
)


def register_builtin_tools(allowed_root: Optional[Path] = None) -> None:
    """Register all built-in tools with the global registry"""
    
    safe_root = allowed_root or Path.home()

    def _is_safe_path(path: str) -> bool:
        """Check if path is within allowed root"""
        try:
            resolved = Path(path).resolve()
            return str(resolved).startswith(str(safe_root.resolve()))
        except Exception:
            return False

    # ============ File Operations ============

    def list_directory(path: str = ".", show_hidden: bool = False) -> ToolResult:
        """List contents of a directory"""
        try:
            if not _is_safe_path(path):
                return ToolResult(False, None, f"Access denied: {path}")
            
            p = Path(path)
            if not p.exists():
                return ToolResult(False, None, f"Path does not exist: {path}")
            if not p.is_dir():
                return ToolResult(False, None, f"Not a directory: {path}")
            
            entries = []
            for entry in sorted(p.iterdir()):
                if not show_hidden and entry.name.startswith('.'):
                    continue
                entry_type = "dir" if entry.is_dir() else "file"
                size = entry.stat().st_size if entry.is_file() else None
                entries.append({
                    "name": entry.name,
                    "type": entry_type,
                    "size": size,
                })
            
            return ToolResult(True, entries)
        except PermissionError:
            return ToolResult(False, None, f"Permission denied: {path}")
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="list_directory",
        description="List the contents of a directory. Returns file names, types, and sizes.",
        handler=list_directory,
        parameters=[
            ToolParameter("path", ParameterType.STRING, "Path to directory", required=False),
            ToolParameter("show_hidden", ParameterType.BOOLEAN, "Show hidden files", required=False),
        ],
        category="filesystem",
    ))

    def read_file(path: str, max_lines: int = 1000) -> ToolResult:
        """Read contents of a text file"""
        try:
            if not _is_safe_path(path):
                return ToolResult(False, None, f"Access denied: {path}")
            
            p = Path(path)
            if not p.exists():
                return ToolResult(False, None, f"File not found: {path}")
            if not p.is_file():
                return ToolResult(False, None, f"Not a file: {path}")
            
            # Check file size
            size = p.stat().st_size
            if size > 1_000_000:  # 1MB limit
                return ToolResult(False, None, "File too large (>1MB)")
            
            content = p.read_text(encoding='utf-8', errors='replace')
            lines = content.split('\n')
            if len(lines) > max_lines:
                content = '\n'.join(lines[:max_lines])
                content += f"\n... (truncated, {len(lines)} total lines)"
            
            return ToolResult(True, content, metadata={"size": size, "lines": len(lines)})
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="read_file",
        description="Read the contents of a text file. Limited to 1MB files.",
        handler=read_file,
        parameters=[
            ToolParameter("path", ParameterType.STRING, "Path to file"),
            ToolParameter("max_lines", ParameterType.INTEGER, "Maximum lines to read", required=False),
        ],
        category="filesystem",
    ))

    def write_file(path: str, content: str, append: bool = False) -> ToolResult:
        """Write content to a file"""
        try:
            if not _is_safe_path(path):
                return ToolResult(False, None, f"Access denied: {path}")
            
            p = Path(path)
            p.parent.mkdir(parents=True, exist_ok=True)
            
            mode = 'a' if append else 'w'
            with open(p, mode, encoding='utf-8') as f:
                f.write(content)
            
            return ToolResult(True, f"Written {len(content)} bytes to {path}")
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="write_file",
        description="Write content to a file. Creates parent directories if needed.",
        handler=write_file,
        parameters=[
            ToolParameter("path", ParameterType.STRING, "Path to file"),
            ToolParameter("content", ParameterType.STRING, "Content to write"),
            ToolParameter("append", ParameterType.BOOLEAN, "Append instead of overwrite", required=False),
        ],
        category="filesystem",
        requires_confirmation=True,
    ))

    def create_directory(path: str) -> ToolResult:
        """Create a directory"""
        try:
            if not _is_safe_path(path):
                return ToolResult(False, None, f"Access denied: {path}")
            
            p = Path(path)
            p.mkdir(parents=True, exist_ok=True)
            return ToolResult(True, f"Created directory: {path}")
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="create_directory",
        description="Create a directory and any parent directories as needed.",
        handler=create_directory,
        parameters=[
            ToolParameter("path", ParameterType.STRING, "Path to create"),
        ],
        category="filesystem",
    ))

    def delete_path(path: str, recursive: bool = False) -> ToolResult:
        """Delete a file or directory"""
        try:
            if not _is_safe_path(path):
                return ToolResult(False, None, f"Access denied: {path}")
            
            p = Path(path)
            if not p.exists():
                return ToolResult(False, None, f"Path does not exist: {path}")
            
            if p.is_file():
                p.unlink()
            elif p.is_dir():
                if recursive:
                    shutil.rmtree(p)
                else:
                    p.rmdir()  # Only works on empty dirs
            
            return ToolResult(True, f"Deleted: {path}")
        except OSError as e:
            if "not empty" in str(e).lower():
                return ToolResult(False, None, "Directory not empty. Use recursive=true to delete.")
            return ToolResult(False, None, str(e))
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="delete_path",
        description="Delete a file or directory. Use recursive=true for non-empty directories.",
        handler=delete_path,
        parameters=[
            ToolParameter("path", ParameterType.STRING, "Path to delete"),
            ToolParameter("recursive", ParameterType.BOOLEAN, "Delete recursively", required=False),
        ],
        category="filesystem",
        requires_confirmation=True,
    ))

    # ============ System Information ============

    def get_system_info() -> ToolResult:
        """Get system information"""
        try:
            info = {
                "platform": platform.system(),
                "platform_release": platform.release(),
                "platform_version": platform.version(),
                "architecture": platform.machine(),
                "hostname": platform.node(),
                "processor": platform.processor(),
                "python_version": platform.python_version(),
            }
            
            # Try to get memory info
            try:
                import psutil
                mem = psutil.virtual_memory()
                info["memory_total_gb"] = round(mem.total / (1024**3), 2)
                info["memory_available_gb"] = round(mem.available / (1024**3), 2)
                info["memory_percent_used"] = mem.percent
                info["cpu_count"] = psutil.cpu_count()
                info["cpu_percent"] = psutil.cpu_percent(interval=0.1)
            except ImportError:
                pass
            
            return ToolResult(True, info)
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="get_system_info",
        description="Get system information including OS, CPU, memory, etc.",
        handler=get_system_info,
        parameters=[],
        category="system",
    ))

    def get_current_time(timezone: str = "local") -> ToolResult:
        """Get current date and time"""
        try:
            now = datetime.now()
            return ToolResult(True, {
                "datetime": now.isoformat(),
                "date": now.strftime("%Y-%m-%d"),
                "time": now.strftime("%H:%M:%S"),
                "weekday": now.strftime("%A"),
                "timestamp": now.timestamp(),
            })
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="get_current_time",
        description="Get the current date and time.",
        handler=get_current_time,
        parameters=[
            ToolParameter("timezone", ParameterType.STRING, "Timezone (default: local)", required=False),
        ],
        category="system",
    ))

    def get_environment_variable(name: str) -> ToolResult:
        """Get an environment variable value"""
        # Only allow safe env vars
        safe_vars = {"PATH", "HOME", "USER", "SHELL", "LANG", "PWD", "TERM"}
        if name.upper() not in safe_vars:
            return ToolResult(False, None, f"Access to {name} not allowed")
        
        value = os.environ.get(name)
        if value is None:
            return ToolResult(False, None, f"Variable not set: {name}")
        return ToolResult(True, value)

    tool_registry.register(Tool(
        name="get_environment_variable",
        description="Get the value of a safe environment variable.",
        handler=get_environment_variable,
        parameters=[
            ToolParameter("name", ParameterType.STRING, "Variable name", enum=["PATH", "HOME", "USER", "SHELL", "PWD"]),
        ],
        category="system",
    ))

    # ============ Process Management ============

    def list_processes(filter_name: str = "") -> ToolResult:
        """List running processes"""
        try:
            import psutil
            
            processes = []
            for proc in psutil.process_iter(['pid', 'name', 'username', 'memory_percent', 'cpu_percent']):
                try:
                    info = proc.info
                    if filter_name and filter_name.lower() not in info['name'].lower():
                        continue
                    processes.append({
                        "pid": info['pid'],
                        "name": info['name'],
                        "user": info['username'],
                        "memory_pct": round(info['memory_percent'], 2),
                        "cpu_pct": round(info['cpu_percent'], 2),
                    })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            
            # Sort by memory usage
            processes.sort(key=lambda x: x['memory_pct'], reverse=True)
            return ToolResult(True, processes[:50])  # Limit to top 50
        except ImportError:
            return ToolResult(False, None, "psutil not installed")
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="list_processes",
        description="List running processes with CPU and memory usage.",
        handler=list_processes,
        parameters=[
            ToolParameter("filter_name", ParameterType.STRING, "Filter by process name", required=False),
        ],
        category="process",
    ))

    # ============ Shell Commands (restricted) ============

    def run_command(command: str, timeout: int = 30) -> ToolResult:
        """Run a shell command (restricted to safe commands)"""
        # Whitelist of allowed commands
        allowed_commands = {
            "ls", "dir", "pwd", "cd", "cat", "head", "tail", "wc",
            "date", "whoami", "hostname", "uname", "df", "du",
            "echo", "grep", "find", "which", "type", "env",
            "ping", "curl", "wget",
        }
        
        # Extract base command
        parts = command.split()
        if not parts:
            return ToolResult(False, None, "Empty command")
        
        base_cmd = parts[0].split('/')[-1]  # Handle full paths
        
        if base_cmd not in allowed_commands:
            return ToolResult(False, None, f"Command not allowed: {base_cmd}")
        
        # Block dangerous patterns
        dangerous = ['|', ';', '&&', '||', '`', '$(' , '>', '<', '..']
        for pattern in dangerous:
            if pattern in command:
                return ToolResult(False, None, f"Pattern not allowed: {pattern}")
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(safe_root),
            )
            
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            
            return ToolResult(
                success=result.returncode == 0,
                output=output,
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}",
                metadata={"returncode": result.returncode},
            )
        except subprocess.TimeoutExpired:
            return ToolResult(False, None, f"Command timed out after {timeout}s")
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="run_command",
        description="Run a whitelisted shell command. Dangerous operations are blocked.",
        handler=run_command,
        parameters=[
            ToolParameter("command", ParameterType.STRING, "Shell command to run"),
            ToolParameter("timeout", ParameterType.INTEGER, "Timeout in seconds", required=False),
        ],
        category="shell",
        requires_confirmation=True,
    ))

    # ============ Search ============

    def search_files(
        pattern: str,
        directory: str = ".",
        file_type: str = "all",
        max_results: int = 100
    ) -> ToolResult:
        """Search for files matching a pattern"""
        try:
            if not _is_safe_path(directory):
                return ToolResult(False, None, f"Access denied: {directory}")
            
            p = Path(directory)
            if not p.exists():
                return ToolResult(False, None, f"Directory not found: {directory}")
            
            results = []
            for match in p.rglob(pattern):
                if len(results) >= max_results:
                    break
                
                if file_type == "file" and not match.is_file():
                    continue
                if file_type == "dir" and not match.is_dir():
                    continue
                
                results.append({
                    "path": str(match),
                    "type": "dir" if match.is_dir() else "file",
                    "size": match.stat().st_size if match.is_file() else None,
                })
            
            return ToolResult(True, results, metadata={"count": len(results)})
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="search_files",
        description="Search for files matching a glob pattern.",
        handler=search_files,
        parameters=[
            ToolParameter("pattern", ParameterType.STRING, "Glob pattern (e.g., '*.py')"),
            ToolParameter("directory", ParameterType.STRING, "Starting directory", required=False),
            ToolParameter("file_type", ParameterType.STRING, "Filter: 'file', 'dir', or 'all'", required=False, enum=["all", "file", "dir"]),
            ToolParameter("max_results", ParameterType.INTEGER, "Maximum results", required=False),
        ],
        category="filesystem",
    ))

    def search_in_files(
        text: str,
        directory: str = ".",
        file_pattern: str = "*",
        case_sensitive: bool = False,
        max_results: int = 50
    ) -> ToolResult:
        """Search for text within files"""
        try:
            if not _is_safe_path(directory):
                return ToolResult(False, None, f"Access denied: {directory}")
            
            p = Path(directory)
            results = []
            search_text = text if case_sensitive else text.lower()
            
            for file_path in p.rglob(file_pattern):
                if len(results) >= max_results:
                    break
                
                if not file_path.is_file():
                    continue
                
                # Skip binary files and large files
                try:
                    if file_path.stat().st_size > 500_000:  # 500KB
                        continue
                    
                    content = file_path.read_text(encoding='utf-8', errors='ignore')
                    search_content = content if case_sensitive else content.lower()
                    
                    if search_text in search_content:
                        # Find matching lines
                        matches = []
                        for i, line in enumerate(content.split('\n'), 1):
                            check_line = line if case_sensitive else line.lower()
                            if search_text in check_line:
                                matches.append({"line": i, "text": line.strip()[:200]})
                                if len(matches) >= 5:  # Max 5 matches per file
                                    break
                        
                        if matches:
                            results.append({
                                "file": str(file_path),
                                "matches": matches,
                            })
                except Exception:
                    continue
            
            return ToolResult(True, results, metadata={"files_matched": len(results)})
        except Exception as e:
            return ToolResult(False, None, str(e))

    tool_registry.register(Tool(
        name="search_in_files",
        description="Search for text content within files (grep-like).",
        handler=search_in_files,
        parameters=[
            ToolParameter("text", ParameterType.STRING, "Text to search for"),
            ToolParameter("directory", ParameterType.STRING, "Starting directory", required=False),
            ToolParameter("file_pattern", ParameterType.STRING, "File glob pattern", required=False),
            ToolParameter("case_sensitive", ParameterType.BOOLEAN, "Case sensitive search", required=False),
            ToolParameter("max_results", ParameterType.INTEGER, "Maximum file results", required=False),
        ],
        category="filesystem",
    ))
