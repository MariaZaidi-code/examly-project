"""Reproducible demo. Fresh databases, fixed date. Writes logs/demo_transcript.md and logs/demo_trace.json.
Usage: python demo.py            (offline policy, no key needed)
       AGENT_LLM_URL=... AGENT_LLM_KEY=... AGENT_LLM_MODEL=... python demo.py   (real LLM)"""
import os, sys, json, tempfile, pathlib
tmp = tempfile.mkdtemp(prefix="examly_demo_")
os.environ.setdefault("AGENT_DB", os.path.join(tmp, "agent.db")); os.environ.setdefault("STUDY_DB", os.path.join(tmp, "study.db"))
os.environ.setdefault("AGENT_TODAY", "2026-11-03")
from agent.agent import ExamAgent
from agent.mcp_client import MCPBridge

out, traces = [], []
def say(s=""): out.append(s); print(s)
def turn(ag, text):
    r = ag.ask(text); traces.append(r["trace"])
    say(f"**You:** {text}")
    for s in r["trace"]["steps"]:
        if "tool" in s:
            res = json.dumps(s["result"], default=str)
            say(f"> tool `{s['tool']}` via {s['via']} args={json.dumps(s['args'])}\n> result: {res[:230]}{'...' if len(res) > 230 else ''}")
        else: say(f"> {s['error']}")
    mem = [m["content"] for m in r["trace"]["memory_used"]]
    if mem: say(f"> long-term memory retrieved: {mem}")
    say(f"**Agent:** {r['answer']}\n")

mcp = MCPBridge(); mcp.start()
say(f"# Demo transcript\nLLM: {ExamAgent('probe', mcp=mcp).llm.name}  |  today: {os.environ['AGENT_TODAY']}  |  MCP tools: {[t['name'] for t in mcp.tools]}\n")

say("## Session 1 (Monday): RAG + short-term memory (follow-up) + MCP tool + long-term writes\n")
a = ExamAgent("ayesha", mcp=mcp).new_session("session-1")
for t in ["Explain third normal form", "Give me an example of it", "Who won the football world cup?",
          "My name is Ayesha", "I struggle with deadlock handling", "I scored 3/8 on deadlock handling", "I scored 5/9 on transactions",
          "My exam is on 15 Nov", "quiz me"]:
    turn(a, t)

say("## Session 2 (new session, new agent object): long-term memory retrieved; plan needs human confirmation\n")
b = ExamAgent("ayesha", mcp=mcp).new_session("session-2")
say(f"_short-term history at start of session 2: {b.stm.history()}_\n")
for t in ["Make me a revision plan", "yes confirm"]: turn(b, t)

say("## Replanning after a change event: exam moved earlier\n")
mcp.call("mark_session_done", {"user_id": "ayesha", "date": "2026-11-04"})
b.today = "2026-11-05"
for t in ["My exam has been moved to 11 Nov", "confirm"]: turn(b, t)

say("## Error handling: invalid date\n")
turn(b, "My exam has been moved to 2026-11-01")

pathlib.Path("logs").mkdir(exist_ok=True)
pathlib.Path("logs/demo_transcript.md").write_text("\n".join(out), encoding="utf-8")
pathlib.Path("logs/demo_trace.json").write_text(json.dumps(traces, indent=1, default=str), encoding="utf-8")
mcp.close()
