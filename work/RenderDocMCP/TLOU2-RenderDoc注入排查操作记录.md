# The Last of Us Part II — RenderDoc 命令行注入与排查操作记录

> 记录日期：2026-07-17  
> RenderDoc 版本：v1.45 (64-bit Release)  
> 游戏：The Last of Us Part II (内部研发构建, Build v1.6.10721.0105)  
> GPU：NVIDIA GeForce RTX 3080 (Driver 610.74)  
> OS：Windows 11 (build 26200)

---

## 1. 背景

游戏内置启动器，直接双击 `tlou-ii.exe` 可正常进入游戏本体，但通过 RenderDoc GUI 的 Launch Application 启动时会弹出启动器而非游戏本体。需要通过命令行方式启动并挂载 RenderDoc，逐步排查注入失败原因。

## 2. 游戏路径与环境

```
游戏本体路径：
D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered\tlou-ii.exe

工作目录：
D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered

RenderDoc 命令行工具：
C:\Program Files\RenderDoc\renderdoccmd.exe

捕获输出目录：
C:\Work\AI\Iris\output\bb4e8f46-cf95-46f9-a383-d364b8cc4885\captures\

游戏日志：
C:\Users\violinapeng\Documents\The Last of Us Part II\The Last of Us Part II.log

RenderDoc 日志：
C:\Users\violinapeng\AppData\Local\Temp\RenderDoc\RenderDoc_*.log
```

游戏目录中存在 NVIDIA Streamline 组件：
```
sl.interposer.dll
sl.dlss.dll
sl.dlss_g.dll
sl.reflex.dll
nvngx_dlss.dll
nvngx_dlssg.dll
```

## 3. 操作流程

### 3.1 阶段一：确认 renderdoccmd 可用命令

**目的**：确认本机 RenderDoc 支持的命令行操作。

```powershell
# 查看 renderdoccmd 总帮助
& "C:\Program Files\RenderDoc\renderdoccmd.exe" --help

# 查看 inject 子命令参数（向运行中进程注入）
& "C:\Program Files\RenderDoc\renderdoccmd.exe" inject --help

# 查看 capture 子命令参数（启动并注入新进程）
& "C:\Program Files\RenderDoc\renderdoccmd.exe" capture --help
```

**结果**：`renderdoccmd` 支持 `inject`（注入运行中进程）和 `capture`（启动新进程并注入）两个子命令。`capture` 支持 `--working-dir`、`--opt-hook-children`、`--capture-file` 等参数。

---

### 3.2 阶段二：尝试向运行中游戏进程注入（inject）

**目的**：游戏已正常启动后，向其进程注入 RenderDoc。

#### 步骤 1 — 正常启动游戏并查找进程 PID

```powershell
# 查找游戏进程
Get-CimInstance Win32_Process -Filter "Name='tlou-ii.exe'" | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate | Format-List
```

**结果**：找到 `tlou-ii.exe`，PID = 30144。

#### 步骤 2 — 向进程注入 RenderDoc

```powershell
# 创建捕获目录
$captureDir = 'C:\Work\AI\Iris\output\bb4e8f46-cf95-46f9-a383-d364b8cc4885\captures'
New-Item -ItemType Directory -Force -Path $captureDir | Out-Null

# 注入（含子进程挂钩）
& "C:\Program Files\RenderDoc\renderdoccmd.exe" inject --PID=30144 --opt-hook-children --capture-file="$captureDir\tlou2"
```

#### 步骤 3 — 验证注入状态

```powershell
# 检查 renderdoc.dll 是否已加载到游戏进程
$p = Get-Process -Id 30144 -ErrorAction SilentlyContinue
if (-not $p) { 'PROCESS_EXITED' } else {
    try {
        $p.Modules | Where-Object { $_.ModuleName -match 'renderdoc' } | Select-Object ModuleName,FileName | Format-List
    } catch { "MODULE_CHECK_ERROR: $($_.Exception.Message)" }
}

# 检查游戏是否监听 RenderDoc 控制端口
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object { $_.OwningProcess -eq 30144 } | Select-Object LocalAddress,LocalPort,OwningProcess | Format-Table -AutoSize
```

**结果**：
- `renderdoc.dll` **已成功注入**到 `tlou-ii.exe`
- 游戏监听了端口 `38920`（RenderDoc 控制端口）
- **但游戏画面无 RenderDoc Overlay，按 F12 无反应**

