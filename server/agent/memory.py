"""会话管理 — 跟踪活跃会话元数据。

注意：实际的对话状态由 LangGraph 的 checkpointer（MemorySaver）管理，
本模块仅维护会话的元信息（创建时间、消息计数等），用于 REST API 查询。
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from threading import Lock


class SessionManager:
    """线程安全的会话元数据管理器。"""

    def __init__(self, ttl_hours: float = 2.0):
        self._sessions: dict[str, dict] = {}
        self._lock = Lock()
        self._ttl_hours = ttl_hours

    def create_session(self) -> str:
        """创建新会话，返回 session_id。"""
        session_id = uuid.uuid4().hex
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._sessions[session_id] = {
                "session_id": session_id,
                "message_count": 0,
                "created_at": now,
                "last_active": now,
            }
        return session_id

    def touch(self, session_id: str) -> None:
        """更新会话最后活跃时间并递增消息计数。"""
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["last_active"] = (
                    datetime.now(timezone.utc).isoformat()
                )
                self._sessions[session_id]["message_count"] += 1

    def get(self, session_id: str) -> dict | None:
        """获取会话元信息。"""
        with self._lock:
            return self._sessions.get(session_id)

    def exists(self, session_id: str) -> bool:
        with self._lock:
            return session_id in self._sessions

    def delete(self, session_id: str) -> bool:
        """删除会话，返回是否成功。"""
        with self._lock:
            return self._sessions.pop(session_id, None) is not None

    def list_sessions(self) -> list[dict]:
        """列出所有活跃会话。"""
        self._cleanup_expired()
        with self._lock:
            return list(self._sessions.values())

    def _cleanup_expired(self) -> None:
        """清理过期会话。"""
        now = datetime.now(timezone.utc)
        with self._lock:
            expired = []
            for sid, info in self._sessions.items():
                last = datetime.fromisoformat(info["last_active"])
                if (now - last).total_seconds() > self._ttl_hours * 3600:
                    expired.append(sid)
            for sid in expired:
                del self._sessions[sid]


# 全局单例
session_manager = SessionManager(ttl_hours=2.0)
