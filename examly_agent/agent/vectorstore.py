"""Minimal persistent vector database: SQLite for storage, NumPy cosine search."""
import json, sqlite3
import numpy as np

class VectorStore:
    def __init__(self, path, embedder):
        self.path, self.emb = path, embedder
        with self._c() as c:
            c.execute("""CREATE TABLE IF NOT EXISTS vectors(id INTEGER PRIMARY KEY, collection TEXT NOT NULL, text TEXT NOT NULL,
                         meta TEXT NOT NULL DEFAULT '{}', vec BLOB NOT NULL, dim INTEGER NOT NULL, embedder TEXT NOT NULL)""")
            c.execute("CREATE INDEX IF NOT EXISTS ix_vec_col ON vectors(collection)")
    def _c(self):
        return sqlite3.connect(self.path)
    def add(self, collection, texts, metas=None):
        if not texts: return 0
        m = self.emb.embed(texts)
        with self._c() as c:
            c.executemany("INSERT INTO vectors(collection,text,meta,vec,dim,embedder) VALUES(?,?,?,?,?,?)",
                [(collection, t, json.dumps((metas or [{}] * len(texts))[i]), m[i].tobytes(), m.shape[1], self.emb.name) for i, t in enumerate(texts)])
        return len(texts)
    def count(self, collection):
        with self._c() as c:
            return c.execute("SELECT COUNT(*) FROM vectors WHERE collection=?", (collection,)).fetchone()[0]
    def clear(self, collection):
        with self._c() as c: c.execute("DELETE FROM vectors WHERE collection=?", (collection,))
    def query(self, collection, text, k=4):
        with self._c() as c:
            rows = c.execute("SELECT id,text,meta,vec,dim FROM vectors WHERE collection=? AND embedder=?", (collection, self.emb.name)).fetchall()
        if not rows: return []
        mat = np.stack([np.frombuffer(r[3], dtype="float32") for r in rows])
        q = self.emb.embed([text])[0]
        sims = mat @ q
        order = np.argsort(-sims)[:k]
        return [{"id": rows[i][0], "text": rows[i][1], "meta": json.loads(rows[i][2]), "score": float(sims[i])} for i in order]
