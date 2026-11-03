# Examly project bundle
- webapp/        : Examly app. `frontend.html` is now wired to the REST backend (backend/) and served by it at "/".
- examly_agent/  : Assignment 2 deliverable (Exam Preparation Agent). See its README.md and docs/report.md.
- HANDOFF.md     : state + prompt for the next LLM.

## Run the app (frontend + backend together)
    cd webapp/backend
    pip install -r requirements.txt
    uvicorn app.main:app --reload
    # open http://127.0.0.1:8000/
Optional sample data: `python seed.py`. Or run `run_examly.sh` (Mac/Linux) / `run_examly.bat` (Windows) from this folder.
Opening webapp/frontend.html directly from disk also works while the server is running (it calls http://127.0.0.1:8000/api).
Optional LLM for the assistant: copy `webapp/backend/.env.example` to `webapp/backend/.env` and point `GROK_KEY_FILE` / `GEMINI_KEY_FILE` at your key text files (chain: Grok → Gemini; extractive fallback when no provider answers). Nothing is hardcoded — see `webapp/backend/README.md`.