#### 步骤 4 — 通过 Target Control 连接并尝试抓帧

```powershell
# 以管理员权限启动 RenderDoc GUI 并连接到游戏控制端口
Start-Process -FilePath 'C:\Program Files\RenderDoc\qrenderdoc.exe' -ArgumentList '--targetcontrol','localhost:38920' -Verb RunAs

# 验证连接
Start-Sleep -Seconds 3
Get-Process qrenderdoc -ErrorAction SilentlyContinue | Select-Object Id,StartTime,MainWindowTitle,MainWindowHandle | Sort-Object StartTime -Descending | Format-Table -AutoSize
Get-NetTCPConnection -RemotePort 38920 -ErrorAction SilentlyContinue | Select-Object State,LocalAddress,LocalPort,RemoteAddress,RemotePort,OwningProcess | Format-Table -AutoSize
```

**结果**：
- RenderDoc GUI 确实连接到了 `tlou-ii.exe`（TCP 状态 Established）
- GUI 中显示了目标进程
- **但 Overlay 仍不出现，F12 仍无效**

#### 判断

**DLL 注入和控制连接成功 ≠ 图形 API 被成功挂钩。** 游戏的 D3D12 设备和 SwapChain 在注入前已经创建，RenderDoc 错过了图形 API 初始化时机，因此无法抓帧。

**结论**：运行后注入对这类游戏无效，必须在进程创建阶段注入。

---

### 3.3 阶段三：用 capture 启动游戏（未指定工作目录）

**目的**：通过 `renderdoccmd capture` 从进程创建阶段注入。

```powershell
& "C:\Program Files\RenderDoc\renderdoccmd.exe" capture `
  "D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered\tlou-ii.exe"
```

**结果**：启动了启动器而非游戏本体。

**原因**：未指定 `--working-dir`，游戏在错误的工作目录下找不到相对路径配置/运行时文件，回退到启动器逻辑。

---

### 3.4 阶段四：用 capture + 正确工作目录启动

**目的**：修正工作目录后重新启动。

```powershell
$gameDir = 'D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered'
$game = Join-Path $gameDir 'tlou-ii.exe'
$captureDir = 'C:\Work\AI\Iris\output\bb4e8f46-cf95-46f9-a383-d364b8cc4885\captures'

& "C:\Program Files\RenderDoc\renderdoccmd.exe" capture `
  --working-dir "$gameDir" `
  --capture-file "$captureDir\tlou2" `
  "$game"
```

**结果**：游戏本体正常启动了（不再弹出启动器），但 RenderDoc 的追踪页面一闪而过，回到启动前状态。

#### 排查进程树

```powershell
# 查看所有 tlou-ii 进程
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'tlou|launcher' } | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate | Format-List

# 检查最终运行的进程是否加载了 renderdoc.dll
$games = Get-Process -Name 'tlou-ii' -ErrorAction SilentlyContinue
$games | ForEach-Object {
    $p = $_
    [PSCustomObject]@{
        Id = $p.Id
        StartTime = $p.StartTime
        RenderDocLoaded = [bool]($p.Modules | Where-Object ModuleName -eq 'renderdoc.dll')
        D3D12Loaded = [bool]($p.Modules | Where-Object ModuleName -eq 'd3d12.dll')
    }
} | Format-List

# 查看父进程链
$ppid = (Get-CimInstance Win32_Process -Filter "ProcessId=35052").ParentProcessId
Get-CimInstance Win32_Process -Filter "ProcessId=$ppid" | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate | Format-List
```

**结果**：
- 发生了**进程自重启/二次拉起**：
  1. RenderDoc 启动并注入第一个 `tlou-ii.exe`（父进程）
  2. 第一个进程马上创建第二个 `tlou-ii.exe`，然后退出
  3. RenderDoc 的追踪页面随父进程退出而一闪而过
  4. 最终运行的是新进程 PID 35052，已加载 D3D12、DXGI，**但没有加载 renderdoc.dll**

**结论**：需要启用子进程挂钩（`--opt-hook-children`），让 RenderDoc 在子进程创建时自动注入。

---

### 3.5 阶段五：用 capture + 工作目录 + 子进程挂钩启动

**目的**：启用 `--opt-hook-children` 后，让 RenderDoc 跟踪二次拉起的子进程。

