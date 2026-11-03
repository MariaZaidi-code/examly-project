"""End-to-end tests. Runs a real uvicorn server (httpx for TestClient is unavailable offline)."""
import os, sys, time, threading, tempfile, socket
tmp = tempfile.mkdtemp()
os.environ["EXAMLY_DB"] = os.path.join(tmp, "t.db")
os.environ["EXAMLY_TODAY"] = "2026-11-03"
os.environ.pop("EXAMLY_LLM_URL", None)
os.environ["EXAMLY_ENV_FILE"] = os.path.join(tmp, "no.env")   # never pick up local .env keys
os.environ["EXAMLY_DISABLE_LLM"] = "1"                        # never call real providers from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests, uvicorn, pytest
from app.main import app

NOTES = ("Third normal form removes transitive dependencies so that non key attributes depend only on the primary key. "
         "Second normal form removes partial dependencies on a composite candidate key. "
         "Deadlock occurs when processes hold resources while waiting for resources held by other processes. "
         "Transactions guarantee atomicity, consistency, isolation and durability through logging and recovery. "
         "Normalization decomposes relations to reduce redundancy and update anomalies in relational databases. "
         "Indexing structures such as balanced trees accelerate lookups on frequently queried attributes.\n\n") * 3

def test_cloze_ignores_markdown_headings():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
    from app.services import make_cloze
    result = make_cloze(
        "# Normalization and functional dependencies\n"
        "Normalization organizes relations so that redundancy and update anomalies are reduced.",
        ["Normalization", "relations", "redundancy"],
    )
    assert result
    assert "functional dependencies" not in result[0]
    assert result[3].startswith("Normalization organizes relations")

@pytest.fixture(scope="module")
def api():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); port = s.getsockname()[1]; s.close()
    srv = uvicorn.Server(uvicorn.Config(app, port=port, log_level="warning"))
    threading.Thread(target=srv.run, daemon=True).start()
    base = f"http://127.0.0.1:{port}/api"
    for _ in range(50):
        try: requests.get(base + "/profile"); break
        except Exception: time.sleep(0.1)
    yield base
    srv.should_exit = True

S = {}

def test_starts_empty(api):
    d = requests.get(api + "/dashboard").json()
    assert d["next_exam"] is None and d["weakest"] == [] and d["streak_days"] == 0 and d["last7_total"] == 0
    assert len(d["last7"]) == 7 and requests.get(api + "/materials").json() == []
    assert d["counts"] == {"documents": 0, "sessions": 0, "quizzes": 0, "answers": 0}   # drives the empty-dashboard upload prompt

def test_profile_and_exam(api):
    r = requests.put(api + "/profile", json={"name": "Ayesha Khan", "program": "BS Artificial Intelligence", "term": "Fall 2026"}).json()
    assert r["initial"] == "A"
    sid = requests.post(api + "/subjects", json={"name": "Database Systems"}).json()[0]["id"]; S["sid"] = sid
    assert requests.post(api + "/exams", json={"subject_id": sid, "title": "Midterm", "date": "bad"}).status_code == 400
    requests.post(api + "/exams", json={"subject_id": sid, "title": "Midterm", "date": "2026-11-15"})
    d = requests.get(api + "/dashboard").json()
    assert d["next_exam"]["days_left"] == 12 and d["profile"]["name"] == "Ayesha Khan"

def test_upload_and_indexing(api):
    assert requests.post(api + "/materials", files={"file": ("x.exe", b"abc")}, data={"subject_id": S["sid"]}).status_code == 400
    r = requests.post(api + "/materials", files={"file": ("dbms_normalization.txt", NOTES.encode())}, data={"subject_id": S["sid"]})
    assert r.status_code == 201
    for _ in range(40):
        m = requests.get(api + "/materials").json()
        if m[0]["status"] != "indexing": break
        time.sleep(0.1)
    assert m[0]["status"] == "indexed" and m[0]["pages"] >= 1
    S["docid"] = m[0]["id"]

