"""Business logic: indexing, retrieval, assistant, quiz, planner, analytics."""
import io, os, re, json, random, math, collections, datetime as dt
from . import db

STOP = set("the a an and or of to in on for with is are was were be been it its as at by from that this these those which who whom not no but if then so than into onto over under can may must should will would only each every other such their there they them we you your our he she his her also more most any all one two".split())
LEVEL_HINT = {"Basic": "Keep it very simple.", "Standard": "", "Advanced": "Go deep and be precise."}

def tok(s):
    return [w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP and len(w) > 1]

# ---------- materials ----------
def extract_pages(filename, data):
    ext = os.path.splitext(filename.lower())[1]
    if ext == ".pdf":
        from pypdf import PdfReader
        r = PdfReader(io.BytesIO(data))
        return [(p.extract_text() or "") for p in r.pages]
    text = data.decode("utf-8", errors="ignore")
    if not text.strip(): return []
    size, pages, cur = 2500, [], ""
    for para in text.split("\n\n"):
        if len(cur) + len(para) > size and cur:
            pages.append(cur); cur = ""
        cur += para + "\n\n"
    if cur.strip(): pages.append(cur)
    return pages

def index_document(doc_id, filename, data):
    """Runs in background; flips status indexing -> indexed (or failed)."""
    try:
        pages = extract_pages(filename, data)
        with db.conn() as c:
            for i, t in enumerate(pages, 1):
                for ch in split_chunks(t):
                    c.execute("INSERT INTO chunks(document_id,page,text) VALUES(?,?,?)", (doc_id, i, ch))
            c.execute("UPDATE documents SET pages=?, status=? WHERE id=?", (len(pages), "indexed" if pages else "failed", doc_id))
    except Exception:
        with db.conn() as c:
            c.execute("UPDATE documents SET status='failed' WHERE id=?", (doc_id,))

def split_chunks(text, target=600):
    text = re.sub(r"\s+", " ", text).strip()
    if not text: return []
    sents = re.split(r"(?<=[.!?])\s+", text)
    out, cur = [], ""
    for s in sents:
        if len(cur) + len(s) > target and cur:
            out.append(cur); cur = ""
        cur += (" " if cur else "") + s
    if cur: out.append(cur)
    return out

# ---------- retrieval ----------
def retrieve(c, query, subject_id=None, document_ids=None, k=4):
    q = set(tok(query))
    if not q: return []
    sql = "SELECT ch.id, ch.text, ch.page, d.id doc_id, d.filename FROM chunks ch JOIN documents d ON d.id=ch.document_id WHERE d.status='indexed'"
    args = []
    if subject_id: sql += " AND d.subject_id=?"; args.append(subject_id)
    if document_ids: sql += " AND d.id IN (%s)" % ",".join("?" * len(document_ids)); args += document_ids
    cands = db.rows(c, sql, args)
    n = max(len(cands), 1)
    df = collections.Counter(w for r in cands for w in set(tok(r["text"])))
    scored = []
    for r in cands:
        words = collections.Counter(tok(r["text"]))
        s = sum((1 + math.log(words[w])) * math.log(1 + n / df[w]) for w in q if words[w])
        if s > 0: scored.append((s / math.sqrt(len(r["text"]) / 200 + 1), r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:k]]

def best_sentence(text, q):
    sents = re.split(r"(?<=[.!?])\s+", text)
    return max(sents, key=lambda s: len(q & set(tok(s))))

# ---------- assistant ----------
def llm_configured():
    return bool(os.environ.get("EXAMLY_LLM_URL") and os.environ.get("EXAMLY_LLM_KEY"))