```powershell
$gameDir = 'D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered'
$game = Join-Path $gameDir 'tlou-ii.exe'
$captureDir = 'C:\Work\AI\Iris\output\bb4e8f46-cf95-46f9-a383-d364b8cc4885\captures'
New-Item -ItemType Directory -Force -Path $captureDir | Out-Null

& "C:\Program Files\RenderDoc\renderdoccmd.exe" capture `
  --working-dir "$gameDir" `
  --opt-hook-children `
  --capture-file "$captureDir\tlou2" `
  "$game"
```

#### 验证注入与 Hook 状态

```powershell
# 等待游戏启动
Start-Sleep -Seconds 12

# 检查进程状态
$games = Get-Process -Name 'tlou-ii' -ErrorAction SilentlyContinue
if (-not $games) { 'NO_GAME_PROCESS' } else {
    $games | ForEach-Object {
        $p = $_
        [PSCustomObject]@{
            Id = $p.Id
            StartTime = $p.StartTime
            RenderDocLoaded = [bool]($p.Modules | Where-Object ModuleName -eq 'renderdoc.dll')
            D3D12Loaded = [bool]($p.Modules | Where-Object ModuleName -eq 'd3d12.dll')
        }
    } | Format-List
}

# 检查 RenderDoc 控制端口
Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {$_.OwningProcess -in $games.Id} | Select-Object LocalPort,OwningProcess | Format-Table -AutoSize
```

#### 检查 RenderDoc 日志

```powershell
# 查找本次启动的日志
Get-ChildItem "$env:LOCALAPPDATA\Temp\RenderDoc" -Filter 'RenderDoc_*.log' -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 5 FullName,Length,LastWriteTime | Format-List
```

读取日志 `RenderDoc_2026.07.17_11.42.45.log`，关键内容：

```
[11:42:45] Running process tlou-ii.exe
[11:42:45] Injecting renderdoc into process 16396
[11:42:46] Loading into tlou-ii.exe
[11:42:46] Registering D3D12 hooks
[11:42:46] Registering DXGI hooks
[11:42:46] Injecting renderdoc into process 8340   ← crs-handler.exe（子进程）
[11:42:47] Injecting renderdoc into process 46300   ← crs-video.exe（子进程）
[11:42:47] NvAPI disabled: Returning NULL for nvapi_QueryInterface(NvAPI_EnumPhysicalGPUs)
[11:42:47] NvAPI disabled: Returning NULL for nvapi_QueryInterface(NvAPI_SYS_GetDriverAndBranchVersion)
[11:42:47] NvAPI disabled: Returning NULL for nvapi_QueryInterface(NvAPI_Stereo_IsEnabled)
[11:42:50] New D3D12 device created: nVidia / NVIDIA GeForce RTX 3080
[11:42:50] Adding D3D12 device frame capturer
[11:42:50] Clamping shader model from 0x68 to 6.7
[11:42:50] Clamping raytracing tier support
[11:42:50] Forcing no sampler feedback tier support
```

**结果**：
- `--opt-hook-children` **确实生效**
- RenderDoc 成功注入 `tlou-ii.exe` 及子进程 `crs-handler.exe`、`crs-video.exe`
- 成功注册 D3D12 Hook
- 成功捕获到 D3D12 设备创建（`New D3D12 device created: NVIDIA GeForce RTX 3080`）
- **但游戏随后立即崩溃**

#### 检查崩溃记录

```powershell
# 系统应用程序错误日志
Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-5)} -ErrorAction SilentlyContinue | Where-Object { $_.ProviderName -in 'Application Error','Windows Error Reporting' -or $_.Message -match 'tlou-ii|renderdoc' } | Select-Object TimeCreated,ProviderName,Id,LevelDisplayName,Message | Format-List

# 崩溃转储与日志
Get-ChildItem "$env:LOCALAPPDATA\CrashDumps","$env:USERPROFILE\Documents" -Recurse -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -gt (Get-Date).AddMinutes(-5) -and ($_.Name -match 'tlou|crash|dump|log') } | Select-Object FullName,Length,LastWriteTime | Sort-Object LastWriteTime -Descending | Select-Object -First 30 | Format-List
```

**崩溃证据**：

系统事件日志：
```
APPCRASH: tlou-ii.exe
Exception Code: 0xc0000005 (ACCESS_VIOLATION)
Fault Offset: 0x1291b99
```

游戏日志最后记录：
```
Unhandled exception ... code: 0x80000003
"A breakpoint was encountered"
```

