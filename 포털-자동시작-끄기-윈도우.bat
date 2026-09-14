@echo off
chcp 65001 >nul
REM 자동 시작을 해제한다. 그 뒤에는 포털-켜기-윈도우.bat 을 눌러서 직접 켠다.
schtasks /Delete /TN "검수포털 자동시작" /F
echo.
echo 자동 시작을 껐습니다.
pause