def test_source_grounded_summaries(api):
    whole = requests.post(api + "/summaries", json={"subject_id": S["sid"], "detail": "short"})
    assert whole.status_code == 200
    result = whole.json()
    assert result["mode"] == "extractive" and result["detail"] == "short"
    assert result["citations"] and result["citations"][0]["filename"] == "dbms_normalization.txt"
    assert "[1]" in result["summary"] and "Third normal form" in result["summary"]
    scoped = requests.post(api + "/summaries", json={
        "subject_id": S["sid"], "document_id": S["docid"], "detail": "detailed",
    })
    assert scoped.status_code == 200 and scoped.json()["scope"]["document_id"] == S["docid"]
    assert scoped.json()["detail"] == "detailed"
    assert requests.post(api + "/summaries", json={"subject_id": S["sid"], "detail": "long"}).status_code == 400
    requests.post(api + "/subjects", json={"name": "Empty Subject"})
    empty_subject = next(x["id"] for x in requests.get(api + "/subjects").json() if x["name"] == "Empty Subject")
    assert requests.post(api + "/summaries", json={"subject_id": empty_subject}).status_code == 422
    assert requests.post(api + "/summaries", json={
        "subject_id": empty_subject, "document_id": S["docid"],
    }).status_code == 404

def test_assistant_grounded_and_refuses(api):
    r = requests.post(api + "/assistant/chat", json={"message": "Explain third normal form", "subject_id": S["sid"]}).json()
    assert r["grounded"] and r["citations"] and r["citations"][0]["filename"] == "dbms_normalization.txt" and "[1]" in r["answer"]
    r = requests.post(api + "/assistant/chat", json={"message": "quantum chromodynamics gluon", "subject_id": S["sid"]}).json()
    assert r["grounded"] is False and r["citations"] == []
    assert requests.post(api + "/assistant/chat", json={"message": " "}).status_code == 400

def test_retrieval_prefers_full_query_coverage(api):
    from app import db as adb, services as sv
    # a decoy deck that repeats one query word ("key") far more often than the
    # real answer does - ranking must favour covering the whole question
    decoy = ("AES encryption expands a secret key into round key values; each round key masks the state. " * 12)
    r = requests.post(api + "/materials", files={"file": ("aes_keys.txt", decoy.encode())}, data={"subject_id": S["sid"]})
    assert r.status_code == 201
    for _ in range(40):
        m = requests.get(api + "/materials").json()
        if all(x["status"] != "indexing" for x in m): break
        time.sleep(0.1)
    try:
        with adb.conn() as c:
            hits = sv.retrieve(c, "What is a primary key?")
        assert hits and hits[0]["filename"] == "dbms_normalization.txt"
    finally:
        did = next(x["id"] for x in m if x["filename"] == "aes_keys.txt")
        requests.delete(f"{api}/materials/{did}")                     # leave the workspace as we found it
    assert len(requests.get(api + "/assistant/history").json()) == 4
    assert requests.get(api + "/assistant/status").json()["llm_connected"] is False

def test_quiz_flow_and_weak_topics(api):
    assert requests.post(api + "/quizzes", json={"subject_id": S["sid"], "difficulty": "expert"}).status_code == 400
    r = requests.post(api + "/quizzes", json={"subject_id": S["sid"], "count": 3, "difficulty": "basic"})
    assert r.status_code == 201
    q = r.json(); assert q["total"] >= 1 and q["difficulty"] == "basic" and "correct_index" not in q["questions"][0]
    first = q["questions"][0]
    wrong = (0 if first["options"] else 0)
    a = requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": 99})
    assert a.status_code == 400
    a = requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": wrong}).json()
    assert "explanation" in a and a["source"]["file"] == "dbms_normalization.txt"
    assert a["review"]["interval_days"] == 1 and a["review"]["due"] == "2026-11-04"   # first review is scheduled for tomorrow
    assert requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": wrong}).status_code == 409
    v = requests.get(f"{api}/quizzes/{q['id']}").json()
    assert v["answered"] == 1 and v["questions"][0]["answered"] and "correct_index" in v["questions"][0]
    trend = requests.get(api + "/analytics").json()["quiz_trend"]
    point = next(x for x in trend if x["quiz_id"] == q["id"])
    assert point == {"quiz_id": q["id"], "date": "2026-11-03",
                     "score": 100 if a["correct"] else 0, "correct": int(a["correct"]),
                     "answered": 1, "total": q["total"]}
    w = requests.get(api + "/weak-topics").json()
    assert w["ranked"][0]["answers"] == 1 and w["heatmap"]["rows"][0]["subject"] == "Database Systems"
    assert len(trend) == 1

