"""Optional: load the sample data shown in Examly_UI_preview.html. Usage: python seed.py"""
import datetime as dt, json, os
from app import db, services as sv
db.init()
t = db.today()
with db.conn() as c:
    c.execute("UPDATE profile SET name='Ayesha Khan', program='BS Artificial Intelligence', term='Fall 2026' WHERE id=1")
    for n in ("Database Systems", "Operating Systems", "Networks"): c.execute("INSERT OR IGNORE INTO subjects(name) VALUES(?)", (n,))
    sid = {r["name"]: r["id"] for r in db.rows(c, "SELECT * FROM subjects")}
    c.execute("INSERT INTO exams(subject_id,title,date) VALUES(?,?,?)", (sid["Database Systems"], "Midterm", (t + dt.timedelta(days=12)).isoformat()))
    for sub, topic, area, ok, n in [("Database Systems", "Transactions", "Locks", 56, 10), ("Operating Systems", "Deadlock handling", "Joins", 38, 8), ("Networks", "Subnetting", "Basics", 64, 10)]:
        c.execute("INSERT OR IGNORE INTO topics(subject_id,name,area) VALUES(?,?,?)", (sid[sub], topic, area))
        tid = db.one(c, "SELECT id FROM topics WHERE subject_id=? AND name=?", (sid[sub], topic))["id"]
        c.execute("INSERT INTO quizzes(subject_id,created_at) VALUES(?,?)", (sid[sub], db.now_iso())); qz = c.execute("SELECT last_insert_rowid()").fetchone()[0]
        right = round(n * ok / 100)
        for i in range(n):
            c.execute("INSERT INTO questions(quiz_id,position,prompt,options,correct_index,topic_id) VALUES(?,?,?,?,?,?)", (qz, i + 1, "sample", json.dumps(["a", "b", "c"]), 0, tid))
            qi = c.execute("SELECT last_insert_rowid()").fetchone()[0]
            c.execute("INSERT INTO answers(question_id,chosen,correct,answered_at) VALUES(?,?,?,?)", (qi, 0, int(i < right), db.now_iso()))
    for off, m in enumerate([55, 70, 30, 0, 80, 60, 90]):
        if m: c.execute("INSERT INTO study_log(day,minutes) VALUES(?,?)", ((t - dt.timedelta(days=6 - off)).isoformat(), m))
    for d, sub, topic, st in [(0, "Database Systems", "Normalization", "done"), (0, "Operating Systems", "Deadlock handling", "planned")]:
        c.execute("INSERT INTO sessions(subject_id,topic,scheduled_at,duration_min,status) VALUES(?,?,?,?,?)", (sid[sub], topic, f"{t.isoformat()}T{'18:00' if d == 0 and st == 'done' else '19:45'}", 45, st))
print("seeded")
