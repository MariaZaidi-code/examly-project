"""LLM adapters sharing one interface: chat(messages, tools) -> {"content": str|None, "tool_calls": [{"id","name","arguments"}]}.
OpenAICompatLLM talks to any OpenAI-compatible chat endpoint. OfflineLLM is a deterministic rule-based stand-in so the
project runs and is testable without network or API keys; it is NOT a language model and the report says so."""
import json, re, datetime as dt
from . import config

MONTHS = {m: i + 1 for i, m in enumerate("jan feb mar apr may jun jul aug sep oct nov dec".split())}

def parse_date(text, today):
    m = re.search(r"(\d{4})-(\d{2})-(\d{2})", text)
    if m: return m.group(0)
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*", text.lower())
    if m:
        mo, d = MONTHS[m.group(2)], int(m.group(1))
        y = today.year + (1 if (mo, d) < (today.month, today.day) else 0)
        try: return dt.date(y, mo, d).isoformat()
        except ValueError: return None
    return None

class OpenAICompatLLM:
    name = "openai-compatible"
    def __init__(self):
        self.name = f"openai-compatible:{config.LLM_MODEL}"
    def chat(self, messages, tools):
        import requests
        body = {"model": config.LLM_MODEL, "messages": messages,
                "tools": [{"type": "function", "function": {"name": t["name"], "description": t["description"], "parameters": t["parameters"]}} for t in tools]}
        r = requests.post(config.LLM_URL.rstrip("/") + "/chat/completions", headers={"Authorization": "Bearer " + (config.LLM_KEY or "")}, json=body, timeout=90)
        r.raise_for_status()
        m = r.json()["choices"][0]["message"]
        return {"content": m.get("content"), "tool_calls": [{"id": c["id"], "name": c["function"]["name"], "arguments": json.loads(c["function"]["arguments"] or "{}")} for c in m.get("tool_calls") or []]}