def test_topic_area_groups_heatmap(api):
    tid = requests.get(api + "/weak-topics").json()["ranked"][0]["topic_id"]
    assert requests.put(f"{api}/topics/{tid}", json={}).status_code == 400
    assert requests.put(f"{api}/topics/{tid}", json={"area": "x" * 41}).status_code == 400
    assert requests.put(f"{api}/topics/99999", json={"area": "Schema"}).status_code == 404
    assert requests.put(f"{api}/topics/{tid}", json={"area": "Schema"}).json() == {"id": tid, "area": "Schema"}
    w = requests.get(api + "/weak-topics").json()
    assert "Schema" in w["heatmap"]["columns"] and w["heatmap"]["rows"][0]["cells"]["Schema"] is not None
    requests.put(f"{api}/topics/{tid}", json={"area": None})
    assert "Schema" not in requests.get(api + "/weak-topics").json()["heatmap"]["columns"]

def test_topic_scoped_quiz_uses_matching_sentences(api):
    r = requests.post(api + "/quizzes", json={"subject_id": S["sid"], "count": 4, "topic": "deadlock"})
    assert r.status_code == 201
    qs = r.json()["questions"]
    assert qs and all("deadlock" in (x["prompt"] + " " + " ".join(x["options"])).lower() for x in qs)
    assert requests.post(api + "/quizzes", json={"subject_id": S["sid"], "count": 2, "topic": "quantum chromodynamics"}).status_code == 201

def test_review_schedule_and_due_queue(api):
    from app import db as adb, services as asv
    import datetime as dt
    tid = requests.get(api + "/weak-topics").json()["ranked"][0]["topic_id"]
    with adb.conn() as c:
        c.execute("DELETE FROM reviews")
        first = asv.sm2_update(c, tid, True, day=dt.date(2026, 11, 3))
        assert first["interval_days"] == 1 and first["due"] == "2026-11-04"
        second = asv.sm2_update(c, tid, True, day=dt.date(2026, 11, 4))
        assert second["interval_days"] == 3 and second["due"] == "2026-11-07"
    assert requests.get(api + "/review/due").json()["count"] == 0       # scheduled for the 7th, not today
    os.environ["EXAMLY_TODAY"] = "2026-11-07"
    try:
        due = requests.get(api + "/review/due").json()
        assert due["count"] == 1 and due["due"][0]["topic_id"] == tid
        assert due["due"][0]["band"] in ("bad", "warn", "ok")
        assert len(requests.get(api + "/dashboard").json()["reviews_due"]) == 1
    finally:
        os.environ["EXAMLY_TODAY"] = "2026-11-03"
    with adb.conn() as c:
        lapse = asv.sm2_update(c, tid, False, day=dt.date(2026, 11, 7))
        assert lapse["interval_days"] == 1 and lapse["lapses"] == 1 and lapse["due"] == "2026-11-08"
        c.execute("DELETE FROM reviews")

