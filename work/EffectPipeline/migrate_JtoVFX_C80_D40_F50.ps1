# migrate_JtoVFX_C80_D40_F50.ps1
# 避开中文路径硬编码(PS5.1读.ps1按ANSI会乱码): 用通配符动态发现 J 盘源目录。
# 规则: 跳过 *_BuiltData.uasset; C80两侧分目录(金沙->FX_C80, 云雾->FX_C80_Cloud); D40/F50->同名。
$OutputEncoding = [System.Text.Encoding]::UTF8
$ErrorActionPreference = "Continue"
$root = "J:\vendors\漫行者\Final最终归档\BYDC\BYDC文件重新整理"
$dst  = "D:\Work\Company\UE\Jianlai\TMR\UnrealEngine\Games\JyGame\Content\AssetsJGAME\Effects\VFX_SQ_CP"
$logdir = "C:\Work\AI\Iris\work\EffectPipeline\migrate_logs"
New-Item -ItemType Directory -Force -Path $logdir | Out-Null

# 动态发现: 在 $root 下递归找 \<bundle>\<CODE>\Content\FX_<CODE> 目录, 按bundle是"金沙/云雾"区分
function Find-Src($code, $side){
  $hits = Get-ChildItem -Path $root -Recurse -Directory -ErrorAction SilentlyContinue |
    Where-Object { $_.FullName -like ("*Content\FX_" + $code) -and $_.FullName -like ("*" + $side + "*") }
  if($hits){ return $hits[0].FullName } else { return $null }
}

# 用 Unicode 码点表示"金沙"和"云雾", 彻底规避文件编码问题
$JINSHA = [string]([char]0x91D1 + [char]0x6C99)  # 金沙
$YUNWU  = [string]([char]0x4E91 + [char]0x96FE)  # 云雾

$jobs = @(
  @{ name="C80_Jinsha"; code="C80"; side=$JINSHA; dst="$dst\FX_C80";       skipBuilt=$true  },
  @{ name="C80_Cloud";  code="C80"; side=$YUNWU;  dst="$dst\FX_C80_Cloud"; skipBuilt=$false },
  @{ name="D40";        code="D40"; side=$YUNWU;  dst="$dst\FX_D40";       skipBuilt=$true  },
  @{ name="F50";        code="F50"; side=$YUNWU;  dst="$dst\FX_F50";       skipBuilt=$true  }
)

$summary = @()
foreach($j in $jobs){
  Write-Host "========================================================"
  Write-Host ("[MIGRATE] {0}" -f $j.name)
  $src = Find-Src $j.code $j.side
  Write-Host ("  src: {0}" -f $src)
  Write-Host ("  dst: {0}" -f $j.dst)
  if(-not $src -or -not (Test-Path $src)){ Write-Host "  !! 源未找到, 跳过"; continue }
  New-Item -ItemType Directory -Force -Path $j.dst | Out-Null
  $log = Join-Path $logdir ("robocopy_" + $j.name + ".log")
  $rcArgs = @($src, $j.dst, "/E", "/J", "/R:2", "/W:3", "/MT:8", "/NP", ("/LOG:" + $log))
  if($j.skipBuilt){ $rcArgs += @("/XF", "*_BuiltData.uasset"); Write-Host "  跳过: *_BuiltData.uasset" }
  robocopy @rcArgs | Out-Null
  $code = $LASTEXITCODE
  Write-Host ("  robocopy exit code: {0} (0-7=成功, >=8=错误)" -f $code)

  $srcFiles = Get-ChildItem $src -Recurse -File -ErrorAction SilentlyContinue
  if($j.skipBuilt){ $srcFiles = $srcFiles | Where-Object { $_.Name -notlike "*_BuiltData.uasset" } }
  $srcSum = ($srcFiles | Measure-Object Length -Sum)
  $dstSum = (Get-ChildItem $j.dst -Recurse -File -ErrorAction SilentlyContinue | Measure-Object Length -Sum)
  Write-Host ("  校验 源(应拷) 文件数={0} 字节={1:N0}" -f $srcSum.Count, $srcSum.Sum)
  Write-Host ("  校验 目标     文件数={0} 字节={1:N0}" -f $dstSum.Count, $dstSum.Sum)
  $summary += [pscustomobject]@{ Job=$j.name; Exit=$code; SrcFiles=$srcSum.Count; DstFiles=$dstSum.Count; Match=($srcSum.Sum -eq $dstSum.Sum) }
}

Write-Host "========================================================"
Write-Host "==================== MIGRATION SUMMARY ===================="
$summary | Format-Table -AutoSize
Write-Host ("log dir: {0}" -f $logdir)
