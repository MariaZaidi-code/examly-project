"""Examly API (Starlette). Run: uvicorn app.main:app --reload"""
import datetime as dt, calendar, os, re
from starlette.applications import Starlette
from starlette.background import BackgroundTask
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse, FileResponse, PlainTextResponse, RedirectResponse
from starlette.routing import Route
from . import db, services as sv, auth, config, llm

# The single-page frontend lives next to backend/ (webapp/frontend.html) and is served at "/".
FRONTEND = os.environ.get("EXAMLY_FRONTEND") or os.path.join(os.path.dirname(__file__), "..", "..", "frontend.html")
LOGIN = os.environ.get("EXAMLY_LOGIN") or os.path.join(os.path.dirname(__file__), "..", "..", "login.html")

async def index(req):
    if not os.path.isfile(FRONTEND): return PlainTextResponse("frontend.html not found at " + os.path.abspath(FRONTEND), status_code=404)
    r = FileResponse(FRONTEND, media_type="text/html")
    r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    r.headers["Pragma"] = "no-cache"
    r.headers["Expires"] = "0"
    return r

async def login_page(req):
    if not os.path.isfile(LOGIN): return PlainTextResponse("login.html not found at " + os.path.abspath(LOGIN), status_code=404)
    return FileResponse(LOGIN, media_type="text/html")

def err(msg, code=400): return JSONResponse({"error": msg}, status_code=code)

async def body(req):
    try:
        d = await req.json()
        return d if isinstance(d, dict) else {}
    except Exception:
        return {}

def subject_id_for(c, d):
    """Accept subject_id or subject (name, created on demand)."""
    if d.get("subject_id"): return int(d["subject_id"])
    name = (d.get("subject") or "").strip()
    if not name: return None
    c.execute("INSERT OR IGNORE INTO subjects(name) VALUES(?)", (name,))
    return db.one(c, "SELECT id FROM subjects WHERE name=?", (name,))["id"]

# ---- profile & subjects & exams ----
async def profile(req):
    with db.conn() as c:
        if req.method == "PUT":
            d = await body(req)
            c.execute("UPDATE profile SET name=COALESCE(?,name), program=COALESCE(?,program), term=COALESCE(?,term) WHERE id=1",
                      (d.get("name"), d.get("program"), d.get("term")))
        p = db.one(c, "SELECT name,program,term FROM profile WHERE id=1")
        p["initial"] = (p["name"] or "?")[:1].upper()
        return JSONResponse(p)

async def subjects(req):
    with db.conn() as c:
        if req.method == "POST":
            d = await body(req)
            if not (d.get("name") or "").strip(): return err("name required")
            c.execute("INSERT OR IGNORE INTO subjects(name) VALUES(?)", (d["name"].strip(),))
        return JSONResponse(db.rows(c, "SELECT id,name FROM subjects ORDER BY name"))

async def exams(req):
    with db.conn() as c:
        if req.method == "POST":
            d = await body(req)
            sid = subject_id_for(c, d)
            try: dt.date.fromisoformat(d.get("date", ""))
            except ValueError: return err("date must be YYYY-MM-DD")
            if not sid: return err("subject required")
            c.execute("INSERT INTO exams(subject_id,title,date) VALUES(?,?,?)", (sid, d.get("title") or "Exam", d["date"]))
        return JSONResponse(db.rows(c, "SELECT e.id,e.title,e.date,s.name subject,s.id subject_id FROM exams e JOIN subjects s ON s.id=e.subject_id ORDER BY date"))

