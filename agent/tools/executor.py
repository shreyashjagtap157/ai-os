"""
Tool Executor - Executes tools with validation, sandboxing, and logging.
"""

import asyncio
import logging
import time
from typing import Any, Dict, Optional
from concurrent.futures import ThreadPoolExecutor

from .registry import Tool, ToolRegistry, ToolResult, tool_registry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """Executes tools with safety checks and logging"""

    def __init__(
        self,
        registry: Optional[ToolRegistry] = None,
        max_workers: int = 4,
        timeout_seconds: float = 30.0,
        require_confirmation_callback: Optional[callable] = None,
    ):
        self.registry = registry or tool_registry
        self.max_workers = max_workers
        self.timeout = timeout_seconds
        self._executor = ThreadPoolExecutor(max_workers=max_workers)
        self._confirmation_callback = require_confirmation_callback
        self._execution_history: list = []

    def validate_args(self, tool: Tool, args: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate arguments against tool schema"""
        for param in tool.parameters:
            if param.required and param.name not in args:
                return False, f"Missing required parameter: {param.name}"
            
            if param.name in args:
                value = args[param.name]
                # Basic type checking
                expected = param.type.value
                if expected == "string" and not isinstance(value, str):
                    return False, f"Parameter {param.name} must be a string"
                elif expected == "integer" and not isinstance(value, int):
                    return False, f"Parameter {param.name} must be an integer"
                elif expected == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param.name} must be a number"
                elif expected == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param.name} must be a boolean"
                elif expected == "array" and not isinstance(value, list):
                    return False, f"Parameter {param.name} must be an array"
                
                # Enum validation
                if param.enum and value not in param.enum:
                    return False, f"Parameter {param.name} must be one of: {param.enum}"
        
        return True, None

    def execute(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool synchronously"""
        tool = self.registry.get(tool_name)
        if not tool:
            return ToolResult(
                success=False,
                output=None,
                error=f"Unknown tool: {tool_name}"
            )

        # Validate arguments
        valid, error = self.validate_args(tool, args)
        if not valid:
            return ToolResult(success=False, output=None, error=error)

        # Check confirmation if required
        if tool.requires_confirmation and self._confirmation_callback:
            confirmed = self._confirmation_callback(tool_name, args)
            if not confirmed:
                return ToolResult(
                    success=False,
                    output=None,
                    error="User cancelled operation"
                )

        # Execute with timeout
        start_time = time.time()
        try:
            future = self._executor.submit(tool.handler, **args)
            result = future.result(timeout=self.timeout)
            
            if not isinstance(result, ToolResult):
                result = ToolResult(success=True, output=result)
                
        except TimeoutError:
            result = ToolResult(
                success=False,
                output=None,
                error=f"Tool execution timed out after {self.timeout}s"
            )
        except Exception as e:
            logger.exception(f"Tool {tool_name} failed")
            result = ToolResult(
                success=False,
                output=None,
                error=str(e)
            )

        elapsed = time.time() - start_time
        result.metadata["execution_time"] = elapsed
        result.metadata["tool_name"] = tool_name

        # Log execution
        self._execution_history.append({
            "tool": tool_name,
            "args": args,
            "result": result.to_dict(),
            "timestamp": time.time(),
            "duration": elapsed,
        })

        logger.info(f"Executed {tool_name} in {elapsed:.3f}s: success={result.success}")
        return result

    async def execute_async(self, tool_name: str, args: Dict[str, Any]) -> ToolResult:
        """Execute a tool asynchronously"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            None,
            lambda: self.execute(tool_name, args)
        )

    def execute_multiple(
        self,
        calls: list[tuple[str, Dict[str, Any]]]
    ) -> list[ToolResult]:
        """Execute multiple tools in parallel"""
        futures = []
        for tool_name, args in calls:
            tool = self.registry.get(tool_name)
            if tool:
                valid, _ = self.validate_args(tool, args)
                if valid:
                    futures.append(
                        self._executor.submit(self.execute, tool_name, args)
                    )
                else:
                    futures.append(None)
            else:
                futures.append(None)

        results = []
        for i, future in enumerate(futures):
            if future is None:
                tool_name = calls[i][0]
                results.append(ToolResult(
                    success=False,
                    output=None,
                    error=f"Invalid tool or arguments: {tool_name}"
                ))
            else:
                try:
                    results.append(future.result(timeout=self.timeout))
                except Exception as e:
                    results.append(ToolResult(
                        success=False,
                        output=None,
                        error=str(e)
                    ))
        return results

    def get_history(self, limit: int = 100) -> list:
        """Get recent execution history"""
        return self._execution_history[-limit:]

    def clear_history(self) -> None:
        """Clear execution history"""
        self._execution_history.clear()

    def shutdown(self) -> None:
        """Shutdown the executor"""
        self._executor.shutdown(wait=True)
