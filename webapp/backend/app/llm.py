"""Answer generation: an ordered chain of LLM providers.

The chain (default: grok -> gemini) is resolved from config on every call, so
key files and `.env` changes apply without restarting the server. Each provider
may list several models (comma-separated) which are tried in order, and the
whole chain runs inside a total time budget so a hung provider can never stall
a chat request: when the budget is spent (or no provider is configured) the
caller falls back to the extractive answerer, so the app keeps working offline.

Auth-class failures (bad/revoked key) are remembered per key fingerprint for a
few minutes, so a broken key does not add latency to every request while a
freshly pasted key is picked up immediately.
"""
import sys
import time

import requests

from . import config

_DEGRADE_SECONDS = 900          # remember an unusable key for 15 minutes
_degraded = {}                  # key fingerprint -> expiry epoch
_handlers = {}


def _log(msg):
    print(msg, file=sys.stderr, flush=True)


def _remember_bad_key(key):
    _degraded[config.fingerprint(key)] = time.time() + _DEGRADE_SECONDS


def _bad_key_now(key):
    exp = _degraded.get(config.fingerprint(key))
    return bool(exp and exp > time.time())


def _is_auth_failure(resp):
    if resp.status_code not in (400, 401, 403):
        return False
    body = (resp.text or "").lower()
    return any(s in body for s in ("api key", "unauthorized", "permission", "invalid key", "credential"))


def _models(cfg):
    return [m.strip() for m in str(cfg.get("model", "")).split(",") if m.strip()] or [""]


def _call_openai_compatible(cfg, system, user, timeout):
    """Grok (xAI) and the legacy custom provider: OpenAI-compatible chat completions."""
    models = _models(cfg)
    per = timeout / len(models) if len(models) > 1 else timeout
    last = None
    for model in models:
        try:
            r = requests.post(cfg["base"].rstrip("/") + "/chat/completions",
                              headers={"Authorization": "Bearer " + cfg["key"]},
                              json={"model": model,
                                    "messages": [{"role": "system", "content": system},
                                                 {"role": "user", "content": user}]},
                              timeout=per)
            if _is_auth_failure(r):
                _remember_bad_key(cfg["key"])     # same key for every model: stop now
                r.raise_for_status()
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
        except Exception as e:                    # noqa: BLE001 - try the next model
            last = e
            if _bad_key_now(cfg["key"]):
                raise
    raise last or RuntimeError("no model configured")


def _call_gemini(cfg, system, user, timeout):
    """Gemini: generateContent with a system instruction; model list supported."""
    models = _models(cfg)
    per = timeout / len(models) if len(models) > 1 else timeout
    body = {"system_instruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}]}
    last = None
    for model in models:
        try:
            url = cfg["base"].rstrip("/") + "/models/" + model + ":generateContent"
            r = requests.post(url, headers={"x-goog-api-key": cfg["key"], "Content-Type": "application/json"},
                              json=body, timeout=per)
            if _is_auth_failure(r):
                _remember_bad_key(cfg["key"])
                r.raise_for_status()
            r.raise_for_status()
            data = r.json()
            cands = data.get("candidates") or []
            parts = ((cands[0].get("content") or {}).get("parts") or []) if cands else []
            text = "".join(p.get("text", "") for p in parts if isinstance(p, dict)).strip()
            if not text:
                raise RuntimeError("Gemini returned no text")
            return text
        except Exception as e:                    # noqa: BLE001 - try the next model
            last = e
            if _bad_key_now(cfg["key"]):
                raise
    raise last or RuntimeError("no model configured")


_handlers["grok"] = _call_openai_compatible
_handlers["gemini"] = _call_gemini
_handlers["custom"] = _call_openai_compatible    # legacy EXAMLY_LLM_* is OpenAI-compatible


def status():
    """What the assistant status pill shows (`llm_connected` kept for the API contract)."""
    names = config.configured_providers()
    label = (" + ".join(n.capitalize() for n in names) + " ready") if names \
        else "Extractive mode (no language model configured)"
    return {"configured": bool(names), "llm_connected": bool(names),
            "providers": names, "label": label}


def generate(system, user):
    """Run the provider chain within the total budget. Returns {"text", "provider"} or None."""
    deadline = time.time() + config.total_seconds()
    for name in config.provider_order():
        cfg = config.provider_config(name)
        handler = _handlers.get(name)
        if not (cfg and handler):
            continue
        if _bad_key_now(cfg["key"]):
            _log(f"llm: skipping {name} (unusable key, retried later)")
            continue
        for attempt in (1, 2):
            remaining = deadline - time.time()
            if remaining < 5:
                _log("llm: time budget spent, stopping the chain")
                return None
            timeout = min(config.timeout_seconds(), remaining)
            try:
                return {"text": handler(cfg, system, user, timeout), "provider": name}
            except Exception as e:               # noqa: BLE001 - chain must survive any provider error
                _log(f"llm: {name} attempt {attempt}/2 failed: {e}")
                if _bad_key_now(cfg["key"]):
                    break                        # bad key: no point retrying it now
                if attempt == 1:
                    time.sleep(0.3)
                    continue
                break
    _log("llm: no provider answered; caller should fall back")
    return None
