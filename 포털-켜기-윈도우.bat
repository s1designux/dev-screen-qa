@echo off
chcp 65001 >nul
REM 검수 포털을 켠다. 같은 망의 동료도 들어올 수 있다.

REM 이미 켜져 있으면 또 켜지 않는다 (자동 시작으로 켜진 뒤 두 번 눌렀을 때)
netstat -ano | findstr ":8765" | findstr LISTENING >nul
if not errorlevel 1 (
  echo 포털이 이미 켜져 있습니다. 이 창은 닫아도 됩니다.
  timeout /t 10 >nul
  exit /b
)

cd /d "%~dp0mvp0"
set QA_PORTAL_SHARE=1
python portal.py
pause
