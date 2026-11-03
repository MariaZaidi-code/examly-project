import json, pytest
from agent.agent import ExamAgent
from agent.mcp_client import MCPBridge

@pytest.fixture(scope="module")
def mcp():
    b = MCPBridge(); b.start(); yield b; b.close()

@pytest.fixture(scope="module")
def ag(mcp):
    a = ExamAgent("ayesha", mcp=mcp).new_session("s1"); yield a

def tools_used(r): return [(s.get("tool"), s.get("via")) for s in r["trace"]["steps"] if "tool" in s]

# ---- RAG
def test_rag_ingests_at_least_five_documents(ag):
    docs = {h["source"] for q in ["normal form", "deadlock", "subnet", "transactions", "joins", "revision"] for h in ag.kb.search(q, 1)}
    assert len(docs) >= 5 and ag.store.count("kb") >= 15

def test_grounded_answer_has_citations_and_scores(ag):
    r = ag.ask("What are the Coffman conditions?")
    assert tools_used(r) == [("search_notes", "local")]
    a = r["answer"]
    assert "mutual exclusion" in a and "[1]" in a and "os_deadlocks.md" in a
    ev = r["trace"]["steps"][0]["result"]["hits"][0]
    assert ev["source"] == "os_deadlocks.md" and ev["score"] > 0.12

def test_out_of_scope_question_is_not_answered_from_thin_air(ag):
    r = ag.ask("Who won the football world cup?")
    assert "will not guess" in r["answer"] and "[1]" not in r["answer"]

# ---- short-term memory
def test_followup_resolved_from_session_history(ag):
    ag.ask("Explain third normal form")
    r = ag.ask("Give me an example of it")
    q = r["trace"]["steps"][0]["args"]["query"]
    assert "Third normal form" in q and "transitive" in r["answer"]

# ---- MCP (real protocol over stdio)
def test_mcp_lists_tools_and_executes(mcp):
    names = {t["name"] for t in mcp.tools}
    assert {"get_weak_topics", "record_quiz_result", "generate_revision_plan", "save_revision_plan", "replan"} <= names
    r = mcp.call("record_quiz_result", {"user_id": "t1", "topic": "Subnetting", "correct": 2, "total": 5})
    assert r["ok"] and r["data"]["accuracy_pct"] == 40
    assert mcp.call("get_weak_topics", {"user_id": "t1"})["data"]["weak_topics"][0]["topic"] == "subnetting"
    assert not mcp.call("record_quiz_result", {"user_id": "t1", "topic": "x", "correct": 9, "total": 5})["ok"]

def test_agent_routes_quiz_score_through_mcp(ag):
    r = ag.ask("I scored 3/8 on deadlock handling")
    assert tools_used(r) == [("record_quiz_result", "MCP")] and "38%" in r["answer"]

def test_adaptive_question_targets_weakest_topic(ag):
    r = ag.ask("quiz me")
    assert [t for t, _ in tools_used(r)] == ["get_weak_topics", "search_notes"]
    assert "deadlock" in r["answer"].lower() and "_____" in r["answer"]

# ---- human oversight
def test_save_requires_confirmation_at_tool_level(mcp):
    p = mcp.call("generate_revision_plan", {"user_id": "t2", "exam_date": "2026-11-15", "today": "2026-11-03"})["data"]
    r = mcp.call("save_revision_plan", {"user_id": "t2", "plan_id": p["plan_id"], "confirmed": False})
    assert not r["ok"] and "confirmation" in r["error"].lower()

def test_plan_proposed_then_saved_only_after_confirm(mcp):
    a = ExamAgent("bilal", mcp=mcp).new_session("p")
    a.ask("My exam is on 15 Nov")
    a.ask("I scored 2/5 on indexes")
    r = a.ask("Make me a revision plan")
    assert [t for t, _ in tools_used(r)] == ["get_weak_topics", "generate_revision_plan"] and "Nothing is saved yet" in r["answer"]
    assert a.stm.pending_plan_id is not None
    r2 = a.ask("yes confirm")
    assert tools_used(r2) == [("save_revision_plan", "MCP")] and "Saved" in r2["answer"] and a.stm.pending_plan_id is None
    assert "no proposed plan" in a.ask("confirm")["answer"]