def test_planner_proposal_not_saved_until_confirmed(api):
    p = requests.post(api + "/planner/propose", json={"days": 3, "start_time": "18:00"}).json()
    assert len(p["items"]) == 3 and p["items"][0]["scheduled_at"].startswith("2026-11-04T18:00")
    cal = requests.get(api + "/planner/calendar?month=2026-11").json()
    assert cal["days"].get("2026-11-04", {}).get("sessions", []) == []          # nothing saved yet
    assert cal["days"]["2026-11-15"]["exams"][0]["title"] == "Midterm" and cal["first_weekday"] == 6
    assert requests.post(f"{api}/planner/proposals/{p['id']}/confirm").json()["saved"] == 3
    assert requests.post(f"{api}/planner/proposals/{p['id']}/confirm").status_code == 404
    cal = requests.get(api + "/planner/calendar?month=2026-11").json()
    assert len(cal["days"]["2026-11-04"]["sessions"]) == 1
    p2 = requests.post(api + "/planner/propose", json={"days": 2}).json()
    requests.delete(f"{api}/planner/proposals/{p2['id']}")
    assert requests.get(f"{api}/planner/proposals/{p2['id']}").status_code == 404
    assert requests.post(api + "/planner/propose", json={"days": 0}).status_code == 400

def test_session_completion_feeds_streak_and_dashboard(api):
    sess = requests.get(api + "/planner/calendar?month=2026-11").json()["days"]["2026-11-04"]["sessions"][0]
    assert requests.patch(f"{api}/sessions/{sess['id']}", json={"status": "bogus"}).status_code == 400
    requests.post(api + "/study-log", json={"minutes": 45, "subject_id": S["sid"]})
    d = requests.get(api + "/dashboard").json()
    assert d["streak_days"] == 1 and d["last7_total"] == 45 and d["last7"][-1]["minutes"] == 45
    a = requests.get(api + "/analytics").json()
    assert a["active_days_30d"] == 1 and a["study_hours_30d"] == 0.8
    assert d["daily_goal"]["studied_minutes"] == 45

def test_analytics_filters_drilldown_and_exports(api):
    a = requests.get(api + "/analytics?days=7&subject_id=" + str(S["sid"])).json()
    assert a["filters"] == {"days": 7, "subject_id": S["sid"]}
    assert len(a["daily_minutes"]) == 7
    assert a["daily_minutes"][-1]["minutes"] >= 45
    assert requests.get(api + "/analytics?days=8").status_code == 400
    assert requests.get(api + "/analytics?subject_id=not-a-number").status_code == 400
    day = requests.get(api + "/analytics/day?date=2026-11-03&subject_id=" + str(S["sid"])).json()
    assert day["study_minutes"] >= 45 and day["study_logs"] and day["quizzes"]
    assert requests.get(api + "/analytics/day?date=bad").status_code == 400
    assert requests.get(api + "/analytics/day?date=2026-11-03&subject_id=99999").status_code == 404
    csv_export = requests.get(api + "/export?format=csv")
    assert csv_export.status_code == 200 and "text/csv" in csv_export.headers["content-type"]
    assert "examly-study-log.csv" in csv_export.headers["content-disposition"]
    assert "date,minutes,subject,session_id" in csv_export.text
    json_export = requests.get(api + "/export?format=json").json()
    assert json_export["study_log"] and json_export["quiz_results"]
    assert "examly-study-data.json" in requests.get(api + "/export?format=json").headers["content-disposition"]
    assert requests.get(api + "/export?format=xml").status_code == 400

def test_daily_study_goal_configuration(api):
    assert requests.get(api + "/study-goal").json()["target_minutes"] == 60
    goal = requests.put(api + "/study-goal", json={"target_minutes": 90}).json()
    assert goal["target_minutes"] == 90 and goal["studied_minutes"] == 45 and goal["progress_percent"] == 50
    assert requests.put(api + "/study-goal", json={"target_minutes": 4}).status_code == 400
    assert requests.put(api + "/study-goal", json={"target_minutes": "many"}).status_code == 400
    assert requests.get(api + "/dashboard").json()["daily_goal"]["target_minutes"] == 90
    requests.put(api + "/study-goal", json={"target_minutes": 60})

