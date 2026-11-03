"""Single-account login: PBKDF2 password hashes and opaque server-side session cookies.

Examly stores one workspace, so registration is only allowed until the first account exists.
"""
import datetime as dt, hashlib, hmac, secrets
from . import db

COOKIE = "examly_session"
SESSION_DAYS = 30
MIN_PASSWORD = 6


def _hash(password, salt_hex):
    return hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt_hex), 120_000).hex()


def hash_password(password):
    salt = secrets.token_hex(16)
    return _hash(password, salt), salt


def verify(password, salt, expected):
    return hmac.compare_digest(_hash(password, salt), expected)


def user_count(c):
    return db.one(c, "SELECT COUNT(*) n FROM users")["n"]


def get_user(c, username):
    return db.one(c, "SELECT * FROM users WHERE username=?", ((username or "").strip().lower(),))


def create_user(c, username, password):
    username = (username or "").strip().lower()
    if not 3 <= len(username) <= 32:
        raise ValueError("username must be 3 to 32 characters")
    if not all(ch.isalnum() or ch in "._-" for ch in username):
        raise ValueError("username may only use letters, numbers, dot, underscore or dash")
    if len(password or "") < MIN_PASSWORD:
        raise ValueError(f"password must be at least {MIN_PASSWORD} characters")
    if get_user(c, username):
        raise LookupError("that username is already taken")
    h, salt = hash_password(password)
    c.execute("INSERT INTO users(username,pass_hash,salt,created_at) VALUES(?,?,?,?)", (username, h, salt, db.now_iso()))
    return {"id": c.execute("SELECT last_insert_rowid()").fetchone()[0], "username": username}


def create_session(c, user_id):
    token = secrets.token_urlsafe(32)
    now = dt.datetime.now(dt.timezone.utc)
    exp = now + dt.timedelta(days=SESSION_DAYS)
    c.execute("INSERT INTO auth_sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)",
              (token, user_id, now.isoformat(timespec="seconds"), exp.isoformat(timespec="seconds")))
    return token, exp


def session_user(c, token):
    if not token:
        return None
    row = db.one(c, "SELECT s.expires_at,u.id,u.username FROM auth_sessions s JOIN users u ON u.id=s.user_id WHERE s.token=?", (token,))
    if not row:
        return None
    if dt.datetime.fromisoformat(row["expires_at"]) <= dt.datetime.now(dt.timezone.utc):
        c.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        return None
    return {"id": row["id"], "username": row["username"]}


def drop_session(c, token):
    if token:
        c.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
