#!/bin/sh
cd "$(dirname "$0")/webapp/backend" && pip install -r requirements.txt && uvicorn app.main:app --reload