def call_llm(system, user):
    import requests
    r = requests.post(os.environ["EXAMLY_LLM_URL"].rstrip("/") + "/chat/completions",
        headers={"Authorization": "Bearer " + os.environ["EXAMLY_LLM_KEY"]},
        json={"model": os.environ.get("EXAMLY_LLM_MODEL", "gpt-4o-mini"),
              "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}, timeout=60)
    r.raise_for_status()
    return r.json()["choices"][0]["message"]["content"]

def answer(c, message, subject_id=None, level="Standard", document_ids=None):
    hits = retrieve(c, message, subject_id, document_ids)
    if not hits:
        return {"answer": "I could not find this in your uploaded materials, so I will not guess. Try uploading notes that cover it or widen the documents in scope.",
                "citations": [], "grounded": False, "mode": "none"}
    cites = [{"n": i + 1, "document_id": h["doc_id"], "filename": h["filename"], "page": h["page"], "quote": h["text"][:300]} for i, h in enumerate(hits)]
    ctx = "\n".join(f"[{x['n']}] ({x['filename']}, p.{x['page']}) {h['text']}" for x, h in zip(cites, hits))
    if llm_configured():
        try:
            sys_p = ("You are a study assistant. Answer ONLY from the numbered excerpts. Cite like [1]. "
                     "If the excerpts do not contain the answer, say so. " + LEVEL_HINT.get(level, ""))
            return {"answer": call_llm(sys_p, f"Excerpts:\n{ctx}\n\nQuestion: {message}"), "citations": cites, "grounded": True, "mode": "llm"}
        except Exception:
            pass
    q = set(tok(message))
    body = " ".join(f"{best_sentence(h['text'], q)} [{i + 1}]" for i, h in enumerate(hits[:2]))
    return {"answer": body, "citations": cites, "grounded": True, "mode": "extractive"}

# ---------- quiz ----------
def make_cloze(text, pool):
    sents = [s for s in re.split(r"(?<=[.!?])\s+", text) if 8 <= len(s.split()) <= 40]
    random.shuffle(sents)
    for s in sents:
        cands = [w for w in re.findall(r"[A-Za-z]{6,}", s) if w.lower() not in STOP]
        if not cands: continue
        target = max(cands, key=len)
        distract = [w for w in pool if w.lower() != target.lower() and abs(len(w) - len(target)) <= 4]
        distract = list(dict.fromkeys(w.lower() for w in distract))
        if len(distract) < 2: continue
        opts = random.sample(distract, 2) + [target.lower()]
        random.shuffle(opts)
        prompt = "Complete the statement from your notes:\n\n" + re.sub(r"\b%s\b" % re.escape(target), "_____", s, count=1)
        return prompt, opts, opts.index(target.lower()), s
    return None

def generate_quiz(c, subject_id, count=5, topic=None, document_ids=None):
    sql = "SELECT ch.text, ch.page, d.filename FROM chunks ch JOIN documents d ON d.id=ch.document_id WHERE d.status='indexed' AND d.subject_id=?"
    args = [subject_id]
    if document_ids: sql += " AND d.id IN (%s)" % ",".join("?" * len(document_ids)); args += document_ids
    chunks = db.rows(c, sql, args)
    if not chunks: return None
    pool = list({w for ch in chunks for w in re.findall(r"[A-Za-z]{6,}", ch["text"]) if w.lower() not in STOP})
    random.shuffle(chunks)
    qid_list, made = [], []
    c.execute("INSERT INTO quizzes(subject_id,created_at) VALUES(?,?)", (subject_id, db.now_iso()))
    quiz_id = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    for ch in chunks * 3:
        if len(made) >= count: break
        m = make_cloze(ch["text"], pool)
        if not m or any(m[3] == x for x in made): continue
        prompt, opts, ci, sent = m
        tname = topic or os.path.splitext(ch["filename"])[0].replace("_", " ")
        c.execute("INSERT OR IGNORE INTO topics(subject_id,name) VALUES(?,?)", (subject_id, tname))
        tid = db.one(c, "SELECT id FROM topics WHERE subject_id=? AND name=?", (subject_id, tname))["id"]
        c.execute("INSERT INTO questions(quiz_id,position,prompt,options,correct_index,explanation,source_file,source_page,topic_id) VALUES(?,?,?,?,?,?,?,?,?)",
                  (quiz_id, len(made) + 1, prompt, json.dumps(opts), ci, sent, ch["filename"], ch["page"], tid))
        made.append(sent)
    if not made:
        c.execute("DELETE FROM quizzes WHERE id=?", (quiz_id,)); return None
    return quiz_id

def public_question(q, reveal=False):
    out = {"id": q["id"], "position": q["position"], "prompt": q["prompt"], "options": db.jloads(q["options"], [])}
    if reveal:
        out.update(correct_index=q["correct_index"], explanation=q["explanation"], source={"file": q["source_file"], "page": q["source_page"]})
    return out

def quiz_view(c, quiz_id):
    qz = db.one(c, "SELECT * FROM quizzes WHERE id=?", (quiz_id,))
    if not qz: return None
    qs = db.rows(c, "SELECT q.*, a.chosen, a.correct FROM questions q LEFT JOIN answers a ON a.question_id=q.id WHERE quiz_id=? ORDER BY position", (quiz_id,))
    items = []
    for q in qs:
        it = public_question(q, reveal=q["chosen"] is not None)
        it["answered"] = q["chosen"] is not None
        if it["answered"]: it.update(chosen=q["chosen"], correct=bool(q["correct"]))
        items.append(it)
    done = sum(1 for i in items if i["answered"])
    return {"id": quiz_id, "subject_id": qz["subject_id"], "total": len(items), "answered": done,
            "correct": sum(1 for i in items if i.get("correct")), "questions": items}

# ---------- proficiency ----------
def topic_stats(c, subject_id=None):
    sql = """SELECT t.id topic_id, t.name topic, t.area, s.id subject_id, s.name subject FROM topics t JOIN subjects s ON s.id=t.subject_id"""
    args = []
    if subject_id: sql += " WHERE s.id=?"; args.append(subject_id)
    out = []
    for t in db.rows(c, sql, args):
        ans = db.rows(c, "SELECT a.correct FROM answers a JOIN questions q ON q.id=a.question_id WHERE q.topic_id=? ORDER BY a.answered_at DESC, a.id DESC", (t["topic_id"],))
        if not ans: continue
        n, ok = len(ans), sum(a["correct"] for a in ans)
        last = ans[:5]
        out.append({**t, "answers": n, "proficiency": round(100 * ok / n), "last_correct": sum(a["correct"] for a in last), "last_total": len(last)})
    return out

def band(p):
    return "bad" if p < 50 else "warn" if p < 70 else "ok"

# ---------- study log / streak ----------
def minutes_by_day(c, days):
    start = (db.today() - dt.timedelta(days=days - 1)).isoformat()
    m = {r["day"]: r["m"] for r in db.rows(c, "SELECT day, SUM(minutes) m FROM study_log WHERE day>=? GROUP BY day", (start,))}
    return [((db.today() - dt.timedelta(days=days - 1 - i)), m.get((db.today() - dt.timedelta(days=days - 1 - i)).isoformat(), 0)) for i in range(days)]

def streak(c):
    active = {r["day"] for r in db.rows(c, "SELECT DISTINCT day FROM study_log WHERE minutes>0")}
    d, n = db.today(), 0
    if d.isoformat() not in active: d -= dt.timedelta(days=1)  # today not yet studied does not break it
    while d.isoformat() in active:
        n += 1; d -= dt.timedelta(days=1)
    return n

# ---------- planner ----------
def propose(c, subject_ids=None, days=7, start_time="18:00", duration=45, per_day=1, start_date=None):
    stats = topic_stats(c)
    if subject_ids: stats = [s for s in stats if s["subject_id"] in subject_ids]
    subj = db.rows(c, "SELECT id,name FROM subjects" + (" WHERE id IN (%s)" % ",".join("?" * len(subject_ids)) if subject_ids else ""), subject_ids or [])
    exams = {e["subject_id"]: e["date"] for e in db.rows(c, "SELECT subject_id, MIN(date) date FROM exams WHERE date>=? GROUP BY subject_id", (db.today().isoformat(),))}
    queue = sorted(stats, key=lambda s: s["proficiency"])
    seen = {s["subject_id"] for s in stats}
    for s in subj:  # subjects with no quiz history still get a general review slot
        if s["id"] not in seen: queue.append({"subject_id": s["id"], "subject": s["name"], "topic": "General review", "proficiency": 50})
    queue.sort(key=lambda s: (exams.get(s["subject_id"], "9999"), s["proficiency"]))
    if not queue: return None
    first = dt.date.fromisoformat(start_date) if start_date else db.today() + dt.timedelta(days=1)
    hh, mm = map(int, start_time.split(":"))
    items, i = [], 0
    for d in range(days):
        for k in range(per_day):
            t = queue[i % len(queue)]; i += 1
            at = dt.datetime.combine(first + dt.timedelta(days=d), dt.time(hh, mm)) + dt.timedelta(minutes=k * (duration + 15))
            items.append((t["subject_id"], t["topic"], at.isoformat(timespec="minutes"), duration))
    c.execute("INSERT INTO proposals(created_at) VALUES(?)", (db.now_iso(),))
    pid = c.execute("SELECT last_insert_rowid()").fetchone()[0]
    c.executemany("INSERT INTO proposal_items(proposal_id,subject_id,topic,scheduled_at,duration_min) VALUES(?,?,?,?,?)", [(pid, *x) for x in items])
    return pid

def proposal_view(c, pid):
    p = db.one(c, "SELECT * FROM proposals WHERE id=?", (pid,))
    if not p: return None
    items = db.rows(c, "SELECT i.id, i.subject_id, s.name subject, i.topic, i.scheduled_at, i.duration_min FROM proposal_items i JOIN subjects s ON s.id=i.subject_id WHERE proposal_id=? ORDER BY scheduled_at", (pid,))
    return {"id": pid, "saved": False, "note": "Nothing is saved until you confirm", "items": items}