# ---- dashboard ----
async def dashboard(req):
    t = db.today()
    with db.conn() as c:
        p = db.one(c, "SELECT name,program,term FROM profile WHERE id=1")
        ex = db.one(c, "SELECT e.title,e.date,s.name subject FROM exams e JOIN subjects s ON s.id=e.subject_id WHERE date>=? ORDER BY date LIMIT 1", (t.isoformat(),))
        if ex: ex["days_left"] = (dt.date.fromisoformat(ex["date"]) - t).days
        today_s = db.rows(c, "SELECT x.id,x.topic,s.name subject,x.scheduled_at,x.duration_min,x.status FROM sessions x JOIN subjects s ON s.id=x.subject_id WHERE substr(x.scheduled_at,1,10)=? ORDER BY scheduled_at", (t.isoformat(),))
        last7 = [{"date": d.isoformat(), "weekday": d.strftime("%a"), "minutes": m} for d, m in sv.minutes_by_day(c, 7)]
        weak = sorted(sv.topic_stats(c), key=lambda s: s["proficiency"])
        due = sv.due_reviews(c)
        hour = dt.datetime.now().hour
        counts = {k: db.one(c, f"SELECT COUNT(*) n FROM {k}")["n"]
                  for k in ("documents", "sessions", "quizzes", "answers")}
        return JSONResponse({
            "greeting": "Good morning" if hour < 12 else "Good afternoon" if hour < 18 else "Good evening",
            "profile": p, "next_exam": ex, "streak_days": sv.streak(c),
            "today_sessions": today_s, "last7": last7, "last7_total": sum(x["minutes"] for x in last7),
            "weakest": [{**w, "band": sv.band(w["proficiency"])} for w in weak[:3]],
            "reviews_due": due,
            "counts": counts,
            "recommended": ({"topic": weak[0]["topic"], "subject": weak[0]["subject"], "proficiency": weak[0]["proficiency"], "answers": weak[0]["answers"]} if weak else None),
        })

# ---- materials ----
async def materials(req):
    with db.conn() as c:
        if req.method == "POST":
            max_bytes = config.max_upload_bytes()
            cl = req.headers.get("content-length") or ""
            if cl.isdigit() and int(cl) > max_bytes + 65536:   # fast path (multipart overhead allowed)
                return err(f"file is larger than the {max_bytes // (1024 * 1024)} MB upload limit", 413)
            form = await req.form()
            f = form.get("file")
            if f is None or not hasattr(f, "filename"): return err("file required")
            sid = subject_id_for(c, dict(form))
            if not sid: return err("subject or subject_id required")
            data = await f.read()
            if not data: return err("empty file")
            if len(data) > max_bytes:                          # exact check after reading
                return err(f"file is larger than the {max_bytes // (1024 * 1024)} MB upload limit", 413)
            ext = f.filename.lower().rsplit(".", 1)[-1]
            if ext not in ("pdf", "txt", "md", "pptx", "ppt"): return err("only pdf, txt, md, pptx or ppt supported")
            old = db.one(c, "SELECT id FROM documents WHERE subject_id=? AND filename=?", (sid, f.filename))
            if old: c.execute("DELETE FROM documents WHERE id=?", (old["id"],))   # replace, so a re-upload never leaves stale chunks
            c.execute("INSERT INTO documents(subject_id,filename,added_at) VALUES(?,?,?)", (sid, f.filename, db.today().isoformat()))
            did = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.commit()
            return JSONResponse({"id": did, "filename": f.filename, "status": "indexing"}, status_code=201,
                                background=BackgroundTask(sv.index_document, did, f.filename, data))
        q = ("SELECT d.id,d.filename,d.pages,d.status,d.added_at,(SELECT COUNT(*) FROM chunks WHERE document_id=d.id) chunks,"
             "s.id subject_id,s.name subject FROM documents d JOIN subjects s ON s.id=d.subject_id")
        args = []
        if req.query_params.get("subject_id"): q += " WHERE s.id=?"; args.append(req.query_params["subject_id"])
        return JSONResponse(db.rows(c, q + " ORDER BY d.id DESC", args))

async def material_delete(req):
    with db.conn() as c:
        c.execute("DELETE FROM documents WHERE id=?", (req.path_params["id"],))
    return JSONResponse({"ok": True})

# ---- assistant ----
async def assistant_status(req):
    st = llm.status()
    return JSONResponse({"llm_connected": st["configured"], "label": st["label"], "providers": st["providers"]})

async def assistant_chat(req):
    d = await body(req)
    msg = (d.get("message") or "").strip()
    if not msg: return err("message required")
    with db.conn() as c:
        sid = d.get("subject_id")
        res = sv.answer(c, msg, sid, d.get("level", "Standard"), d.get("document_ids"))
        c.execute("INSERT INTO messages(role,subject_id,content,created_at) VALUES('user',?,?,?)", (sid, msg, db.now_iso()))
        c.execute("INSERT INTO messages(role,subject_id,content,citations,created_at) VALUES('assistant',?,?,?,?)",
                  (sid, res["answer"], __import__("json").dumps(res["citations"]), db.now_iso()))
    return JSONResponse(res)

