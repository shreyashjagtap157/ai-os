"""
AI-OS LLM Integration Module
Provides a unified interface for different LLM providers (OpenAI, Anthropic, local)
"""
import os
from typing import Optional, Dict, Any, List, AsyncIterator
from dataclasses import dataclass
from abc import ABC, abstractmethod
import json


@dataclass
class Message:
    """Represents a chat message"""
    role: str  # system, user, assistant
    content: str
    
    def to_dict(self) -> Dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass
class LLMResponse:
    """Response from an LLM"""
    content: str
    model: str
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None


class LLMProvider(ABC):
    """Abstract base class for LLM providers"""
    
    @abstractmethod
    async def complete(self, messages: List[Message], **kwargs) -> LLMResponse:
        """Generate a completion"""
        pass
    
    @abstractmethod
    async def stream(self, messages: List[Message], **kwargs) -> AsyncIterator[str]:
        """Stream a completion"""
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI API provider"""
    
    def __init__(self, api_key: str, model: str = "gpt-4"):
        self.api_key = api_key
        self.model = model
        self._client = None
    
    @property
    def client(self):
        if self._client is None:
            try:
                from openai import AsyncOpenAI
                self._client = AsyncOpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("OpenAI library not installed. Run: pip install openai")
        return self._client
    
    async def complete(self, messages: List[Message], **kwargs) -> LLMResponse:
        response = await self.client.chat.completions.create(
            model=kwargs.get("model", self.model),
            messages=[m.to_dict() for m in messages],
            temperature=kwargs.get("temperature", 0.7),
            max_tokens=kwargs.get("max_tokens", 2048)
        )
        
        return LLMResponse(
            content=response.choices[0].message.content,
            model=response.model,
            usage={
                "prompt_tokens": response.usage.prompt_tokens,
                "completion_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens
            },
            finish_reason=response.choices[0].finish_reason
        )
    
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
    """Manages LLM providers and routing"""
    
    SYSTEM_PROMPT = """You are AI-OS, an intelligent operating system assistant. 
You help users interact with their computer through natural language commands.
You can execute system commands, manage files, answer questions, and automate tasks.

Available system commands you can help with:
- File operations: ls, cd, pwd, cat, mkdir, rm, cp, mv
- System info: time, date, whoami, uptime
- Process management: ps, kill
- Network: ping, curl

Always be helpful, concise, and security-conscious. Never execute dangerous commands without confirmation.
If a task requires multiple steps, explain your plan before executing."""

    MAX_CONVERSATION_HISTORY = 20  # Limit to prevent memory issues

    def __init__(self):
        self._provider: Optional[LLMProvider] = None
        self._conversation: List[Message] = []
        self._setup_provider()
    
    def _setup_provider(self):
        """Setup the appropriate LLM provider based on available API keys"""
        from agent.config import settings
        
        if settings.ai.openai_api_key:
            self._provider = OpenAIProvider(
                api_key=settings.ai.openai_api_key,
                model=settings.ai.default_model
            )
            print("[AI-OS] Using OpenAI provider")
        elif settings.ai.anthropic_api_key:
            self._provider = AnthropicProvider(
                api_key=settings.ai.anthropic_api_key
            )
            print("[AI-OS] Using Anthropic provider")
        else:
            self._provider = LocalProvider()
            print("[AI-OS] No API key found, using local fallback mode")
        
        # Initialize conversation with system prompt
        self._conversation = [Message(role="system", content=self.SYSTEM_PROMPT)]
    
    def _truncate_history(self):
        """Truncate conversation history to prevent memory issues"""
        if len(self._conversation) > self.MAX_CONVERSATION_HISTORY:
            # Keep system prompt and last N-1 messages
            self._conversation = [self._conversation[0]] + self._conversation[-(self.MAX_CONVERSATION_HISTORY - 1):]
    
    async def chat(self, user_input: str, stream: bool = False) -> str:
        """Send a message and get a response"""
        self._conversation.append(Message(role="user", content=user_input))
        self._truncate_history()
        
        if stream:
            full_response = ""
            async for chunk in self._provider.stream(self._conversation):
                print(chunk, end="", flush=True)
                full_response += chunk
            print()  # Newline after streaming
            response_content = full_response
        else:
            response = await self._provider.complete(self._conversation)
            response_content = response.content
        
        self._conversation.append(Message(role="assistant", content=response_content))
        self._truncate_history()
        return response_content
    
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
