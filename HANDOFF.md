# HANDOFF: Examly Exam Preparation Agent (Assignment 2, Agent Based Modeling, Scenario 7)

Due 06/11/2026, 40 marks. Requirements: one Python agent + LLM, short-term memory, long-term memory (persistent, retrieved in a NEW session),
RAG over >=5 docs with embeddings + vector DB, a real MCP client-server tool call, system prompt + justification, architecture diagram,
tests, error handling, reproducible demo, human oversight for consequential actions.

## State (update this list)
- [x] agent/ (config, embeddings, vectorstore, rag, memory, mcp_client, llm, prompts, agent, cli)
- [x] mcp_server/study_tools_server.py (official `mcp` SDK 2.x, MCPServer, stdio): get_weak_topics, record_quiz_result, generate_revision_plan, save_revision_plan (needs confirmed=true), replan, mark_session_done
- [x] data/knowledge: 6 synthetic notes (>=5 required)
- [x] tests/ (pytest, 18 pass): RAG evidence, STM follow-up, LTM in new session, MCP call, human-confirm refusal, error paths, replanning
- [x] demo.py -> logs/demo_transcript.md (3 sessions: STM follow-up; new session proves LTM; replan after exam date moves)
- [x] docs/: architecture.png/.mmd, report.md
- [x] final zip (examly_project.zip)
- [ ] STUDENT TODO: run demo.py with a real LLM key; fill name/reg no.; swap in instructor's scenario pack; export report.md to PDF if required

## Honest limitations (must appear in the report)
- Sandbox had no LLM API key/network, so the default LLM is `OfflineLLM`, a deterministic rule policy, NOT a language model. The real path is `OpenAICompatLLM`
  (set AGENT_LLM_URL / AGENT_LLM_KEY / AGENT_LLM_MODEL). The assignment requires a configured chat model: the student MUST run the demo once with a real key and keep that transcript.
- Embeddings default to an offline hashed lexical embedder (1024-d). Set AGENT_EMBED_URL for real semantic embeddings. Vector DB is custom SQLite+NumPy (chromadb/faiss unavailable offline).
- Data is synthetic. The instructor's scenario pack (evidence, constraints, change event) was NOT available; replace data/knowledge with it and adapt the replan demo to its change event.
- pip/PyPI was blocked in the sandbox; only preinstalled packages were used (mcp 2.3, numpy, scikit-learn, starlette, pypdf).

## Prompt for the next LLM
```
Continue the project in this folder (examly_agent/). Read HANDOFF.md, then agent/agent.py, agent/llm.py, mcp_server/study_tools_server.py.
Finish every unchecked item in the State list. Keep: one primary agent, MCP over stdio via the official SDK (not plain HTTP), RAG kept separate from
long-term memory, save_revision_plan only after explicit confirmation. Run `python -m pytest tests` and `python demo.py`. If an LLM key is available,
set AGENT_LLM_URL/KEY/MODEL and re-run demo.py to produce a transcript with a real model, and tell the student the offline transcript is a fallback.
Write docs/report.md covering: scenario, architecture diagram, component mapping to the requirement table, system-prompt justification (agent/prompts.py JUSTIFICATION),
test evidence, limitations above. Do not claim the offline policy is an LLM.
```

## Frontend/backend wiring (added)
- [x] webapp/frontend.html rewritten: all 7 screens fetch from /api (profile, exam and upload dialogs, chat with citations, planner propose/confirm/discard, quizzes, weak topics, analytics). Backend serves it at "/".
- Verified end-to-end against real uvicorn: `/` serves frontend.html, and the API flow works (upload -> indexed -> grounded chat with citations -> quiz -> weak topics -> planner propose/confirm -> session done -> analytics). Backend tests: 9/9 pass.
- [x] Topic groups: `PUT /api/topics/{id}` plus a "Group" button on My Weak Topics lets the student set heatmap columns (previously seed-only).
- [x] Login: single-account first-run setup + sign-in page (`webapp/login.html`, `/login`), PBKDF2 hashes, SQLite session cookies, log out in the sidebar. Once an account exists the app and `/api` require a session.
- [x] Ingestion: six sample Database Systems notes in `webapp/backend/sample_materials/database_systems/`, `ingest_sample.py` verifier, re-upload replaces a document, chunks reset on re-index, interrupted `indexing` documents become `failed` at startup, and `materials` now reports chunk counts.
- [x] Frontend replaced with the downloaded `examly_preview.html` design (purple dashboard, 9 screens: adds Flashcards and Agent Activity) and wired to /api. Flashcards use generated questions + SM-2 (`GET /api/flashcards`, `POST /api/review/{id}`); Agent Activity shows real assistant history and stored study data (`GET /api/activity`), not a fabricated MCP log.
- Known behaviour: quiz may have fewer than the requested questions on short notes (backend cloze generator). "Practice now" now draws questions from notes/sentences that mention the topic and falls back to the whole subject when the topic is absent.
- [x] Spaced repetition (simplified SM-2, inspired by Anki/FSRS and Mind Mentor): each quiz answer schedules the topic's next review (1 -> 3 -> 7 days, then interval x ease; wrong resets to tomorrow). `GET /api/review/due` and `dashboard.reviews_due` feed a "Reviews due today" card on Overview.
- [x] Topic-scoped quizzes (inspired by PrepPilot/NoteBotLM): `topic` on POST /quizzes filters both chunks and sentences, so the existing "Practice now" button actually targets the weak topic.
- Not used: DOC-20261103-WA0009.zip (separate Streamlit "examination_agent"); ask the student if it should be merged.
- Student TODO still open: real-LLM demo transcript, name/reg no. in report, instructor scenario pack.
