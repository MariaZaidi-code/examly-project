# Examly backend

Starlette + SQLite. Frontend source of truth: `Examly_UI_preview.html`.

```
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000/api/...
python seed.py                        # optional sample data from the preview
python -m pytest tests                # end-to-end tests
```
Env: `EXAMLY_DB` (sqlite path), `EXAMLY_TODAY` (override date for tests), plus LLM config below.

## Configuration (nothing hardcoded)
Copy `.env.example` to `.env` (gitignored) or set environment variables — process env wins over the file. API keys are **never** in code: they are read from key *files* (or env vars) on every request, so a new key applies without restarting.

| Setting | Default | Meaning |
|---|---|---|
| `OMNI_KEY_FILE` / `OMNI_API_KEY` | – | OmniRoute key: path to a text file (localhost gateway) or the key directly |
| `OMNI_BASE_URL` / `OMNI_MODEL` | `http://localhost:20128/v1` / `free-fast` | OpenAI-compatible endpoint (comma-separated model list = tried in order) |
| `GROK_KEY_FILE` / `GROK_API_KEY` | – | Grok (xAI) key: path to a text file, or the key directly as an env var |
| `GROK_BASE_URL` / `GROK_MODEL` | `https://api.x.ai/v1` / `grok-4-fast` | OpenAI-compatible endpoint (comma-separated model list = tried in order) |
| `GEMINI_KEY_FILE` / `GEMINI_API_KEY` | – | Gemini key: file path or env var |
| `GEMINI_BASE_URL` / `GEMINI_MODEL` | Google `v1beta` / `gemini-3.6-flash,gemini-3.5-flash` | generateContent endpoint + model fallback list |
| `LLM_PROVIDER_ORDER` | `omni,grok,gemini` | Provider chain, tried in order |
| `LLM_TIMEOUT_S` / `LLM_TOTAL_S` | `30` / `45` | Per-request timeout / hard budget for the whole chain |
| `MAX_UPLOAD_MB` | `25` | Per-file upload limit (returns 413 above it) |
| `EXAMLY_DISABLE_LLM` | `0` | `1` forces extractive answers (used by tests) |
| `EXAMLY_LLM_URL/KEY/MODEL` | – | Optional legacy OpenAI-compatible provider, tried first |

The assistant answers via the chain (OmniRoute -> Grok -> Gemini) with numbered citations; if no provider answers inside the budget it falls back to extractive answers from retrieved passages. The status pill reports the live chain.
The app starts empty. Files: pdf, txt, md, pptx, ppt (25 MB max).

## Endpoints (all JSON under /api)
| Method + path | Notes |
|---|---|
| GET/PUT /profile | name, program, term, initial |
| GET/POST /subjects, GET/POST /exams | exam: {subject_id, title, date YYYY-MM-DD} |
| GET /dashboard | greeting, next_exam{days_left}, streak_days, today_sessions, last7[], last7_total, weakest[3], recommended, reviews_due[] |
| GET/POST /materials, DELETE /materials/{id} | multipart `file` + `subject_id` or `subject`; status indexing->indexed; accepted files: pdf, txt, md, pptx/ppt |
| GET /assistant/status; POST /assistant/chat | {message, subject_id?, level?, document_ids?} -> {answer, citations[{n,filename,page,quote}], grounded, mode} |
| GET/DELETE /assistant/history | |
| GET /planner/calendar?month=YYYY-MM | first_weekday (Mon=0), days{date:{sessions,exams}} |
| POST /planner/propose | {days, start_time, duration_min, per_day, subject_ids?} -> proposal, NOT saved |
| POST /planner/proposals/{id}/confirm, DELETE .../{id} | confirm saves sessions |
| PATCH/DELETE /sessions/{id} | status planned/done/skipped; done logs study minutes |
| POST /study-log | {minutes, day?, subject_id?} |
| POST /quizzes, GET /quizzes/{id} | {subject_id, count, topic?, document_ids?} cloze MCQs; `topic` focuses generation on sentences that mention it (falls back to the whole subject); `document_ids` restricts generation to those files (used by Flashcards "Build cards from this file"); answers hidden until answered |
| POST /quizzes/{id}/questions/{qid}/answer | {chosen} -> correct, explanation, source, next_question_id |
| GET /weak-topics | heatmap{columns,rows} + ranked[{proficiency, band, last_correct/last_total, answers}] |
| PUT /topics/{id} | sets the topic group used as a heatmap column (`area`); blank clears it |
| GET /auth/status | {login_required, user}; first run reports no account |
| POST /auth/register, /auth/login, /auth/logout | single-account setup, sign in, sign out (HttpOnly session cookie) |
| GET /review/due | spaced-repetition queue: topics due today with {due, interval_days, reps, lapses, proficiency, band} |
| POST /review/{id} | grades a flashcard review for that topic: {correct: bool} -> updated schedule |
| GET /flashcards?limit=20&document_id= | cards built from generated questions, grouped by topic review due date; {total, due_count, mastered, cards[], scope}; `document_id` restricts the deck to one file (404 if unknown) |
| GET /activity | real assistant history plus stored profile, exams, weakest topics and review counts |
| GET /analytics | study_hours_30d, active_days_30d, current_streak, quiz_trend, subject_comparison, daily_minutes |

Spaced repetition: every quiz answer reschedules that topic (simplified SM-2: 1 -> 3 -> 7 days, then interval x ease; a wrong answer resets it to tomorrow). Due topics appear on the dashboard and in `GET /review/due`.

## Login (single account)
First run has no account: `/login` offers **Create your account** (username 3-32 chars, password 6+). After that, pages redirect to `/login` and `/api` returns 401 until signed in. Passwords are PBKDF2-SHA256 (120k iterations) with per-user salt; sessions are opaque tokens in SQLite, sent as an HttpOnly SameSite=Lax cookie for 30 days. One workspace account, no per-user data separation. Log out from the sidebar.

## Ingest the six sample documents
With the server running:

```
python ingest_sample.py                              # open workspace
python ingest_sample.py --user ayesha --password ... # locked workspace
```

It uploads `sample_materials/database_systems/*.md` (six notes), waits for indexing, and prints a table of status, pages and chunks. It exits non-zero unless all six are `indexed` with pages and chunks and the assistant cites one of them. Re-uploading a filename replaces that document (old chunks are removed), and documents left `indexing` by a crash are marked `failed` on the next start.

Known gaps: no auth (single user), quiz questions are heuristic cloze unless extended with the LLM.
