@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup-schedule-on.ps1" "%~dp0."
pause
