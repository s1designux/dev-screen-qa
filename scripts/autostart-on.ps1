# PC를 켜고 로그인하면 검수 포털이 저절로 켜지게 등록한다.
# 윈도우 '시작프로그램' 폴더에 바로가기를 하나 넣는 방식이라 관리자 권한이 필요 없다.
# (작업 스케줄러의 ONLOGON 은 관리자 권한을 요구해서 사내 PC에서 쓸 수 없다.)
param([Parameter(Mandatory=$true)][string]$Root)

$ErrorActionPreference = 'Stop'
try {
    $Root = (Resolve-Path $Root).Path
    $run = Join-Path $Root '포털-자동시작-실행.bat'
    if (-not (Test-Path $run)) {
        Write-Host ''
        Write-Host '자동 시작을 걸지 못했습니다.'
        Write-Host "필요한 파일을 찾지 못했습니다: $run"
        exit 1
    }

    $link = Join-Path ([Environment]::GetFolderPath('Startup')) '검수포털 자동시작.lnk'
    $w = New-Object -ComObject WScript.Shell
    $s = $w.CreateShortcut($link)
    $s.TargetPath = $run
    $s.WorkingDirectory = $Root
    $s.Description = '검수 포털 자동 시작'
    $s.Save()

    if (-not (Test-Path $link)) {
        Write-Host ''
        Write-Host '자동 시작을 걸지 못했습니다. 바로가기가 만들어지지 않았습니다.'
        exit 1
    }

    Write-Host ''
    Write-Host '자동 시작을 등록했습니다.'
    Write-Host '이제 PC를 켜고 로그인하면 30초 뒤 포털이 저절로 켜집니다.'
    Write-Host '(검은 창이 하나 뜹니다. 그 창은 닫지 마세요 - 닫으면 포털이 꺼집니다)'
}
catch {
    Write-Host ''
    Write-Host '자동 시작을 걸지 못했습니다.'
    Write-Host $_.Exception.Message
    exit 1
}
