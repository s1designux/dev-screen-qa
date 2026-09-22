# 촬영 준비 사이트를 켠다. 같은 망의 동료도 들어올 수 있다.
# 이 창을 닫으면 촬영 준비 사이트가 꺼진다.
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$dir  = Join-Path $Root 'capture-app'

# 켜져 있던 옛 창은 끄고 최신으로 다시 켠다
#  (새로 받은 파일이 깔려도 옛 창이 계속 화면을 내주던 일을 막는다)
. (Join-Path $PSScriptRoot 'free-port.ps1')
if (-not (포트비우기 8767 '촬영 준비 사이트')) {
    Start-Sleep -Seconds 15
    exit 1
}

if (-not (Test-Path (Join-Path $dir 'site\server.py'))) {
    Write-Host ''
    Write-Host '촬영 준비 사이트를 켜지 못했습니다.'
    Write-Host "필요한 파일을 찾지 못했습니다: $(Join-Path $dir 'site\server.py')"
    Start-Sleep -Seconds 15
    exit 1
}

Set-Location $dir
$env:QA_CAPTURE_BIND = '0.0.0.0'

try {
    & python site\server.py
}
catch {
    Write-Host ''
    Write-Host '촬영 준비 사이트를 켜지 못했습니다.'
    Write-Host $_.Exception.Message
    Write-Host '파이썬이 깔려 있는지 확인해 주세요.'
    Start-Sleep -Seconds 15
    exit 1
}

Write-Host ''
Write-Host '촬영 준비 사이트가 꺼졌습니다.'
Start-Sleep -Seconds 15