# ---- long-term memory across sessions
def test_long_term_memory_survives_new_session_and_new_agent(mcp):
    a1 = ExamAgent("sara", mcp=mcp).new_session("monday")
    a1.ask("My name is Sara"); a1.ask("My exam is on 20 Nov"); a1.ask("I struggle with joins")
    del a1
    a2 = ExamAgent("sara", mcp=mcp).new_session("friday")          # brand-new agent object, brand-new STM
    assert a2.stm.history() == []
    r = a2.ask("Make me a revision plan")                          # no date given: must come from LTM
    assert "2026-11-20" in r["answer"], r["answer"]
    mem = r["trace"]["memory_used"]
    assert any("Sara" in m["content"] for m in mem) and any("struggle with joins" in m["content"] for m in a2.ltm.recall("sara", "joins"))

def test_ltm_is_per_user(mcp):
    assert ExamAgent("other", mcp=mcp).ltm.all("other") == []

# ---- replanning
def test_replan_keeps_completed_sessions(mcp):
    u = "re1"
    mcp.call("record_quiz_result", {"user_id": u, "topic": "transactions", "correct": 3, "total": 8})
    p = mcp.call("generate_revision_plan", {"user_id": u, "exam_date": "2026-11-15", "today": "2026-11-03"})["data"]
    mcp.call("save_revision_plan", {"user_id": u, "plan_id": p["plan_id"], "confirmed": True})
    assert mcp.call("mark_session_done", {"user_id": u, "date": "2026-11-04"})["ok"]
    r = mcp.call("replan", {"user_id": u, "new_exam_date": "2026-11-09", "today": "2026-11-05"})["data"]
    assert r["kept_completed_sessions"] == 1 and r["status"] == "proposed"
    assert r["items"][0] == {"date": "2026-11-04", "topic": r["items"][0]["topic"], "minutes": 45, "status": "done"}
    assert max(i["date"] for i in r["items"]) < "2026-11-09"

def test_agent_replans_when_exam_date_moves(mcp):
    a = ExamAgent("moved", mcp=mcp).new_session("m")
    a.ask("I scored 4/10 on transactions"); a.ask("My exam is on 15 Nov"); a.ask("revision plan"); a.ask("confirm")
    r = a.ask("My exam has been moved to 10 Nov")
    assert tools_used(r) == [("replan", "MCP")] and "2026-11-10" in r["answer"] and "Nothing is saved yet" in r["answer"]

# ---- error handling
def test_missing_exam_date_asks_instead_of_guessing(mcp):
    r = ExamAgent("nodate", mcp=mcp).new_session("n").ask("Make me a revision plan")
    assert "exam date" in r["answer"].lower() and tools_used(r) == []

def test_tool_error_is_reported_not_hidden(mcp):
    r = ExamAgent("past", mcp=mcp).new_session("n").ask("My exam has been moved to 2026-11-01")
    assert "could not build the plan" in r["answer"] and "after today" in r["answer"]

def test_llm_failure_degrades_gracefully(mcp):
    class Boom:
        name = "boom"
        def chat(self, m, t): raise ConnectionError("down")
    r = ExamAgent("x", mcp=mcp, llm=Boom()).new_session("s").ask("hello")
    assert "could not reach the language model" in r["answer"]

def test_step_limit_prevents_infinite_tool_loops(mcp):
    class Loop:
        name = "loop"
        def chat(self, m, t): return {"content": None, "tool_calls": [{"id": "1", "name": "search_notes", "arguments": {"query": "x"}}]}
    r = ExamAgent("y", mcp=mcp, llm=Loop()).new_session("s").ask("hi")
    assert "too many tool steps" in r["answer"]

def test_confirmed_replan_updates_long_term_exam_date(mcp):
    a = ExamAgent("upd", mcp=mcp).new_session("u1")
    a.ask("I scored 4/10 on transactions"); a.ask("My exam is on 15 Nov"); a.ask("revision plan"); a.ask("confirm")
    a.ask("My exam has been moved to 10 Nov"); a.ask("confirm")
    exams = [m["content"] for m in a.ltm.all("upd") if m["kind"] == "exam"]
    assert len(exams) == 1 and "2026-11-10" in exams[0]
