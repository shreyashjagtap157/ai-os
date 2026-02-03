"""
WebSocket Streaming API for Real-time LLM Responses

Provides real-time streaming of LLM responses and events
through WebSocket connections.

Features:
- Token-by-token streaming
- Multiple concurrent sessions
- Event-based notifications
- Heartbeat/keepalive
- Graceful reconnection support
"""

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class MessageType(str, Enum):
    """WebSocket message types"""
    # Client -> Server
    CHAT_REQUEST = "chat_request"
    CANCEL = "cancel"
    PING = "ping"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"
    
    # Server -> Client
    STREAM_START = "stream_start"
    STREAM_TOKEN = "stream_token"
    STREAM_END = "stream_end"
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    ERROR = "error"
    PONG = "pong"
    EVENT = "event"
    

@dataclass
class StreamSession:
    """A streaming session with a client"""
    session_id: str
    websocket: WebSocket
    user_id: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    subscriptions: set = field(default_factory=set)
    active_request_id: Optional[str] = None
    cancelled: bool = False
    
    def update_activity(self):
        self.last_activity = time.time()


class ConnectionManager:
    """Manages WebSocket connections and broadcasting"""
    
    def __init__(self):
        self.sessions: dict[str, StreamSession] = {}
        self.user_sessions: dict[str, set[str]] = defaultdict(set)
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket, user_id: Optional[str] = None) -> StreamSession:
        """Accept a new WebSocket connection"""
        await websocket.accept()
        
        session_id = str(uuid.uuid4())
        session = StreamSession(
            session_id=session_id,
            websocket=websocket,
            user_id=user_id
        )
        
        async with self._lock:
            self.sessions[session_id] = session
            if user_id:
                self.user_sessions[user_id].add(session_id)
        
        logger.info(f"WebSocket connected: {session_id}")
        return session
    
    async def disconnect(self, session_id: str):
        """Handle disconnection"""
        async with self._lock:
            session = self.sessions.pop(session_id, None)
            if session and session.user_id:
                self.user_sessions[session.user_id].discard(session_id)
        
        logger.info(f"WebSocket disconnected: {session_id}")
    
    async def send_message(self, session_id: str, message: dict):
        """Send a message to a specific session"""
        session = self.sessions.get(session_id)
        if session:
            try:
                await session.websocket.send_json(message)
                session.update_activity()
            except Exception as e:
                logger.error(f"Error sending to {session_id}: {e}")
                await self.disconnect(session_id)
    
    async def broadcast_to_user(self, user_id: str, message: dict):
        """Broadcast to all sessions of a user"""
        session_ids = list(self.user_sessions.get(user_id, set()))
        for session_id in session_ids:
            await self.send_message(session_id, message)
    
    async def broadcast_event(self, event_type: str, data: dict, subscribed_only: bool = True):
        """Broadcast an event to subscribed sessions"""
        message = {
            "type": MessageType.EVENT.value,
            "event": event_type,
            "data": data,
            "timestamp": time.time()
        }
        
        for session_id, session in list(self.sessions.items()):
            if not subscribed_only or event_type in session.subscriptions:
                await self.send_message(session_id, message)
    
    def get_session(self, session_id: str) -> Optional[StreamSession]:
        return self.sessions.get(session_id)
    
    def get_stats(self) -> dict:
        return {
            "active_connections": len(self.sessions),
            "unique_users": len(self.user_sessions)
        }


