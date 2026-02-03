"""
Conversation Persistence - SQLite-backed conversation history with session management.
"""

import sqlite3
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from dataclasses import dataclass, asdict
import logging

logger = logging.getLogger(__name__)


@dataclass
class ConversationMessage:
    """Stored conversation message"""
    id: str
    session_id: str
    role: str
    content: str
    timestamp: datetime
    metadata: Dict[str, Any] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata or {},
        }


@dataclass
class Session:
    """Conversation session"""
    id: str
    name: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    metadata: Dict[str, Any] = None


class ConversationStore:
    """SQLite-backed conversation storage with session management"""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or Path.home() / ".ai-os" / "conversations.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        return self._conn

    def _init_db(self):
        """Initialize database schema"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                metadata TEXT
            );

            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                metadata TEXT,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            );

            CREATE INDEX IF NOT EXISTS idx_messages_session ON messages(session_id);
            CREATE INDEX IF NOT EXISTS idx_messages_timestamp ON messages(timestamp);
            CREATE INDEX IF NOT EXISTS idx_sessions_updated ON sessions(updated_at);

            -- Full-text search for message content
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='rowid'
            );

            -- Triggers to keep FTS in sync
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_ad AFTER DELETE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
            END;

            CREATE TRIGGER IF NOT EXISTS messages_au AFTER UPDATE ON messages BEGIN
                INSERT INTO messages_fts(messages_fts, rowid, content) VALUES('delete', old.rowid, old.content);
                INSERT INTO messages_fts(rowid, content) VALUES (new.rowid, new.content);
            END;
        """)
        conn.commit()
        logger.info(f"Initialized conversation database at {self.db_path}")

    # ============ Session Management ============

    def create_session(self, name: Optional[str] = None) -> Session:
        """Create a new conversation session"""
        session_id = str(uuid.uuid4())
        now = datetime.utcnow()
        name = name or f"Session {now.strftime('%Y-%m-%d %H:%M')}"

        conn = self._get_conn()
        conn.execute(
            "INSERT INTO sessions (id, name, created_at, updated_at, metadata) VALUES (?, ?, ?, ?, ?)",
            (session_id, name, now.isoformat(), now.isoformat(), "{}")
        )
        conn.commit()

        return Session(
            id=session_id,
            name=name,
            created_at=now,
            updated_at=now,
            message_count=0,
        )

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get a session by ID"""
        conn = self._get_conn()
        row = conn.execute(
            """SELECT s.*, COUNT(m.id) as message_count 
               FROM sessions s 
               LEFT JOIN messages m ON s.id = m.session_id 
               WHERE s.id = ?
               GROUP BY s.id""",
            (session_id,)
        ).fetchone()

        if row:
            return Session(
                id=row["id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["message_count"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
        return None

    def list_sessions(self, limit: int = 50, offset: int = 0) -> List[Session]:
        """List sessions ordered by most recent"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT s.*, COUNT(m.id) as message_count 
               FROM sessions s 
               LEFT JOIN messages m ON s.id = m.session_id 
               GROUP BY s.id
               ORDER BY s.updated_at DESC
               LIMIT ? OFFSET ?""",
            (limit, offset)
        ).fetchall()

        return [
            Session(
                id=row["id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                message_count=row["message_count"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    def rename_session(self, session_id: str, new_name: str) -> bool:
        """Rename a session"""
        conn = self._get_conn()
        cursor = conn.execute(
            "UPDATE sessions SET name = ?, updated_at = ? WHERE id = ?",
            (new_name, datetime.utcnow().isoformat(), session_id)
        )
        conn.commit()
        return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        """Delete a session and all its messages"""
        conn = self._get_conn()
        conn.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
        cursor = conn.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
        conn.commit()
        return cursor.rowcount > 0

    # ============ Message Management ============

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict] = None
    ) -> ConversationMessage:
        """Add a message to a session"""
        msg_id = str(uuid.uuid4())
        now = datetime.utcnow()

        conn = self._get_conn()
        conn.execute(
            "INSERT INTO messages (id, session_id, role, content, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (msg_id, session_id, role, content, now.isoformat(), json.dumps(metadata or {}))
        )
        conn.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (now.isoformat(), session_id)
        )
        conn.commit()

        return ConversationMessage(
            id=msg_id,
            session_id=session_id,
            role=role,
            content=content,
            timestamp=now,
            metadata=metadata,
        )

    def get_messages(
        self,
        session_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[ConversationMessage]:
        """Get messages for a session"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM messages 
               WHERE session_id = ? 
               ORDER BY timestamp ASC
               LIMIT ? OFFSET ?""",
            (session_id, limit, offset)
        ).fetchall()

        return [
            ConversationMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    def get_recent_messages(self, session_id: str, count: int = 20) -> List[ConversationMessage]:
        """Get most recent messages for a session (for context)"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT * FROM (
                SELECT * FROM messages 
                WHERE session_id = ? 
                ORDER BY timestamp DESC
                LIMIT ?
            ) ORDER BY timestamp ASC""",
            (session_id, count)
        ).fetchall()

        return [
            ConversationMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    # ============ Search ============

    def search_messages(self, query: str, limit: int = 50) -> List[ConversationMessage]:
        """Full-text search across all messages"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT m.* FROM messages m
               JOIN messages_fts fts ON m.rowid = fts.rowid
               WHERE messages_fts MATCH ?
               ORDER BY rank
               LIMIT ?""",
            (query, limit)
        ).fetchall()

        return [
            ConversationMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    def search_in_session(self, session_id: str, query: str) -> List[ConversationMessage]:
        """Search messages within a specific session"""
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT m.* FROM messages m
               JOIN messages_fts fts ON m.rowid = fts.rowid
               WHERE m.session_id = ? AND messages_fts MATCH ?
               ORDER BY m.timestamp ASC""",
            (session_id, query)
        ).fetchall()

        return [
            ConversationMessage(
                id=row["id"],
                session_id=row["session_id"],
                role=row["role"],
                content=row["content"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                metadata=json.loads(row["metadata"]) if row["metadata"] else None,
            )
            for row in rows
        ]

    # ============ Export ============

    def export_session(self, session_id: str, format: str = "json") -> str:
        """Export a session to JSON or Markdown"""
        session = self.get_session(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        messages = self.get_messages(session_id, limit=10000)

        if format == "json":
            return json.dumps({
                "session": {
                    "id": session.id,
                    "name": session.name,
                    "created_at": session.created_at.isoformat(),
                },
                "messages": [m.to_dict() for m in messages],
            }, indent=2)

        elif format == "markdown":
            lines = [
                f"# {session.name}",
                f"*Created: {session.created_at.strftime('%Y-%m-%d %H:%M')}*",
                "",
            ]
            for msg in messages:
                role_label = "**User**" if msg.role == "user" else "**Assistant**"
                lines.append(f"### {role_label}")
                lines.append(msg.content)
                lines.append("")
            return "\n".join(lines)

        else:
            raise ValueError(f"Unknown format: {format}")

    # ============ Maintenance ============

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        conn = self._get_conn()
        session_count = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        message_count = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]

        return {
            "session_count": session_count,
            "message_count": message_count,
            "db_path": str(self.db_path),
            "db_size_mb": round(self.db_path.stat().st_size / (1024 * 1024), 2),
        }

    def vacuum(self):
        """Compact the database"""
        conn = self._get_conn()
        conn.execute("VACUUM")
        logger.info("Database vacuumed")

    def close(self):
        """Close database connection"""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global store instance
conversation_store = ConversationStore()