async def assistant_history(req):
    if req.method == "DELETE": return await assistant_clear(req)
    with db.conn() as c:
        r = db.rows(c, "SELECT id,role,subject_id,content,citations,created_at FROM messages ORDER BY id")
    for m in r: m["citations"] = db.jloads(m["citations"], [])
    return JSONResponse(r)

async def assistant_clear(req):
    with db.conn() as c: c.execute("DELETE FROM messages")
    return JSONResponse({"ok": True})

# ---- planner ----
async def calendar_view(req):
    month = req.query_params.get("month") or db.today().strftime("%Y-%m")
    try: y, m = map(int, month.split("-")); calendar.monthrange(y, m)
    except Exception: return err("month must be YYYY-MM")
    first, last = f"{y:04d}-{m:02d}-01", f"{y:04d}-{m:02d}-{calendar.monthrange(y, m)[1]:02d}"
    with db.conn() as c:
        ss = db.rows(c, "SELECT x.id,x.topic,s.name subject,x.scheduled_at,x.duration_min,x.status FROM sessions x JOIN subjects s ON s.id=x.subject_id WHERE substr(scheduled_at,1,10) BETWEEN ? AND ? ORDER BY scheduled_at", (first, last))
        es = db.rows(c, "SELECT e.id,e.title,e.date,s.name subject FROM exams e JOIN subjects s ON s.id=e.subject_id WHERE date BETWEEN ? AND ?", (first, last))
    days = {}
    for s in ss: days.setdefault(s["scheduled_at"][:10], {"sessions": [], "exams": []})["sessions"].append(s)
    for e in es: days.setdefault(e["date"], {"sessions": [], "exams": []})["exams"].append(e)
    return JSONResponse({"month": month, "first_weekday": dt.date(y, m, 1).weekday(), "days_in_month": calendar.monthrange(y, m)[1], "days": days})

async def planner_propose(req):
    d = await body(req)
    try: days, dur = int(d.get("days", 7)), int(d.get("duration_min", 45)); dt.datetime.strptime(d.get("start_time", "18:00"), "%H:%M")
    except ValueError: return err("invalid days, duration_min or start_time (HH:MM)")
    if not (1 <= days <= 31 and 10 <= dur <= 240): return err("days 1-31, duration_min 10-240")
    with db.conn() as c:
        pid = sv.propose(c, d.get("subject_ids"), days, d.get("start_time", "18:00"), dur, int(d.get("per_day", 1)), d.get("start_date"))
        if not pid: return err("Add a subject and some materials first, there is nothing to plan.", 422)
        return JSONResponse(sv.proposal_view(c, pid), status_code=201)

async def proposal_get(req):
    with db.conn() as c:
        v = sv.proposal_view(c, req.path_params["id"])
    return JSONResponse(v) if v else err("not found", 404)

async def proposal_confirm(req):
    pid = req.path_params["id"]
    with db.conn() as c:
        items = db.rows(c, "SELECT * FROM proposal_items WHERE proposal_id=?", (pid,))
        if not items: return err("proposal not found or already handled", 404)
        c.executemany("INSERT INTO sessions(subject_id,topic,scheduled_at,duration_min) VALUES(?,?,?,?)", [(i["subject_id"], i["topic"], i["scheduled_at"], i["duration_min"]) for i in items])
        c.execute("DELETE FROM proposals WHERE id=?", (pid,))
    return JSONResponse({"saved": len(items)}, status_code=201)

async def proposal_discard(req):
    with db.conn() as c: c.execute("DELETE FROM proposals WHERE id=?", (req.path_params["id"],))
    return JSONResponse({"ok": True})

