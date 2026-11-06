"""SQLite tabanlı konuşma hafızası.

Geçmiş yalnızca sona ekleme (append-only) şeklinde tutulur: Claude'un döndürdüğü içerik
blokları (thinking blokları dahil) olduğu gibi saklanır ve aynen geri gönderilir. Bu hem
prompt önbelleğinin isabet etmesini sağlar hem de thinking bloklarının geçerli kalmasını.
"""

import json
import sqlite3
import threading
from typing import Any


class ConversationStore:
    def __init__(self, path: str) -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._conn:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX IF NOT EXISTS idx_messages_user ON messages(user_id, id);
                CREATE TABLE IF NOT EXISTS processed_events (
                    event_id TEXT PRIMARY KEY
                );
                """
            )

    def history(self, user_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT role, content FROM messages WHERE user_id = ? ORDER BY id",
                (user_id,),
            ).fetchall()
        return [{"role": role, "content": json.loads(content)} for role, content in rows]

    def append_turn(self, user_id: str, user_content: Any, assistant_content: Any) -> None:
        """Kullanıcı mesajını ve Claude'un cevabını tek işlemde ekler."""
        with self._lock, self._conn:
            self._conn.executemany(
                "INSERT INTO messages (user_id, role, content) VALUES (?, ?, ?)",
                [
                    (user_id, "user", json.dumps(user_content, ensure_ascii=False)),
                    (user_id, "assistant", json.dumps(assistant_content, ensure_ascii=False)),
                ],
            )

    def reset(self, user_id: str) -> None:
        with self._lock, self._conn:
            self._conn.execute("DELETE FROM messages WHERE user_id = ?", (user_id,))

    def mark_processed(self, event_id: str) -> bool:
        """Olay daha önce işlenmediyse True döner (WhatsApp aynı olayı tekrar gönderebilir)."""
        with self._lock, self._conn:
            cur = self._conn.execute(
                "INSERT OR IGNORE INTO processed_events (event_id) VALUES (?)", (event_id,)
            )
            return cur.rowcount == 1
