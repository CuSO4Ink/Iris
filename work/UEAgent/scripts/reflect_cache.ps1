[CmdletBinding()]
param(
    [ValidateSet('read', 'reconcile')]
    [string]$Action = 'read',

    [string]$AssetPath,
    [string]$Sidecar,
    [string]$ProjectRoot,
    [string]$RouteFile,

    [ValidateSet('summary', 'refs', 'detail', 'full')]
    [string]$View = 'summary',
    [string[]]$Section,
    [int]$MaxItems = 64,
    [string]$OutFile,
    [switch]$Pretty
)

$ErrorActionPreference = 'Stop'
if ($MaxItems -lt 1) { throw 'MaxItems must be positive.' }

$KnownCacheFormats = @(
    'vibeue-material-cache-v2',
    'vibeue-material-function-cache-v1',
    'vibeue-material-instance-cache-v1',
    'vibeue-blueprint-cache-v1',
    'vibeue-niagara-system-cache-v1'
)

function Read-JsonFile($Path, $Label) {
    if (-not (Test-Path -LiteralPath $Path)) { throw "$Label not found: $Path" }
    try { return (Get-Content -Raw -LiteralPath $Path | ConvertFrom-Json) }
    catch { throw "Invalid $Label`: $($_.Exception.Message)" }
}

function Resolve-ProjectRoot {
    if ($ProjectRoot) { return (Resolve-Path -LiteralPath $ProjectRoot).Path }
    if ($RouteFile) {
        $routePath = (Resolve-Path -LiteralPath $RouteFile).Path
        $route = Read-JsonFile $routePath 'route file'
        if ($route.schema -ne 'ueagent-route-v1') { throw "Unsupported route schema: $($route.schema)" }
        return (Split-Path ([string]$route.uProject) -Parent)
    }
    return $null
}

function Get-PackagePath($Path) {
    if (-not $Path -or -not $Path.StartsWith('/Game/', [StringComparison]::OrdinalIgnoreCase)) { return $null }
    $slash = $Path.LastIndexOf('/')
    $dot = $Path.IndexOf('.', $slash)
    if ($dot -gt $slash) { return $Path.Substring(0, $dot) }
    return $Path
}