def test_flashcards_and_review_grading(api):
    f = requests.get(api + "/flashcards").json()
    assert f["total"] >= 1 and f["due_count"] >= 1 and f["cards"]
    c = f["cards"][0]
    assert c["front"] and c["back"] and c["source"]["file"] == "dbms_normalization.txt"
    assert requests.post(f"{api}/review/{c['topic_id']}", json={"correct": "yes"}).status_code == 400
    assert requests.post(f"{api}/review/99999", json={"correct": True}).status_code == 404
    r = requests.post(f"{api}/review/{c['topic_id']}", json={"correct": True}).json()
    assert r["review"]["interval_days"] == 1
    assert requests.get(api + "/flashcards").json()["due_count"] < f["due_count"]   # topic rescheduled, cards no longer due
    assert requests.get(api + "/flashcards?limit=1").json()["cards"][0:1] and len(requests.get(api + "/flashcards?limit=1").json()["cards"]) == 1
    assert requests.get(api + "/flashcards?limit=x").status_code == 400

def test_flashcards_scoped_to_selected_document(api):
    # a second document appears in the selector; decks can be scoped to it
    text = ("A left join preserves every record from the left table even when no matching record exists on the right. "
            "An inner join returns only those records with matching values in both relations. "
            "Database systems optimise join operations using specialised indexes and hash tables. ") * 6
    r = requests.post(api + "/materials", files={"file": ("joins_cheatsheet.txt", text.encode())}, data={"subject_id": S["sid"]})
    assert r.status_code == 201
    doc2 = r.json()["id"]
    try:
        for _ in range(40):
            m = requests.get(api + "/materials").json()
            if all(x["status"] != "indexing" for x in m): break
            time.sleep(0.1)
        assert requests.get(api + "/flashcards").json()["scope"] is None              # default deck is unscoped
        assert requests.get(api + "/flashcards", params={"document_id": doc2}).json()["total"] == 0   # no cards from this file yet
        q = requests.post(api + "/quizzes", json={"subject_id": S["sid"], "count": 4, "document_ids": [doc2]})
        assert q.status_code == 201                                                   # build cards straight from it
        f = requests.get(api + "/flashcards", params={"document_id": doc2}).json()
        assert f["scope"] == {"document_id": doc2, "filename": "joins_cheatsheet.txt", "subject_id": S["sid"]}
        assert f["total"] >= 1 and f["due_count"] >= 1 and f["cards"]
        assert all(c["source"]["file"] == "joins_cheatsheet.txt" for c in f["cards"]) # nothing leaks in from other files
        whole_subject = requests.get(api + "/flashcards", params={"subject_id": S["sid"], "due_only": 0}).json()
        assert whole_subject["scope"] == {"subject_id": S["sid"], "subject": "Database Systems"}
        assert whole_subject["total"] >= f["total"]
        assert all(c["subject_id"] == S["sid"] for c in whole_subject["cards"])
        assert requests.get(api + "/flashcards", params={"subject_id": 99999}).status_code == 404
        assert requests.get(api + "/flashcards?subject_id=x").status_code == 400
        assert requests.get(api + "/flashcards", params={"subject_id": 99999, "document_id": doc2}).status_code == 404
        assert requests.get(api + "/flashcards", params={"document_id": 99999}).status_code == 404
        assert requests.get(api + "/flashcards?document_id=x").status_code == 400
    finally:
        requests.delete(f"{api}/materials/{doc2}")                                    # restore: only the original doc remains
    remaining = requests.get(api + "/flashcards", params={"subject_id": S["sid"], "due_only": 0}).json()
    assert all(c["source"]["file"] != "joins_cheatsheet.txt" for c in remaining["cards"])

