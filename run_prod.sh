#!/usr/bin/env bash
# One server: builds the web app, then serves everything from http://localhost:8000
cd "$(dirname "$0")"
. .venv/bin/activate
(cd frontend && npm run build)
cd backend && uvicorn main:app --host 0.0.0.0 --port 8000