class StreamingLLMHandler:
    """Handles streaming LLM responses over WebSocket"""
    
    def __init__(self, llm_manager, tool_executor=None):
        self.llm = llm_manager
        self.tools = tool_executor
        self.active_requests: dict[str, asyncio.Task] = {}
    
    async def handle_chat_request(
        self,
        session: StreamSession,
        connection_manager: ConnectionManager,
        request_id: str,
        messages: list[dict],
        model: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        tools_enabled: bool = True
    ):
        """Process a chat request with streaming response"""
        session.active_request_id = request_id
        session.cancelled = False
        
        # Send stream start
        await connection_manager.send_message(session.session_id, {
            "type": MessageType.STREAM_START.value,
            "request_id": request_id,
            "timestamp": time.time()
        })
        
        try:
            full_response = ""
            tool_calls = []
            
            # Stream tokens from LLM
            async for chunk in self._stream_llm_response(
                messages=messages,
                model=model,
                temperature=temperature,
                max_tokens=max_tokens
            ):
                if session.cancelled:
                    break
                
                if chunk.get("type") == "token":
                    token = chunk["content"]
                    full_response += token
                    
                    await connection_manager.send_message(session.session_id, {
                        "type": MessageType.STREAM_TOKEN.value,
                        "request_id": request_id,
                        "token": token,
                        "timestamp": time.time()
                    })
                
                elif chunk.get("type") == "tool_call":
                    tool_call = chunk["tool_call"]
                    tool_calls.append(tool_call)
                    
                    await connection_manager.send_message(session.session_id, {
                        "type": MessageType.TOOL_CALL.value,
                        "request_id": request_id,
                        "tool_call": tool_call,
                        "timestamp": time.time()
                    })
                    
                    # Execute tool if enabled
                    if tools_enabled and self.tools:
                        result = await self._execute_tool(tool_call)
                        
                        await connection_manager.send_message(session.session_id, {
                            "type": MessageType.TOOL_RESULT.value,
                            "request_id": request_id,
                            "tool_call_id": tool_call.get("id"),
                            "result": result,
                            "timestamp": time.time()
                        })
            
            # Send stream end
            await connection_manager.send_message(session.session_id, {
                "type": MessageType.STREAM_END.value,
                "request_id": request_id,
                "full_response": full_response,
                "tool_calls": tool_calls,
                "cancelled": session.cancelled,
                "timestamp": time.time()
            })
            
        except Exception as e:
            logger.error(f"Error in chat request {request_id}: {e}")
            await connection_manager.send_message(session.session_id, {
                "type": MessageType.ERROR.value,
                "request_id": request_id,
                "error": str(e),
                "timestamp": time.time()
            })
        
        finally:
            session.active_request_id = None
    
    async def _stream_llm_response(
        self,
        messages: list[dict],
        model: Optional[str],
        temperature: float,
        max_tokens: int
    ):
        """Stream response from LLM provider"""
        # This integrates with the LLM manager's streaming capability
        # Implementation depends on the specific LLM provider
        
        try:
            import openai
            
            client = openai.AsyncOpenAI()
            
            response = await client.chat.completions.create(
                model=model or "gpt-4",
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                stream=True
            )
            
            async for chunk in response:
                if chunk.choices[0].delta.content:
                    yield {"type": "token", "content": chunk.choices[0].delta.content}
                
                if chunk.choices[0].delta.tool_calls:
                    for tool_call in chunk.choices[0].delta.tool_calls:
                        yield {
                            "type": "tool_call",
                            "tool_call": {
                                "id": tool_call.id,
                                "name": tool_call.function.name,
                                "arguments": tool_call.function.arguments
                            }
                        }
        
        except ImportError:
            # Fallback for testing without OpenAI
            test_response = "This is a simulated streaming response for testing purposes."
            for word in test_response.split():
                yield {"type": "token", "content": word + " "}
                await asyncio.sleep(0.05)
    
    async def _execute_tool(self, tool_call: dict) -> dict:
        """Execute a tool call"""
        if not self.tools:
            return {"error": "Tools not available"}
        
        try:
            result = await self.tools.execute(
                tool_call["name"],
                json.loads(tool_call.get("arguments", "{}"))
            )
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def cancel_request(self, request_id: str):
        """Cancel an active request"""
        task = self.active_requests.get(request_id)
        if task:
            task.cancel()


def create_streaming_app(
    llm_manager=None,
    tool_executor=None,
    cors_origins: list[str] = None
) -> FastAPI:
    """Create FastAPI app with WebSocket streaming support"""
    
    app = FastAPI(title="AI-OS Streaming API")
    
    # CORS
    if cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=cors_origins,
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"]
        )
    
    connection_manager = ConnectionManager()
    streaming_handler = StreamingLLMHandler(llm_manager, tool_executor)
    
    @app.websocket("/ws/chat")
    async def websocket_chat(websocket: WebSocket, user_id: Optional[str] = None):
        """Main WebSocket endpoint for chat streaming"""
        session = await connection_manager.connect(websocket, user_id)
        
        # Send welcome message
        await connection_manager.send_message(session.session_id, {
            "type": "connected",
            "session_id": session.session_id,
            "timestamp": time.time()
        })
        
        try:
            while True:
                # Receive message
                data = await websocket.receive_json()
                message_type = data.get("type")
                
                if message_type == MessageType.PING.value:
                    await connection_manager.send_message(session.session_id, {
                        "type": MessageType.PONG.value,
                        "timestamp": time.time()
                    })
                
                elif message_type == MessageType.CHAT_REQUEST.value:
                    request_id = data.get("request_id", str(uuid.uuid4()))
                    
                    # Handle chat request in background task
                    task = asyncio.create_task(
                        streaming_handler.handle_chat_request(
                            session=session,
                            connection_manager=connection_manager,
                            request_id=request_id,
                            messages=data.get("messages", []),
                            model=data.get("model"),
                            temperature=data.get("temperature", 0.7),
                            max_tokens=data.get("max_tokens", 2048),
                            tools_enabled=data.get("tools_enabled", True)
                        )
                    )
                    streaming_handler.active_requests[request_id] = task
                
                elif message_type == MessageType.CANCEL.value:
                    request_id = data.get("request_id")
                    if request_id:
                        session.cancelled = True
                        streaming_handler.cancel_request(request_id)
                
                elif message_type == MessageType.SUBSCRIBE.value:
                    events = data.get("events", [])
                    session.subscriptions.update(events)
                
                elif message_type == MessageType.UNSUBSCRIBE.value:
                    events = data.get("events", [])
                    session.subscriptions.difference_update(events)
        
        except WebSocketDisconnect:
            pass
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
        finally:
            await connection_manager.disconnect(session.session_id)
    
    @app.get("/ws/stats")
    async def get_stats():
        """Get WebSocket connection statistics"""
        return connection_manager.get_stats()
    
    @app.post("/ws/broadcast")
    async def broadcast_event(event_type: str, data: dict):
        """Broadcast an event to all subscribed clients"""
        await connection_manager.broadcast_event(event_type, data)
        return {"success": True}
    
    return app


# Standalone runner
if __name__ == "__main__":
    import uvicorn
    
    app = create_streaming_app(cors_origins=["*"])
    uvicorn.run(app, host="0.0.0.0", port=8765)
