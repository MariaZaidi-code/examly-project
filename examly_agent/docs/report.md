# Examination Preparation Agent (Scenario 7): Report

Agent Based Modeling (AIDE3313), Assignment 2. Data is synthetic. The instructor's scenario pack was not available when this was built; replace `data/knowledge/` and adapt the replanning demo to its change event.

## 1. Scenario and environment
A university student prepares for exams. The agent explains concepts from the student's own lecture notes, tracks weak topics from quiz results, generates adaptive practice questions, and builds then replans a revision schedule when the exam date changes. It is the backend counterpart of the Examly web UI (`webapp/`).
Environment: partially observable (it sees only notes, memory and MCP data), dynamic (exam date and scores change), single agent, human-in-the-loop for consequential actions.

## 2. Architecture
![architecture](docs/architecture.png)

| Required component | Implementation | Where |
|---|---|---|
| AI agent + LLM | `ExamAgent` loop: LLM chooses tool calls, max 5 steps, trace of every decision | `agent/agent.py`, `agent/llm.py` |
| Short-term memory | Per-session message window plus `last_topic` and pending plan; resolves "Give me an example of it" | `agent/memory.py` |
| Long-term memory | SQLite `ltm` table plus vector index per user; retrieved in a new session and new agent object | `agent/memory.py` |
| RAG | 6 documents, 23 section-based chunks, embedded, stored in SQLite vector DB, cosine search plus heading re-rank, cited sources with scores | `agent/rag.py`, `agent/vectorstore.py` |
| MCP | Official `mcp` SDK 2.x. Server `mcp_server/study_tools_server.py` runs as a subprocess; client speaks JSON-RPC over stdio (`tools/list`, `tools/call`). 6 tools | `agent/mcp_client.py` |
| Prompt engineering | System prompt with role, scope, tool rules, evidence, memory, failure behavior | `agent/prompts.py` |

RAG notes and long-term memory are kept in separate collections (`kb` vs `ltm:<user>`) because they differ in purpose: notes are evidence about the course, memory is facts about the student.

## 3. System prompt justification
- **role**: Fixes persona and the pedagogical stance (guide, not answer-machine), which reduces academic-integrity risk.
- **scope**: Bounds behaviour to exam prep so off-topic requests are declined instead of hallucinated.
- **tool_selection_rules**: Makes routing explicit and testable: each intent maps to one tool path, so the trace shows why a tool was chosen.
- **evidence_use**: Forces grounding: answers must come from retrieved chunks with [n] citations, giving the student a way to verify.
- **memory_handling**: Separates personalisation (LTM) from evidence (RAG) and defines STM's job (follow-ups).
- **failure_uncertainty**: Defines safe behaviour on empty retrieval, tool errors and missing inputs, instead of letting the model improvise.
- **human_oversight**: save_revision_plan is consequential; the prompt and the MCP tool both require explicit confirmation.

## 4. Human oversight
`generate_revision_plan` and `replan` only propose. `save_revision_plan` raises an error unless `confirmed=true`, and the agent only sets that after the student replies "confirm". Enforced in the tool as well as the prompt, so a model mistake cannot save a plan alone.

## 5. Evidence
- `python -m pytest tests`: 18 tests pass (RAG grounding and scores, refusal when no evidence, follow-up, MCP list and call, tool-level confirmation, long-term memory in a new session, replanning keeps completed sessions, exam-date supersede, missing input, tool error, LLM failure, step limit).
- `python demo.py` writes `logs/demo_transcript.md` (tool calls and results, memory retrieved) and `logs/demo_trace.json`.

## 6. Limitations (honest)
1. **LLM:** with no API key in the build environment the default model is `OfflineLLM`, a deterministic rule policy, not a language model. The transcript in `logs/` was produced by it. The real path, `OpenAICompatLLM`, is implemented but was not exercised against a live model. Run `demo.py` with `AGENT_LLM_URL/KEY/MODEL` set and keep that transcript for submission.
2. **Embeddings:** default is an offline hashed lexical embedder, so retrieval is keyword-like, not truly semantic. Set `AGENT_EMBED_URL` for real embeddings.
3. **Vector DB:** custom SQLite plus NumPy, since chromadb/faiss could not be installed. It is persistent and queryable but not a production engine.
4. Retrieval re-ranking uses a heading-match boost tuned on these six notes.
5. Single user at a time per agent object; no authentication.
