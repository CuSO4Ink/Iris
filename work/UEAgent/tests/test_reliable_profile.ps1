[CmdletBinding()]
param(
    [string]$VibeUEPath,
    [string]$EngineRoot
)

$ErrorActionPreference = 'Stop'
$root = Split-Path $PSScriptRoot -Parent

function Assert-True($Condition, $Message) {
    if (-not $Condition) { throw $Message }
}

function Get-NormalizedSha256($Path) {
    $text = [IO.File]::ReadAllText($Path) -replace "`r`n", "`n" -replace "`r", "`n"
    $sha = [Security.Cryptography.SHA256]::Create()
    try {
        return ([BitConverter]::ToString(
            $sha.ComputeHash([Text.UTF8Encoding]::new($false).GetBytes($text))
        )).Replace('-', '')
    } finally {
        $sha.Dispose()
    }
}

function Assert-PowerShellParses($Path) {
    $tokens = $null
    $errors = $null
    [Management.Automation.Language.Parser]::ParseFile($Path, [ref]$tokens, [ref]$errors) | Out-Null
    Assert-True ($errors.Count -eq 0) "$Path has parser errors: $($errors.Message -join '; ')"
}

$manifestPath = Join-Path $root 'STACK-MANIFEST.json'
$manifest = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
Assert-True ($manifest.runtime.reliable_protocol -eq '2.0.0') 'Manifest reliable protocol is not 2.0.0.'
Assert-True ($manifest.runtime.mutation_transport -eq 'ueagent-command-queue') 'Manifest mutation transport is not the command queue.'
Assert-True (@($manifest.runtime.control_tools).Count -eq 9) 'Manifest must expose exactly nine reliable control tools.'
Assert-True (-not ($manifest.profiles.PSObject.Properties.Name -contains 'project-unrealmcp-readonly')) 'Manifest still exposes the retired UnrealMCP compatibility profile.'
Assert-True ('patches/ue58-mcp-authorization-gate.patch' -in @($manifest.profiles.base.apply)) 'Base profile misses the MCP authorization gate.'
Assert-True ('patches/vibeue-reliable-kernel.patch' -in @($manifest.profiles.base.apply)) 'Base profile misses the reliable kernel.'
Assert-True ('patches/vibeue-reliable-kernel.patch' -in @($manifest.profiles.'niagara-authoring'.apply)) 'Niagara authoring profile misses the reliable kernel.'
Assert-True (@($manifest.profiles.default.apply).Count -eq 1 -and $manifest.profiles.default.apply[0] -eq 'patches/ue58-mcp-tool-search.patch') 'Default MCP tool-search profile is not one current patch.'
$reliablePatchText = Get-Content -Raw -LiteralPath (Join-Path $root 'patches\vibeue-reliable-kernel.patch')
Assert-True (-not $reliablePatchText.Contains('TEXT("ueagent_get_receipt")')) 'Reliable patch still publishes the redundant receipt tool.'
Assert-True (-not $reliablePatchText.Contains('StringProperty(TEXT("fault_injection")')) 'Reliable patch still publishes test-only fault injection fields.'