async def session_patch(req):
    sid, d = req.path_params["id"], await body(req)
    if d.get("status") not in ("planned", "done", "skipped"): return err("status must be planned, done or skipped")
    with db.conn() as c:
        s = db.one(c, "SELECT * FROM sessions WHERE id=?", (sid,))
        if not s: return err("not found", 404)
        c.execute("DELETE FROM study_log WHERE session_id=?", (sid,))
        if d["status"] == "done":
            c.execute("UPDATE sessions SET status='done', completed_at=? WHERE id=?", (db.now_iso(), sid))
            mins = int(d.get("minutes", s["duration_min"]))
            c.execute("INSERT INTO study_log(day,minutes,subject_id,session_id) VALUES(?,?,?,?)", (db.today().isoformat(), mins, s["subject_id"], sid))
        else:
            c.execute("UPDATE sessions SET status=?, completed_at=NULL WHERE id=?", (d["status"], sid))
    return JSONResponse({"ok": True})

async def session_delete(req):
    with db.conn() as c:
        c.execute("DELETE FROM study_log WHERE session_id=?", (req.path_params["id"],))
        c.execute("DELETE FROM sessions WHERE id=?", (req.path_params["id"],))
    return JSONResponse({"ok": True})

async def study_log_add(req):
    d = await body(req)
    try: m = int(d["minutes"]); assert 1 <= m <= 1440
    except Exception: return err("minutes 1-1440 required")
    day = d.get("day") or db.today().isoformat()
    with db.conn() as c:
        c.execute("INSERT INTO study_log(day,minutes,subject_id) VALUES(?,?,?)", (day, m, d.get("subject_id")))
    return JSONResponse({"ok": True}, status_code=201)

# ---- quizzes ----
async def quizzes_list(req):
    with db.conn() as c:
        rows = db.rows(c, """SELECT z.id, z.subject_id, s.name subject, z.created_at,
            (SELECT COUNT(*) FROM questions WHERE quiz_id=z.id) total,
            (SELECT COUNT(*) FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.quiz_id=z.id) answered,
            (SELECT AVG(a.correct)*100 FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.quiz_id=z.id) score
            FROM quizzes z LEFT JOIN subjects s ON s.id=z.subject_id ORDER BY z.id DESC""")
    out = []
    for r in rows:
        d = dict(r)
        d["score"] = round(d["score"], 1) if d.get("score") is not None else None
        d["completed"] = (d.get("answered") or 0) >= (d.get("total") or 0) and (d.get("total") or 0) > 0
        out.append(d)
    return JSONResponse({"quizzes": out})

async def quiz_create(req):
    d = await body(req)
    with db.conn() as c:
        sid = subject_id_for(c, d)
        if not sid: return err("subject_id required")
        count = max(1, min(int(d.get("count", 5)), 20))
        qid = sv.generate_quiz(c, sid, count, d.get("topic"), d.get("document_ids"))
        if not qid: return err("No usable text in this subject's indexed materials. Upload notes first.", 422)
        return JSONResponse(sv.quiz_view(c, qid), status_code=201)

async def quiz_get(req):
    with db.conn() as c: v = sv.quiz_view(c, req.path_params["id"])
    return JSONResponse(v) if v else err("not found", 404)

async def quiz_extend(req):
    qid = req.path_params["id"]
    d = await body(req)
    try: count = max(1, min(int(d.get("count", 5)), 20))
    except (TypeError, ValueError): return err("count must be an integer")
    with db.conn() as c:
        v = sv.quiz_view(c, qid)
        if not v: return err("not found", 404)
        new_qid = sv.extend_quiz(c, qid, count, d.get("document_ids"))
        if not new_qid: return err("No more usable text for additional questions.", 422)
    return JSONResponse(sv.quiz_view(c, qid), status_code=200)

async def quiz_answer(req):
    d = await body(req)
    with db.conn() as c:
        q = db.one(c, "SELECT * FROM questions WHERE id=? AND quiz_id=?", (req.path_params["qid"], req.path_params["id"]))
        if not q: return err("not found", 404)
        n = len(db.jloads(q["options"], []))
        ch = d.get("chosen")
        if not isinstance(ch, int) or not 0 <= ch < n: return err(f"chosen must be an integer 0-{n - 1}")
        if db.one(c, "SELECT 1 FROM answers WHERE question_id=?", (q["id"],)): return err("already answered", 409)
        ok = int(ch == q["correct_index"])
        c.execute("INSERT INTO answers(question_id,chosen,correct,answered_at) VALUES(?,?,?,?)", (q["id"], ch, ok, db.now_iso()))
        rev = sv.sm2_update(c, q["topic_id"], bool(ok))
        nxt = db.one(c, "SELECT id FROM questions WHERE quiz_id=? AND position>? ORDER BY position LIMIT 1", (q["quiz_id"], q["position"]))
        return JSONResponse({"correct": bool(ok), "correct_index": q["correct_index"], "explanation": q["explanation"],
                             "source": {"file": q["source_file"], "page": q["source_page"]}, "next_question_id": nxt["id"] if nxt else None,
                             "review": rev})

