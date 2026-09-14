# 이 PC 에서 검수기가 돌 준비가 됐는지 본다. 아무것도 고치지 않는다.
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Continue'
$Root = (Resolve-Path $Root).Path
$검사기 = Join-Path $Root 'scripts\check_env.py'

# 창 글자를 UTF-8 로 (한글이 깨지지 않게)
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}

if (-not (Test-Path $검사기)) {
    Write-Host ''
    Write-Host '점검 파일을 찾지 못했습니다:' $검사기
    Write-Host '깃허브에서 다시 내려받아 주세요 (동료공유-읽어보기.md 1단계).'
    Write-Host ''
    Read-Host '엔터를 누르면 창이 닫힙니다'
    exit 1
}

$파이썬 = $null
foreach ($이름 in @('python', 'py', 'python3')) {
    if (Get-Command $이름 -ErrorAction SilentlyContinue) { $파이썬 = $이름; break }
}
if (-not $파이썬) {
    Write-Host ''
    Write-Host '파이썬          안됨 이 PC 에 파이썬이 없습니다'
    Write-Host '                     -> 파이썬 3.9 이상을 깔아 주세요 (python.org).'
    Write-Host '                        깔 때 "Add python.exe to PATH" 를 꼭 켜 주세요.'
    Write-Host ''
    Write-Host '이 창을 그대로 보여 주시면 고쳐 드립니다.'
    Write-Host ''
    Read-Host '엔터를 누르면 창이 닫힙니다'
    exit 1
}

Set-Location $Root
$env:PYTHONIOENCODING = 'utf-8'
& $파이썬 $검사기

Write-Host ''
Read-Host '엔터를 누르면 창이 닫힙니다'
