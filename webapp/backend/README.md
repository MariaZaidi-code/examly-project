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
| GET /dashboard | greeting, next_exam{days_left}, streak_days, today_sessions, last7[], last7_total, weakest[3], recommended |
| GET/POST /materials, DELETE /materials/{id} | multipart `file` + `subject_id` or `subject`; status indexing->indexed |
| GET /assistant/status; POST /assistant/chat | {message, subject_id?, level?, document_ids?} -> {answer, citations[{n,filename,page,quote}], grounded, mode} |
| GET/DELETE /assistant/history | |
| GET /planner/calendar?month=YYYY-MM | first_weekday (Mon=0), days{date:{sessions,exams}} |
| POST /planner/propose | {days, start_time, duration_min, per_day, subject_ids?} -> proposal, NOT saved |
| POST /planner/proposals/{id}/confirm, DELETE .../{id} | confirm saves sessions |
| PATCH/DELETE /sessions/{id} | status planned/done/skipped; done logs study minutes |
| POST /study-log | {minutes, day?, subject_id?} |
| POST /quizzes, GET /quizzes/{id} | {subject_id, count, topic?} cloze MCQs; answers hidden until answered |
| POST /quizzes/{id}/questions/{qid}/answer | {chosen} -> correct, explanation, source, next_question_id |
| GET /weak-topics | heatmap{columns,rows} + ranked[{proficiency, band, last_correct/last_total, answers}] |
| GET /analytics | study_hours_30d, active_days_30d, current_streak, quiz_trend, subject_comparison, daily_minutes |

Known gaps: no auth (single user), quiz questions are heuristic cloze unless extended with the LLM, heatmap `area` is only set by seed or a future topic-edit endpoint.