# ---- topics / review / flashcards / activity ----
async def review_due(req):
    with db.conn() as c:
        due = sv.due_reviews(c)
    return JSONResponse({"count": len(due), "due": due})

async def review_grade(req):
    """Flashcard grading: correct (bool) or confidence in {hard, medium, easy}."""
    d = await body(req)
    conf = d.get("confidence")
    if conf is not None:
        if conf not in ("hard", "medium", "easy"): return err("confidence must be hard, medium or easy")
        quality = {"hard": 2, "medium": 4, "easy": 5}[conf]
        correct = quality >= 3
    else:
        if not isinstance(d.get("correct"), bool): return err("correct must be true or false")
        correct = d["correct"]
        quality = None
    with db.conn() as c:
        t = db.one(c, "SELECT id FROM topics WHERE id=?", (req.path_params["id"],))
        if not t: return err("not found", 404)
        rev = sv.sm2_update(c, t["id"], correct, quality=quality)
    return JSONResponse({"ok": True, "review": rev})

async def flashcards_build(req):
    d = await body(req)
    try: sid = int(d.get("subject_id"))
    except (TypeError, ValueError): return err("subject_id required")
    try: count = max(1, min(int(d.get("count", 8)), 20))
    except (TypeError, ValueError): return err("count must be an integer")
    doc_ids = d.get("document_ids")
    with db.conn() as c:
        n = sv.generate_standalone_cards(c, sid, count, doc_ids)
    if not n: return err("No usable text in this subject's indexed materials. Upload notes first.", 422)
    return JSONResponse({"built": n}, status_code=201)

async def flashcards(req):
    try: limit = max(1, min(int(req.query_params.get("limit", 20)), 50))
    except ValueError: return err("limit must be an integer")
    doc_id = None
    if (req.query_params.get("document_id") or "").strip():
        try: doc_id = int(req.query_params["document_id"])
        except ValueError: return err("document_id must be an integer")
    due_only = (req.query_params.get("due_only", "1") or "1").strip().lower() not in ("0", "false", "no", "all")
    with db.conn() as c:
        out = sv.flashcards(c, limit, doc_id, due_only)
    if out is None: return err("document not found", 404)
    return JSONResponse(out)

async def activity(req):
    """Real activity: recent assistant answers plus what the app has stored (no fabricated tool log)."""
    with db.conn() as c:
        msgs = db.rows(c, "SELECT id,role,content,citations,created_at FROM messages ORDER BY id DESC LIMIT 12")
        for m in msgs: m["citations"] = db.jloads(m["citations"], [])
        prof = db.one(c, "SELECT name,program,term FROM profile WHERE id=1")
        exams = db.rows(c, "SELECT e.title,e.date,s.name subject FROM exams e JOIN subjects s ON s.id=e.subject_id ORDER BY date")
        weak = sorted(sv.topic_stats(c), key=lambda s: s["proficiency"])[:3]
        for w in weak: w["band"] = sv.band(w["proficiency"])
        due = sv.due_reviews(c)
        return JSONResponse({
            "assistant": llm.status(),
            "recent": list(reversed(msgs)),
            "counts": {"messages": db.one(c, "SELECT COUNT(*) n FROM messages")["n"],
                       "documents": db.one(c, "SELECT COUNT(*) n FROM documents")["n"],
                       "quizzes": db.one(c, "SELECT COUNT(*) n FROM quizzes")["n"],
                       "answers": db.one(c, "SELECT COUNT(*) n FROM answers")["n"],
                       "topics": db.one(c, "SELECT COUNT(*) n FROM topics")["n"]},
            "memory": {"profile": prof, "exams": exams, "weakest": weak,
                       "reviews": {"due": len(due), "mastered": db.one(c, "SELECT COUNT(*) n FROM reviews WHERE interval_days>=7")["n"]}},
        })

