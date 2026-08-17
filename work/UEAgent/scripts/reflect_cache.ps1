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
    [string]$Manifest,
    [string]$GeneratorFingerprint,
    [switch]$Repair,
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

function Resolve-ManifestPath {
    if ($Manifest) { return [IO.Path]::GetFullPath($Manifest) }
    $root = Resolve-ProjectRoot
    if (-not $root) { throw 'reconcile requires -ProjectRoot or -RouteFile.' }
    return (Join-Path $root 'Saved\UEAgent\cache-manifest.json')
}

function Resolve-GeneratorFingerprint {
    if ($GeneratorFingerprint) { return [string]$GeneratorFingerprint }
    if (-not $RouteFile) { return $null }
    try {
        $route = Read-JsonFile ((Resolve-Path -LiteralPath $RouteFile).Path) 'route file'
        $parts = @($route.vibeUEPatchSha256, $route.vibeUEMcpShutdownGuardPatchSha256,
            $route.engineNiagaraPatchSha256,
            $route.engineNiagaraAuthoringPatchSha256, $route.mcpToolSearchPatchSha256) | Where-Object { $_ }
        if ($parts.Count -eq 0) { return $null }
        $sha = [Security.Cryptography.SHA256]::Create()
        try { return ([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::UTF8.GetBytes(($parts -join '|'))))).Replace('-', '').ToLowerInvariant() }
        finally { $sha.Dispose() }
    } catch { return $null }
}

