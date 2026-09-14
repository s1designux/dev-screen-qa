@echo off
chcp 65001 >nul
rem 디자인 기준 TC대로 PC 웹 화면을 재고 찍는다.
rem   웹TC.bat 촬영요청.json apps\웹-주소표-예시.yaml
cd /d "%~dp0"
py -3 lib\webtc.py %*
if errorlevel 1 pause