function Resolve-SidecarPath {
    if ($Sidecar) { return (Resolve-Path -LiteralPath $Sidecar).Path }
    $root = Resolve-ProjectRoot
    $package = Get-PackagePath $AssetPath
    if (-not $root -or -not $package) {
        throw 'Provide -Sidecar or both -AssetPath (/Game/...) and -ProjectRoot/-RouteFile.'
    }
    $relative = $package.Substring('/Game/'.Length).Replace('/', '\')
    $source = Join-Path $root (Join-Path 'Content' ($relative + '.uasset'))
    return ($source + '.ai.md')
}

function Get-SourcePath($CachePath, $Metadata) {
    if ($CachePath -match '(?i)\.uasset\.ai\.md$') {
        $adjacent = $CachePath.Substring(0, $CachePath.Length - 6)
        if (Test-Path -LiteralPath $adjacent) { return $adjacent }
    }
    if ($Metadata.file -and (Test-Path -LiteralPath ([string]$Metadata.file))) {
        return (Resolve-Path -LiteralPath ([string]$Metadata.file)).Path
    }
    return $null
}

function Get-Sections($Lines) {
    $sections = [ordered]@{}
    $current = $null
    foreach ($line in $Lines) {
        if ($line -match '^##\s+(.+?)\s*$') {
            $current = $matches[1]
            $sections[$current] = [Collections.Generic.List[string]]::new()
            continue
        }
        if ($current) { $sections[$current].Add([string]$line) }
    }
    return $sections
}

function Get-Metadata($Lines) {
    $metadata = [ordered]@{}
    $inside = $false
    foreach ($line in $Lines) {
        if ($line -match '^```yaml\s*$') { $inside = $true; continue }
        if ($inside -and $line -match '^```\s*$') { break }
        if (-not $inside -or $line -notmatch '^([A-Za-z_][A-Za-z0-9_]*)\s*:\s*(.*)$') { continue }
        $key = $matches[1]
        $value = $matches[2].Trim()
        if ($value -match '^(-?\d+)$') { $metadata[$key] = [int64]$value }
        elseif ($value -match '^(true|false)$') { $metadata[$key] = [bool]::Parse($value) }
        else { $metadata[$key] = $value }
    }
    return $metadata
}

function Get-SectionLines($Sections, $Name) {
    if ($Sections.Contains($Name)) { return @($Sections[$Name]) }
    return @()
}

function Get-Dependencies($Sections) {
    # ponytail: direct deps only; recursive expansion belongs to an explicit per-asset read.
    $deps = [Collections.Generic.List[string]]::new()
    if (-not $Sections.Contains('Deps')) { return @() }
    foreach ($line in @($Sections['Deps'])) {
        foreach ($match in [Regex]::Matches([string]$line, '/Game/[^\s,\)\]\}`]+')) {
            $value = $match.Value.TrimEnd([char[]]@('.', ';', [char]39, [char]34))
            if (-not $deps.Contains($value)) { $deps.Add($value) }
        }
    }
    return @($deps)
}

function Get-SemanticReferences($Sections) {
    $references = [Collections.Generic.List[object]]::new()
    if (-not $Sections.Contains('Deps')) { return @() }
    foreach ($line in @($Sections['Deps'])) {
        if ([string]$line -notmatch '^\s*([A-Z][A-Z0-9_]*):\s+(/Game/[^\s|]+)(?:\s+\|\s+(.+))?$') { continue }
        $kind = $matches[1]
        $target = $matches[2]
        $details = $matches[3]
        $reference = [ordered]@{ target = $target }
        foreach ($detail in @($details -split '\s+\|\s+')) {
            if ($detail -match '^([a-z_][a-z0-9_]*)=(.+)$') { $reference[$matches[1]] = $matches[2] }
        }
        if (-not $reference.Contains('relation')) {
            $reference.relation = switch ($kind) {
                'MF' { 'FunctionCall' }
                'MPC' { 'CollectionParameter' }
                'TEX' { 'Texture' }
                'PARENT' { 'Parent' }
                default { $kind }
            }
        }
        $references.Add([pscustomobject]$reference)
    }
    return @($references)
}

function Get-UsefulLines($Lines) {
    @($Lines | Where-Object { [string]$_ -and [string]$_ -ne '-' })
}

function Get-CacheRecord($CachePath) {
    if (-not (Test-Path -LiteralPath $CachePath)) { throw "Cache sidecar not found: $CachePath" }
    $resolved = (Resolve-Path -LiteralPath $CachePath).Path
    $lines = [IO.File]::ReadAllLines($resolved)
    $metadata = Get-Metadata $lines
    $sections = Get-Sections $lines
    $sourcePath = Get-SourcePath $resolved $metadata
    $sidecarInfo = Get-Item -LiteralPath $resolved
    $sourceInfo = if ($sourcePath -and (Test-Path -LiteralPath $sourcePath)) { Get-Item -LiteralPath $sourcePath } else { $null }
    $declaredSize = if ($metadata.Contains('size')) { [int64]$metadata.size } else { $null }
    $format = if ($metadata.format) { [string]$metadata.format } else { $null }
    $formatKnown = $format -and $KnownCacheFormats -contains $format
    $sourceMetadataCurrent = [bool]$sourceInfo -and
        $sidecarInfo.LastWriteTimeUtc -ge $sourceInfo.LastWriteTimeUtc -and
        ($null -eq $declaredSize -or $declaredSize -lt 0 -or [int64]$sourceInfo.Length -eq $declaredSize)
    $state = if (-not $sourceInfo) { 'ORPHAN' }
        elseif (-not $formatKnown) { 'UNSUPPORTED_FORMAT' }
        elseif (-not $sourceMetadataCurrent) { 'STALE' }
        else { 'FRESH' }
    $logic = Get-UsefulLines (Get-SectionLines $sections 'Logic')
    $deps = Get-Dependencies $sections
    $references = @(Get-SemanticReferences $sections)
    return [ordered]@{
        path = $resolved
        lines = $lines
        metadata = $metadata
        sections = $sections
        sourcePath = $sourcePath
        source = if ($sourceInfo) {
            [ordered]@{ exists = $true; bytes = [int64]$sourceInfo.Length; mtimeUtc = $sourceInfo.LastWriteTimeUtc.ToString('o') }
        } else {
            [ordered]@{ exists = $false; bytes = $null; mtimeUtc = $null }
        }
        cache = [ordered]@{
            bytes = [int64]$sidecarInfo.Length
            mtimeUtc = $sidecarInfo.LastWriteTimeUtc.ToString('o')
            format = $format
            state = $state
        }
        stats = [ordered]@{
            sections = @($sections.Keys)
            logicLines = $logic.Count
            dependencyCount = $deps.Count
            referenceCount = $references.Count
            parameterLines = (Get-UsefulLines (Get-SectionLines $sections 'Params')).Count
        }
        dependencies = $deps
        references = $references
    }
}

function New-Summary($Record) {
    $cache = [ordered]@{
        format = $Record.cache.format
        state = $Record.cache.state
    }
    $stats = [ordered]@{ sections = $Record.stats.sections }
    foreach ($name in @('logicLines', 'dependencyCount', 'referenceCount', 'parameterLines')) {
        if ([int]$Record.stats[$name] -gt 0) { $stats[$name] = [int]$Record.stats[$name] }
    }
    return [ordered]@{ cache = $cache; stats = $stats }
}

function Add-SectionView($Target, $Record, $Names, $Limit) {
    $blocks = [ordered]@{}
    $truncated = [Collections.Generic.List[string]]::new()
    foreach ($name in $Names) {
        if (-not $Record.sections.Contains($name)) { continue }
        $lines = @(Get-UsefulLines (Get-SectionLines $Record.sections $name))
        if ($lines.Count -gt $Limit) {
            $blocks[$name] = @($lines | Select-Object -First $Limit)
            $truncated.Add($name)
        } else {
            $blocks[$name] = $lines
        }
    }
    $Target['blocks'] = $blocks
    $Target['truncated'] = @($truncated)
}

function Get-ReadView($Record) {
    $result = New-Summary $Record
    if ($View -eq 'refs') {
        $result.dependencies = @($Record.dependencies | Select-Object -First $MaxItems)
        $result.dependenciesTruncated = $Record.dependencies.Count -gt $MaxItems
        if ($Record.references.Count -gt 0) {
            $result.references = @($Record.references | Select-Object -First $MaxItems)
            $result.referencesTruncated = $Record.references.Count -gt $MaxItems
        }
        return $result
    }
    if ($View -eq 'detail') {
        $names = if ($Section) { @($Section) } else { @('Params', 'Interface', 'Outputs', 'Deps', 'Custom', 'Summary', 'Logic') }
        Add-SectionView $result $Record $names $MaxItems
        return $result
    }
    if ($View -eq 'full') {
        if ($Section) {
            Add-SectionView $result $Record @($Section) ([int]::MaxValue)
            return $result
        } else {
            return [ordered]@{
                cache = $result.cache
                stats = $result.stats
                raw = [IO.File]::ReadAllText($Record.path)
            }
        }
        return $result
    }
    return $result
}

function Get-ReconcileView {
    $root = Resolve-ProjectRoot
    if (-not $root) { throw 'reconcile requires a project root or route.' }
    $content = Join-Path $root 'Content'
    $items = [Collections.Generic.List[object]]::new()
    foreach ($sidecar in Get-ChildItem -LiteralPath $content -Filter '*.uasset.ai.md' -Recurse -File) {
        $record = Get-CacheRecord $sidecar.FullName
        $items.Add((New-Summary $record))
    }
    # Caches are disposable. Report stale/orphan entries; never infer renames or move files.
    return [ordered]@{ action = 'reconcile'; entries = @($items); next = 'Regenerate stale or missing caches on the next asset save.' }
}

function Write-Result($Object) {
    $json = if ($Pretty) { $Object | ConvertTo-Json -Depth 10 } else { $Object | ConvertTo-Json -Depth 10 -Compress }
    if ($OutFile) {
        $parent = Split-Path $OutFile -Parent
        if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
        [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
    } else { $json }
}

if ($Action -eq 'reconcile') {
    Write-Result (Get-ReconcileView)
    exit 0
}

Write-Result (Get-ReadView (Get-CacheRecord (Resolve-SidecarPath)))
