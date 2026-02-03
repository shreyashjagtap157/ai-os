"""
AI-OS LLM Integration Module
Provides a unified interface for different LLM providers (OpenAI, Anthropic, local)
with integrated tool/function calling support.
"""
import os
import logging
from typing import Optional, Dict, Any, List, AsyncIterator, Union
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import json

logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Represents a chat message"""
    role: str  # system, user, assistant, tool
    content: str
    tool_calls: Optional[List[Dict]] = None  # For assistant messages with tool calls
    tool_call_id: Optional[str] = None  # For tool response messages
    name: Optional[str] = None  # Tool name for tool responses
    
    def to_dict(self) -> Dict[str, Any]:
        d = {"role": self.role, "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = self.tool_calls
        if self.tool_call_id:
            d["tool_call_id"] = self.tool_call_id
        if self.name:
            d["name"] = self.name
        return d


@dataclass
class ToolCall:
    """Represents an LLM tool call request"""
    id: str
    name: str
    arguments: Dict[str, Any]

    @classmethod
    def from_openai(cls, tc: Dict) -> "ToolCall":
        args = tc.get("function", {}).get("arguments", "{}")
        if isinstance(args, str):
            args = json.loads(args)
        return cls(
            id=tc.get("id", ""),
            name=tc.get("function", {}).get("name", ""),
            arguments=args,
        )


@dataclass
class LLMResponse:
    """Response from an LLM"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    tool_calls: List[ToolCall] = field(default_factory=list)


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def complete(self, messages: List[Message], tools: Optional[List[Dict]] = None, **kwargs) -> LLMResponse:
        """Generate a completion, optionally with tools"""
        pass
    
    @abstractmethod
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[str]:
        """Stream a completion"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider with retry logic and tool calling support"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self._client = None
        self.max_retries = 3
        self.retry_delay = 1.0
    
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        return self._client
    
    async def complete(self, messages: List[Message], tools: Optional[List[Dict]] = None, **kwargs) -> LLMResponse:
        import asyncio
        
        last_error = None
        for attempt in range(self.max_retries):
            try:
                request_kwargs = {
                    "model": kwargs.get("model", self.model),
                    "messages": [m.to_dict() for m in messages],
                    "temperature": kwargs.get("temperature", 0.7),
                    "max_tokens": kwargs.get("max_tokens", 2048),
                }
                
                # Add tools if provided
                if tools:
                    request_kwargs["tools"] = tools
                    request_kwargs["tool_choice"] = kwargs.get("tool_choice", "auto")
                
                response = await self.client.chat.completions.create(**request_kwargs)
                
                # Parse tool calls if present
                tool_calls = []
                message = response.choices[0].message
                if hasattr(message, 'tool_calls') and message.tool_calls:
                    for tc in message.tool_calls:
                        tool_calls.append(ToolCall.from_openai({
                            "id": tc.id,
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            }
                        }))
                
                return LLMResponse(
                    content=message.content or "",
                    model=response.model,
                    usage={
                        "prompt_tokens": response.usage.prompt_tokens,
                        "completion_tokens": response.usage.completion_tokens,
                        "total_tokens": response.usage.total_tokens
                    },
                    finish_reason=response.choices[0].finish_reason,
                    tool_calls=tool_calls,
                )
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)  # Exponential backoff
                    await asyncio.sleep(delay)
        
        raise last_error
    
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[str]:
        stream = await self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[m.to_dict() for m in messages],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048),
            stream=True
        )
        
        async for chunk in stream:
            if chunk.choices[0].delta.content:
                yield chunk.choices[0].delta.content

class AnthropicProvider(LLMProvider):
    """Anthropic Claude API provider"""
    
    def __init__(self, api_key: str, model: str = "claude-3-opus-20240229"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from anthropic import AsyncAnthropic
                self._client = AsyncAnthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("Anthropic library not installed. Run: pip install anthropic")
        return self._client
    
    async def complete(self, messages: List[Message], **kwargs) -> LLMResponse:
        # Separate system message from conversation
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                conv_messages.append({"role": m.role, "content": m.content})
        
        response = await self.client.messages.create(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", 2048),
            system=system_msg,
            messages=conv_messages
        )
        
        return LLMResponse(
            content=response.content[0].text,
            model=response.model,
            usage={
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            },
            finish_reason=response.stop_reason
        )
    
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[str]:
        system_msg = ""
        conv_messages = []
        for m in messages:
            if m.role == "system":
                system_msg = m.content
            else:
                conv_messages.append({"role": m.role, "content": m.content})
        
        async with self.client.messages.stream(
            model=kwargs.get("model", self.model),
            max_tokens=kwargs.get("max_tokens", 2048),
            system=system_msg,
            messages=conv_messages
        ) as stream:
            async for text in stream.text_stream:
                yield text


class LocalProvider(LLMProvider):
    """Local/fallback provider for when no API is available"""
    
    def __init__(self):
        self.model = "local-rule-based"
        self._commands = {
            "help": "Available commands: help, time, date, ls, cd, echo, clear, exit",
            "time": "Use 'time' to get current time",
            "ls": "Use 'ls [path]' to list directory contents",
            "echo": "Use 'echo [message]' to print a message",
        }
    
    async def complete(self, messages: List[Message], **kwargs) -> LLMResponse:
        last_message = messages[-1].content.lower().strip() if messages else ""
        
        # Simple pattern matching fallback
        if "help" in last_message:
            content = self._commands["help"]
        elif any(word in last_message for word in ["hello", "hi", "hey"]):
            content = "Hello! I'm AI-OS assistant. Type 'help' for available commands."
        elif "?" in last_message:
            content = "I'm running in local mode without AI backend. Type 'help' for available commands."
        else:
            content = f"Command not recognized: {last_message}. Type 'help' for assistance."
        
        return LLMResponse(
            content=content,
            model=self.model,
            usage={"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        )
    
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[str]:
        response = await self.complete(messages, **kwargs)
        for char in response.content:
            yield char


class LLMManager:
    """Manages LLM providers, routing, and tool execution"""
    
    SYSTEM_PROMPT = """You are AI-OS, an intelligent operating system assistant. 
