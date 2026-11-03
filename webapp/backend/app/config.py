"""Configuration for Examly.

Single source of truth for provider settings. Nothing sensitive lives in code:
- API keys are read from key *files* (or environment variables) at call time,
  so pasting a new key into the file takes effect without a restart.
- Base URLs, model names, provider order, timeouts and upload limits come from
  environment variables, optionally seeded by a `.env` file.

Precedence (highest first):
  1. process environment variables
  2. the env file (`EXAMLY_ENV_FILE`, default `backend/.env`)
  3. built-in non-secret defaults (URLs / model names only, never keys)
"""
import hashlib
import os
import re
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent      # webapp/backend
DEFAULT_ENV_FILE = BACKEND_DIR / ".env"

_PLACEHOLDER = re.compile(r"^(paste|replace|your|example|<)", re.I)

_file_cache = {}   # path -> (mtime, parsed dict)


def _parse_env_file(path):
    """Parse KEY=VALUE lines; `#` comments and blank lines are ignored."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return {}
    out = {}
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        k, v = k.strip(), v.strip().strip('"').strip("'")
        if " #" in v:                       # inline comment: KEY=value  # note
            v = v.split(" #", 1)[0].rstrip()
        if k:
            out[k] = v
    return out


def _file_settings():
    """Env-file contents, re-read only when the file changes (cheap mtime check)."""
    path = os.environ.get("EXAMLY_ENV_FILE") or str(DEFAULT_ENV_FILE)
    try:
        mtime = os.stat(path).st_mtime
    except OSError:
        return {}
    hit = _file_cache.get(path)
    if hit and hit[0] == mtime:
        return hit[1]
    data = _parse_env_file(path)
    _file_cache[path] = (mtime, data)
    return data


def settings(name, default=""):
    """One setting: live environment wins, then the env file, then default."""
    v = os.environ.get(name)
    if v is not None:
        return v
    return _file_settings().get(name, default)


def read_key(path):
    """Read an API key from a text file.

    Handles `#` comments, `KEY=value` lines, quotes and placeholder lines, so
    key files can be self-documenting (see `.env.example`).
    """
    if not path:
        return ""
    p = Path(os.path.expandvars(os.path.expanduser(str(path))))
    try:
        text = p.read_text(encoding="utf-8-sig", errors="ignore")
    except OSError:
        return ""
    for line in text.splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue
        if re.match(r"^[A-Za-z0-9_]+\s*=", s):        # KEY=value form
            s = s.split("=", 1)[1].strip().strip('"').strip("'")
        if s and not _PLACEHOLDER.match(s):
            return s
    return ""


def _key_from_env_or_file(env_names, file_setting):
    for var in env_names:
        v = (os.environ.get(var) or "").strip()
        if v:
            return v
    return read_key(settings(file_setting))


def grok_key():
    return _key_from_env_or_file(("GROK_API_KEY", "XAI_API_KEY"), "GROK_KEY_FILE")


def omni_key():
    return _key_from_env_or_file(("OMNI_API_KEY", "OMNIRoute_API_KEY", "OMNIROUTE_API_KEY"), "OMNI_KEY_FILE")


def gemini_key():
    return _key_from_env_or_file(("GEMINI_API_KEY", "GOOGLE_API_KEY"), "GEMINI_KEY_FILE")


def provider_config(name):
    """Resolved {base, model, key} for a provider, or None when unusable."""
    if name == "grok":
        key = grok_key()
        base = settings("GROK_BASE_URL", "https://api.x.ai/v1")
        model = settings("GROK_MODEL", "grok-4-fast")
    elif name == "gemini":
        key = gemini_key()
        base = settings("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta")
        model = settings("GEMINI_MODEL", "gemini-3.5-flash")
    elif name == "omni":                            # OmniRoute (OpenAI-compatible local gateway)
        key = omni_key()
        base = settings("OMNI_BASE_URL", "http://localhost:20128/v1")
        model = settings("OMNI_MODEL", "free-fast")
    elif name == "custom":                           # legacy OpenAI-compatible env config
        key, base = (settings("EXAMLY_LLM_KEY"), settings("EXAMLY_LLM_URL"))
        model = settings("EXAMLY_LLM_MODEL", "gpt-4o-mini")
    else:
        return None
    key, base, model = key.strip(), base.strip(), model.strip()
    if not (key and base and model):
        return None
    return {"base": base, "model": model, "key": key}


def provider_order():
    """Provider chain, e.g. ['grok', 'gemini']. Legacy EXAMLY_LLM_* goes first."""
    names = [n.strip().lower() for n in settings("LLM_PROVIDER_ORDER", "grok,gemini").split(",") if n.strip()]
    if settings("EXAMLY_LLM_URL") and settings("EXAMLY_LLM_KEY"):
        names.insert(0, "custom")
    return names


def configured_providers():
    """Providers that are enabled and actually have a key."""
    if disabled():
        return []
    return [n for n in provider_order() if provider_config(n)]


def disabled():
    return (settings("EXAMLY_DISABLE_LLM", "0") or "0").strip().lower() in ("1", "true", "yes", "on")


def timeout_seconds():
    try:
        v = float(settings("LLM_TIMEOUT_S", "30"))
    except ValueError:
        v = 30.0
    return max(5.0, min(v, 120.0))


def total_seconds():
    """Hard budget for the whole provider chain (chat must never hang)."""
    try:
        v = float(settings("LLM_TOTAL_S", "45"))
    except ValueError:
        v = 45.0
    return max(10.0, min(v, 300.0))


def max_upload_bytes():
    try:
        mb = int(settings("MAX_UPLOAD_MB", "25"))
    except ValueError:
        mb = 25
    return max(1, min(mb, 1024)) * 1024 * 1024


def fingerprint(key):
    """Stable short id for a key, used to remember auth failures (never the key)."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]
