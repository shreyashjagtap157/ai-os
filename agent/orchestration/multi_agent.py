"""
Multi-Agent Orchestration System

Enables multiple specialized agents to work together on complex tasks
with a supervisor coordinating their activities.

Features:
- Supervisor agent for task decomposition and coordination
- Specialized agent roles (coder, researcher, writer, etc.)
- Inter-agent communication protocol
- Parallel and sequential task execution
- State machine for workflow management
- Human-in-the-loop checkpoints
"""

import asyncio
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional
from collections import defaultdict

logger = logging.getLogger(__name__)


class AgentRole(Enum):
    """Predefined agent roles with specializations"""
    SUPERVISOR = "supervisor"
    CODER = "coder"
    RESEARCHER = "researcher"
    WRITER = "writer"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    PLANNER = "planner"
    EXECUTOR = "executor"
    CUSTOM = "custom"


class TaskState(Enum):
    """Task execution states"""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_HUMAN = "waiting_human"
    WAITING_AGENT = "waiting_agent"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageType(Enum):
    """Inter-agent message types"""
    TASK_ASSIGNMENT = "task_assignment"
    TASK_RESULT = "task_result"
    QUERY = "query"
    RESPONSE = "response"
    STATUS_UPDATE = "status_update"
    FEEDBACK = "feedback"
    ESCALATION = "escalation"


@dataclass
class AgentMessage:
    """Message between agents"""
    id: str
    msg_type: MessageType
    sender: str
    recipient: str
    content: dict
    timestamp: float = field(default_factory=time.time)
    reply_to: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.msg_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "content": self.content,
            "timestamp": self.timestamp,
            "reply_to": self.reply_to
        }


@dataclass
class Task:
    """A task to be executed by an agent"""
    id: str
    description: str
    assigned_to: Optional[str] = None
    created_by: str = "supervisor"
    state: TaskState = TaskState.PENDING
    priority: int = 5  # 1-10, higher is more urgent
    dependencies: list[str] = field(default_factory=list)
    subtasks: list[str] = field(default_factory=list)
    result: Any = None
    error: Optional[str] = None
    context: dict = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    completed_at: Optional[float] = None
    metadata: dict = field(default_factory=dict)
    
    def is_ready(self, completed_tasks: set[str]) -> bool:
        """Check if all dependencies are satisfied"""
        return all(dep in completed_tasks for dep in self.dependencies)


@dataclass
class AgentCapabilities:
    """Defines what an agent can do"""
    role: AgentRole
    skills: list[str]
    tools: list[str]
    max_concurrent_tasks: int = 1
    system_prompt: str = ""
    
    def can_handle(self, task_description: str, required_skills: list[str] = None) -> bool:
        """Check if agent can handle a task"""
        if required_skills:
            return all(skill in self.skills for skill in required_skills)
        return True


class Agent(ABC):
    """Base class for all agents"""
    
    def __init__(
        self,
        agent_id: str,
        capabilities: AgentCapabilities,
        llm_provider=None
    ):
        self.id = agent_id
        self.capabilities = capabilities
        self.llm = llm_provider
        
        self.inbox: asyncio.Queue[AgentMessage] = asyncio.Queue()
        self.current_tasks: dict[str, Task] = {}
        self.completed_tasks: set[str] = set()
        self._running = False
    
    @abstractmethod
    async def process_task(self, task: Task) -> Any:
        """Process a task and return result"""
        pass
    
    async def send_message(self, msg: AgentMessage, message_bus: "MessageBus"):
        """Send a message to another agent"""
        await message_bus.send(msg)
    
    async def receive_message(self) -> AgentMessage:
        """Receive a message from inbox"""
        return await self.inbox.get()
    
    async def run(self, message_bus: "MessageBus"):
        """Main agent loop"""
        self._running = True
        
        while self._running:
            try:
                # Check for messages with timeout
                try:
                    msg = await asyncio.wait_for(self.receive_message(), timeout=0.5)
                    await self._handle_message(msg, message_bus)
                except asyncio.TimeoutError:
                    pass
                
                # Process current tasks
                await self._process_pending_tasks(message_bus)
                
            except Exception as e:
                logger.error(f"Agent {self.id} error: {e}")
                await asyncio.sleep(1)
    
    async def _handle_message(self, msg: AgentMessage, message_bus: "MessageBus"):
        """Handle incoming message"""
        if msg.msg_type == MessageType.TASK_ASSIGNMENT:
            task = Task(**msg.content["task"])
            self.current_tasks[task.id] = task
            
        elif msg.msg_type == MessageType.QUERY:
            response = await self._handle_query(msg.content)
            await self.send_message(
                AgentMessage(
                    id=str(uuid.uuid4()),
                    msg_type=MessageType.RESPONSE,
                    sender=self.id,
                    recipient=msg.sender,
                    content=response,
                    reply_to=msg.id
                ),
                message_bus
            )
    
    async def _handle_query(self, query: dict) -> dict:
        """Handle a query from another agent"""
        return {"status": "ok", "agent_id": self.id}
    
    async def _process_pending_tasks(self, message_bus: "MessageBus"):
        """Process pending tasks"""
        for task_id, task in list(self.current_tasks.items()):
            if task.state == TaskState.PENDING:
                task.state = TaskState.IN_PROGRESS
                
                try:
                    result = await self.process_task(task)
                    task.result = result
                    task.state = TaskState.COMPLETED
                    task.completed_at = time.time()
                    
                    # Report result back
                    await self.send_message(
                        AgentMessage(
                            id=str(uuid.uuid4()),
                            msg_type=MessageType.TASK_RESULT,
                            sender=self.id,
                            recipient=task.created_by,
                            content={
                                "task_id": task.id,
                                "result": result,
                                "state": task.state.value
                            }
                        ),
                        message_bus
                    )
                    
                except Exception as e:
                    task.error = str(e)
                    task.state = TaskState.FAILED
                    logger.error(f"Task {task_id} failed: {e}")
                
                finally:
                    self.completed_tasks.add(task_id)
                    del self.current_tasks[task_id]
    
    def stop(self):
        """Stop the agent"""
        self._running = False