foreach ($property in $manifest.patches.PSObject.Properties) {
    $path = Join-Path $root ([string]$property.Name).Replace('/', '\')
    Assert-True (Test-Path -LiteralPath $path) "Manifest patch is missing: $path"
    Assert-True ((Get-NormalizedSha256 $path) -eq [string]$property.Value) "Manifest hash differs: $($property.Name)"
}

foreach ($script in @('ueagent_common.ps1', 'bootstrap.ps1', 'doctor.ps1', 'mcp_gateway.ps1', 'mcp_gateway_daemon.ps1', 'compact_context.ps1', 'reflect_cache.ps1')) {
    Assert-PowerShellParses (Join-Path $root "scripts\$script")
}

. (Join-Path $root 'scripts\ueagent_common.ps1')
$pluginFixture = Join-Path ([IO.Path]::GetTempPath()) ('ueagent-plugin-inventory-' + [Guid]::NewGuid().ToString('N'))
try {
    $descriptorDir = Join-Path $pluginFixture 'Plugins\ExternalFixture'
    $null = New-Item -ItemType Directory -Path $descriptorDir
    $descriptorPath = Join-Path $descriptorDir 'ExternalFixture.uplugin'
    [IO.File]::WriteAllText($descriptorPath, '{"Version":7,"VersionName":"7.1"}', [Text.UTF8Encoding]::new($false))
    $anotherDir = Join-Path $pluginFixture 'Plugins\AnotherFixture'
    $null = New-Item -ItemType Directory -Path $anotherDir
    [IO.File]::WriteAllText((Join-Path $anotherDir 'AnotherFixture.uplugin'), '{"Version":1,"VersionName":"1.0"}', [Text.UTF8Encoding]::new($false))
    $fixtureProject = [pscustomobject]@{ Plugins = @(
        [pscustomobject]@{ Name = 'ExternalFixture'; Enabled = $true },
        [pscustomobject]@{ Name = 'AnotherFixture'; Enabled = $true },
        [pscustomobject]@{ Name = 'DisabledFixture'; Enabled = $false },
        [pscustomobject]@{ Name = 'EngineFixture'; Enabled = $true },
        [pscustomobject]@{ Name = 'VibeUE'; Enabled = $true }
    ) }
    $inventory = @(Get-EnabledExternalPluginInventory $fixtureProject $pluginFixture)
    Assert-True ($inventory.Count -eq 2 -and $inventory[0].name -eq 'AnotherFixture') 'Bootstrap inventory did not isolate and sort enabled project-local plugins.'
    Assert-True ($inventory[1].name -eq 'ExternalFixture' -and $inventory[1].descriptor -eq 'Plugins/ExternalFixture/ExternalFixture.uplugin') 'Bootstrap inventory lost external plugin identity.'
    Assert-True ($inventory[1].version -eq 7 -and $inventory[1].versionName -eq '7.1' -and $inventory[1].descriptorSha256 -eq (Get-NormalizedFileSha256 $descriptorPath)) 'Bootstrap inventory lost external plugin version or fingerprint.'
} finally {
    Remove-Item -LiteralPath $pluginFixture -Recurse -Force -ErrorAction SilentlyContinue
}

$gatewayPath = Join-Path $root 'scripts\mcp_gateway.ps1'
$gateway = Get-Content -Raw -LiteralPath $gatewayPath
$gatewayParameters = (Get-Command $gatewayPath).Parameters.Keys
Assert-True ('RouteFile' -in $gatewayParameters) 'Gateway cannot bind target route defaults.'
foreach ($retiredParameter in @('ReuseSession', 'DataOnly', 'DisableProcessGuard')) {
    Assert-True ($retiredParameter -notin $gatewayParameters) "Gateway still exposes redundant or unsafe parameter: $retiredParameter"
}
foreach ($rawJsonParameter in @('RequestJson', 'ArgumentsJson', 'ProjectionJson')) {
    Assert-True ($rawJsonParameter -notin $gatewayParameters) "Gateway still exposes unsafe raw JSON parameter: $rawJsonParameter"
}
Assert-True ($gateway.Contains("'ueagent_state' -in `$topLevelTools")) 'Gateway preflight does not prefer ueagent_state.'
Assert-True ($gateway -match 'reliableStateRead') 'Gateway preflight omits reliable-state evidence.'
Assert-True ($gateway -match 'callViewAvailable') 'Gateway preflight omits native call-view evidence.'
Assert-True (-not $gateway.Contains("'dataOnly'")) 'Gateway still forwards the retired implicit dataOnly request field.'
foreach ($retiredHelper in @('Convert-ToCallView', 'Get-CompactSchemaType', 'Get-CompactToolName', 'Get-CompactEffect')) {
    Assert-True (-not $gateway.Contains($retiredHelper)) "Gateway still contains retired call-view fallback helper: $retiredHelper"
}
foreach ($retiredAction in @('python.execute', 'script.execute', 'level.current')) {
    Assert-True (-not $gateway.Contains("'$retiredAction'")) "Gateway still exposes retired action: $retiredAction"
}
. $gatewayPath -AsLibrary
$staleLock = Join-Path ([IO.Path]::GetTempPath()) ('ueagent-stale-lock-' + [Guid]::NewGuid().ToString('N'))
try {
    [IO.File]::WriteAllText("$staleLock.lock", '', [Text.UTF8Encoding]::new($false))
    $lock = Enter-SessionFileLock $staleLock 250
    Assert-True ($null -ne $lock) 'A stale lock file still blocks session access.'
    Exit-SessionFileLock $staleLock $lock
} finally {
    Remove-Item -LiteralPath "$staleLock.lock" -Force -ErrorAction SilentlyContinue
}
$schemaCache = Join-Path ([IO.Path]::GetTempPath()) ('ueagent-schema-cache-' + [Guid]::NewGuid().ToString('N') + '.json')
try {
    Write-SchemaCacheEntry 'tools.list' 'http://127.0.0.1:8001/mcp' '' @([ordered]@{ name = 'fixture' }) $schemaCache 300 '' '' 'session'
    $schemaText = [IO.File]::ReadAllText($schemaCache)
    Assert-True (-not $schemaText.Contains("`n")) 'Machine-only schema cache is still pretty-printed.'
} finally {
    Remove-Item -LiteralPath $schemaCache -Force -ErrorAction SilentlyContinue
}
$callSchema = '[{"name":"describe_toolset","inputSchema":{"properties":{"detail":{"enum":["call","summary","full"]}}}}]' | ConvertFrom-Json
Assert-True (Test-ToolInputEnumValue $callSchema 'describe_toolset' 'detail' 'call') 'Gateway does not recognize the native call schema.'
$legacySchema = '[{"name":"describe_toolset","inputSchema":{"properties":{"detail":{"enum":["summary","full"]}}}}]' | ConvertFrom-Json
Assert-True (-not (Test-ToolInputEnumValue $legacySchema 'describe_toolset' 'detail' 'call')) 'Gateway accepts a schema without the native call view.'
$minimalRequest = Resolve-GatewayRequest ([pscustomobject]@{ tool = 'ueagent_state' })
Assert-True ($minimalRequest.action -eq 'direct.call') 'Gateway did not infer a reliable direct call from the tool alone.'
Assert-True (Test-GatewayFailure ([ordered]@{ ok = $false; code = 'fixture' })) 'Gateway did not classify its own ordered error result as a failure.'
$qualifiedRequest = Resolve-GatewayRequest ([pscustomobject]@{ tool = 'VibeUE.ActorService.GetAllProperties' })
Assert-True ($qualifiedRequest.action -eq 'tool.call') 'Gateway did not infer a qualified tool call.'
Assert-True ((Resolve-GatewayProjection $qualifiedRequest).structured -eq $true) 'Gateway did not default tool calls to structured-only transport.'
$discoveryForward = Get-DaemonRequest ([pscustomobject]@{ action = 'tools.list' }) 'C:\fixture\schema.json' 123
Assert-True ($discoveryForward.schemaCacheFile -eq 'C:\fixture\schema.json' -and $discoveryForward.schemaCacheTtlSec -eq 123) 'Daemon discovery lost routed schema-cache defaults.'
$profileForward = Get-DaemonRequest ([pscustomobject]@{ action = 'tool.call'; tool = 'VibeUE.ActorService.GetAllProperties'; projectionProfile = 'topology'; schemaCacheFile = 'C:\do-not-forward.json' }) 'C:\fixture\schema.json' 123
Assert-True ($profileForward.projectionProfile -eq 'topology' -and -not ($profileForward.PSObject.Properties.Name -contains 'projection')) 'Gateway expanded a compact projection profile before daemon forwarding.'
Assert-True (-not ($profileForward.PSObject.Properties.Name -contains 'schemaCacheFile')) 'Gateway leaked schema-cache paths into an ordinary daemon call.'
$reliableData = [pscustomobject]@{
    success = $true
    enabled = $true
    editor_epoch = 'epoch'
    active_command_id = ''
    queued_command_ids = @()
    performance_frozen = $false
    command_succeeded = $true
    outcome = 'succeeded'
    accepted_at = '2026-08-12T00:00:00Z'
    result = '{"success":true,"returnValue":{"name":"Asset","empty":""}}'
}
$compressedData = Compress-GatewayData $reliableData $minimalRequest
Assert-True (-not ($compressedData.PSObject.Properties.Name -contains 'success')) 'Gateway retained redundant success=true.'
Assert-True (-not ($compressedData.PSObject.Properties.Name -contains 'enabled')) 'Gateway retained redundant enabled=true.'
Assert-True (-not ($compressedData.PSObject.Properties.Name -contains 'active_command_id')) 'Gateway retained an empty reliable field.'
Assert-True (-not ($compressedData.PSObject.Properties.Name -contains 'command_succeeded')) 'Gateway retained a derived success field.'
Assert-True (-not ($compressedData.PSObject.Properties.Name -contains 'accepted_at')) 'Gateway retained diagnostic timing in model output.'
Assert-True ($compressedData.editor_epoch -eq 'epoch' -and $compressedData.outcome -eq 'succeeded') 'Gateway removed reliable identity or outcome.'
Assert-True ($compressedData.result.name -eq 'Asset' -and $compressedData.result.empty -eq '') 'Gateway did not parse the nested result or changed its semantic payload.'
$genericData = Compress-GatewayData ([pscustomobject]@{ success = $true; returnValue = [pscustomobject]@{ name = 'Asset'; empty = ''; nil = $null } }) $qualifiedRequest
Assert-True ($genericData.name -eq 'Asset' -and $genericData.empty -eq '' -and $genericData.PSObject.Properties.Name -contains 'nil') 'Gateway changed generic tool data while removing its wrapper.'

$bootstrap = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\bootstrap.ps1')
Assert-True ($bootstrap -match 'Test-Path -LiteralPath \$projectEditor') 'Bootstrap launch does not prefer the freshly built project Editor.'
Assert-True (-not $bootstrap.Contains('UseProjectUnrealMcp')) 'Bootstrap still exposes the retired UnrealMCP compatibility route.'
Assert-True ($bootstrap -match "PSBoundParameters\.ContainsKey\('Endpoint'\).+route\.endpoint") 'Bootstrap CheckOnly does not inherit the routed endpoint.'
Assert-True ($bootstrap -match 'Read-UeAgentStackManifest') 'Bootstrap does not use STACK-MANIFEST.json as its protocol source.'
foreach ($staticAuditMarker in @('Get-UeAgentManifestPatchErrors', 'Assert-UeAgentReliableConfig', 'Test-GitPatchesApplied', 'Build.version', '.mcp.json')) {
    Assert-True ($bootstrap.Contains($staticAuditMarker)) "Bootstrap lost static audit coverage: $staticAuditMarker"
}
$doctor = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\doctor.ps1')
$doctorParameters = (Get-Command (Join-Path $root 'scripts\doctor.ps1')).Parameters.Keys
Assert-True ('RouteFile' -in $doctorParameters) 'Doctor does not require RouteFile.'
foreach ($retiredParameter in @('UProject', 'EngineRoot', 'Endpoint', 'Profile')) {
    Assert-True ($retiredParameter -notin $doctorParameters) "Doctor still exposes retired parameter: $retiredParameter"
}
Assert-True (-not $doctor.Contains('project-unrealmcp-stdio')) 'Doctor still exposes the retired UnrealMCP compatibility route.'
Assert-True (-not $doctor.Contains('vibeUEPatchPath')) 'Doctor still exposes the producerless custom VibeUE patch route.'
Assert-True (-not $doctor.Contains('Get-NetTCPConnection')) 'Doctor still performs slow system listener enumeration.'
foreach ($staticAuditMarker in @('Test-GitPatch', 'Get-IniSectionBody', 'Build.version', '.mcp.json', 'Test-RoutedPatchPackage', 'static = [ordered]')) {
    Assert-True (-not $doctor.Contains($staticAuditMarker)) "Doctor still duplicates bootstrap static audit: $staticAuditMarker"
}
foreach ($liveMarker in @("Invoke-GatewayProbe 'preflight'", 'Get-PluginFingerprint')) {
    Assert-True ($doctor.Contains($liveMarker)) "Doctor lost required runtime evidence: $liveMarker"
}
Assert-True ($doctor -match 'editor_pid') 'Doctor does not bind receipts to the reliable editor PID.'
Assert-True ($doctor -match 'callViewAvailable') 'Doctor does not require the native compact call view.'
Assert-True ($doctor -match '\[string\]\$OutFile') 'Doctor cannot persist the reusable receipt directly.'
Assert-True (-not $doctor.Contains('next = switch')) 'Doctor still guesses a task route that belongs to compact_context.'
$compact = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\compact_context.ps1')
Assert-True ($compact -match 'LIVE_MUTATE_RELIABLE_QUEUE') 'Compact router omits the reliable mutation route.'
Assert-True ($compact -match 'LIVE_SAVE_CAPABILITY_REQUIRED') 'Compact router omits the capability-gated save route.'
Assert-True ($compact -match '\$healthy\s*=.+\$kernelCurrent') 'Compact router can grant mutation from a stale kernel epoch.'
Assert-True (-not $compact.Contains('liveDirtyCheck')) 'Compact router still emits a constant live-dirty flag.'
Assert-True (-not $compact.Contains("'inspect'")) 'Compact router still exposes read under a second operation name.'
Assert-True ($compact -match '\[ordered\]@\{ next = \$next \}\s*\r?\n\} else') 'Compact live route still emits fields that do not affect dispatch.'
$common = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\ueagent_common.ps1')
Assert-True ($common -match 'Binaries\\Win64\\\$\{ProjectName\}Editor-VibeUE\*\.dll') 'Plugin fingerprint omits the actual project VibeUE binary.'
Assert-True ($common -match 'VibeUE\.patch_\*\.exe') 'Plugin fingerprint omits Live Coding VibeUE patches.'
Assert-True (-not $common.Contains('Plugins\UnrealMCP')) 'Plugin fingerprint still includes the retired UnrealMCP profile.'
Assert-True ($common.Contains('[IO.Directory]::EnumerateFiles')) 'Plugin fingerprint still uses PowerShell filesystem discovery.'
$daemon = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\mcp_gateway_daemon.ps1')
Assert-True ($daemon -match '-not \$sessionRecovered.+Test-McpSessionInvalidError') 'Daemon cannot recover a session it initialized itself.'
Assert-True ($daemon -match 'Close-McpSession \$Endpoint \$script:headers\s+Remove-McpSessionFile \$SessionFile') 'Daemon leaves a locally reusable file after closing its session.'
$reflect = Get-Content -Raw -LiteralPath (Join-Path $root 'scripts\reflect_cache.ps1')
Assert-True (-not $reflect.Contains('$Record.text')) 'Reflect cache still reads full raw text for every view.'
Assert-True ($reflect.Contains('[IO.File]::ReadAllLines')) 'Reflect cache still wraps every sidecar line in PowerShell provider metadata.'
$reflectRoot = Join-Path ([IO.Path]::GetTempPath()) ('ueagent-reflect-' + [Guid]::NewGuid().ToString('N'))
try {
    $null = New-Item -ItemType Directory -Path $reflectRoot
    $source = Join-Path $reflectRoot 'Fixture.uasset'
    $sidecar = $source + '.ai.md'
    [IO.File]::WriteAllBytes($source, [byte[]](1, 2, 3))
    $sourceText = $source.Replace('\', '/')
    $sidecarText = @(
        '```yaml',
        'format: vibeue-niagara-system-cache-v1',
        "file: $sourceText",
        'size: 3',
        'graph_sha1: fixture-graph',
        '```',
        '## Params',
        '-',
        '## Logic',
        'line',
        '## Deps',
        '- /Game/Fixture/Dep',
        'PARENT: /Game/Fixture/M_Master | relation=Parent',
        'TEX: /Game/Fixture/T_Normal | relation=TextureOverride | parameter=Normal'
    ) -join "`n"
    [IO.File]::WriteAllText($sidecar, $sidecarText, [Text.UTF8Encoding]::new($false))
    $summary = (& (Join-Path $root 'scripts\reflect_cache.ps1') -Sidecar $sidecar) | ConvertFrom-Json
    Assert-True (@($summary.PSObject.Properties.Name).Count -eq 2 -and $summary.cache.state -eq 'FRESH') 'Reflect summary still emits fixed wrapper fields or lost freshness state.'
    foreach ($redundant in @('path', 'source', 'sourceFile', 'sha256', 'fresh', 'formatKnown')) {
        Assert-True (-not ($summary.cache.PSObject.Properties.Name -contains $redundant)) "Reflect summary still emits redundant field: $redundant"
    }
    $refs = (& (Join-Path $root 'scripts\reflect_cache.ps1') -Sidecar $sidecar -View refs) | ConvertFrom-Json
    Assert-True (@($refs.references).Count -eq 2) 'Reflect refs view lost semantic direct references.'
    Assert-True ($refs.references[0].relation -eq 'Parent' -and $refs.references[0].target -eq '/Game/Fixture/M_Master') 'Reflect refs view lost the parent edge.'
    Assert-True ($refs.references[1].relation -eq 'TextureOverride' -and $refs.references[1].parameter -eq 'Normal') 'Reflect refs view lost the texture-override reason.'
    $full = (& (Join-Path $root 'scripts\reflect_cache.ps1') -Sidecar $sidecar -View full) | ConvertFrom-Json
    Assert-True ([string]$full.cache.sha256 -and [string]$full.raw) 'Explicit full reflect view lost provenance hash or raw content.'
} finally {
    Remove-Item -LiteralPath $reflectRoot -Recurse -Force -ErrorAction SilentlyContinue
}

if ($VibeUEPath) {
    $patch = Join-Path $root 'patches\vibeue-reliable-kernel.patch'
    & git -C $VibeUEPath apply --reverse --check $patch
    Assert-True ($LASTEXITCODE -eq 0) 'Reliable VibeUE patch does not match the supplied checkout.'
    . (Join-Path $root 'scripts\ueagent_common.ps1')
    $runtimePatches = @(
        (Join-Path $root 'patches\vibeue-performance-monitor.patch'),
        (Join-Path $root 'patches\vibeue-mcp-shutdown-guard.patch'),
        $patch
    )
    Assert-True (Test-GitPatchesApplied $VibeUEPath $runtimePatches) 'VibeUE runtime patch batch does not match the supplied checkout.'
}
if ($EngineRoot) {
    $patch = Join-Path $root 'patches\ue58-mcp-authorization-gate.patch'
    & git -C $EngineRoot apply --reverse --check $patch
    Assert-True ($LASTEXITCODE -eq 0) 'MCP authorization patch does not match the supplied engine.'
}

[ordered]@{
    ok = $true
    protocol = [string]$manifest.runtime.reliable_protocol
    controlTools = @($manifest.runtime.control_tools).Count
    patchCount = @($manifest.patches.PSObject.Properties).Count
    targetPatchesVerified = [bool]($VibeUEPath -and $EngineRoot)
} | ConvertTo-Json -Compress
