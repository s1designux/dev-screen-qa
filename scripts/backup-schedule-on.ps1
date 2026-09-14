# 매일 오후 4시 자동 백업을 등록한다. 한 번만 실행하면 된다.
# 작업 스케줄러의 DAILY 예약은 일반 권한으로도 걸린다(ONLOGON 과 다르다).
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$bat = Join-Path $Root '백업-지금-윈도우.bat'

if (-not (Test-Path $bat)) {
    Write-Host ''
    Write-Host '자동 백업을 걸지 못했습니다.'
    Write-Host "필요한 파일을 찾지 못했습니다: $bat"
    exit 1
}

$out = & schtasks /Create /TN '검수포털 백업' /TR "\"$bat\"" /SC DAILY /ST 16:00 /F 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host ''
    Write-Host '자동 백업을 걸지 못했습니다.'
    Write-Host ($out | Out-String).Trim()
    Write-Host '이 PC의 권한으로는 예약을 걸 수 없습니다. 백업이 필요할 때 백업-지금-윈도우.bat 을 눌러 직접 하세요.'
    exit 1
}

Write-Host ''
Write-Host '자동 백업을 등록했습니다. 매일 오후 4시에 돌아갑니다.'
