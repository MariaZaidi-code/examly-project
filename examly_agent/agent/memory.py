"""Short-term memory (per-session message window) and long-term memory (persistent, vector-searchable)."""
import sqlite3, datetime as dt
from collections import deque
from . import config

class ShortTermMemory:
    """Session-scoped conversational history. Lost when the session ends by design."""
    def __init__(self, session_id, window=config.STM_WINDOW):
        self.session_id, self.msgs = session_id, deque(maxlen=window)
        self.last_topic, self.pending_plan_id = None, None
    def add(self, role, content): self.msgs.append({"role": role, "content": content})
    def history(self): return list(self.msgs)

class LongTermMemory:
    """Persistent user/task memory. Separate from the RAG knowledge base (collection 'ltm:<user>')."""
    def __init__(self, path, store):
        self.path, self.store = path, store
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS ltm(id INTEGER PRIMARY KEY, user_id TEXT NOT NULL, kind TEXT NOT NULL,
                         content TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(user_id, kind, content))""")
    def _c(self): return sqlite3.connect(self.path)
    def remember(self, user_id, kind, content):
        content = content.strip()
        with self._c() as c:
            cur = c.execute("INSERT OR IGNORE INTO ltm(user_id,kind,content,created_at) VALUES(?,?,?,?)",
                            (user_id, kind, content, dt.datetime.now().isoformat(timespec="seconds")))
            new = cur.rowcount == 1
        if new: self.store.add(f"ltm:{user_id}", [f"{kind}: {content}"], [{"kind": kind, "content": content}])
        return new
    def replace(self, user_id, kind, content):
        """Supersede stale facts of one kind (e.g. an exam date that moved)."""
        with self._c() as c:
            c.execute("DELETE FROM ltm WHERE user_id=? AND kind=?", (user_id, kind))
            c.execute("DELETE FROM vectors WHERE collection=? AND json_extract(meta,'$.kind')=?", (f"ltm:{user_id}", kind))
        return self.remember(user_id, kind, content)
    def all(self, user_id):
        with self._c() as c:
            return [{"kind": k, "content": t} for k, t in c.execute("SELECT kind,content FROM ltm WHERE user_id=? ORDER BY id", (user_id,))]
    def recall(self, user_id, query, k=4):
        always = [m for m in self.all(user_id) if m["kind"] in ("profile", "exam")]
        hits = [h["meta"] for h in self.store.query(f"ltm:{user_id}", query, k) if h["score"] > 0.05]
        seen, out = set(), []
        for m in always + hits:
            key = (m["kind"], m["content"])
            if key not in seen: seen.add(key); out.append(m)
        return out
