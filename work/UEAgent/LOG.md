# UEAgent · LOG

> 决策流水。追加式，新条目加在**文件末尾**。由 `/log` 命令维护。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签（可选，加在标题前）

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

### 2026-04-27 10:45 — [决策] 选用 UnrealGenAISupport 而非 UnrealMCPBridge
对比两个 UE MCP 插件：UnrealGenAISupport 功能更丰富（29 个工具）、架构更清晰（FastMCP + CommandDispatcher 模式）；UnrealMCPBridge 工具少且有明显 bug（接收缓冲区 16KB 截断、`execute_python` 代码被多余 `""` 包裹破坏传输）。

### 2026-04-27 11:20 — [发现] fastmcp 3.x 实测可用
插件代码 `from fastmcp import FastMCP, Image` 按 1.x/2.x API 写，本以为要降级。实测 fastmcp 3.2.4 仍能 import `Image`，`mcp_server.py` 可正常启动并完成 MCP initialize 握手。不需要降级。

### 2026-04-27 11:52 — [发现] UE 插件面板 Start 按钮是假状态
UnrealGenAISupport 面板上那个绿色 "Running ✓ localhost:9877" 是纯前端状态，**不真正 bind 端口**。必须在 UE Python 命令栏手动敲 `py "<unreal_socket_server.py 绝对路径>"` 才会真正监听 9877。验证方法：`netstat -ano | findstr :9877`。

### 2026-04-27 12:00 — [决策] mcp.json 的 command 用 Python 绝对路径
WorkBuddy spawn MCP 子进程时的环境不继承用户 shell PATH，裸 `python` 命令找不到。统一改成 `C:/Users/violinapeng/AppData/Local/Programs/Python/Python313/python.exe`。这是 WorkBuddy 下所有 stdio MCP 的通用解法。

### 2026-04-27 12:10 — [发现] WorkBuddy 把 MCP 叫「连接器」
手改 `~/.workbuddy/mcp.json` 不会生效，WorkBuddy 不热扫描。正确入口是左侧栏「连接器」，在里面启用 `unreal-genai` 才会 spawn server 进程并登记到 `mcp-approvals.json`。工具前缀变成 `mcp__connector-proxy__unreal-genai_<name>`。

### 2026-04-27 12:15 — [决策] 29 个工具先"用而不修"
体检发现两个 handler 有 bug：`handshake_test` 线程违规、`get_all_scene_objects` 调废弃 API `EditorLevelLibrary.get_level()`。决策：先用 `execute_unreal_command` 和 `execute_python_script` 两个万能工具推进实际需求，碰到高频绕不过的坏工具再打补丁。

### 2026-04-27 12:15 — [发现] 链路健康体检命令
`execute_unreal_command "stat fps"` 是最稳的体检：既走 game thread 又不碰废弃 API。能返回就说明 WorkBuddy → MCP server → UE socket → dispatcher → UE API 全链路活的。

### 2026-04-27 12:20 — [决策] 把 UEAgent 立成独立项目
决定用 `/project-init UEAgent` 建项目三件套，把调通过程中的上下文完整交接给之后所有接手的 AI。原因：旧对话 AI 用不了 MCP 工具（当前会话无法热加载），debug 不方便；新对话 AI 带项目简报进来就能直接调用工具实操。

### 2026-04-27 14:10 — [发现] 插件暴露的 C++ UCLASS 是读蓝图结构的正道
前期误判：以为 Python 读蓝图内容必须扫 `.uasset` 二进制。实际上插件通过 `unreal.GenBlueprintUtils` 和 `unreal.GenBlueprintNodeCreator` 暴露了 C++ API，可在 `execute_python_script` 里直接调。**`unreal.GenBlueprintNodeCreator.get_all_nodes_in_graph(bp_path, 'EventGraph')` 传字面量 `"EventGraph"` 会自动取 `UbergraphPages[0]`**，返回 JSON（`node_guid` / `node_type` / `position`）。EUW_DyeBake 实测 71 节点 10KB。**缺点**：只有 guid/type/position，不带 Pin 和连线，要连线需改插件 `GenBlueprintNodeCreator.cpp:351-393`。

### 2026-04-27 14:25 — [决策] 读 Widget 结构走插件 `GenWidgetUtils` + 二进制辅助
`WidgetTree.RootWidget` 是 protected，Python reflection 读不到。但插件 `unreal.GenWidgetUtils.edit_widget_property(bp, widget_name, prop, value)` 的错误消息能区分"widget 不存在"和"属性不存在"，由此反查 widget 名是否有效。配合二进制扫 uasset 的 Name Table 找候选名。**加 widget 走 `add_widget_to_user_widget(bp, ClassName, widget_name, parent_name)`**，Border 只能装 1 个 child，实际结构是 `Border → SizeBox → VerticalBox → SpinBox...`，必须 parent 到 VerticalBox 那层。用户手动在 EUW 里把 VerticalBox 命名为 `DiffuseVB / InitVB / BakeVB`。

