@echo off
chcp 65001 >nul
REM 매일 오후 4시 자동 백업을 등록한다. 한 번만 실행하면 된다.
schtasks /Create /TN "검수포털 백업" /TR "\"%~dp0백업-지금-윈도우.bat\"" /SC DAILY /ST 16:00 /F
echo.
echo 자동 백업을 등록했습니다. 매일 오후 4시에 돌아갑니다.
pause