# ---- auth ----
def seed_display_name(c, username):
    """Fill an empty profile name from the account name, so a signed-in user
    always sees their own name (it stays editable in the profile dialog)."""
    p = db.one(c, "SELECT name FROM profile WHERE id=1")
    if p and (p["name"] or "").strip():
        return
    words = [w for w in re.split(r"[._\-]+", (username or "").strip()) if w]
    display = " ".join(w[:1].upper() + w[1:].lower() for w in words)
    if display:
        c.execute("UPDATE profile SET name=? WHERE id=1", (display,))

def set_session_cookie(resp, token, exp):
    resp.set_cookie(auth.COOKIE, token, max_age=auth.SESSION_DAYS * 86400, httponly=True, samesite="lax", path="/")

async def auth_status(req):
    with db.conn() as c:
        return JSONResponse({"login_required": auth.user_count(c) > 0,
                             "user": auth.session_user(c, req.cookies.get(auth.COOKIE))})

async def auth_register(req):
    d = await body(req)
    with db.conn() as c:
        if auth.user_count(c) > 0: return err("An account already exists. Please sign in instead.", 409)
        try:
            u = auth.create_user(c, d.get("username"), d.get("password") or "")
        except LookupError as e:
            return err(str(e), 409)
        except ValueError as e:
            return err(str(e))
        seed_display_name(c, u["username"])
        token, exp = auth.create_session(c, u["id"])
    resp = JSONResponse({"ok": True, "user": u}, status_code=201)
    set_session_cookie(resp, token, exp)
    return resp

async def auth_login(req):
    d = await body(req)
    with db.conn() as c:
        u = auth.get_user(c, d.get("username") or "")
        if not u or not auth.verify(d.get("password") or "", u["salt"], u["pass_hash"]):
            return err("Wrong username or password.", 401)
        seed_display_name(c, u["username"])
        token, exp = auth.create_session(c, u["id"])
    resp = JSONResponse({"ok": True, "user": {"id": u["id"], "username": u["username"]}})
    set_session_cookie(resp, token, exp)
    return resp

async def auth_logout(req):
    with db.conn() as c:
        auth.drop_session(c, req.cookies.get(auth.COOKIE))
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(auth.COOKIE, path="/")
    return resp

class AuthGate(BaseHTTPMiddleware):
    """Once an account exists, pages and API require a session; first run stays open for setup."""
    async def dispatch(self, request, call_next):
        path = request.url.path
        if path == "/login" or path.startswith("/api/auth"):
            return await call_next(request)
        with db.conn() as c:
            needed = auth.user_count(c) > 0
            user = auth.session_user(c, request.cookies.get(auth.COOKIE))
        if needed and not user:
            if path.startswith("/api"): return JSONResponse({"error": "Please sign in."}, status_code=401)
            return RedirectResponse("/login", status_code=303)
        request.state.user = user
        return await call_next(request)

async def topic_update(req):
    """Set the topic group (heatmap column). Blank or null clears it, so the topic name is used."""
    d = await body(req)
    if "area" not in d: return err("area required")
    area = (d.get("area") or "").strip() or None
    if area and len(area) > 40: return err("area must be 40 characters or fewer")
    with db.conn() as c:
        if not db.one(c, "SELECT 1 FROM topics WHERE id=?", (req.path_params["id"],)): return err("not found", 404)
        c.execute("UPDATE topics SET area=? WHERE id=?", (area, req.path_params["id"]))
    return JSONResponse({"id": req.path_params["id"], "area": area})

# ---- weak topics / analytics ----
async def weak_topics(req):
    with db.conn() as c:
        st = sv.topic_stats(c, req.query_params.get("subject_id"))
    ranked = sorted(st, key=lambda s: s["proficiency"])
    for r in ranked: r["band"] = sv.band(r["proficiency"])
    areas = sorted({s["area"] or s["topic"] for s in st})
    subjects_ = sorted({s["subject"] for s in st})
    cells = {}
    for s in st: cells.setdefault(s["subject"], {}).setdefault(s["area"] or s["topic"], []).append(s["proficiency"])
    heat = [{"subject": sub, "cells": {a: (round(sum(v) / len(v)) if (v := cells.get(sub, {}).get(a)) else None) for a in areas}} for sub in subjects_]
    return JSONResponse({"heatmap": {"columns": areas, "rows": heat}, "ranked": ranked})

