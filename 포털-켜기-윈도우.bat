@echo off
chcp 65001 >nul
REM 검수 포털을 켠다. 같은 망의 동료도 들어올 수 있다.
cd /d "%~dp0mvp0"
set QA_PORTAL_SHARE=1
python portal.py
pause