class OfflineLLM:
    name = "offline-rule-policy (deterministic stand-in, not an LLM)"
    def __init__(self, today=None):
        self.today = today
    def _ctx(self, messages):
        sysm = messages[0]["content"]
        g = lambda k: (re.search(rf"^{k}: (.*)$", sysm, re.M) or [None, ""])[1].strip()
        return {"user": g("USER_ID") or "student", "today": g("TODAY"), "last_topic": g("LAST_TOPIC"), "pending": g("PENDING_PLAN_ID"),
                "memory": [l[2:] for l in sysm.splitlines() if l.startswith("- [")]}
    def _call(self, name, **a):
        return {"content": None, "tool_calls": [{"id": f"call_{name}", "name": name, "arguments": a}]}
    def chat(self, messages, tools):
        cx = self._ctx(messages)
        today = dt.date.fromisoformat(cx["today"]) if cx["today"] else dt.date.today()
        last_user = max(i for i, m in enumerate(messages) if m["role"] == "user")
        text = messages[last_user]["content"]; low = text.lower()
        results = {}
        for m in messages[last_user + 1:]:
            if m["role"] == "tool": results[m["name"]] = json.loads(m["content"])
        u = cx["user"]
        mem_exam = next((re.search(r"\d{4}-\d{2}-\d{2}", x).group(0) for x in cx["memory"] if x.startswith("[exam]") and re.search(r"\d{4}-\d{2}-\d{2}", x)), None)
        date = parse_date(text, today)

        # ---- intent
        if re.match(r"^\s*(yes|confirm|save( it)?|go ahead|ok(ay)?,? save)\b", low):
            intent = "confirm"
        elif re.search(r"(moved|postponed|brought forward|pushed|rescheduled|exam is now|changed)", low) and date:
            intent = "replan"
        elif re.search(r"\b(plan|schedule|timetable|revision)\b", low):
            intent = "plan"
        elif re.search(r"(scored|got)\s+\d+\s*(/|out of)\s*\d+", low):
            intent = "result"
        elif re.search(r"(weak|struggl|worst|where am i)", low) and "remember" not in low and not low.startswith("i "):
            intent = "weak"
        elif re.search(r"(my name is|remember|i struggle|i find .+ (hard|difficult)|my exam is|i prefer)", low):
            intent = "remember"
        elif re.search(r"(quiz me|practice question|test me)", low):
            intent = "quiz"
        else:
            intent = "ask"

        if intent == "confirm":
            if "save_revision_plan" in results:
                r = results["save_revision_plan"]
                return self._final(f"Saved. Your plan (id {r['data']['plan_id']}) now has {r['data']['sessions']} sessions." if r["ok"] else f"I could not save the plan: {r['error']}")
            if not cx["pending"]: return self._final("There is no proposed plan waiting for confirmation. Ask me for a revision plan first.")
            return self._call("save_revision_plan", user_id=u, plan_id=int(cx["pending"]), confirmed=True)

        if intent in ("plan", "replan"):
            if intent == "plan" and "generate_revision_plan" not in results:
                exam = date or mem_exam
                if not exam: return self._final("What is your exam date? I need it to build a plan (for example 2026-11-15).")
                if "get_weak_topics" not in results: return self._call("get_weak_topics", user_id=u)
                return self._call("generate_revision_plan", user_id=u, exam_date=exam, today=today.isoformat())
            if intent == "replan" and "replan" not in results:
                if "get_weak_topics" not in results and False: pass
                return self._call("replan", user_id=u, new_exam_date=date, today=today.isoformat())
            r = results.get("generate_revision_plan") or results.get("replan")
            if not r["ok"]: return self._final(f"I could not build the plan: {r['error']}")
            d = r["data"]; extra = f" Kept {d['kept_completed_sessions']} completed sessions." if "kept_completed_sessions" in d else ""
            lines = "\n".join(f"- {i['date']}: {i['topic']} ({i['minutes']} min)" for i in d["items"])
            return self._final(f"Proposed plan {d['plan_id']} for your exam on {d['exam_date']}, weakest topics first:{extra}\n{lines}\n\nNothing is saved yet. Reply 'confirm' to save this plan, or tell me what to change.")

        if intent == "result":
            m = re.search(r"(?:scored|got)\s+(\d+)\s*(?:/|out of)\s*(\d+)\s*(?:in|on|for)?\s*([a-z][a-z \-]*)", low)
            if "record_quiz_result" not in results:
                if not m or not m.group(3).strip(): return self._final("Which topic was that quiz on? Tell me like 'I scored 3/8 on deadlock handling'.")
                return self._call("record_quiz_result", user_id=u, topic=m.group(3).strip(), correct=int(m.group(1)), total=int(m.group(2)))
            r = results["record_quiz_result"]
            return self._final(f"Recorded. Your accuracy on {r['data']['topic']} is now {r['data']['accuracy_pct']}% over {r['data']['answers']} answers." if r["ok"] else f"I could not record that: {r['error']}")

        if intent == "weak":
            if "get_weak_topics" not in results: return self._call("get_weak_topics", user_id=u)
            r = results["get_weak_topics"]
            if not r["ok"]: return self._final(f"I could not read your results: {r['error']}")
            w = r["data"]["weak_topics"]
            if not w: return self._final("I have no quiz results for you yet, so I cannot rank weak topics. Tell me a score like 'I scored 3/8 on deadlock handling'.")
            return self._final("Your weakest topics (by quiz accuracy):\n" + "\n".join(f"- {x['topic']}: {x['accuracy_pct']}% over {x['answers']} answers" for x in w))

        if intent == "remember":
            if "remember_fact" not in results:
                kind = "exam" if "exam" in low else "difficulty" if re.search(r"struggl|hard|difficult", low) else "profile" if "name" in low else "preference"
                content = text.strip().rstrip(".")
                if kind == "exam" and date: content = f"exam date {date} ({content})"
                return self._call("remember_fact", kind=kind, content=content)
            return self._final("Noted, I will remember that in future sessions.")

        if intent == "quiz":
            if "get_weak_topics" not in results: return self._call("get_weak_topics", user_id=u)
            w = results["get_weak_topics"]["data"]["weak_topics"] if results["get_weak_topics"]["ok"] else []
            topic = w[0]["topic"] if w else (cx["last_topic"] or "database")
            if "search_notes" not in results: return self._call("search_notes", query=topic)
            hits = results["search_notes"]["hits"]
            if not hits: return self._final(f"My notes have nothing on {topic}, so I cannot write a grounded question.")
            sent = max(re.split(r"(?<=[.!?])\s+", hits[0]["text"].split(" :: ", 1)[-1]), key=len)
            words = [x for x in re.findall(r"[A-Za-z]{7,}", sent)]
            if not words: return self._final(f"Explain in your own words: {hits[0]['heading']} [1]")
            tgt = max(words, key=len)
            why = f" (targeting your weakest topic, {topic}, at {w[0]['accuracy_pct']}%)" if w else ""
            return self._final(f"Practice question{why}:\n\"{sent.replace(tgt, '_____', 1)}\"\nWhat word fills the blank? Answer and I will check it against your notes [1].\n\nSources:\n[1] {hits[0]['source']} / {hits[0]['heading']}")

        # ---- ask (RAG)
        pron = re.search(r"\b(it|that|this|them|those|its)\b|\b(more|example|why|another)\b", low) and len(text.split()) <= 9
        q = f"{cx['last_topic']} {text}" if pron and cx["last_topic"] else text
        if "search_notes" not in results: return self._call("search_notes", query=q)
        hits = results["search_notes"]["hits"]
        if not hits: return self._final("I could not find this in your notes, so I will not guess. Try uploading material that covers it or rephrase the question.")
        qw = set(re.findall(r"[a-z0-9]+", q.lower()))
        def best(t):
            return max(re.split(r"(?<=[.!?])\s+", t.split(" :: ", 1)[-1]), key=lambda s: len(qw & set(re.findall(r"[a-z0-9]+", s.lower()))))
        body = " ".join(f"{best(h['text'])} [{h['n']}]" for h in hits[:2])
        src = "\n".join(f"[{h['n']}] {h['source']} / {h['heading']} (score {h['score']})" for h in hits[:2])
        return self._final(f"From your notes: {body}\n\nSources:\n{src}")
    def _final(self, text): return {"content": text, "tool_calls": []}

def get_llm(today=None):
    return OpenAICompatLLM() if config.LLM_URL else OfflineLLM(today)