崩溃转储文件：
```
C:\Users\violinapeng\AppData\Local\CrashDumps\tlou-ii.exe.16396.dmp
```

---

## 4. 根因分析

### 4.1 问题演进链

| 阶段 | 问题 | 根因 | 解决方式 |
|------|------|------|----------|
| 1 | RenderDoc GUI Launch 弹出启动器 | 未指定正确工作目录 | 使用命令行 `--working-dir` |
| 2 | 工作目录正确后，追踪页面一闪而过 | 进程二次拉起：父进程退出，子进程未注入 | 启用 `--opt-hook-children` |
| 3 | Hook 成功但游戏崩溃 (0xc0000005) | D3D12 Hook 后与 NVIDIA Streamline/NVAPI 冲突 | 需进一步兼容调整 |

### 4.2 最终崩溃原因

RenderDoc v1.45 在 Hook D3D12 后执行了以下行为：
- **禁用 NVAPI 接口**：`NvAPI disabled`，返回 NULL 给 `NvAPI_EnumPhysicalGPUs`、`NvAPI_SYS_GetDriverAndBranchVersion` 等
- **Clamp Shader Model**：从 6.8 降到 6.7
- **Clamp Raytracing Tier**：强制降级
- **Force no Sampler Feedback**：强制关闭

游戏使用 NVIDIA Streamline 2.7.2（`sl.interposer.dll`、`sl.dlss.dll`、`sl.dlss_g.dll`、`sl.reflex.dll`），Streamline 依赖 NVAPI 接口与 GPU 通信。RenderDoc 禁用 NVAPI 后，Streamline 初始化路径中可能触发空指针访问或断点异常（0x80000003），最终导致 ACCESS_VIOLATION（0xc0000005）崩溃。

### 4.3 子进程附带注入

`--opt-hook-children` 额外注入了两个辅助进程：
```
crs-handler.exe   ← 崩溃处理相关
crs-video.exe     ← 视频编解码相关
```

对这两个进程的注入也可能干扰游戏正常运行，但主崩溃点在 `tlou-ii.exe` 本身的 D3D12 Hook。

---

## 5. 完整排查命令速查

```powershell
# ==================== 变量定义 ====================
$gameDir = 'D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered'
$game = Join-Path $gameDir 'tlou-ii.exe'
$captureDir = 'C:\Work\AI\Iris\output\bb4e8f46-cf95-46f9-a383-d364b8cc4885\captures'
$rdc = 'C:\Program Files\RenderDoc\renderdoccmd.exe'

# ==================== 1. 查看可用命令 ====================
& $rdc --help
& $rdc inject --help
& $rdc capture --help

# ==================== 2. 查找游戏进程 ====================
Get-CimInstance Win32_Process -Filter "Name='tlou-ii.exe'" | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath,CommandLine,CreationDate | Format-List

# ==================== 3. 向运行中进程注入 ====================
& $rdc inject --PID=<PID> --opt-hook-children --capture-file="$captureDir\tlou2"

# ==================== 4. 验证注入状态 ====================
$p = Get-Process -Id <PID> -ErrorAction SilentlyContinue
$p.Modules | Where-Object { $_.ModuleName -match 'renderdoc' } | Select-Object ModuleName,FileName | Format-List
Get-NetTCPConnection -State Listen | Where-Object { $_.OwningProcess -eq <PID> } | Select-Object LocalPort,OwningProcess

# ==================== 5. 用 capture 启动（完整参数） ====================
New-Item -ItemType Directory -Force -Path $captureDir | Out-Null
& $rdc capture --working-dir "$gameDir" --opt-hook-children --capture-file="$captureDir\tlou2" "$game"

# ==================== 6. 验证最终进程 ====================
Start-Sleep -Seconds 12
Get-CimInstance Win32_Process | Where-Object { $_.Name -match 'tlou' } | Select-Object ProcessId,ParentProcessId,Name,ExecutablePath | Format-List
Get-Process -Name 'tlou-ii' -ErrorAction SilentlyContinue | ForEach-Object {
    [PSCustomObject]@{
        Id = $_.Id
        RenderDocLoaded = [bool]($_.Modules | Where-Object ModuleName -eq 'renderdoc.dll')
        D3D12Loaded = [bool]($_.Modules | Where-Object ModuleName -eq 'd3d12.dll')
    }
} | Format-List

# ==================== 7. 检查 RenderDoc 日志 ====================
Get-ChildItem "$env:LOCALAPPDATA\Temp\RenderDoc" -Filter 'RenderDoc_*.log' | Sort-Object LastWriteTime -Descending | Select-Object -First 3 FullName,LastWriteTime

# ==================== 8. 检查崩溃记录 ====================
Get-WinEvent -FilterHashtable @{LogName='Application'; StartTime=(Get-Date).AddMinutes(-10)} | Where-Object { $_.Message -match 'tlou-ii|renderdoc' } | Select-Object TimeCreated,ProviderName,Message | Format-List

Get-ChildItem "$env:LOCALAPPDATA\CrashDumps" -Filter 'tlou-ii*' | Select-Object FullName,Length,LastWriteTime

# ==================== 9. 连接 Target Control ====================
Start-Process -FilePath 'C:\Program Files\RenderDoc\qrenderdoc.exe' -ArgumentList '--targetcontrol','localhost:38920' -Verb RunAs

# ==================== 10. 查找抓帧文件 ====================
Get-ChildItem $captureDir,'C:\Users\violinapeng\Documents','D:\Work\Company\Game' -Filter '*.rdc' -Recurse -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object FullName,Length,LastWriteTime | Format-List
```