function Get-GamePackagePath($ProjectRoot, $SourceFile) {
    if (-not $ProjectRoot -or -not $SourceFile) { return $null }
    $content = (Resolve-Path -LiteralPath (Join-Path $ProjectRoot 'Content')).Path
    $source = (Resolve-Path -LiteralPath $SourceFile).Path
    $prefix = $content.TrimEnd('\') + '\'
    if (-not $source.StartsWith($prefix, [StringComparison]::OrdinalIgnoreCase) -or
        -not $source.EndsWith('.uasset', [StringComparison]::OrdinalIgnoreCase)) { return $null }
    $relative = $source.Substring($prefix.Length, $source.Length - $prefix.Length - '.uasset'.Length)
    return '/Game/' + $relative.Replace('\', '/')
}

function Get-SourceHash($Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try { return (Get-FileHash -Algorithm SHA256 -LiteralPath $Path).Hash.ToLowerInvariant() }
    catch { return $null }
}

function Read-CacheManifest($Path) {
    if (-not $Path -or -not (Test-Path -LiteralPath $Path)) { return $null }
    try {
        $value = Read-JsonFile $Path 'cache manifest'
        if ($value.schema -eq 'ueagent-cache-manifest-v1') { return $value }
    } catch { }
    return $null
}

function Write-CacheManifest($Path, $ManifestObject) {
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
    [IO.File]::WriteAllText($Path, ($ManifestObject | ConvertTo-Json -Depth 20), [Text.UTF8Encoding]::new($false))
}

function Set-CacheSourceMetadata($Path, $ProjectRoot, $SourceFile) {
    $source = Get-Item -LiteralPath $SourceFile
    $package = Get-GamePackagePath $ProjectRoot $SourceFile
    if (-not $package) { throw "Cannot derive /Game package path for $SourceFile" }
    $fileValue = ((Resolve-Path -LiteralPath $SourceFile).Path).Replace('\', '/')
    $text = Get-Content -Raw -LiteralPath $Path
    $replacements = @{
        '(?m)^src:\s*.*$' = "src: $package"
        '(?m)^file:\s*.*$' = "file: $fileValue"
        '(?m)^mtime:\s*.*$' = "mtime: $($source.LastWriteTimeUtc.ToString('o'))"
        '(?m)^size:\s*.*$' = "size: $([int64]$source.Length)"
    }
    foreach ($pattern in $replacements.Keys) {
        $text = [Regex]::Replace($text, $pattern, $replacements[$pattern])
    }
    [IO.File]::WriteAllText($Path, $text, [Text.UTF8Encoding]::new($false))
}

function Get-OrphanTarget($SourceFiles, $ManifestEntry) {
    if (-not $ManifestEntry -or -not $ManifestEntry.sourceSha256 -or $null -eq $ManifestEntry.sourceBytes) { return @() }
    $matches = [Collections.Generic.List[string]]::new()
    foreach ($source in $SourceFiles | Where-Object { [int64]$_.Length -eq [int64]$ManifestEntry.sourceBytes }) {
        if ((Get-SourceHash $source.FullName) -eq [string]$ManifestEntry.sourceSha256) { $matches.Add($source.FullName) }
    }
    return @($matches)
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

function Get-CacheRecord($CachePath, [switch]$IncludeHash) {
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
    $hash = if ($IncludeHash) { (Get-FileHash -Algorithm SHA256 -LiteralPath $resolved).Hash.ToLowerInvariant() } else { $null }
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
            sha256 = $hash
            graphSha1 = if ($metadata.graph_sha1) { [string]$metadata.graph_sha1 } else { $null }
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
        graphSha1 = $Record.cache.graphSha1
        state = $Record.cache.state
    }
    if ($Record.cache.sha256) { $cache.sha256 = $Record.cache.sha256 }
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
    if (-not $root) { throw 'reconcile requires -ProjectRoot or -RouteFile.' }
    $content = Join-Path $root 'Content'
    if (-not (Test-Path -LiteralPath $content)) { throw "Content directory not found: $content" }
    $manifestPath = Resolve-ManifestPath
    $previous = Read-CacheManifest $manifestPath
    $previousEntries = @()
    if ($previous) { $previousEntries = @($previous.entries) }
    $currentGenerator = Resolve-GeneratorFingerprint
    $generatorChanged = $previous -and $previous.generatorFingerprint -and $currentGenerator -and
        [string]$previous.generatorFingerprint -ne [string]$currentGenerator
    $sourceFiles = @(Get-ChildItem -LiteralPath $content -Filter '*.uasset' -File -Recurse)
    $sidecars = @(Get-ChildItem -LiteralPath $content -Filter '*.uasset.ai.md' -File -Recurse)
    $entries = [Collections.Generic.List[object]]::new()
    $renamed = [Collections.Generic.List[object]]::new()
    $quarantined = [Collections.Generic.List[object]]::new()
    $orphans = [Collections.Generic.List[object]]::new()
    $stamp = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssfffZ')
    $contentPrefix = $content.TrimEnd('\') + '\'

    foreach ($sidecar in $sidecars) {
        try { $record = Get-CacheRecord $sidecar.FullName -IncludeHash } catch { continue }
        $sourcePath = $record.sourcePath
        if ($record.source.exists) {
            $entrySource = (Resolve-Path -LiteralPath $sourcePath).Path
            $entryState = if ($generatorChanged) { 'GENERATOR_CHANGED' } else { $record.cache.state }
            $entries.Add([ordered]@{
                sidecar = $record.path
                source = $entrySource
                package = Get-GamePackagePath $root $entrySource
                sourceBytes = [int64]$record.source.bytes
                sourceMtimeUtc = $record.source.mtimeUtc
                sourceSha256 = Get-SourceHash $entrySource
                cacheSha256 = $record.cache.sha256
                format = $record.cache.format
                state = $entryState
            })
            continue
        }

        $oldEntry = @($previousEntries | Where-Object {
            [string]$_.sidecar -and [IO.Path]::GetFullPath([string]$_.sidecar) -eq $record.path
        }) | Select-Object -First 1
        $candidatePaths = @(Get-OrphanTarget $sourceFiles $oldEntry)
        if ($Repair -and $candidatePaths.Count -eq 1) {
            $targetSource = [string]$candidatePaths[0]
            $targetSidecar = $targetSource + '.ai.md'
            if (-not (Test-Path -LiteralPath $targetSidecar)) {
                Move-Item -LiteralPath $record.path -Destination $targetSidecar
                Set-CacheSourceMetadata $targetSidecar $root $targetSource
                $renamed.Add([ordered]@{ from = $record.path; to = $targetSidecar; reason = 'source_sha256_match' })
                $record = Get-CacheRecord $targetSidecar -IncludeHash
                $entryState = if ($generatorChanged) { 'GENERATOR_CHANGED' } else { $record.cache.state }
                $entries.Add([ordered]@{
                    sidecar = $record.path
                    source = (Resolve-Path -LiteralPath $targetSource).Path
                    package = Get-GamePackagePath $root $targetSource
                    sourceBytes = [int64]$record.source.bytes
                    sourceMtimeUtc = $record.source.mtimeUtc
                    sourceSha256 = Get-SourceHash $targetSource
                    cacheSha256 = $record.cache.sha256
                    format = $record.cache.format
                    state = $entryState
                })
                continue
            }
        }

        $orphan = [ordered]@{ sidecar = $record.path; src = $record.metadata.src; candidates = @($candidatePaths); state = 'ORPHAN' }
        $orphans.Add($orphan)
        $entries.Add([ordered]@{
            sidecar = $record.path
            source = $null
            package = if ($record.metadata.src) { [string]$record.metadata.src } else { $null }
            sourceBytes = if ($record.metadata.Contains('size')) { [int64]$record.metadata.size } else { $null }
            sourceMtimeUtc = if ($record.metadata.mtime) { [string]$record.metadata.mtime } else { $null }
            sourceSha256 = if ($oldEntry -and $oldEntry.sourceSha256) { [string]$oldEntry.sourceSha256 } else { $null }
            cacheSha256 = $record.cache.sha256
            format = $record.cache.format
            state = 'ORPHAN'
        })
        if ($Repair -and $candidatePaths.Count -eq 0) {
            # ponytail: quarantine cache-only files; never delete user context.
            $relative = if ($record.path.StartsWith($contentPrefix, [StringComparison]::OrdinalIgnoreCase)) {
                $record.path.Substring($contentPrefix.Length)
            } else { Split-Path -Leaf $record.path }
            $destination = Join-Path (Join-Path $root "Saved\UEAgent\cache-orphans\$stamp") $relative
            $destinationParent = Split-Path -Parent $destination
            New-Item -ItemType Directory -Path $destinationParent -Force | Out-Null
            Move-Item -LiteralPath $record.path -Destination $destination
            $quarantined.Add([ordered]@{ from = $record.path; to = $destination; reason = 'source_missing' })
        }
    }

    $manifestObject = [ordered]@{
        schema = 'ueagent-cache-manifest-v1'
        projectRoot = $root
        generatedAtUtc = [DateTime]::UtcNow.ToString('o')
        generatorFingerprint = $currentGenerator
        entries = @($entries)
    }
    Write-CacheManifest $manifestPath $manifestObject
    return [ordered]@{
        schema = 'ueagent-cache-reconcile-v1'
        projectRoot = $root
        manifest = $manifestPath
        repair = [bool]$Repair
        sidecarCount = $sidecars.Count
        sourceCount = $sourceFiles.Count
        generatorChanged = [bool]$generatorChanged
        freshCount = @($entries | Where-Object { $_.state -eq 'FRESH' }).Count
        staleCount = @($entries | Where-Object { $_.state -in @('STALE', 'UNSUPPORTED_FORMAT', 'GENERATOR_CHANGED') }).Count
        orphanCount = $orphans.Count
        repairedRenames = @($renamed)
        quarantined = @($quarantined)
        orphans = @($orphans)
        next = if ($orphans.Count -and -not $Repair) { @('rerun with -Repair to rehome unique hash matches and quarantine unresolved sidecars') } else { @() }
    }
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

Write-Result (Get-ReadView (Get-CacheRecord (Resolve-SidecarPath) -IncludeHash:($View -eq 'full')))
