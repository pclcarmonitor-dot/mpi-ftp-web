@echo off
cd /d %~dp0
if not exist .venv ( python -m venv .venv )
call .venv\Scripts\activate
pip install -r requirements.txt -q
if not exist .env copy .env.example .env
echo Open http://localhost:8080
waitress-serve --port=8080 app:app