---

## 6. 当前结论与后续方案

### 结论

该版本游戏无法用 RenderDoc v1.45 默认 D3D12 注入稳定运行。注入链路本身已完全打通（工作目录 → 子进程挂钩 → D3D12 Hook 成功），但 Hook 后 NVAPI 被 RenderDoc 禁用，与 NVIDIA Streamline 2.7.2 产生冲突，导致游戏崩溃。

### 后续本机非侵入式方案（按优先级）

1. **游戏内关闭 NVIDIA 功能**：Frame Generation → Off、DLSS → Off/TAA、NVIDIA Reflex → Off
2. **关闭第三方 Overlay**：NVIDIA Overlay、Xbox Game Bar、Steam Overlay、Discord Overlay 等
3. **RenderDoc 设置中允许 NVIDIA 扩展**（如有）：`Tools → Settings` 中查找 `Allow unsupported vendor extensions` 或类似选项
4. **更换 RenderDoc 版本**：优先测试 v1.43（本机已有 `C:\Users\violinapeng\Downloads\RenderDoc_1.43_64.msi`），不同版本对 NVAPI/Streamline 的 Hook 行为可能不同
5. **限制子进程注入范围**：如能配置不注入 `crs-handler.exe`、`crs-video.exe`，可减少干扰

### 不建议的操作

- 删除/改名 `sl.interposer.dll`、`sl.common.dll` 等 Streamline 组件（可能导致游戏无法启动）
- 修改 exe 或打补丁绕过完整性检查
- 重复启动触发崩溃（只会持续产生崩溃转储）

---

## 7. 最终解决方案（2026-07-18，覆盖第 6 节阶段性结论）

> 第 6 节保留的是问题尚未解决时的阶段性判断。本节及后续内容是最终验证通过的根因、修复和日常操作流程。

### 7.1 最终状态

问题已经解决。定制 RenderDoc v1.45 可以完成以下完整链路：

```text
启动 tlou-ii.exe
→ 点击“开始游戏”
→ 游戏正常进入
→ 左上角显示 RenderDoc Overlay
→ 按 F12
→ 生成可打开的 D3D12 .rdc
```

首次成功捕获证据：

```text
Frame: 3460
文件大小: 3,716,522,887 bytes（约 3.46 GiB）
原始 Capture Section: 约 13.65 GiB
压缩率: 25.96%
写入耗时: 约 18.17 秒
```

成功文件：

```text
C:\Work\AI\Iris\work\RenderDocMCP\captures\tlou2_streamline_hooks\tlou2-streamline_frame3460.rdc
```

成功日志：

```text
TLOU2 isolation: wrapping sl.interposer D3D12CreateDevice
Adding D3D12 frame capturer
Starting capture
Finished capture, Frame 3460
Captured D3D12 frame
Written to disk: ...\tlou2-streamline_frame3460.rdc
```

### 7.2 最终根因：连续两层兼容性问题

#### 第一层：NVAPI 被置空导致启动崩溃

RenderDoc 默认不允许 Unsupported NVIDIA Vendor Extensions，因此游戏需要的多个接口被返回 `NULL`，包括：

