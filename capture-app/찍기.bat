@echo off
chcp 65001 >nul
rem 실행 버튼(윈도우) — 이름표 한 장을 골라 실행하면 사진이 shots\ 에 쌓인다.
rem   찍기.bat apps\웹-예시.yaml
cd /d "%~dp0"
py -3 lib\runner.py %*
if errorlevel 1 pause
