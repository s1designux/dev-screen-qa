@echo off
chcp 65001 >nul
REM PC를 켜고 로그인하면 검수 포털이 저절로 켜지게 등록한다. 한 번만 실행하면 된다.
schtasks /Create /TN "검수포털 자동시작" /TR "\"%~dp0포털-켜기-윈도우.bat\"" /SC ONLOGON /DELAY 0000:30 /F
echo.
echo 자동 시작을 등록했습니다.
echo 이제 PC를 켜고 로그인하면 30초 뒤 포털이 저절로 켜집니다.
echo (검은 창이 하나 뜹니다. 그 창은 닫지 마세요 - 닫으면 포털이 꺼집니다)
pause
