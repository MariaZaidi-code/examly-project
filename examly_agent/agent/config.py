import os
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = Path(os.environ.get("AGENT_KB_DIR", ROOT / "data" / "knowledge"))
AGENT_DB = os.environ.get("AGENT_DB", str(ROOT / "data" / "agent.db"))     # vectors + long-term memory
STUDY_DB = os.environ.get("STUDY_DB", str(ROOT / "data" / "study.db"))     # owned by the MCP server
MCP_SERVER = ROOT / "mcp_server" / "study_tools_server.py"
LLM_URL, LLM_KEY, LLM_MODEL = os.environ.get("AGENT_LLM_URL"), os.environ.get("AGENT_LLM_KEY"), os.environ.get("AGENT_LLM_MODEL", "gpt-4o-mini")
EMBED_URL, EMBED_MODEL = os.environ.get("AGENT_EMBED_URL"), os.environ.get("AGENT_EMBED_MODEL", "text-embedding-3-small")
MIN_SCORE = float(os.environ.get("AGENT_MIN_SCORE", "0.12"))   # below this, retrieval is treated as "no evidence"
STM_WINDOW = 12
MAX_STEPS = 5
