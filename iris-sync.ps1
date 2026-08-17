# Scoped Iris sync: commit selected paths, fetch, rebase when safe, then push.
# Examples:
#   powershell -File iris-sync.ps1 -Paths work/MyProject
#   powershell -File iris-sync.ps1 -Paths work/MyProject,README.md -m "update"
#   powershell -File iris-sync.ps1 -Paths work/MyProject -Check
[CmdletBinding()]
param(
    [string]$m = '',
    [string[]]$Paths = @(),
    [switch]$PushOnly,
    [switch]$Check
)

$ErrorActionPreference = 'Stop'

function Invoke-Git {
    param([Parameter(Mandatory = $true)][string[]]$Arguments)

    & git @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "git $($Arguments -join ' ') failed with exit code $LASTEXITCODE"
    }
}

function Assert-ProjectBoundary {
    param(
        [Parameter(Mandatory = $true)][string]$RepoRoot,
        [Parameter(Mandatory = $true)][string[]]$ScopedPaths
    )

    $projectNames = @(
        $ScopedPaths | ForEach-Object {
            if ($_ -match '^work/([^/]+)(?:/|$)') { $Matches[1] }
        } | Select-Object -Unique
    )

    foreach ($projectName in $projectNames) {
        $projectRoot = Join-Path $RepoRoot "work\$projectName"
        if (-not (Test-Path -LiteralPath $projectRoot -PathType Container)) { continue }

        if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'AI-BRIEF.md') -PathType Leaf)) {
            throw "work/$projectName is missing AI-BRIEF.md."
        }
        if (Test-Path -LiteralPath (Join-Path $RepoRoot "archive\$projectName") -PathType Container) {
            throw "$projectName exists in both work/ and archive/."
        }

        $completed = @(
            Get-ChildItem -LiteralPath $projectRoot -Recurse -File -Filter 'BACKLOG.md' |
                Select-String -Pattern '^\s*[-*]\s+\[[xX]\]'
        )
        if ($completed.Count -gt 0) {
            $locations = $completed | ForEach-Object {
                "$($_.Path.Substring($RepoRoot.Length + 1).Replace('\', '/')):$($_.LineNumber)"
            }
            throw "Completed items remain in active BACKLOG files: $($locations -join ', ')"
        }

        $processDirs = @(
            Get-ChildItem -LiteralPath $projectRoot -Recurse -Directory -Force |
                Where-Object { $_.Name -in @('.venv', '__pycache__', '.pytest_cache', '.session_tmps', '.runtime', 'runs') }
        )
        if ($processDirs.Count -gt 0) {
            $locations = $processDirs | ForEach-Object {
                $_.FullName.Substring($RepoRoot.Length + 1).Replace('\', '/')
            }
            throw "Process directories belong under tmp/: $($locations -join ', ')"
        }
    }

    if ($projectNames.Count -gt 0) {
        Write-Host "boundary OK: $($projectNames -join ', ')" -ForegroundColor Green
    }
}

try {
    $repoRoot = (& git rev-parse --show-toplevel 2>$null).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $repoRoot) { throw 'Current directory is not a Git repository.' }

    Push-Location $repoRoot
    try {
        $branch = (& git branch --show-current).Trim()
        if ($LASTEXITCODE -ne 0 -or -not $branch) { throw 'Detached HEAD is not supported.' }

        $scopedPaths = @()
        foreach ($path in @($Paths | ForEach-Object { [string]$_ -split ',' })) {
            $candidate = ([string]$path).Trim().Replace('\', '/')
            if ($candidate.StartsWith('./')) { $candidate = $candidate.Substring(2) }
            if (-not $candidate -or [IO.Path]::IsPathRooted($candidate) -or
                $candidate -in @('.', '/', '.\') -or $candidate.StartsWith('../') -or
                $candidate.Contains('/../') -or $candidate.IndexOfAny([char[]]'*?[') -ge 0 -or
                $candidate.StartsWith(':')) {
                throw "Unsafe or repository-wide path scope: '$path'"
            }
            $scopedPaths += $candidate.TrimEnd('/')
        }
        $scopedPaths = @($scopedPaths | Select-Object -Unique)

        if (($Check -or -not $PushOnly) -and $scopedPaths.Count -eq 0) {
            throw 'Provide at least one project or explicit shared path with -Paths.'
        }

        Assert-ProjectBoundary -RepoRoot $repoRoot -ScopedPaths $scopedPaths

        Write-Host "=== iris-sync @ $branch ===" -ForegroundColor Cyan

        if ($Check) {
            Invoke-Git -Arguments (@('status', '--short', '--') + $scopedPaths)
            Write-Host "scope OK: $($scopedPaths -join ', ')" -ForegroundColor Green
            return
        }

        if (-not $PushOnly) {
            & git diff --cached --quiet
            if ($LASTEXITCODE -eq 1) { throw 'Index already contains staged changes; commit or unstage them first.' }
            if ($LASTEXITCODE -gt 1) { throw 'Could not inspect the Git index.' }

            Invoke-Git -Arguments (@('add', '-A', '--') + $scopedPaths)

            & git diff --cached --quiet
            if ($LASTEXITCODE -eq 1) {
                if (-not $m) { $m = 'sync: ' + (Get-Date -Format 'yyyy-MM-dd HH:mm') }
                Invoke-Git -Arguments @('commit', '-m', $m)
            } elseif ($LASTEXITCODE -gt 1) {
                throw 'Could not inspect staged changes.'
            } else {
                Write-Host 'No scoped changes to commit.' -ForegroundColor DarkGray
            }
        }

        Invoke-Git -Arguments @('fetch', 'origin')

        & git show-ref --verify --quiet "refs/remotes/origin/$branch"
        $hasRemoteBranch = $LASTEXITCODE -eq 0
        if ($LASTEXITCODE -gt 1) { throw 'Could not inspect the remote branch.' }

        $behind = 0
        if ($hasRemoteBranch) {
            $counts = ((& git rev-list --left-right --count "origin/$branch...HEAD").Trim() -split '\s+')
            if ($LASTEXITCODE -ne 0 -or $counts.Count -lt 2) { throw 'Could not compare local and remote history.' }
            $behind = [int]$counts[0]
            Write-Host "remote: behind=$behind ahead=$([int]$counts[1])" -ForegroundColor Yellow
        }

        if ($behind -gt 0) {
            if (@(& git status --porcelain).Count -gt 0) {
                throw 'Remote is ahead and unrelated working-tree changes remain; rebase was not attempted.'
            }
            Invoke-Git -Arguments @('pull', '--rebase', 'origin', $branch)
        }

        if ($hasRemoteBranch) {
            $ahead = [int]((& git rev-list --count "origin/$branch..HEAD").Trim())
            if ($LASTEXITCODE -ne 0) { throw 'Could not inspect commits pending push.' }
            if ($ahead -gt 0) { Invoke-Git -Arguments @('push', 'origin', $branch) }
            else { Write-Host 'Already synchronized.' -ForegroundColor DarkGray }
        } else {
            Invoke-Git -Arguments @('push', '--set-upstream', 'origin', $branch)
        }

        Invoke-Git -Arguments @('status', '-sb')
    } finally {
        Pop-Location
    }
} catch {
    Write-Host "[X] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
