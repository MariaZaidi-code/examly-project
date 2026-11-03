"""MCP server (stdio) exposing study-tracking tools backed by its own SQLite DB (STUDY_DB).
Run by the agent as a subprocess; speaks the Model Context Protocol, not plain HTTP."""
import os, json, sqlite3, datetime as dt
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError

DB = os.environ.get("STUDY_DB", os.path.join(os.path.dirname(__file__), "..", "data", "study.db"))
mcp = MCPServer("examly-study-tools", instructions="Track quiz results, find weak topics, propose and save revision plans.")

def c():
    con = sqlite3.connect(DB); con.row_factory = sqlite3.Row
    con.executescript("""CREATE TABLE IF NOT EXISTS quiz_results(id INTEGER PRIMARY KEY, user_id TEXT, topic TEXT, correct INT, total INT, at TEXT);
      CREATE TABLE IF NOT EXISTS plans(id INTEGER PRIMARY KEY, user_id TEXT, status TEXT, exam_date TEXT, items TEXT, created_at TEXT);""")
    return con

def _iso(s):
    try: return dt.date.fromisoformat(s)
    except Exception: raise ToolError(f"date must be YYYY-MM-DD, got {s!r}")

def _weak(con, user_id):
    rows = con.execute("SELECT topic, SUM(correct) ok, SUM(total) n FROM quiz_results WHERE user_id=? GROUP BY topic", (user_id,)).fetchall()
    out = [{"topic": r["topic"], "accuracy_pct": round(100 * r["ok"] / r["n"]), "answers": r["n"]} for r in rows if r["n"]]
    return sorted(out, key=lambda x: x["accuracy_pct"])

@mcp.tool()
def get_weak_topics(user_id: str, limit: int = 5) -> dict:
    """Return the user's topics ranked weakest-first by quiz accuracy."""
    with c() as con:
        w = _weak(con, user_id)
    return {"user_id": user_id, "weak_topics": w[:limit], "note": "empty list means no quiz results recorded yet"}

@mcp.tool()
def record_quiz_result(user_id: str, topic: str, correct: int, total: int) -> dict:
    """Record a quiz result (correct out of total) for a topic. Updates weak-topic ranking."""
    if total <= 0 or not 0 <= correct <= total:
        raise ToolError("need 0 <= correct <= total and total > 0")
    with c() as con:
        con.execute("INSERT INTO quiz_results(user_id,topic,correct,total,at) VALUES(?,?,?,?,?)",
                    (user_id, topic.strip().lower(), correct, total, dt.datetime.now().isoformat(timespec="seconds")))
        w = [x for x in _weak(con, user_id) if x["topic"] == topic.strip().lower()][0]
    return {"recorded": True, "topic": w["topic"], "accuracy_pct": w["accuracy_pct"], "answers": w["answers"]}

def _build(weak, start, exam, minutes, kept):
    days = (exam - start).days
    free = [start + dt.timedelta(days=i) for i in range(max(days - 1, 0))]       # last day before exam is kept free
    mixed = [d for d in free[-2:]] if len(free) > 3 else []                      # last two study days: mixed practice
    study = [d for d in free if d not in mixed]
    topics = [w["topic"] for w in weak] or ["general review"]
    # weighted round-robin: weaker topics appear more often, never in long blocks (spacing); pad with spaced review
    ws = {w["topic"]: max(1, round(1 + (100 - w["accuracy_pct"]) / 50)) for w in weak}
    if len(ws) < 2: ws["spaced review of earlier topics"] = 1
    seq, left = [], dict(ws)
    while any(left.values()):
        for t in list(left):
            if left[t] > 0: seq.append(t); left[t] -= 1
    items = list(kept)
    taken = {i["date"] for i in kept}
    k = 0
    for d in study:
        if d.isoformat() in taken: continue
        items.append({"date": d.isoformat(), "topic": seq[k % len(seq)], "minutes": minutes, "status": "planned"}); k += 1
    for d in mixed:
        if d.isoformat() not in taken:
            items.append({"date": d.isoformat(), "topic": "mixed practice and light review", "minutes": minutes, "status": "planned"})
    return sorted(items, key=lambda i: i["date"])

