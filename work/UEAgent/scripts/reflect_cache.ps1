[CmdletBinding()]
param(
    [ValidateSet('read', 'diff', 'receipt', 'index', 'reconcile')]
    [string]$Action = 'read',

    [string]$AssetPath,
    [string]$Sidecar,
    [string]$BaseSidecar,
    [string]$ChangeAction = 'cache.readback',
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
            $route.engineNiagaraAuthoringPatchSha256, $route.mcpToolSearchV2PatchSha256,
            $route.mcpToolSearchV3PatchSha256) | Where-Object { $_ }
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

function Get-UsefulLines($Lines) {
    @($Lines | Where-Object { [string]$_ -and [string]$_ -ne '-' })
}

function Get-CacheRecord($CachePath) {
    if (-not (Test-Path -LiteralPath $CachePath)) { throw "Cache sidecar not found: $CachePath" }
    $resolved = (Resolve-Path -LiteralPath $CachePath).Path
    $lines = @(Get-Content -LiteralPath $resolved)
    $text = Get-Content -Raw -LiteralPath $resolved
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
    $fresh = $state -eq 'FRESH'
    $hash = (Get-FileHash -Algorithm SHA256 -LiteralPath $resolved).Hash.ToLowerInvariant()
    $logic = Get-UsefulLines (Get-SectionLines $sections 'Logic')
    $deps = Get-Dependencies $sections
    return [ordered]@{
        path = $resolved
        text = $text
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
            formatKnown = [bool]$formatKnown
            fresh = $fresh
            state = $state
        }
        stats = [ordered]@{
            sections = @($sections.Keys)
            logicLines = $logic.Count
            dependencyCount = $deps.Count
            parameterLines = (Get-UsefulLines (Get-SectionLines $sections 'Params')).Count
        }
        dependencies = $deps
    }
}

function New-Summary($Record, $ViewName) {
    $meta = $Record.metadata
    return [ordered]@{
        schema = 'reflect-cache-view-v1'
        view = $ViewName
        cache = [ordered]@{
            path = $Record.path
            source = $meta.src
            sourceFile = $Record.sourcePath
            format = $Record.cache.format
            graphSha1 = $Record.cache.graphSha1
            sha256 = $Record.cache.sha256
            fresh = $Record.cache.fresh
            state = $Record.cache.state
            formatKnown = $Record.cache.formatKnown
        }
        stats = $Record.stats
        availableViews = @('summary', 'refs', 'detail', 'full')
        next = [ordered]@{
            refs = 'read -View refs'
            detail = 'read -View detail -Section <name>'
            full = 'read -View full'
        }
    }
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
    $result = New-Summary $Record $View
    if ($View -eq 'refs') {
        $result.dependencies = @($Record.dependencies | Select-Object -First $MaxItems)
        $result.dependenciesTruncated = $Record.dependencies.Count -gt $MaxItems
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
                schema = 'reflect-cache-view-v1'
                view = 'full'
                cache = $result.cache
                stats = $result.stats
                availableViews = @('summary', 'refs', 'detail', 'full')
                next = [ordered]@{ detail = 'read -View detail -Section <name>'; refs = 'read -View refs' }
                raw = [string]$Record.text
            }
        }
        return $result
    }
    return $result
}

function Get-DiffView($Current, $Base) {
    # ponytail: bounded line diff is enough for a receipt; structural graph diff is a later upgrade.
    $sectionNames = @($Current.sections.Keys + $Base.sections.Keys | Sort-Object -Unique)
    $changes = [ordered]@{}
    $changed = $false
    foreach ($name in $sectionNames) {
        $old = @(Get-UsefulLines (Get-SectionLines $Base.sections $name))
        $new = @(Get-UsefulLines (Get-SectionLines $Current.sections $name))
        $added = @($new | Where-Object { $_ -notin $old } | Select-Object -First $MaxItems)
        $removed = @($old | Where-Object { $_ -notin $new } | Select-Object -First $MaxItems)
        if ($added.Count -or $removed.Count) {
            $changed = $true
            $changes[$name] = [ordered]@{
                added = $added
                removed = $removed
                addedCount = @($new | Where-Object { $_ -notin $old }).Count
                removedCount = @($old | Where-Object { $_ -notin $new }).Count
            }
        }
    }
    return [ordered]@{
        schema = 'reflect-cache-diff-v1'
        changed = $changed
        from = [ordered]@{ path = $Base.path; sha256 = $Base.cache.sha256; graphSha1 = $Base.cache.graphSha1 }
        to = [ordered]@{ path = $Current.path; sha256 = $Current.cache.sha256; graphSha1 = $Current.cache.graphSha1 }
        sections = $changes
        next = if ($changed) { @('read -View detail -Section <changed section>') } else { @() }
    }
}

