@echo off
chcp 65001 >nul
rem 검수 포털을 연다 →  http://127.0.0.1:8765
cd /d "%~dp0"
py -3 portal.py
pause