def test_activity_returns_real_data(api):
    a = requests.get(api + "/activity").json()
    assert a["assistant"]["llm_connected"] is False
    assert a["counts"]["documents"] == 1 and a["counts"]["answers"] >= 1 and a["counts"]["quizzes"] >= 1
    assert a["memory"]["profile"]["name"] == "Ayesha Khan"
    assert a["memory"]["exams"] and a["memory"]["weakest"]
    assert a["recent"] and a["recent"][-1]["role"] == "assistant"

def test_delete_material_cascades(api):
    mid = requests.get(api + "/materials").json()[0]["id"]
    requests.delete(f"{api}/materials/{mid}")
    assert requests.get(api + "/materials").json() == []
    r = requests.post(api + "/assistant/chat", json={"message": "Explain third normal form"}).json()
    assert r["grounded"] is False

def test_ingest_six_documents_stays_correct(api):
    from pathlib import Path
    from app import db as adb
    files = sorted((Path(__file__).resolve().parent.parent / "sample_materials" / "database_systems").glob("*.md"))
    assert len(files) == 6
    sid = next(x["id"] for x in requests.post(api + "/subjects", json={"name": "Database Systems"}).json() if x["name"] == "Database Systems")
    for f in files:
        r = requests.post(api + "/materials", files={"file": (f.name, f.read_bytes(), "text/markdown")}, data={"subject_id": sid})
        assert r.status_code == 201
    for _ in range(120):
        docs = requests.get(api + "/materials", params={"subject_id": sid}).json()
        if docs and all(d["status"] != "indexing" for d in docs): break
        time.sleep(0.1)
    assert len(docs) == 6
    assert all(d["status"] == "indexed" and d["pages"] >= 1 and d["chunks"] >= 1 for d in docs)
    with adb.conn() as c:
        assert adb.one(c, "SELECT COUNT(*) n FROM chunks")["n"] >= 6        # persisted, not only in memory
    names = {d["filename"] for d in docs}
    r = requests.post(api + "/assistant/chat", json={"message": "Explain third normal form", "subject_id": sid}).json()
    assert r["grounded"] and r["citations"] and r["citations"][0]["filename"] in names
    # Re-uploading the same filename replaces the old document instead of duplicating stale text.
    f = files[0]
    changed = ("Third normal form removes transitive dependencies so that non key attributes depend only on the primary key. " * 12).encode()
    assert requests.post(api + "/materials", files={"file": (f.name, changed, "text/markdown")}, data={"subject_id": sid}).status_code == 201
    for _ in range(80):
        docs = requests.get(api + "/materials", params={"subject_id": sid}).json()
        if len(docs) == 6 and all(d["status"] == "indexed" for d in docs): break
        time.sleep(0.1)
    assert len(docs) == 6 and len({d["filename"] for d in docs}) == 6
    assert requests.post(api + "/quizzes", json={"subject_id": sid, "count": 5}).status_code == 201

def test_interrupted_indexing_is_marked_failed(api):
    from app import db as adb
    with adb.conn() as c:
        sid = adb.one(c, "SELECT id FROM subjects ORDER BY id LIMIT 1")["id"]
        c.execute("INSERT INTO documents(subject_id,filename,added_at,status) VALUES(?,?,?,'indexing')", (sid, "interrupted.md", "2026-11-03"))
    adb.init()
    with adb.conn() as c:
        assert adb.one(c, "SELECT status FROM documents WHERE filename='interrupted.md'")["status"] == "failed"
        c.execute("DELETE FROM documents WHERE filename='interrupted.md'")

def _stub_provider(routes):
    """Throwaway HTTP stub: routes = {path-substring: (status, body-bytes)}."""
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            n = int(self.headers.get("Content-Length") or 0)
            self.rfile.read(n)
            for pat, (code, body) in routes.items():
                if pat in self.path:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(body)
                    return
            self.send_response(404); self.end_headers()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, f"http://127.0.0.1:{srv.server_address[1]}"