function Get-ReceiptView($Current, $Base) {
    $diff = Get-DiffView $Current $Base
    $changedSections = [Collections.Generic.List[object]]::new()
    foreach ($name in @($diff.sections.Keys)) {
        $section = $diff.sections[$name]
        $changedSections.Add([ordered]@{
            name = $name
            added = [int]$section.addedCount
            removed = [int]$section.removedCount
        })
    }
    return [ordered]@{
        schema = 'ueagent-change-receipt-v1'
        source = 'reflect-cache'
        action = $ChangeAction
        changed = [bool]$diff.changed
        before = $diff.from
        after = $diff.to
        changedSections = @($changedSections)
        readback = [ordered]@{
            required = $true
            reason = 'cache describes saved state; live mutation still needs independent MCP readback'
        }
        next = if ($diff.changed) { @('inspect changedSections with read -View detail') } else { @('no cache delta') }
    }
}

function Get-IndexView {
    $root = Resolve-ProjectRoot
    if (-not $root) { throw 'index requires -ProjectRoot or -RouteFile.' }
    $content = Join-Path $root 'Content'
    if (-not (Test-Path -LiteralPath $content)) { throw "Content directory not found: $content" }
    $items = [Collections.Generic.List[object]]::new()
    $reverse = @{}
    foreach ($file in Get-ChildItem -LiteralPath $content -Filter '*.uasset.ai.md' -File -Recurse) {
        try { $record = Get-CacheRecord $file.FullName } catch { continue }
        $src = if ($record.metadata.src) { [string]$record.metadata.src } else { $file.Name }
        $items.Add([ordered]@{
            source = $src
            format = $record.cache.format
            formatKnown = $record.cache.formatKnown
            state = $record.cache.state
            fresh = $record.cache.fresh
            sourceExists = $record.source.exists
            sha256 = $record.cache.sha256
            dependencies = $record.dependencies.Count
        })
        foreach ($dependency in $record.dependencies) {
            if (-not $reverse.ContainsKey($dependency)) { $reverse[$dependency] = [Collections.Generic.List[string]]::new() }
            if ($reverse[$dependency].Count -lt $MaxItems) { $reverse[$dependency].Add($src) }
        }
    }
    $reverseView = [ordered]@{}
    foreach ($key in @($reverse.Keys | Sort-Object | Select-Object -First $MaxItems)) { $reverseView[$key] = @($reverse[$key]) }
    return [ordered]@{
        schema = 'reflect-cache-index-v1'
        root = $root
        assetCount = $items.Count
        assets = @($items | Select-Object -First $MaxItems)
        reverseDependencies = $reverseView
        truncated = $items.Count -gt $MaxItems
    }
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
        try { $record = Get-CacheRecord $sidecar.FullName } catch { continue }
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
                $record = Get-CacheRecord $targetSidecar
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
    $json = if ($Pretty) { $Object | ConvertTo-Json -Depth 30 } else { $Object | ConvertTo-Json -Depth 30 -Compress }
    if ($OutFile) {
        $parent = Split-Path $OutFile -Parent
        if ($parent -and -not (Test-Path -LiteralPath $parent)) { throw "Output directory not found: $parent" }
        [IO.File]::WriteAllText($OutFile, $json, [Text.UTF8Encoding]::new($false))
    } else { $json }
}

if ($Action -eq 'index') {
    Write-Result (Get-IndexView)
    exit 0
}
if ($Action -eq 'reconcile') {
    Write-Result (Get-ReconcileView)
    exit 0
}

$cachePath = Resolve-SidecarPath
$record = Get-CacheRecord $cachePath
if ($Action -eq 'diff') {
    if (-not $BaseSidecar) { throw 'diff requires -BaseSidecar.' }
    Write-Result (Get-DiffView $record (Get-CacheRecord (Resolve-Path -LiteralPath $BaseSidecar).Path))
    exit 0
}
if ($Action -eq 'receipt') {
    if (-not $BaseSidecar) { throw 'receipt requires -BaseSidecar.' }
    Write-Result (Get-ReceiptView $record (Get-CacheRecord (Resolve-Path -LiteralPath $BaseSidecar).Path))
    exit 0
}

Write-Result (Get-ReadView $record)
