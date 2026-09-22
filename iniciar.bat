@echo off
cd /d "%~dp0"
if not exist .env copy .env.example .env >nul
start "" http://localhost:8787
python server.py