def test_key_file_and_config_resolution(tmp_path, monkeypatch):
    from app import config
    keyf = tmp_path / "grok.txt"
    keyf.write_text("# Grok key\nGROK_API_KEY=abc123\n# xai-REPLACE_WITH_YOUR_KEY\n", encoding="utf-8")
    assert config.read_key(str(keyf)) == "abc123"                    # KEY=value form + comments skipped
    raw = tmp_path / "raw.txt"; raw.write_text("  xai-RAW-KEY-42  \n", encoding="utf-8")
    assert config.read_key(str(raw)) == "xai-RAW-KEY-42"             # raw key line
    assert config.read_key(str(tmp_path / "missing.txt")) == ""      # missing file is not an error
    assert config.read_key("") == ""
    monkeypatch.setenv("GROK_API_KEY", "env-wins")                   # env var beats the key file
    assert config.grok_key() == "env-wins"
    monkeypatch.delenv("GROK_API_KEY")
    monkeypatch.setenv("GROK_KEY_FILE", str(keyf))
    assert config.grok_key() == "abc123"
    monkeypatch.setenv("LLM_PROVIDER_ORDER", "grok,nope")            # unknown providers are dropped later
    assert config.provider_order() == ["grok", "nope"]
    monkeypatch.setenv("MAX_UPLOAD_MB", "7")
    assert config.max_upload_bytes() == 7 * 1024 * 1024

def test_env_file_inline_comments_and_numbers(tmp_path, monkeypatch):
    from app import config
    envf = tmp_path / ".env"
    envf.write_text("LLM_TIMEOUT_S=20    # per request\n"
                    "LLM_TOTAL_S=45  # hard budget for the whole chain\n"
                    'GEMINI_MODEL="gemini-3.6-flash,gemini-3.5-flash"\n',
                    encoding="utf-8")
    monkeypatch.setenv("EXAMLY_ENV_FILE", str(envf))
    for k in ("LLM_TIMEOUT_S", "LLM_TOTAL_S", "GEMINI_MODEL"):       # live env must not shadow the file
        monkeypatch.delenv(k, raising=False)
    assert config.settings("LLM_TIMEOUT_S") == "20"                  # inline comments stripped
    assert config.timeout_seconds() == 20.0                          # ...so the number parses
    assert config.total_seconds() == 45.0
    assert config.settings("GEMINI_MODEL") == "gemini-3.6-flash,gemini-3.5-flash"

def test_provider_chain_falls_back_to_next(tmp_path, monkeypatch):
    from app import llm
    import json as _json
    ok = _json.dumps({"candidates": [{"content": {"parts": [{"text": "gemini says hi"}]}}]}).encode()
    srv, base = _stub_provider({"/chat/completions": (500, b"boom"),
                                ":generateContent": (200, ok)})
    try:
        kf = tmp_path / "k.txt"; kf.write_text("stub-key-123\n", encoding="utf-8")
        monkeypatch.setenv("EXAMLY_DISABLE_LLM", "0")
        monkeypatch.setenv("LLM_PROVIDER_ORDER", "grok,gemini")
        monkeypatch.setenv("GROK_KEY_FILE", str(kf)); monkeypatch.setenv("GROK_BASE_URL", base + "/x"); monkeypatch.setenv("GROK_MODEL", "stub")
        monkeypatch.setenv("GEMINI_KEY_FILE", str(kf)); monkeypatch.setenv("GEMINI_BASE_URL", base); monkeypatch.setenv("GEMINI_MODEL", "stub")
        out = llm.generate("sys", "hello")
        assert out and out["provider"] == "gemini" and "hi" in out["text"]   # grok 500 -> chain moves on
        st = llm.status()
        assert st["configured"] and st["llm_connected"] and st["providers"] == ["grok", "gemini"]
        assert st["label"] == "Grok + Gemini ready"
    finally:
        srv.shutdown()

