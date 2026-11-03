"""SQLite layer. One connection per call; schema created on import of init()."""
import os, sqlite3, json, datetime as dt

DB_PATH = os.environ.get("EXAMLY_DB", os.path.join(os.path.dirname(__file__), "..", "examly.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS profile(id INTEGER PRIMARY KEY CHECK(id=1), name TEXT, program TEXT, term TEXT);
CREATE TABLE IF NOT EXISTS subjects(id INTEGER PRIMARY KEY, name TEXT UNIQUE NOT NULL);
CREATE TABLE IF NOT EXISTS documents(id INTEGER PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  filename TEXT NOT NULL, pages INTEGER DEFAULT 0, status TEXT DEFAULT 'indexing', added_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS chunks(id INTEGER PRIMARY KEY, document_id INTEGER REFERENCES documents(id) ON DELETE CASCADE,
  page INTEGER NOT NULL, text TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS exams(id INTEGER PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  title TEXT NOT NULL, date TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS topics(id INTEGER PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  name TEXT NOT NULL, area TEXT, UNIQUE(subject_id, name));
CREATE TABLE IF NOT EXISTS sessions(id INTEGER PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE,
  topic TEXT NOT NULL, scheduled_at TEXT NOT NULL, duration_min INTEGER NOT NULL DEFAULT 45,
  status TEXT NOT NULL DEFAULT 'planned', completed_at TEXT);
CREATE TABLE IF NOT EXISTS proposals(id INTEGER PRIMARY KEY, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS proposal_items(id INTEGER PRIMARY KEY, proposal_id INTEGER REFERENCES proposals(id) ON DELETE CASCADE,
  subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, topic TEXT NOT NULL, scheduled_at TEXT NOT NULL, duration_min INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS study_log(id INTEGER PRIMARY KEY, day TEXT NOT NULL, minutes INTEGER NOT NULL, subject_id INTEGER, session_id INTEGER);
CREATE TABLE IF NOT EXISTS quizzes(id INTEGER PRIMARY KEY, subject_id INTEGER REFERENCES subjects(id) ON DELETE CASCADE, created_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS questions(id INTEGER PRIMARY KEY, quiz_id INTEGER REFERENCES quizzes(id) ON DELETE CASCADE, position INTEGER NOT NULL,
  prompt TEXT NOT NULL, options TEXT NOT NULL, correct_index INTEGER NOT NULL, explanation TEXT,
  source_file TEXT, source_page INTEGER, topic_id INTEGER REFERENCES topics(id));
CREATE TABLE IF NOT EXISTS answers(id INTEGER PRIMARY KEY, question_id INTEGER UNIQUE REFERENCES questions(id) ON DELETE CASCADE,
  chosen INTEGER NOT NULL, correct INTEGER NOT NULL, answered_at TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS messages(id INTEGER PRIMARY KEY, role TEXT NOT NULL, subject_id INTEGER, content TEXT NOT NULL,
  citations TEXT DEFAULT '[]', created_at TEXT NOT NULL);
"""

def today():
    return dt.date.fromisoformat(os.environ["EXAMLY_TODAY"]) if os.environ.get("EXAMLY_TODAY") else dt.date.today()

def now_iso():
    return dt.datetime.combine(today(), dt.datetime.now().time()).isoformat(timespec="seconds")

def conn():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA foreign_keys=ON")
    return c

def init():
    with conn() as c:
        c.executescript(SCHEMA)
        c.execute("INSERT OR IGNORE INTO profile(id,name,program,term) VALUES(1,'','','')")

def rows(c, sql, args=()):
    return [dict(r) for r in c.execute(sql, args).fetchall()]

def one(c, sql, args=()):
    r = c.execute(sql, args).fetchone()
    return dict(r) if r else None

def jloads(s, default=None):
    try: return json.loads(s)
    except Exception: return default
