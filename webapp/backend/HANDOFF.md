# Examly backend: handoff

Source of truth: `Examly_UI_preview.html` (7 screens). Backend lives in this folder.

## Environment constraints found
- pip/PyPI is blocked in the build sandbox. FastAPI and SQLAlchemy could not be installed.
- Available: Python 3.13, starlette, uvicorn, pydantic, pypdf, pdfplumber, requests, sqlite3.
- So the backend is Starlette + raw sqlite3. It can be ported to FastAPI later if wanted.

## Frontend screens -> API (contract)
| Screen | Endpoints |
|---|---|
| Overview | GET /api/dashboard |
| AI Study Assistant | GET /api/assistant/status, POST /api/assistant/chat |
| Study Planner | GET /api/planner/calendar?month=YYYY-MM, POST /api/planner/propose, POST /api/planner/proposals/{id}/confirm, DELETE /api/planner/proposals/{id}, PATCH /api/sessions/{id} |
| Practice & Quizzes | POST /api/quizzes, GET /api/quizzes/{id}, POST /api/quizzes/{id}/questions/{qid}/answer |
| My Weak Topics | GET /api/weak-topics |
| Study Materials | GET/POST /api/materials, DELETE /api/materials/{id} |
| Performance Analytics | GET /api/analytics |
| Shared | GET/PUT /api/profile, GET/POST /api/subjects, POST /api/exams |

## Rules taken from the UI
- App starts EMPTY; data comes from uploads, quizzes, sessions (`seed.py` loads the preview sample data only on request).
- Assistant answers are grounded ONLY in uploaded materials, with numbered citations (file, page, quote). If nothing relevant is found, it says so.
- Planner proposals are NOT saved as sessions until confirmed ("Nothing is saved until you confirm").
- Quiz questions come from the user's own materials and carry a source (file, page).
- Weak topics = proficiency from quiz answers; red < 50%, amber < 70%.
- Material status: indexing -> indexed.
- Streak = consecutive days with study minutes ending today.

## Status
See the checklist at the bottom of this file, updated as work completes.

## Prompt for the next LLM (copy everything in the box)

```
You are continuing a backend build for "Examly", an exam-study web app. The
frontend is `Examly_UI_preview.html` (the source of truth: every field shown
on screen must be derivable from an API response). Work in `examly-backend/`.
Read HANDOFF.md first, then the code in app/, then finish the unchecked items
in the Status checklist.

Constraints: Python 3.13, Starlette + uvicorn + sqlite3 + pypdf only (no
network installs were possible). LLM config lives in app/config.py (env file
or env vars, keys read from key files at call time - nothing hardcoded): a
Grok -> Gemini provider chain in app/llm.py with timeouts, a total budget and
a per-key degrade cache; when no provider answers, fall back to extractive
answers from retrieved chunks. Never answer outside the uploaded materials;
always return citations.
Planner proposals must not be persisted as sessions until confirmed.
Run `python -m pytest tests` and fix failures. Do not change the JSON shapes
documented in README.md without updating the README and tests.
```

## Status checklist
- [x] app/db.py schema
- [x] app/services (retrieval, quiz, planner, analytics)
- [x] app/main.py routes
- [x] seed.py
- [x] tests pass (9/9)
- [x] README.md
- [x] spaced repetition: `reviews` table, simplified SM-2 on each quiz answer, `GET /api/review/due`, `dashboard.reviews_due`, Overview "Reviews due today" card
- [x] topic-scoped quiz generation: `topic` filters chunks and sentences ("Practice now" now actually focuses)
- [x] verified against real uvicorn: `/` serves the frontend; full flow works (profile -> subject/exam -> upload -> indexed -> grounded chat with citations -> quiz -> weak topics -> topic group -> planner propose/confirm -> session done -> analytics), no server errors
- [x] LLM provider chain: `app/config.py` (env file + env vars, key files read per call) + `app/llm.py` (grok -> gemini, comma model lists, `LLM_TIMEOUT_S`/`LLM_TOTAL_S` budget, 15-min per-key degrade), `.env.example` committed, `.env` gitignored; live E2E answers via Gemini with citations (`e2e_verify.py`)
- [x] signed-in name everywhere: login/register seed an empty profile name from the username; frontend `displayName()` falls back to the title-cased username (sidebar, greeting, profile card, chat avatar)
- [x] empty-dashboard upload prompt: `dashboard.counts` -> "Upload your first documents" hero + "Getting started" checklist with progress (`ui_verify.py` screenshots in `ui_shots/`)
- [x] upload hardening: `MAX_UPLOAD_MB` -> HTTP 413, drag-and-drop dropzone in the UI
- [x] UI polish: count-up stats, confetti on quiz finish, toast variants, bell badge for reviews due, top-bar Upload button (respects `prefers-reduced-motion`)
- [x] tests 21/21 (`python -m pytest tests -q`); tests isolate from real keys via `EXAMLY_ENV_FILE` + `EXAMLY_DISABLE_LLM=1`

## Remaining ideas (not done)
- LLM-generated quiz questions (currently heuristic cloze) and topic extraction.
- Serve the frontend and wire its hardcoded sample data to these endpoints (fetch calls).
- Auth if multi-user; port to FastAPI once pip works.
