cd /d "%~dp0webapp\backend"
pip install -r requirements.txt
uvicorn app.main:app --reload
