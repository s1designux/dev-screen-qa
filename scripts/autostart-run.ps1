# 로그인할 때 윈도우가 대신 실행한다. 검수 포털을 켜기만 한다.
# 사람이 직접 누르는 파일이 아니다.
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$portal = Join-Path $Root '포털-켜기-윈도우.bat'

if (-not (Test-Path $portal)) {
    Write-Host "포털-켜기-윈도우.bat 을 찾지 못했습니다: $portal"
    exit 1
}

Start-Process -FilePath $portal -WorkingDirectory $Root