class CoderAgent(Agent):
    """Specialized agent for coding tasks"""
    
    def __init__(self, agent_id: str, llm_provider=None):
        capabilities = AgentCapabilities(
            role=AgentRole.CODER,
            skills=["python", "javascript", "typescript", "debugging", "code_review"],
            tools=["file_read", "file_write", "run_command", "search_code"],
            max_concurrent_tasks=2,
            system_prompt="""You are an expert software developer. 
            Write clean, efficient, and well-documented code.
            Follow best practices and design patterns."""
        )
        super().__init__(agent_id, capabilities, llm_provider)
    
    async def process_task(self, task: Task) -> Any:
        """Process coding task"""
        if self.llm:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": self.capabilities.system_prompt},
                    {"role": "user", "content": task.description}
                ]
            )
            return {"code": response.content, "language": task.context.get("language", "python")}
        
        return {"code": "# Placeholder implementation", "language": "python"}


class ResearcherAgent(Agent):
    """Specialized agent for research tasks"""
    
    def __init__(self, agent_id: str, llm_provider=None):
        capabilities = AgentCapabilities(
            role=AgentRole.RESEARCHER,
            skills=["web_search", "summarization", "fact_checking", "data_analysis"],
            tools=["web_search", "file_read", "knowledge_base"],
            max_concurrent_tasks=3,
            system_prompt="""You are a skilled researcher.
            Find accurate, relevant information and cite sources.
            Summarize findings clearly and objectively."""
        )
        super().__init__(agent_id, capabilities, llm_provider)
    
    async def process_task(self, task: Task) -> Any:
        """Process research task"""
        if self.llm:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": self.capabilities.system_prompt},
                    {"role": "user", "content": f"Research the following: {task.description}"}
                ]
            )
            return {"findings": response.content, "sources": []}
        
        return {"findings": "Research placeholder", "sources": []}


class WriterAgent(Agent):
    """Specialized agent for writing tasks"""
    
    def __init__(self, agent_id: str, llm_provider=None):
        capabilities = AgentCapabilities(
            role=AgentRole.WRITER,
            skills=["technical_writing", "documentation", "copywriting", "editing"],
            tools=["file_read", "file_write", "grammar_check"],
            max_concurrent_tasks=2,
            system_prompt="""You are a professional writer.
            Write clear, engaging, and well-structured content.
            Adapt your style to the target audience."""
        )
        super().__init__(agent_id, capabilities, llm_provider)
    
    async def process_task(self, task: Task) -> Any:
        """Process writing task"""
        if self.llm:
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": self.capabilities.system_prompt},
                    {"role": "user", "content": task.description}
                ]
            )
            return {"content": response.content, "word_count": len(response.content.split())}
        
        return {"content": "Writing placeholder", "word_count": 0}


class MessageBus:
    """Central message bus for inter-agent communication"""
    
    def __init__(self):
        self.agents: dict[str, Agent] = {}
        self.message_history: list[AgentMessage] = []
        self._lock = asyncio.Lock()
    
    def register_agent(self, agent: Agent):
        """Register an agent with the message bus"""
        self.agents[agent.id] = agent
        logger.info(f"Agent registered: {agent.id}")
    
    def unregister_agent(self, agent_id: str):
        """Unregister an agent"""
        self.agents.pop(agent_id, None)
    
    async def send(self, message: AgentMessage):
        """Send a message to the recipient's inbox"""
        async with self._lock:
            self.message_history.append(message)
        
        recipient = self.agents.get(message.recipient)
        if recipient:
            await recipient.inbox.put(message)
        else:
            logger.warning(f"Unknown recipient: {message.recipient}")
    
    async def broadcast(self, message: AgentMessage, exclude: list[str] = None):
        """Broadcast message to all agents"""
        exclude = exclude or []
        for agent_id, agent in self.agents.items():
            if agent_id not in exclude:
                msg_copy = AgentMessage(
                    id=message.id,
                    msg_type=message.msg_type,
                    sender=message.sender,
                    recipient=agent_id,
                    content=message.content,
                    timestamp=message.timestamp
                )
                await agent.inbox.put(msg_copy)