```text
NvAPI_EnumPhysicalGPUs
NvAPI_GPU_GetArchInfo
NvAPI_SYS_GetDriverAndBranchVersion
NvAPI_GPU_GetLogicalGpuInfo
NvAPI_DRS_*
```

游戏没有正确处理初始化失败，最终稳定崩溃在：

```text
Exception Code: 0xC0000005
Fault Offset: tlou-ii.exe+0x1291B99
Fault Access: read address 0x8
RBX: 0
Instruction: movsxd rax, dword ptr [rbx+8]
```

在目标进程内启用 RenderDoc 官方已有的 NVIDIA Vendor Extension 开关后，日志由：

```text
NvAPI disabled: Returning NULL for nvapi_QueryInterface(...)
```

变为：

```text
NvAPI allowed: Returning 00007FF... for nvapi_QueryInterface(...)
```

游戏随即可以正常进入，证明 NVAPI 查询被置空是启动崩溃的决定性原因。

#### 第二层：Streamline 绕过 RenderDoc，导致无 Overlay、F12 无效

完整放行 NVAPI 后游戏虽然能运行，但日志只出现三次短生命周期探测设备：

```text
Adding D3D12 device frame capturer
Removing device frame capturer
```

没有 SwapChain/Present，左上角没有 Overlay，`F12` 无反应。

进程模块与导出表确认 `sl.interposer.dll 2.7.2` 自己导出了：

```text
D3D12CreateDevice
CreateDXGIFactory
CreateDXGIFactory1
CreateDXGIFactory2
```

原版 RenderDoc 只对 `d3d12.dll` 和 `dxgi.dll` 注册 Hook。三个系统 D3D12 Device 只是探测设备，真正的 Device、Factory 和 SwapChain 由 Streamline Interposer 创建，因此绕过了 RenderDoc。

### 7.3 已排除的错误方向

以下操作均不能解决 `+0x1291B99` 崩溃：

- 关闭 NVIDIA In-Game Overlay；
- 使用 RenderDoc v1.43；
- 使用 RenderDoc v1.45 Release；
- 设置 `NV.BlockNVAPI=false`；
- 设置 `NV.BlockNVAPI=true`；
- 只恢复 Shader Model 6.8；
- 只恢复 Raytracing Tier 1.2；
- 只恢复 Sampler Feedback Tier 0.9；
- 三项 D3D12 能力全部按驱动原值返回。

因此以下 RenderDoc 能力降级不是启动崩溃根因：

```text
Shader Model 6.8 → 6.7
Raytracing Tier 1.2 → 1.1
Sampler Feedback Tier 0.9 → NOT_SUPPORTED
```

最终成功版本恢复了这三项原始 RenderDoc 行为，仍可正常启动和截帧。

---

## 8. 定制 RenderDoc 实现

### 8.1 源码与产物

```text
官方源码提交:
2fc0bc04cb95499635f63986a55bc6f67849dd9f

源码目录:
C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04

截帧启动程序:
C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04\x64\Development\renderdoccmd.exe

注入 DLL:
C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04\x64\Development\renderdoc.dll
```

### 8.2 NVAPI 修改

文件：

```text
renderdoc\driver\ihv\nv\nvapi_hooks.cpp
```

处理方式：

1. 在 `NvAPI_Initialize_hook()` 中调用官方 `EnableVendorExtensions(VendorExtensions::NvAPI)`；
2. 放行显卡枚举、驱动信息、显示和 DRS 等启动所需查询；
3. 对未经 RenderDoc 正式包装的原始 `NvAPI_D3D12_*` 接口返回 `NULL`，防止 NVIDIA Driver 收到无法识别的 Wrapped Device。

核心逻辑：

```cpp
if(!NV_BlockNVAPI())
  RenderDoc::Inst().EnableVendorExtensions(VendorExtensions::NvAPI);

if(cname && !strncmp(cname, "NvAPI_D3D12_", 12))
  return NULL;
```

RenderDoc 已经正式实现的 NVIDIA D3D12 接口会在更早的 `NVAPI_FUNCS()` 分支处理，不会进入上述过滤分支。

### 8.3 Streamline D3D12 Hook

文件：

```text
renderdoc\driver\d3d12\d3d12_hooks.cpp
```

新增对 Streamline 导出的注册：

```cpp
LibraryHooks::RegisterLibraryHook("sl.interposer.dll", NULL);
StreamlineCreateDevice.Register(
    "sl.interposer.dll",
    "D3D12CreateDevice",
    Streamline_D3D12CreateDevice_hook);
```

