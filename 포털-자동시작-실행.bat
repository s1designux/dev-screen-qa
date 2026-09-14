@echo off
chcp 65001 >nul
timeout /t 30 /nobreak >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\autostart-run.ps1" "%~dp0."
