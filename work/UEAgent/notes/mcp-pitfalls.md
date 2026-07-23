# UEAgent · MCP Pitfalls（坑册）

> MCP / 连接器调用踩坑的**计数台账**。踩一次记一笔，同一类坑连续命中 3 次 → 归并成一条「经验」沉淀。
> 台账只留**活跃计数**；毕业的经验单独成节，并优先反哺 `AI-BRIEF.md` 硬约束或跨项目 MEMORY。

## 计数规则

- 一次调用踩一个坑 → 对应条目计数 +1，附日期 + 一句现场
- 同类连续命中 **3 次** → 提炼成 §经验，台账条目归档
- 「连续」按命中该类的时序算，中间夹别的坑**不算断**
- 拿不准是否同类 → 先各记各的，别硬并；宁可晚毕业

## 活跃台账（未毕业）

> 2026-07-09：旧栈（UnrealGenAISupport/TCP 9877）已弃用，其专属技术坑（原 K1 废弃 API / K2 插件覆盖不全 / K3 UObject 层无此操作 / K4 WorkBuddy 连接器机制 / K5 子进程环境不继承 shell）随旧栈一并归档删除，不再适用于新栈。已毕业的通用经验（E1/E2）不受影响，继续保留。

| # | 坑类 | 计数 | 最近命中 | 现场（一句） |
|---|---|---|---|---|
| K6 | 大体量返回值在工具调用链路里被截断 | 3（已毕业→E2） | 2026-07-09 | `CaptureViewport` 返回的 base64 图片：①写入本地 `.b64` 文件后长度对4取模≠0 ②再次尝试同样失败 ③改设 `maxOutputLength=2000000` 重调，结果直接被上层标"Tool call output was truncated"——说明截断发生在工具调用结果传输/展示层，不是本地文件写入层，`maxOutputLength` 参数管不到这层 |
| K7 | UObject 数组扩容时同时改变旧元素会触发歧义 | 2 | 2026-07-15 | `MaterialExpressionCustom.Inputs` 直接改名并扩容失败；分步后若扩容时省略旧元素的嵌套 `FExpressionInput` 仍失败。已验证完整 read-modify-write 可用，待第三次命中再毕业。 |
| K8 | ProgrammaticToolset 无法转发部分枚举参数 | 1 | 2026-07-15 | `execute_tool_script` 向 `MaterialTools.get_property_input` 传 `MP_BaseColor` 时把 `material_property` 变成 int 后无法 pythonize；同一调用改由原生 MCP 在脚本外执行成功。 |
| K9 | `list_properties` 暴露只读字段为可设置候选 | 1 | 2026-07-15 | `MaterialExpressionCustom.showCode` 出现在属性 schema 中，但 `set_properties` 明确拒绝；其余同批属性仍已写入。后续不设置该字段。 |
| K10 | 空 referencers 被实现为异常而非空数组 | 1 | 2026-07-15 | 新建且未引用的 `/Game/MCPTests/M_Bifrost_Cloud_CustomProbe` 调 `get_referencers` 返回 `'NoneType' object is not iterable`；按已知临时资产精确路径删除并用 `exists=false` 验证清理。 |

> [!NOTE] 新栈（UE 官方 MCP 插件）继续沿用本台账机制，后续每次真跑 MCP 命中同类坑 → 在这里 +1。
> — ai 2026-07-09

## 已毕业经验

### E1 · 别信"自报成功"，一律用独立手段验真

> [!Q] 这条是我按「连命中 3 次」规则归并的，三次算不算同一类你拍一下：
> ① 面板绿色 "Running ✓ 9877" 是纯前端假状态、不真 bind 端口（04-27 11:52）
> ② 二进制扫 uasset 把 Niagara 模板占位符当"当前生效参数"（04-27 14:35）
> ③ Live Coding 报 "Patch succeeded" 但静态数据 `CommonLibraries` 没真生效（04-27 15:15）
> 三者共性：**工具/系统自报的"成功/生效"都不可信**。合理就保留，不合理就拆回台账。
> — ai 2026-07-07

- **教训**：MCP 链路上任何"自报状态"（UI 灯、Patch succeeded、扫描出的名字）都只是"声称"，不是"事实"。
- **验真手段清单**（认独立信号，不认自报）：
  - 端口真监听 → `netstat -ano | findstr :9877`
  - 全链路活着 → `execute_unreal_command "stat fps"`（走 game thread、不碰废弃 API）
  - 插件改动生效 → `get_node_suggestions("SetVariableFloat")` 返回含目标才算数
  - 参数/结构真相 → 以 UE UI 或 user 确认为准，二进制扫描只当"出现过的名字"

### E2 · 大体量二进制/图片数据别走 MCP 工具调用返回值，走"人眼直接看"或落盘路径

> K6 三次同类命中直接毕业：`CaptureViewport` 截图的 base64 图片数据反复在"返回值→本地文件"链路中损坏/截断，提高 `maxOutputLength` 也压不住（截断点在工具调用结果传输层，不在 execute_command 层）。
> — ai 2026-07-09