You help users interact with their computer through natural language commands.
You have access to tools that can execute system commands, manage files, and retrieve information.

When a user asks you to perform a task:
1. Analyze what tools you need to use
2. Call the appropriate tools to complete the task
3. Report the results clearly to the user

Always be helpful, concise, and security-conscious. For dangerous operations, explain what will happen.
If a task requires multiple steps, you can call multiple tools in sequence."""

    MAX_CONVERSATION_HISTORY = 20
    MAX_TOOL_ITERATIONS = 10  # Prevent infinite tool loops

    def __init__(self, tool_executor=None):
        self._provider: Optional[LLMProvider] = None
        self._conversation: List[Message] = []
        self._tool_executor = tool_executor
        self._tools_schema: List[Dict] = []
        self._setup_provider()
    
    def _setup_provider(self):
        """Setup the appropriate LLM provider based on available API keys"""
        from agent.config import settings
        
        if settings.ai.openai_api_key:
            self._provider = OpenAIProvider(
                api_key=settings.ai.openai_api_key,
                model=settings.ai.default_model
            )
            logger.info("Using OpenAI provider")
        elif settings.ai.anthropic_api_key:
            self._provider = AnthropicProvider(
                api_key=settings.ai.anthropic_api_key
            )
            logger.info("Using Anthropic provider")
        else:
            self._provider = LocalProvider()
            logger.info("No API key found, using local fallback mode")
        
        self._conversation = [Message(role="system", content=self.SYSTEM_PROMPT)]
    
    def set_tool_executor(self, executor):
        """Set the tool executor and load tool schemas"""
        self._tool_executor = executor
        if executor and executor.registry:
            self._tools_schema = executor.registry.get_openai_tools()
            logger.info(f"Loaded {len(self._tools_schema)} tools for LLM")
    
    def _truncate_history(self):
        """Truncate conversation history to prevent memory issues"""
        if len(self._conversation) > self.MAX_CONVERSATION_HISTORY:
            self._conversation = [self._conversation[0]] + self._conversation[-(self.MAX_CONVERSATION_HISTORY - 1):]
    
    async def _execute_tool_calls(self, tool_calls: List[ToolCall]) -> List[Message]:
        """Execute tool calls and return tool response messages"""
        tool_messages = []
        
        for tc in tool_calls:
            logger.info(f"Executing tool: {tc.name} with args: {tc.arguments}")
            
            if self._tool_executor:
                result = await self._tool_executor.execute_async(tc.name, tc.arguments)
                output = str(result)
            else:
                output = f"Error: Tool executor not configured"
            
            tool_messages.append(Message(
                role="tool",
                content=output,
                tool_call_id=tc.id,
                name=tc.name,
            ))
        
        return tool_messages
    
    async def chat(self, user_input: str, stream: bool = False, use_tools: bool = True) -> str:
        """Send a message and get a response, potentially with tool use"""
        self._conversation.append(Message(role="user", content=user_input))
        self._truncate_history()
        
        tools = self._tools_schema if (use_tools and self._tool_executor) else None
        
        # Tool use loop
        for iteration in range(self.MAX_TOOL_ITERATIONS):
            if stream and not tools:
                # Streaming only for final response without tools
                full_response = ""
                async for chunk in self._provider.stream(self._conversation):
                    print(chunk, end="", flush=True)
                    full_response += chunk
                print()
                response_content = full_response
                self._conversation.append(Message(role="assistant", content=response_content))
                return response_content
            
            response = await self._provider.complete(self._conversation, tools=tools)
            
            # Check if LLM wants to call tools
            if response.tool_calls:
                # Add assistant message with tool calls
                self._conversation.append(Message(
                    role="assistant",
                    content=response.content or "",
                    tool_calls=[{
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.name, "arguments": json.dumps(tc.arguments)}
                    } for tc in response.tool_calls]
                ))
                
                # Execute tools and add results
                tool_messages = await self._execute_tool_calls(response.tool_calls)
                self._conversation.extend(tool_messages)
                
                # Continue loop for LLM to process tool results
                continue
            
            # No more tool calls, we have the final response
            response_content = response.content
            self._conversation.append(Message(role="assistant", content=response_content))
            self._truncate_history()
            return response_content
        
        # Max iterations reached
        return "I've reached the maximum number of tool calls. Please try a simpler request."
    
    async def chat_simple(self, user_input: str) -> str:
        """Simple chat without tools (for quick queries)"""
        return await self.chat(user_input, use_tools=False)
    
    def clear_history(self):
        """Clear conversation history (keep system prompt)"""
        self._conversation = [self._conversation[0]]
    
    @property
    def provider_name(self) -> str:
        """Get current provider name"""
        if isinstance(self._provider, OpenAIProvider):
            return "OpenAI"
        elif isinstance(self._provider, AnthropicProvider):
            return "Anthropic"
        else:
            return "Local"

# Global LLM manager instance
llm_manager = LLMManager()
