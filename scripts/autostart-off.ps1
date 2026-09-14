# 자동 시작을 해제한다. 그 뒤에는 포털-켜기-윈도우.bat 을 눌러서 직접 켠다.
$ErrorActionPreference = 'Stop'
$link = Join-Path ([Environment]::GetFolderPath('Startup')) '검수포털 자동시작.lnk'

if (-not (Test-Path $link)) {
    Write-Host ''
    Write-Host '자동 시작은 원래 걸려 있지 않았습니다. 바뀐 것은 없습니다.'
    Write-Host '포털이 필요하면 포털-켜기-윈도우.bat 을 눌러서 직접 켜세요.'
    exit 0
}

try {
    Remove-Item $link -Force
}
catch {
    Write-Host ''
    Write-Host '자동 시작을 끄지 못했습니다.'
    Write-Host $_.Exception.Message
    exit 1
}

Write-Host ''
Write-Host '자동 시작을 껐습니다.'
Write-Host '포털이 필요하면 포털-켜기-윈도우.bat 을 눌러서 직접 켜세요.'
