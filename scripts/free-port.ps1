# 그 자리(포트)를 쓰고 있는 옛 서버를 끈다. 우리 것(python)일 때만 끈다.
# portal-start.ps1 / capture-start.ps1 이 함께 쓴다.

function 포트비우기 {
    param([int]$Port, [string]$Name)

    $줄 = @(netstat -ano | Select-String ":$Port\s" | Select-String 'LISTENING')
    if ($줄.Count -eq 0) { return $true }

    $번호들 = @()
    foreach ($한줄 in $줄) {
        $칸 = ($한줄.ToString().Trim() -split '\s+')
        $끝 = $칸[$칸.Length - 1]
        if ($끝 -match '^\d+$' -and [int]$끝 -gt 0) { $번호들 += [int]$끝 }
    }
    $번호들 = @($번호들 | Sort-Object -Unique)
    if ($번호들.Count -eq 0) { return $true }

    foreach ($번호 in $번호들) {
        $것 = Get-Process -Id $번호 -ErrorAction SilentlyContinue
        if (-not $것) { continue }
        if ($것.ProcessName -notmatch '^python') {
            Write-Host ''
            Write-Host "$Name 자리를 다른 프로그램이 쓰고 있습니다: $($것.ProcessName)"
            Write-Host '그 프로그램을 끄고 다시 눌러 주세요.'
            return $false
        }
        Write-Host "$Name 옛 창을 끕니다. 최신으로 다시 켭니다."
        Stop-Process -Id $번호 -Force -ErrorAction SilentlyContinue
    }

    for ($차례 = 0; $차례 -lt 20; $차례++) {
        Start-Sleep -Milliseconds 300
        $아직 = @(netstat -ano | Select-String ":$Port\s" | Select-String 'LISTENING')
        if ($아직.Count -eq 0) { return $true }
    }

    Write-Host ''
    Write-Host "$Name 옛 창이 끝나지 않았습니다. 잠시 뒤 다시 눌러 주세요."
    return $false
}
