# 검수 데이터와 이미지를 복사한다. 7일치 보관. 원본은 건드리지 않는다.
# 사람이 눌러서 쓰기도 하고, 오후 4시 예약이 대신 부르기도 한다.
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path $Root).Path
$src  = Join-Path $Root 'mvp0'
$dst  = Join-Path $env:USERPROFILE 'dev-screen-qa-백업'
$out  = Join-Path $dst (Get-Date -Format 'yyyyMMdd')

if (-not (Test-Path $src)) {
    Write-Host ''
    Write-Host '백업하지 못했습니다.'
    Write-Host "검수 자료 폴더를 찾지 못했습니다: $src"
    exit 1
}

try {
    New-Item -ItemType Directory -Path $out -Force | Out-Null

    $db = Join-Path $src 'mvp0-real.db'
    if (Test-Path $db) {
        Copy-Item $db (Join-Path $out 'mvp0-real.db') -Force
    }

    $uploads = Join-Path $src 'uploads'
    if (Test-Path $uploads) {
        & robocopy $uploads (Join-Path $out 'uploads') /MIR /NFL /NDL /NJH /NJS | Out-Null
        if ($LASTEXITCODE -ge 8) { throw "이미지 복사에 실패했습니다 (robocopy $LASTEXITCODE)" }
    }

    $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
    Add-Content -Path (Join-Path $dst '백업기록.txt') -Value "$stamp 백업 완료 - $out" -Encoding UTF8

    # 7일치만 남기기
    $cut = (Get-Date).AddDays(-7)
    Get-ChildItem $dst -Directory | Where-Object { $_.LastWriteTime -lt $cut } | Remove-Item -Recurse -Force

    Write-Host ''
    Write-Host "백업했습니다: $out"
}
catch {
    Write-Host ''
    Write-Host '백업하지 못했습니다.'
    Write-Host $_.Exception.Message
    exit 1
}