class SupervisorAgent(Agent):
    """
    Supervisor agent that coordinates other agents.
    Decomposes complex tasks and assigns to specialized agents.
    """
    
    def __init__(self, agent_id: str, llm_provider=None):
        capabilities = AgentCapabilities(
            role=AgentRole.SUPERVISOR,
            skills=["task_decomposition", "coordination", "planning", "decision_making"],
            tools=["assign_task", "query_agent", "escalate"],
            max_concurrent_tasks=10,
            system_prompt="""You are a supervisor coordinating a team of specialized agents.
            Decompose complex tasks into subtasks and assign them appropriately.
            Monitor progress and ensure quality outcomes."""
        )
        super().__init__(agent_id, capabilities, llm_provider)
        
        self.agent_registry: dict[str, AgentCapabilities] = {}
        self.task_queue: list[Task] = []
        self.all_tasks: dict[str, Task] = {}
        self.message_bus: Optional[MessageBus] = None
    
    def register_worker(self, agent_id: str, capabilities: AgentCapabilities):
        """Register a worker agent's capabilities"""
        self.agent_registry[agent_id] = capabilities
    
    async def submit_task(self, description: str, context: dict = None) -> str:
        """Submit a new task for processing"""
        task_id = str(uuid.uuid4())[:8]
        
        task = Task(
            id=task_id,
            description=description,
            created_by="user",
            context=context or {}
        )
        
        self.all_tasks[task_id] = task
        self.task_queue.append(task)
        
        logger.info(f"Task submitted: {task_id}")
        return task_id
    
    async def process_task(self, task: Task) -> Any:
        """Decompose and coordinate task execution"""
        # Step 1: Analyze and decompose task
        subtasks = await self._decompose_task(task)
        
        # Step 2: Assign subtasks to agents
        assignments = await self._assign_subtasks(subtasks)
        
        # Step 3: Wait for results
        results = await self._collect_results(assignments)
        
        # Step 4: Synthesize final result
        final_result = await self._synthesize_results(task, results)
        
        return final_result
    
    async def _decompose_task(self, task: Task) -> list[Task]:
        """Decompose complex task into subtasks"""
        if self.llm:
            # Use LLM to decompose
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": """Decompose the task into subtasks.
                    Output as JSON: {"subtasks": [{"description": "...", "role": "coder|researcher|writer", "priority": 1-10}]}"""},
                    {"role": "user", "content": task.description}
                ]
            )
            
            # Parse response and create subtasks
            import json
            try:
                data = json.loads(response.content)
                subtasks = []
                for i, st in enumerate(data.get("subtasks", [])):
                    subtask = Task(
                        id=f"{task.id}-{i}",
                        description=st["description"],
                        created_by=self.id,
                        priority=st.get("priority", 5),
                        context={"parent_task": task.id, "role": st.get("role")}
                    )
                    subtasks.append(subtask)
                return subtasks
            except json.JSONDecodeError:
                pass
        
        # Default: single subtask
        return [task]
    
    async def _assign_subtasks(self, subtasks: list[Task]) -> dict[str, str]:
        """Assign subtasks to appropriate agents"""
        assignments = {}
        
        for subtask in subtasks:
            preferred_role = subtask.context.get("role")
            
            # Find suitable agent
            best_agent = None
            for agent_id, caps in self.agent_registry.items():
                if preferred_role and caps.role.value == preferred_role:
                    best_agent = agent_id
                    break
                elif caps.can_handle(subtask.description):
                    best_agent = agent_id
            
            if best_agent and self.message_bus:
                subtask.assigned_to = best_agent
                self.all_tasks[subtask.id] = subtask
                
                # Send assignment
                await self.message_bus.send(AgentMessage(
                    id=str(uuid.uuid4()),
                    msg_type=MessageType.TASK_ASSIGNMENT,
                    sender=self.id,
                    recipient=best_agent,
                    content={"task": {
                        "id": subtask.id,
                        "description": subtask.description,
                        "created_by": subtask.created_by,
                        "priority": subtask.priority,
                        "context": subtask.context
                    }}
                ))
                
                assignments[subtask.id] = best_agent
            else:
                # No agent available, execute locally
                assignments[subtask.id] = self.id
        
        return assignments
    
    async def _collect_results(self, assignments: dict[str, str], timeout: float = 60.0) -> dict[str, Any]:
        """Collect results from assigned agents"""
        results = {}
        pending = set(assignments.keys())
        start_time = time.time()
        
        while pending and (time.time() - start_time) < timeout:
            # Check for completed tasks
            for task_id in list(pending):
                task = self.all_tasks.get(task_id)
                if task and task.state == TaskState.COMPLETED:
                    results[task_id] = task.result
                    pending.remove(task_id)
            
            if pending:
                await asyncio.sleep(0.5)
        
        # Mark timeout for pending tasks
        for task_id in pending:
            results[task_id] = {"error": "timeout"}
        
        return results
    
    async def _synthesize_results(self, task: Task, results: dict[str, Any]) -> Any:
        """Synthesize final result from subtask results"""
        if self.llm and len(results) > 1:
            # Use LLM to synthesize
            results_summary = "\n".join([
                f"Subtask result: {r}" for r in results.values()
            ])
            
            response = await self.llm.complete(
                messages=[
                    {"role": "system", "content": "Synthesize the subtask results into a coherent final result."},
                    {"role": "user", "content": f"Task: {task.description}\n\nResults:\n{results_summary}"}
                ]
            )
            return {"synthesis": response.content, "subtask_results": results}
        
        return {"results": results}
    
    def get_task_status(self, task_id: str) -> Optional[dict]:
        """Get status of a task"""
        task = self.all_tasks.get(task_id)
        if task:
            return {
                "id": task.id,
                "state": task.state.value,
                "assigned_to": task.assigned_to,
                "result": task.result if task.state == TaskState.COMPLETED else None,
                "error": task.error
            }
        return None


class Orchestrator:
    """
    Main orchestration system that manages all agents.
    """
    
    def __init__(self, llm_provider=None):
        self.llm = llm_provider
        self.message_bus = MessageBus()
        
        # Create supervisor
        self.supervisor = SupervisorAgent("supervisor", llm_provider)
        self.supervisor.message_bus = self.message_bus
        self.message_bus.register_agent(self.supervisor)
        
        # Worker agents
        self.workers: dict[str, Agent] = {}
        self._agent_tasks: list[asyncio.Task] = []
        self._running = False
    
    def add_agent(self, agent: Agent):
        """Add a worker agent to the system"""
        self.workers[agent.id] = agent
        self.message_bus.register_agent(agent)
        self.supervisor.register_worker(agent.id, agent.capabilities)
    
    def add_default_agents(self):
        """Add default set of specialized agents"""
        self.add_agent(CoderAgent("coder-1", self.llm))
        self.add_agent(ResearcherAgent("researcher-1", self.llm))
        self.add_agent(WriterAgent("writer-1", self.llm))
    
    async def start(self):
        """Start the orchestration system"""
        self._running = True
        
        # Start supervisor
        self._agent_tasks.append(
            asyncio.create_task(self.supervisor.run(self.message_bus))
        )
        
        # Start workers
        for agent in self.workers.values():
            self._agent_tasks.append(
                asyncio.create_task(agent.run(self.message_bus))
            )
        
        logger.info("Orchestrator started with %d agents", len(self.workers) + 1)
    
    async def stop(self):
        """Stop the orchestration system"""
        self._running = False
        
        self.supervisor.stop()
        for agent in self.workers.values():
            agent.stop()
        
        # Cancel all tasks
        for task in self._agent_tasks:
            task.cancel()
        
        await asyncio.gather(*self._agent_tasks, return_exceptions=True)
        logger.info("Orchestrator stopped")
    
    async def execute(self, task_description: str, context: dict = None) -> dict:
        """Execute a task through the orchestration system"""
        task_id = await self.supervisor.submit_task(task_description, context)
        
        # Wait for completion
        while True:
            status = self.supervisor.get_task_status(task_id)
            if status and status["state"] in ["completed", "failed", "cancelled"]:
                return status
            await asyncio.sleep(0.5)
    
    def get_status(self) -> dict:
        """Get orchestration system status"""
        return {
            "running": self._running,
            "supervisor": self.supervisor.id,
            "workers": list(self.workers.keys()),
            "active_tasks": len(self.supervisor.all_tasks),
            "completed_tasks": len(self.supervisor.completed_tasks)
        }


# Example usage
async def main():
    """Example of multi-agent orchestration"""
    orchestrator = Orchestrator()
    orchestrator.add_default_agents()
    
    await orchestrator.start()
    
    try:
        result = await orchestrator.execute(
            "Create a Python web scraper that extracts article titles from a news website"
        )
        print(f"Result: {result}")
    finally:
        await orchestrator.stop()


if __name__ == "__main__":
    asyncio.run(main())
