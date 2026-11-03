# Examly Exam Preparation Agent

```
pip install -r requirements.txt     # mcp, numpy, scikit-learn, pytest (all pure-Python friendly)
python -m pytest tests               # 18 tests
python demo.py                       # reproducible 3-session demo -> logs/demo_transcript.md
python -m agent.cli --user ayesha --session s1 --trace      # interactive
```
Real LLM: `export AGENT_LLM_URL=https://api.openai.com/v1 AGENT_LLM_KEY=... AGENT_LLM_MODEL=gpt-4o-mini` (any OpenAI-compatible endpoint).
Real embeddings: `AGENT_EMBED_URL` (+ `AGENT_EMBED_MODEL`). See docs/report.md and HANDOFF.md.
