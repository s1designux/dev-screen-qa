@echo off
chcp 65001 >nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\backup-now.ps1" "%~dp0."
timeout /t 15 >nul
