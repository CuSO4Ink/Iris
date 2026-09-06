[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot '../scripts/mcp_gateway.ps1') -AsLibrary
$Endpoint='http://127.0.0.1:8000/mcp'
$SessionFile=$null
$script:headers=@{'Mcp-Session-Id'='task-fixture'}
$script:TaskBindings=@{}
$script:route=$null
$project=[IO.Path]::GetFullPath('C:/UEAgentFixture/Test.uproject').Replace('\','/')
$script:events=[Collections.Generic.List[object]]::new()
$script:value=@{answer=40}
$script:pending=$false
$invoke={param($name,$parameters)
    $script:events.Add([pscustomobject]@{name=$name;parameters=$parameters})
    switch($name){
        'ueagent_state' { return [pscustomobject]@{protocol_version='3.0.0';enabled=$true;editor_epoch='epoch-a';project_file=$project} }
        'ueagent_submit' {
            if($script:pending){return [pscustomobject]@{state='queued';command_id=$parameters.command_id}}
            return [pscustomobject]@{state='terminal';success=$true;result=$script:value;command_id=$parameters.command_id}
        }
        'ueagent_get_job' {return [pscustomobject]@{state='terminal';success=$true;result=$script:value;command_id=$parameters.command_id}}
        default {throw "Unexpected fixture operation $name"}
    }
}
function Check($condition,$message){if(-not $condition){throw $message}}
foreach($case in @(
    @{value=@();json='[]'},@{value=@('one');json='["one"]'},@{value=$null;json='null'},
    @{value=$false;json='false'},@{value=@{value=@();enabled=$false};json=$null}
)){
    $script:value=$case.value
    $request=[pscustomobject]@{toolset='Fixture';tool='Read';arguments=@{};readOnly=$true;expectedProject=$project}
    $actual=Invoke-TaskCall $request $invoke
    if($case.json){$json=if($null -eq $actual){'null'}else{ConvertTo-Json -InputObject $actual -Depth 8 -Compress};Check ($json -ceq $case.json) "Read changed shape: $json"}
    else{Check ($actual.enabled -eq $false -and $actual.value.Count -eq 0) 'Nested data changed'}
}
Check (@($script:events|Where-Object name -eq ueagent_state).Count -eq 1) 'Identity was repeatedly probed'
$before=$script:events.Count
$bad=Invoke-TaskCall ([pscustomobject]@{tool='Read';expectedProject='C:/Other/Other.uproject';readOnly=$true}) $invoke
Check ($bad.error_code -eq 'PROJECT_MISMATCH' -and $script:events.Count -eq $before) 'Wrong project reached dispatch'
$script:pending=$true
$id=[guid]::NewGuid().ToString()
$request=[pscustomobject]@{toolset='Fixture';tool='Set';arguments=@{value=40};expectedProject=$project;commandId=$id;scopes=@('/Game/Test');readback=@{tool_name='Read';expect=@{value=40}};save=$true}
$result=Invoke-TaskCall $request $invoke
Check ($result.state -eq 'terminal' -and $result.command_id -eq $id) 'Local wait lost identity'
$submit=@($script:events|Where-Object name -eq ueagent_submit)[-1].parameters
Check ($submit.editor_epoch -eq 'epoch-a' -and $submit.expected_project -eq $project -and $submit.save -eq $true) 'Binding or save intent lost'
$automatic=[pscustomobject]@{toolset='Fixture';tool='Set';arguments=@{};expectedProject=$project;wait=$false}
$first=Invoke-TaskCall $automatic $invoke
$second=Invoke-TaskCall $automatic $invoke
Check ($first.command_id -eq $second.command_id) 'Session recovery could create a second mutation ID'
[pscustomobject]@{passed=$true;checks=@('read_shapes','one_identity_bind','wrong_project_predispatch','local_wait','save_intent','stable_generated_id')}|ConvertTo-Json -Compress
