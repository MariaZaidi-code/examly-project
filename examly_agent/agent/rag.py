"""RAG pipeline: load documents -> chunk by section -> embed -> store -> retrieve with evidence."""
import re
from . import config

def chunk_markdown(name, text, max_chars=700):
    title = re.sub(r"\s*\(.*?\)\s*$", "", (re.match(r"#\s+(.+)", text) or [None, name])[1])
    chunks, head, buf = [], "", []
    def flush():
        body = " ".join(buf).strip()
        if body:
            chunks.append({"text": f"{title} / {head} :: {body}" if head else f"{title} :: {body}", "heading": head or title})
    for line in text.splitlines():
        if line.startswith("## "):
            flush(); head, buf = line[3:].strip(), []
        elif not line.startswith("# ") and line.strip():
            buf.append(line.strip())
    flush()
    out = []
    for c in chunks:  # split overlong chunks on sentence boundaries
        if len(c["text"]) <= max_chars: out.append(c); continue
        cur = ""
        for s in re.split(r"(?<=[.!?])\s+", c["text"]):
            if len(cur) + len(s) > max_chars and cur: out.append({**c, "text": cur}); cur = ""
            cur += (" " if cur else "") + s
        if cur: out.append({**c, "text": cur})
    return title, out

class KnowledgeBase:
    COLLECTION = "kb"
    def __init__(self, store):
        self.store = store
    def ingest(self, directory=None, force=False):
        d = directory or config.KNOWLEDGE_DIR
        if self.store.count(self.COLLECTION) and not force:
            return {"documents": None, "chunks": self.store.count(self.COLLECTION), "skipped": True}
        self.store.clear(self.COLLECTION)
        docs = sorted(d.glob("*.md")) + sorted(d.glob("*.txt"))
        n = 0
        for f in docs:
            title, chunks = chunk_markdown(f.stem, f.read_text(encoding="utf-8"))
            n += self.store.add(self.COLLECTION, [c["text"] for c in chunks],
                                [{"source": f.name, "title": title, "heading": c["heading"], "chunk": i} for i, c in enumerate(chunks)])
        return {"documents": len(docs), "chunks": n, "skipped": False}
    STOPQ = {"explain", "what", "is", "are", "define", "tell", "me", "about", "give", "example", "how", "does", "the", "of", "a", "an", "and", "to", "in", "my", "notes", "please"}
    def search(self, query, k=3):
        """Dense retrieval re-ranked with a small heading-match boost (lecture notes are heading-structured)."""
        hits = self.store.query(self.COLLECTION, query, 8)
        qw = {w for w in re.findall(r"[a-z0-9]+", query.lower()) if w not in self.STOPQ}
        for h in hits:
            hw = set(re.findall(r"[a-z0-9]+", h["meta"]["heading"].lower()))
            h["score"] += 1.0 * (len(qw & hw) / len(qw) if qw else 0)
        hits = sorted(hits, key=lambda h: -h["score"])[:k]
        return [{"n": i + 1, "source": h["meta"]["source"], "heading": h["meta"]["heading"], "chunk": h["meta"]["chunk"],
                 "score": round(h["score"], 3), "text": h["text"]} for i, h in enumerate(hits)]
