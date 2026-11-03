import os, sys, tempfile
tmp = tempfile.mkdtemp(prefix="examly_test_")
os.environ["AGENT_DB"] = os.path.join(tmp, "agent.db")
os.environ["STUDY_DB"] = os.path.join(tmp, "study.db")
os.environ["AGENT_TODAY"] = "2026-11-03"
for k in ("AGENT_LLM_URL", "AGENT_EMBED_URL"): os.environ.pop(k, None)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
