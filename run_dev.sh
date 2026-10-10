#!/usr/bin/env bash
# Development: API on :8000, web app on :5173 (open http://localhost:5173)
cd "$(dirname "$0")"
. .venv/bin/activate
(cd backend && uvicorn main:app --reload --port 8000) &
API=$!
trap "kill $API" EXIT
cd frontend && npm run dev