def test_all_providers_down_uses_extractive_answer(tmp_path, monkeypatch):
    from app import llm, services as sv, db as adb
    srv, base = _stub_provider({"/chat/completions": (500, b"boom"),
                                ":generateContent": (500, b"boom")})
    try:
        kf = tmp_path / "k.txt"; kf.write_text("stub-key-123\n", encoding="utf-8")
        monkeypatch.setenv("EXAMLY_DISABLE_LLM", "0")
        monkeypatch.setenv("LLM_PROVIDER_ORDER", "grok,gemini")
        monkeypatch.setenv("GROK_KEY_FILE", str(kf)); monkeypatch.setenv("GROK_BASE_URL", base + "/x"); monkeypatch.setenv("GROK_MODEL", "stub")
        monkeypatch.setenv("GEMINI_KEY_FILE", str(kf)); monkeypatch.setenv("GEMINI_BASE_URL", base); monkeypatch.setenv("GEMINI_MODEL", "stub")
        assert llm.generate("sys", "hello") is None                    # every provider failed
        with adb.conn() as c:
            res = sv.answer(c, "Explain third normal form")            # falls back to the excerpts
        assert res["mode"] == "extractive" and res["grounded"] and res["citations"]
    finally:
        srv.shutdown()

def test_register_seeds_display_name_and_keeps_edits(api):
    from app import db as adb
    with adb.conn() as c:
        c.execute("UPDATE profile SET name=''")                        # fresh, empty profile
        c.execute("DELETE FROM auth_sessions"); c.execute("DELETE FROM users")
    s = requests.Session()
    r = s.post(api + "/auth/register", json={"username": "maria.khan", "password": "secret123"})
    assert r.status_code == 201
    assert s.get(api + "/profile").json()["name"] == "Maria Khan"      # name shows as soon as you sign in
    s.put(api + "/profile", json={"name": "Maria Zaidi"})
    s.post(api + "/auth/logout")
    assert s.post(api + "/auth/login", json={"username": "maria.khan", "password": "secret123"}).status_code == 200
    assert s.get(api + "/profile").json()["name"] == "Maria Zaidi"     # a chosen name is never overwritten
    s.post(api + "/auth/logout")
    with adb.conn() as c:                                              # restore state for the login-gate test
        c.execute("DELETE FROM auth_sessions"); c.execute("DELETE FROM users")
        c.execute("UPDATE profile SET name='Ayesha Khan'")

def test_upload_size_limit(api, monkeypatch):
    monkeypatch.setenv("MAX_UPLOAD_MB", "1")
    big = b"a" * (1024 * 1024 + 2048)
    r = requests.post(api + "/materials", files={"file": ("big_note.txt", big)}, data={"subject_id": S["sid"]})
    assert r.status_code == 413 and "upload limit" in r.json()["error"]
    r = requests.post(api + "/materials", files={"file": ("small_note.txt", b"Short note. " * 20)}, data={"subject_id": S["sid"]})
    assert r.status_code == 201                                       # normal files still upload

def test_login_gate_and_session(api):
    root = api[:-4]
    s = requests.Session()
    assert s.get(api + "/auth/status").json()["login_required"] is False
    assert s.post(api + "/auth/register", json={"username": "ab", "password": "secret123"}).status_code == 400
    assert s.post(api + "/auth/register", json={"username": "Ayesha", "password": "secret123"}).status_code == 201
    assert s.get(api + "/dashboard").status_code == 200
    assert requests.get(api + "/dashboard").status_code == 401              # a client without the cookie is locked out
    assert requests.get(root + "/", allow_redirects=False).status_code == 303
    assert requests.get(root + "/login").status_code == 200
    assert s.post(api + "/auth/logout").status_code == 200
    assert s.get(api + "/dashboard").status_code == 401
    assert s.post(api + "/auth/login", json={"username": "ayesha", "password": "wrong"}).status_code == 401
    r = s.post(api + "/auth/login", json={"username": "ayesha", "password": "secret123"})
    assert r.status_code == 200 and r.json()["user"]["username"] == "ayesha"
    assert s.get(api + "/dashboard").status_code == 200
    assert s.post(api + "/auth/register", json={"username": "other", "password": "secret123"}).status_code == 409