### 2026-04-27 14:35 — [发现] 二进制扫字符串会把引擎模板占位符当真相
早期扫 NS_DyeBaker.uasset 拿到 57 个 `Module.*` 名，列给用户时混进了 `Damping / BaseDt / Gamma / g / InitSpeed / MinSpacing / ArrivalThreshold / MinGradientValue / DomainSize / SeedRadius` 等——**这些其实是 Niagara 内置模板（Diffusion 等）留在 uasset 里的 metadata，不是该 emitter 实际用到的 Input**。用户通过截图纠正：实际 DiffuseGrid 的 Input 只有图里那 13 条。**教训**：二进制扫给出的是"出现过的名字"，不是"当前生效参数"，以 UE UI 或 user 确认为准。

### 2026-04-27 14:45 — [决策] EUW 侧参数面板设计（final，基于 user 截图）
按 sim stage 分三个 Border 分组（每 Border 下 `SizeBox > VerticalBox`）。**最终 20 个参数要加**（SeedCount / RandomSeed / ScatterRadius 已在 EUW 完成，NoiseSampler 用户自己做）：
- **DiffuseSetting（10）**：BaseStep, NoiseIntensity, NoiseScale, ArcScale, NoiseOffset, ForceDirection(Vec2), ForceStrength, ForceDecay, SeedCenter(Vec2), DiffuseStrength
- **InitSetting（?）**：等用户给 InitGrid 截图确认
- **BakeSetting（?）**：用户说是"前后流程其他参数"，待定
每组节点链照抄 ScatterRadius 的现成模板：`OnValueChanged(float) → [Truncate 仅 int 类型] → SetNiagaraVariable(Type)("User.X") → SetEditorProperty("bAutoActivate"=true, Always)`。Target/Object 全接 `SpawnedNiagaraBaker`（NiagaraComponent 变量）。

### 2026-04-27 14:55 — [否决] 用 Python 在 NS 侧批量 Promote Input → User Parameter
扫遍 256 个 `unreal.Niagara*` 类，**无任何公开 UFUNCTION 支持 "Promote Input to User Parameter"**。该操作活在 Niagara 编辑器 Slate 层，不在 UObject 层。**决策**：Promote 步骤交给用户手工点（右键 Input → Promote to User Parameter），一个 5-10 秒，可接受。

### 2026-04-27 15:00 — [发现] 插件 `add_node_to_blueprint` 只搜 10 个 Kismet 库
`GenBlueprintNodeCreator.cpp:862` 的 `CommonLibraries` 硬编码列表只有 `KismetMathLibrary / KismetSystemLibrary / KismetStringLibrary / KismetArrayLibrary / KismetTextLibrary / GameplayStatics / BlueprintFunctionLibrary / Actor / Pawn / Character`，不含 NiagaraComponent / NiagaraFunctionLibrary，因此 `SetVariableFloat` 这类 Niagara 成员函数**找不到**。`FindFirstObject<UClass>(*Name)` 是运行时反射，不需要编译期依赖 Niagara 模块。

### 2026-04-27 15:10 — [决策] 改插件 C++：给 `CommonLibraries` 加 Niagara 条目
改 `GenBlueprintNodeCreator.cpp:862 / 995` 两处 `CommonLibraries`，加 `TEXT("NiagaraComponent"), TEXT("NiagaraFunctionLibrary")`。改前备份为 `GenBlueprintNodeCreator.cpp.bak.20260427`。插件有 git，双重兜底。**目的**：让 `add_node_to_blueprint "SetVariableFloat"` 能直接建 Niagara setter 节点，后续 20 个参数的节点链可完全自动化。

### 2026-04-27 15:15 — [发现] Live Coding 对静态数据改动不热加载
`Ctrl+Alt+F11` Live Coding 报 "Patch succeeded"，但插件 `CommonLibraries`（static const TArray）未生效——`get_node_suggestions("SetVariableFloat")` 仍空返回。**教训**：Live Coding 可靠地热加载函数体，但对静态数据 / 类元数据可能不触发重新构造。改插件影响模块结构时必须关 UE 让它走正常 rebuild 流程。

### 2026-04-27 15:18 — [断点] 等 UE 重启加载新插件
用户准备关 UE → 让弹窗选"Plugin out of date, rebuild?" → Yes → 等编译 → 重开项目 → Python 命令栏跑 `py "unreal_socket_server.py"` → WorkBuddy 新开对话。新会话接手的工作：用 `/project UEAgent` 接入，跑一次 `unreal.GenBlueprintNodeCreator.get_node_suggestions("SetVariableFloat")`，返回含 `NiagaraComponent.SetVariableFloat` 即确认改动生效，然后照下方"进度断点"继续做。