使用独立的 `HookedFunction<PFN_D3D12_CREATE_DEVICE>` 保存 Streamline 原函数指针，再调用 RenderDoc 原有 `Create_Internal()` 包装最终 Device。递归进入系统 `d3d12.dll` 时沿用 RenderDoc 的 TLS 重入保护，避免二次包装。

### 8.4 Streamline DXGI Hook

文件：

```text
renderdoc\driver\dxgi\dxgi_hooks.cpp
```

新增对以下 Streamline 导出的 Hook：

```text
CreateDXGIFactory
CreateDXGIFactory1
CreateDXGIFactory2
```

调用 Streamline 原函数时使用 `ScopedSuppressHooking`，避免其内部再次调用系统 DXGI 导出造成双重包装；随后调用 `RefCountDXGIObject::HandleWrap()` 包装 Streamline 最终返回的 Factory。

---

## 9. 编译方法

本机使用 Visual Studio Build Tools 2022 v143 和 Windows 11 SDK。官方工程默认指向 v140，因此通过命令行临时指定 v143：

```powershell
$src = 'C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04\'
+$msbuild = 'C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\MSBuild\Current\Bin\MSBuild.exe'

& $msbuild `
  "$src\renderdoccmd\renderdoccmd.vcxproj" `
  /m:8 `
  /nodeReuse:false `
  /p:Configuration=Development `
  /p:Platform=x64 `
  /p:PlatformToolset=v143 `
  "/p:SolutionDir=$src"
```

成功产物位于：

```text
x64\Development\renderdoccmd.exe
x64\Development\renderdoc.dll
```

---

## 10. 日常截帧流程

### 10.1 推荐：一键启动脚本

```text
C:\Work\AI\Iris\work\RenderDocMCP\启动TLOU2_RenderDoc截帧.cmd
```

脚本会自动：

- 检查定制 RenderDoc 和游戏 EXE；
- 阻止游戏已经运行时重复注入；
- 按时间创建独立捕获目录；
- 设置正确工作目录并注入 `tlou-ii.exe`。

日常操作：

1. 确认游戏已经完全退出；
2. 双击 `启动TLOU2_RenderDoc截帧.cmd`；
3. 在游戏启动窗口点击“开始游戏”；
4. 确认左上角出现 RenderDoc Overlay；
5. 进入目标场景，按一次 `F12`；
6. 等待捕获写入完成后再退出游戏；
7. 使用系统安装的 RenderDoc v1.45 打开 `.rdc`。

自动捕获目录：

```text
C:\Work\AI\Iris\work\RenderDocMCP\captures\tlou2_manual\<时间戳>\
```

### 10.2 手动启动命令

```powershell
& "C:\Work\AI\Iris\work\RenderDocMCP\tools\renderdoc_src_2fc0bc04\x64\Development\renderdoccmd.exe" capture `
  --working-dir "D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered" `
  --capture-file "C:\Work\AI\Iris\work\RenderDocMCP\captures\tlou2_capture" `
  "D:\Work\Company\Game\The Last Of Us Part II (2020-2025)\The Last of Us II Rematered\tlou-ii.exe"
```

最终验证流程不依赖 `--opt-hook-children`；捕获对象是直接启动的 `tlou-ii.exe`。

---

## 11. 注意事项

- 不要使用系统安装版 RenderDoc 直接注入游戏；它没有本次 NVAPI 和 Streamline 兼容修改。
- 系统安装版 RenderDoc v1.45 可以用于打开 `.rdc`，但截帧启动必须使用定制 `renderdoccmd.exe`。
- 不要删除或覆盖 `tools\renderdoc_src_2fc0bc04\x64\Development`，一键脚本依赖其中的 EXE 和 DLL。
- 单帧可能达到 3–4 GiB，原始数据可超过 13 GiB。按一次 `F12` 后等待写入完成，不要连续触发。
- 打开大型 `.rdc` 前先退出游戏，避免游戏内存/显存与回放资源叠加导致 Device Lost。
- 不建议删除或改名 `sl.interposer.dll`、`sl.common.dll` 等游戏组件；最终方案只修改 RenderDoc，不修改游戏文件。
- `AllowUnsupportedVendorExtensions` 在 RenderDoc 中被标记为不受支持。本补丁额外阻止了未包装的原始 `NvAPI_D3D12_*`，但仍应只用于本游戏的离线图形分析。
