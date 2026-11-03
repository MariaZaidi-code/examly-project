# Examly backend

Starlette + SQLite. Frontend source of truth: `Examly_UI_preview.html`.

```
pip install -r requirements.txt
uvicorn app.main:app --reload        # http://127.0.0.1:8000/api/...
python seed.py                        # optional sample data from the preview
python -m pytest tests                # end-to-end tests
```
Env: `EXAMLY_DB` (sqlite path), `EXAMLY_LLM_URL` / `EXAMLY_LLM_KEY` / `EXAMLY_LLM_MODEL` (OpenAI-compatible; without them the assistant answers extractively from retrieved passages), `EXAMLY_TODAY` (override date for tests).
The app starts empty. Files: pdf, txt, md.

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
| POST /quizzes, GET /quizzes/{id} | {subject_id, count, topic?} cloze MCQs; `topic` focuses generation on sentences that mention it (falls back to the whole subject); answers hidden until answered |
| POST /quizzes/{id}/questions/{qid}/answer | {chosen} -> correct, explanation, source, next_question_id |
| GET /weak-topics | heatmap{columns,rows} + ranked[{proficiency, band, last_correct/last_total, answers}] |
| PUT /topics/{id} | sets the topic group used as a heatmap column (`area`); blank clears it |
| GET /auth/status | {login_required, user}; first run reports no account |
| POST /auth/register, /auth/login, /auth/logout | single-account setup, sign in, sign out (HttpOnly session cookie) |
| GET /review/due | spaced-repetition queue: topics due today with {due, interval_days, reps, lapses, proficiency, band} |
| POST /review/{id} | grades a flashcard review for that topic: {correct: bool} -> updated schedule |
| GET /flashcards?limit=20 | cards built from generated questions, grouped by topic review due date; {total, due_count, mastered, cards[]} |
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
