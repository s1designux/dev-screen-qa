# 검수 포털과 촬영 준비 사이트를 함께 켠다. 같은 망의 동료도 들어올 수 있다.
# 이 창을 닫으면 포털이 꺼진다(촬영 준비 사이트는 따로 뜬 창에서 돈다).
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$dir  = Join-Path $Root 'mvp0'

# 촬영 준비 사이트도 같이 켠다. 이미 켜져 있으면 그 창이 스스로 알린다.
$촬영 = Join-Path $Root '촬영준비-켜기-윈도우.bat'
if (Test-Path $촬영) {
    Start-Process -FilePath $촬영 -WorkingDirectory $Root
}

# 이미 켜져 있으면 또 켜지 않는다 (자동 시작으로 켜진 뒤 두 번 눌렀을 때)
$busy = (netstat -ano | Select-String ':8765' | Select-String 'LISTENING')
if ($busy) {
    Write-Host '포털이 이미 켜져 있습니다. 이 창은 닫아도 됩니다.'
    Start-Sleep -Seconds 10
    exit 0
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