async def analytics(req):
    with db.conn() as c:
        days = sv.minutes_by_day(c, 30)
        qz = db.rows(c, "SELECT z.id, MIN(a.answered_at) at, AVG(a.correct)*100 score, COUNT(a.id) n FROM quizzes z JOIN questions q ON q.quiz_id=z.id JOIN answers a ON a.question_id=q.id GROUP BY z.id ORDER BY z.id")
        subj = {}
        for s in sv.topic_stats(c): subj.setdefault(s["subject"], []).append(s)
        return JSONResponse({
            "study_hours_30d": round(sum(m for _, m in days) / 60, 1),
            "active_days_30d": sum(1 for _, m in days if m > 0), "window_days": 30,
            "current_streak": sv.streak(c),
            "quiz_trend": [{"quiz_id": z["id"], "date": (z["at"] or "")[:10], "score": round(z["score"])} for z in qz],
            "subject_comparison": [{"subject": k, "proficiency": round(sum(x["proficiency"] * x["answers"] for x in v) / sum(x["answers"] for x in v))} for k, v in sorted(subj.items())],
            "daily_minutes": [{"date": d.isoformat(), "minutes": m} for d, m in days],
        })

routes = [
    Route("/", index),
    Route("/login", login_page),
    Route("/api/auth/status", auth_status),
    Route("/api/auth/register", auth_register, methods=["POST"]),
    Route("/api/auth/login", auth_login, methods=["POST"]),
    Route("/api/auth/logout", auth_logout, methods=["POST"]),
    Route("/api/profile", profile, methods=["GET", "PUT"]),
    Route("/api/subjects", subjects, methods=["GET", "POST"]),
    Route("/api/exams", exams, methods=["GET", "POST"]),
    Route("/api/dashboard", dashboard),
    Route("/api/materials", materials, methods=["GET", "POST"]),
    Route("/api/materials/{id:int}", material_delete, methods=["DELETE"]),
    Route("/api/assistant/status", assistant_status),
    Route("/api/assistant/chat", assistant_chat, methods=["POST"]),
    Route("/api/assistant/history", assistant_history, methods=["GET", "DELETE"]),
    Route("/api/planner/calendar", calendar_view),
    Route("/api/planner/propose", planner_propose, methods=["POST"]),
    Route("/api/planner/proposals/{id:int}", proposal_get, methods=["GET"]),
    Route("/api/planner/proposals/{id:int}/confirm", proposal_confirm, methods=["POST"]),
    Route("/api/planner/proposals/{id:int}", proposal_discard, methods=["DELETE"]),
    Route("/api/sessions/{id:int}", session_patch, methods=["PATCH"]),
    Route("/api/sessions/{id:int}", session_delete, methods=["DELETE"]),
    Route("/api/study-log", study_log_add, methods=["POST"]),
    Route("/api/quizzes", quizzes_list, methods=["GET"]),
    Route("/api/quizzes", quiz_create, methods=["POST"]),
    Route("/api/quizzes/{id:int}", quiz_get),
    Route("/api/quizzes/{id:int}/questions/{qid:int}/answer", quiz_answer, methods=["POST"]),
    Route("/api/quizzes/{id:int}/extend", quiz_extend, methods=["POST"]),
    Route("/api/topics/{id:int}", topic_update, methods=["PUT"]),
    Route("/api/review/due", review_due),
    Route("/api/review/{id:int}", review_grade, methods=["POST"]),
    Route("/api/flashcards", flashcards),
    Route("/api/flashcards/build", flashcards_build, methods=["POST"]),
    Route("/api/activity", activity),
    Route("/api/weak-topics", weak_topics),
    Route("/api/analytics", analytics),
]

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(_app):
    db.init()
    yield

app = Starlette(routes=routes, lifespan=lifespan,
                middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]),
                            Middleware(AuthGate)])
