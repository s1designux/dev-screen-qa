# 촬영 준비 사이트를 켠다. 같은 망의 동료도 들어올 수 있다.
# 이 창을 닫으면 촬영 준비 사이트가 꺼진다.
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$dir  = Join-Path $Root 'capture-app'

# 이미 켜져 있으면 또 켜지 않는다 (포털 켜기에서 같이 불러도 두 번 뜨지 않게)
$busy = (netstat -ano | Select-String ':8767' | Select-String 'LISTENING')
if ($busy) {
    Write-Host '촬영 준비 사이트가 이미 켜져 있습니다. 이 창은 닫아도 됩니다.'
    Start-Sleep -Seconds 10
    exit 0
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
