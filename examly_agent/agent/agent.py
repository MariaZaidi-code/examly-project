"""The primary agent: interprets the request, chooses a tool/retrieval path, uses memory, returns a grounded answer + trace."""
import json, os, datetime as dt
from . import config
from .embeddings import get_embedder
from .vectorstore import VectorStore
from .rag import KnowledgeBase
from .memory import ShortTermMemory, LongTermMemory
from .mcp_client import MCPBridge
from .llm import get_llm
from .prompts import SYSTEM_PROMPT

LOCAL_TOOLS = [
    {"name": "search_notes", "description": "RAG: semantic search over the student's lecture notes. Returns cited chunks with similarity scores.",
     "parameters": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]}},
    {"name": "remember_fact", "description": "Store a durable fact about the student in long-term memory (kind: profile|difficulty|preference|exam).",
     "parameters": {"type": "object", "properties": {"kind": {"type": "string"}, "content": {"type": "string"}}, "required": ["kind", "content"]}},
]

class ExamAgent:
    def __init__(self, user_id, llm=None, mcp=None, today=None, db_path=None):
        db = db_path or config.AGENT_DB
        self.user_id = user_id
        self.today = today or os.environ.get("AGENT_TODAY") or dt.date.today().isoformat()
        self.store = VectorStore(db, get_embedder())
        self.kb = KnowledgeBase(self.store); self.kb.ingest()
        self.ltm = LongTermMemory(db, self.store)
        self.mcp = mcp or MCPBridge(); self._own_mcp = mcp is None
        self.mcp_tools = self.mcp.start() if self._own_mcp else mcp.tools
        self.llm = llm or get_llm(self.today)
        self.stm = None
    def new_session(self, session_id):
        self.stm = ShortTermMemory(session_id); return self
    def close(self):
        if self._own_mcp: self.mcp.close()

    def _system(self, query):
        mem = self.ltm.recall(self.user_id, query)
        lines = [SYSTEM_PROMPT, "", f"USER_ID: {self.user_id}", f"TODAY: {self.today}", f"LAST_TOPIC: {self.stm.last_topic or ''}",
                 f"PENDING_PLAN_ID: {self.stm.pending_plan_id or ''}", "LONG-TERM MEMORY (about the student, not course evidence):"]
        lines += [f"- [{m['kind']}] {m['content']}" for m in mem] or ["- (none yet)"]
        return "\n".join(lines), mem

    def _exec(self, name, args):
        if name == "search_notes":
            hits = self.kb.search(args.get("query", ""), k=3)
            hits = [h for h in hits if h["score"] >= config.MIN_SCORE]
            if hits: self.stm.last_topic = hits[0]["heading"]
            return {"hits": hits}
        if name == "remember_fact":
            return {"stored": self.ltm.remember(self.user_id, args.get("kind", "preference"), args.get("content", ""))}
        r = self.mcp.call(name, args)
        if r["ok"] and name in ("generate_revision_plan", "replan"):
            self.stm.pending_plan_id = r["data"]["plan_id"]; self.stm.pending_exam = r["data"]["exam_date"]
        if r["ok"] and name == "save_revision_plan":      # the student confirmed: the saved plan's exam date is now the truth
            if getattr(self.stm, "pending_exam", None):
                self.ltm.replace(self.user_id, "exam", f"exam date {self.stm.pending_exam} (from confirmed plan)")
            self.stm.pending_plan_id = None
        return r

    def ask(self, text):
        assert self.stm, "call new_session() first"
        system, mem = self._system(text)
        tools = LOCAL_TOOLS + self.mcp_tools
        msgs = [{"role": "system", "content": system}] + self.stm.history() + [{"role": "user", "content": text}]
        trace = {"user": text, "memory_used": mem, "steps": [], "llm": self.llm.name}
        answer = None
        for step in range(config.MAX_STEPS):
            try:
                reply = self.llm.chat(msgs, tools)
            except Exception as e:
                answer = f"I could not reach the language model ({type(e).__name__}). Your question was not lost; please try again."
                trace["steps"].append({"step": step, "error": f"LLM failure: {e}"}); break
            if not reply["tool_calls"]:
                answer = reply["content"]; break
            msgs.append({"role": "assistant", "content": None, "tool_calls": [{"id": c["id"], "type": "function", "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}} for c in reply["tool_calls"]]})
            for c in reply["tool_calls"]:
                try: out = self._exec(c["name"], c["arguments"])
                except Exception as e: out = {"ok": False, "error": f"{type(e).__name__}: {e}"}
                via = "local" if c["name"] in {t["name"] for t in LOCAL_TOOLS} else "MCP"
                trace["steps"].append({"step": step, "tool": c["name"], "via": via, "args": c["arguments"], "result": out})
                msgs.append({"role": "tool", "tool_call_id": c["id"], "name": c["name"], "content": json.dumps(out)})
        if answer is None: answer = "I stopped after too many tool steps without a final answer. Please rephrase."
        self.stm.add("user", text); self.stm.add("assistant", answer)
        trace["answer"] = answer
        return {"answer": answer, "trace": trace}