- **教训**：MCP 工具调用返回值这条通道，对大体量 payload（几十KB+ 的 base64 图片/二进制）不可靠，会被上层截断，且**没有参数能保证突破**（试过的 `maxOutputLength` 无效）。
- **实践规律**：
  - 需要"看画面效果"时，**别指望截图走 MCP 拿图**——直接让人在编辑器视口里肉眼确认最快最省 token，比"AI 截图→写文件→解码→read_file 验证"整条链路省 10 倍以上交互
  - 只有当 MCP 工具本身支持"保存到磁盘文件路径"参数（返回文件路径而非 base64 内容）时，才走截图自动化；纯返回 base64 的工具对大图慎用
  - 判断要不要用截图工具，先问一句"用户现在是不是就在编辑器里、能直接看"——能看就不用截图，省一整条排障循环
- **硬规则（用户 2026-07-09 拍板）**：任何我判断为"截图 / CaptureViewport / 拿视觉画面"的操作，**先找用户二次确认要不要跑，不擅自执行**——用户默认不需要 AI 截图，需要看效果时会自己在编辑器里看。
- **调用格式规律**（避免重复踩 arguments 格式坑）：
  - `mcp_call_tool` 的 `arguments` 必须是**合法 JSON 对象**（不是字符串包一层），顶层要带 `toolset_name` + `tool_name` + `arguments`（内层才是真正传给工具的参数）
  - actor 引用一律用**完整 refPath**（`/Game/Xxx/Maps/L_Xxx.L_Xxx:PersistentLevel.StaticMeshActor_51`），短名会解析失败
  - 不确定某工具的参数 schema 时，先 `describe_toolset` 查一遍，比瞎猜省几轮 trial-and-error
  - 有"必填但语义上想传空"的对象参数（如 `annotations`），得显式传全 0/null 的完整结构，不能省略字段

### E3 · 材质 Pin 名必须查询，不能按 UE UI 或直觉猜

> 新栈材质编辑连续命中：WorldPosition 默认输出/ComponentMask 输入、VectorParameter 的 `RG`、TextureSample 的 `Coordinates` 均与猜测不符；实际名称通过 MaterialTools 查询后接线成功。

- 连接前先调用 `get_expression_input_names` / `get_expression_output_names`。
- 把查询结果当作当前 UE/插件版本事实，不把 UI 标签直接翻译成 MCP Pin 名。
- 已验证示例统一维护在 `../skills/ue-mcp-workflows/references/materials.md`，版本变化或连接失败时重新查询。

---

## 维护

- 新坑先进台账；毕业条目搬到本节并考虑反哺 `../AI-BRIEF.md`
- 台账 > 8 行或经验 > 5 条 → 考虑拆分 / 归并到跨项目 MEMORY

### 2026-07-16 ocean-material audit additions

- K8 count +1 (now 2): `ProgrammaticToolset` could not pythonize `MP_PixelDepthOffset` for `MaterialTools.get_property_input`; workaround: omit that enum value and query supported roots only.
- K11 count 1: `MaterialTools.get_property_input` returned `expression` as a ref-path string although its schema described an object reference; consumers must accept both shapes.
- K12 count 1: `TextureTools.get_size` accepts `Texture2D` only and rejects render targets and volume textures; use `ObjectTools.get_properties` (`sizeX`, `sizeY`, format) for those classes.
- K13 count 1: `AssetTools.find_assets.asset_type` rejected the bare class name `NiagaraSystem` as an object path; omit the filter when the exact class refPath has not been queried, then verify returned asset classes separately.
- K14 count 1: `NiagaraToolset_System.GetSystemCompileState` timed out after 120 seconds on `/Game/Bifrost/Ocean/Wave/NS/NS_InfiniteMesh` while summary, topology, input-value, and renderer reads succeeded; treat the async compile/stack diagnostics endpoints as unavailable for this asset until their completion callback is fixed.
- K15 count 1: a large `GetScriptGraphText` response written through the Access Pack `-OutFile` path was not valid JSON when the exported Niagara graph contained backslash-quote text inside an HLSL comment; direct MCP output remained readable. Workaround: extract the needed raw substring without `ConvertFrom-Json`, or return a smaller filtered payload.
- K10 count +1 (now 2): `AssetTools.get_referencers` again raised `'NoneType' object is not iterable` for the unreferenced `/Game/Bifrost/Materials/M_Env_Uber_ProbeRepair`; exact-path deletion followed by `exists=false` verified cleanup.

### 2026-07-22 VibeUE integration additions

- K16 count 3: `PerformanceService.frame_timing` via MCP twice reported about 3370 ms game thread outside PIE and about 7817 ms in PIE while render/GPU stayed near 1–3 ms. The interface is verified, but the data is rejected; game-thread blocking or stale-stat contamination is only a hypothesis until an independent trace/async sample agrees.
