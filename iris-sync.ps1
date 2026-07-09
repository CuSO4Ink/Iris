# iris-sync.ps1 - 一键同步当前git仓库: commit -> fetch -> rebase pull -> push
# 用法(在任意git仓库目录下):
#   powershell -File iris-sync.ps1                    # 自动生成commit信息
#   powershell -File iris-sync.ps1 -m "本次说明"       # 自定义commit信息
#   powershell -File iris-sync.ps1 -PushOnly          # 跳过commit,只pull+push
param([string]$m = "", [switch]$PushOnly)
$ErrorActionPreference = "Continue"
git config i18n.commitEncoding utf-8 | Out-Null

# 0. 确认在git仓库内
$inRepo = (git rev-parse --is-inside-work-tree 2>$null)
if ($inRepo -ne "true") { Write-Host "[X] 当前目录不是git仓库: $(Get-Location)" -ForegroundColor Red; exit 1 }
$branch = (git branch --show-current).Trim()
Write-Host "=== iris-sync @ $branch ($(Get-Location)) ===" -ForegroundColor Cyan

# 1. commit本地改动
if (-not $PushOnly) {
    $dirty = git status --porcelain
    if ($dirty) {
        git add -A
        if (-not $m) { $m = "sync: " + (Get-Date -Format "yyyy-MM-dd HH:mm") }
        git commit -m $m | Out-Null
        Write-Host "[1] committed: $m" -ForegroundColor Green
    } else { Write-Host "[1] 无本地改动,跳过commit" -ForegroundColor DarkGray }
} else { Write-Host "[1] PushOnly模式,跳过commit" -ForegroundColor DarkGray }

# 2. fetch + 检查落后
git fetch origin 2>$null
$counts = (git rev-list --left-right --count "origin/$branch...HEAD" 2>$null) -split "\s+"
$behind = if ($counts.Count -ge 1) { [int]$counts[0] } else { 0 }
$ahead  = if ($counts.Count -ge 2) { [int]$counts[1] } else { 0 }
Write-Host "[2] 远端对比: behind=$behind ahead=$ahead" -ForegroundColor Yellow

# 3. 落后则rebase pull
if ($behind -gt 0) {
    Write-Host "[3] 落后$behind个commit,执行 rebase pull..." -ForegroundColor Yellow
    git pull --rebase origin $branch 2>&1 | Out-Host
    # 检测rebase是否卡在冲突
    if (Test-Path (Join-Path (git rev-parse --git-dir) "rebase-merge")) {
        Write-Host "[X] rebase遇到冲突!已停止。请手动解决冲突后:" -ForegroundColor Red
        Write-Host "    解决文件 -> git add <文件> -> git rebase --continue -> 再次运行本脚本" -ForegroundColor Red
        Write-Host "    或放弃: git rebase --abort" -ForegroundColor Red
        exit 2
    }
    Write-Host "[3] rebase完成,无冲突" -ForegroundColor Green
} else { Write-Host "[3] 未落后,无需pull" -ForegroundColor DarkGray }

# 4. push
$ahead2 = (git rev-list --count "origin/$branch..HEAD" 2>$null)
if ([int]$ahead2 -gt 0) {
    Write-Host "[4] 推送$ahead2个commit..." -ForegroundColor Yellow
    git push origin $branch 2>&1 | Out-Host
    Write-Host "[4] push完成" -ForegroundColor Green
} else { Write-Host "[4] 无待推送,已是最新" -ForegroundColor DarkGray }

Write-Host "=== 同步完成 ===" -ForegroundColor Cyan
git status -sb 2>$null | Out-Host