"""End-to-end tests. Runs a real uvicorn server (httpx for TestClient is unavailable offline)."""
import os, sys, time, threading, tempfile, socket
tmp = tempfile.mkdtemp()
os.environ["EXAMLY_DB"] = os.path.join(tmp, "t.db")
os.environ["EXAMLY_TODAY"] = "2026-11-03"
os.environ.pop("EXAMLY_LLM_URL", None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import requests, uvicorn, pytest
from app.main import app

NOTES = ("Third normal form removes transitive dependencies so that non key attributes depend only on the primary key. "
         "Second normal form removes partial dependencies on a composite candidate key. "
         "Deadlock occurs when processes hold resources while waiting for resources held by other processes. "
         "Transactions guarantee atomicity, consistency, isolation and durability through logging and recovery. "
         "Normalization decomposes relations to reduce redundancy and update anomalies in relational databases. "
         "Indexing structures such as balanced trees accelerate lookups on frequently queried attributes.\n\n") * 3

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

def test_assistant_grounded_and_refuses(api):
    r = requests.post(api + "/assistant/chat", json={"message": "Explain third normal form", "subject_id": S["sid"]}).json()
    assert r["grounded"] and r["citations"] and r["citations"][0]["filename"] == "dbms_normalization.txt" and "[1]" in r["answer"]
    r = requests.post(api + "/assistant/chat", json={"message": "quantum chromodynamics gluon", "subject_id": S["sid"]}).json()
    assert r["grounded"] is False and r["citations"] == []
    assert requests.post(api + "/assistant/chat", json={"message": " "}).status_code == 400
    assert len(requests.get(api + "/assistant/history").json()) == 4
    assert requests.get(api + "/assistant/status").json()["llm_connected"] is False

def test_quiz_flow_and_weak_topics(api):
    r = requests.post(api + "/quizzes", json={"subject_id": S["sid"], "count": 3})
    assert r.status_code == 201
    q = r.json(); assert q["total"] >= 1 and "correct_index" not in q["questions"][0]
    first = q["questions"][0]
    wrong = (0 if first["options"] else 0)
    a = requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": 99})
    assert a.status_code == 400
    a = requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": wrong}).json()
    assert "explanation" in a and a["source"]["file"] == "dbms_normalization.txt"
    assert requests.post(f"{api}/quizzes/{q['id']}/questions/{first['id']}/answer", json={"chosen": wrong}).status_code == 409
    v = requests.get(f"{api}/quizzes/{q['id']}").json()
    assert v["answered"] == 1 and v["questions"][0]["answered"] and "correct_index" in v["questions"][0]
    w = requests.get(api + "/weak-topics").json()
    assert w["ranked"][0]["answers"] == 1 and w["heatmap"]["rows"][0]["subject"] == "Database Systems"
    assert len(requests.get(api + "/analytics").json()["quiz_trend"]) == 1

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

def test_delete_material_cascades(api):
    mid = requests.get(api + "/materials").json()[0]["id"]
    requests.delete(f"{api}/materials/{mid}")
    assert requests.get(api + "/materials").json() == []
    r = requests.post(api + "/assistant/chat", json={"message": "Explain third normal form"}).json()
    assert r["grounded"] is False