@mcp.tool()
def generate_revision_plan(user_id: str, exam_date: str, today: str, minutes_per_session: int = 45) -> dict:
    """Propose a revision plan (weak topics first, spaced, last 2 days mixed practice). NOT saved until save_revision_plan is called with confirmed=true."""
    ex, td = _iso(exam_date), _iso(today)
    if ex <= td: raise ToolError("exam_date must be after today")
    if not 15 <= minutes_per_session <= 180: raise ToolError("minutes_per_session must be 15-180")
    with c() as con:
        items = _build(_weak(con, user_id), td + dt.timedelta(days=1), ex, minutes_per_session, [])
        cur = con.execute("INSERT INTO plans(user_id,status,exam_date,items,created_at) VALUES(?,?,?,?,?)",
                          (user_id, "proposed", exam_date, json.dumps(items), dt.datetime.now().isoformat(timespec="seconds")))
        pid = cur.lastrowid
    return {"plan_id": pid, "status": "proposed", "exam_date": exam_date, "items": items,
            "requires_confirmation": True, "note": "Nothing is saved until the student confirms."}

@mcp.tool()
def save_revision_plan(user_id: str, plan_id: int, confirmed: bool) -> dict:
    """Save a proposed plan. Consequential action: only call with confirmed=true after the student explicitly agreed."""
    if not confirmed:
        raise ToolError("Human confirmation required: the student has not confirmed this plan.")
    with c() as con:
        row = con.execute("SELECT * FROM plans WHERE id=? AND user_id=?", (plan_id, user_id)).fetchone()
        if not row: raise ToolError(f"no plan {plan_id} for this user")
        con.execute("UPDATE plans SET status='superseded' WHERE user_id=? AND status='saved'", (user_id,))
        con.execute("UPDATE plans SET status='saved' WHERE id=?", (plan_id,))
    return {"plan_id": plan_id, "status": "saved", "sessions": len(json.loads(row["items"]))}

@mcp.tool()
def replan(user_id: str, new_exam_date: str, today: str, minutes_per_session: int = 45) -> dict:
    """Replan after a change (e.g. exam date moved): keep sessions already completed (status done) and rebuild the rest. Returns a NEW proposal."""
    ex, td = _iso(new_exam_date), _iso(today)
    if ex <= td: raise ToolError("new_exam_date must be after today")
    with c() as con:
        old = con.execute("SELECT items FROM plans WHERE user_id=? AND status='saved' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        kept = [i for i in json.loads(old["items"]) if i["status"] == "done" and i["date"] <= today] if old else []
        items = _build(_weak(con, user_id), td + dt.timedelta(days=1), ex, minutes_per_session, kept)
        pid = con.execute("INSERT INTO plans(user_id,status,exam_date,items,created_at) VALUES(?,?,?,?,?)",
                          (user_id, "proposed", new_exam_date, json.dumps(items), dt.datetime.now().isoformat(timespec="seconds"))).lastrowid
    return {"plan_id": pid, "status": "proposed", "exam_date": new_exam_date, "kept_completed_sessions": len(kept),
            "items": items, "requires_confirmation": True}

@mcp.tool()
def mark_session_done(user_id: str, date: str) -> dict:
    """Mark the session on `date` in the user's saved plan as done."""
    with c() as con:
        row = con.execute("SELECT id, items FROM plans WHERE user_id=? AND status='saved' ORDER BY id DESC LIMIT 1", (user_id,)).fetchone()
        if not row: raise ToolError("no saved plan")
        items = json.loads(row["items"]); hit = [i for i in items if i["date"] == date]
        if not hit: raise ToolError(f"no session on {date}")
        hit[0]["status"] = "done"
        con.execute("UPDATE plans SET items=? WHERE id=?", (json.dumps(items), row["id"]))
    return {"date": date, "status": "done"}

if __name__ == "__main__":
    mcp.run("stdio")
