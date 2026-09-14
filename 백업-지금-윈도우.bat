@echo off
chcp 65001 >nul
REM 검수 데이터와 이미지를 복사한다. 7일치 보관.
setlocal
set SRC=%~dp0mvp0
set DST=%USERPROFILE%\dev-screen-qa-백업
for /f "tokens=1-3 delims=/- " %%a in ("%date%") do set DAY=%%a%%b%%c
set DAY=%DAY: =%
set OUT=%DST%\%DAY%
if not exist "%OUT%" mkdir "%OUT%"

if exist "%SRC%\mvp0-real.db" copy /Y "%SRC%\mvp0-real.db" "%OUT%\mvp0-real.db" >nul
if exist "%SRC%\uploads" robocopy "%SRC%\uploads" "%OUT%\uploads" /MIR /NFL /NDL /NJH /NJS >nul

echo %date% %time% 백업 완료 - %OUT% >> "%DST%\백업기록.txt"

REM 7일치만 남기기
forfiles /P "%DST%" /D -7 /C "cmd /c if @isdir==TRUE rmdir /s /q @path" 2>nul
endlocal
