@echo off
chcp 65001 >nul
rem 촬영 준비 사이트를 연다 →  http://127.0.0.1:8767
cd /d "%~dp0"
py -3 site\server.py
pause
