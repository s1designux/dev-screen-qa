# 검수 포털과 촬영 준비 사이트를 함께 켠다. 같은 망의 동료도 들어올 수 있다.
# 이 창을 닫으면 포털이 꺼진다(촬영 준비 사이트는 따로 뜬 창에서 돈다).
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$dir  = Join-Path $Root 'mvp0'

# 촬영 준비 사이트도 같이 켠다. 켜져 있던 옛 창은 그쪽이 스스로 끄고 다시 켠다.
$촬영 = Join-Path $Root '촬영준비-켜기-윈도우.bat'
if (Test-Path $촬영) {
    Start-Process -FilePath $촬영 -WorkingDirectory $Root
}

# 켜져 있던 옛 포털은 끄고 최신으로 다시 켠다
#  (새로 받은 파일이 깔려도 옛 창이 계속 화면을 내주던 일을 막는다)
. (Join-Path $PSScriptRoot 'free-port.ps1')
if (-not (포트비우기 8765 '포털')) {
    Start-Sleep -Seconds 15
    exit 1
}

if (-not (Test-Path (Join-Path $dir 'portal.py'))) {
    Write-Host ''
    Write-Host '포털을 켜지 못했습니다.'
    Write-Host "포털 파일을 찾지 못했습니다: $(Join-Path $dir 'portal.py')"
    Start-Sleep -Seconds 15
    exit 1
}

Set-Location $dir
$env:QA_PORTAL_SHARE = '1'

try {
    & python portal.py
}
catch {
    Write-Host ''
    Write-Host '포털을 켜지 못했습니다.'
    Write-Host $_.Exception.Message
    Write-Host '파이썬이 깔려 있는지 확인해 주세요.'
    Start-Sleep -Seconds 15
    exit 1
}

Write-Host ''
Write-Host '포털이 꺼졌습니다.'
Start-Sleep -Seconds 15
