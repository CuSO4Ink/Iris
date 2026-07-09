# UEAgent · MCP 坑册

> MCP / 连接器调用踩坑的**计数台账**。踩一次记一笔，同一类坑连续命中 3 次 → 归并成一条「经验」沉淀。
> 台账只留**活跃计数**；毕业的经验单独成节，并优先反哺 `AI-BRIEF.md` 硬约束或跨项目 MEMORY。

## 计数规则

- 一次调用踩一个坑 → 对应条目计数 +1，附日期 + 一句现场
- 同类连续命中 **3 次** → 提炼成 §经验，台账条目归档
- 「连续」按命中该类的时序算，中间夹别的坑**不算断**
- 拿不准是否同类 → 先各记各的，别硬并；宁可晚毕业

## 活跃台账（未毕业）

| # | 坑类 | 计数 | 最近命中 | 现场（一句） |
|---|---|---|---|---|
| K1 | 废弃 API 直接抛错 | 2 | 2026-04-27 | `EditorLevelLibrary.get_level()` 在 5.7.3 报错；新 API 是 `get_all_level_actors()`（AI-BRIEF + BACKLOG 各一次） |
| K2 | 插件覆盖/枚举不全 | 1 | 2026-04-27 | `add_node_to_blueprint` 的 `CommonLibraries` 硬编码只 10 个 Kismet 库，Niagara 成员函数搜不到 |
| K3 | UObject 层没有的编辑器操作 | 1 | 2026-04-27 | 扫 256 个 `Niagara*` 类无 "Promote Input→User Parameter"，该操作只活在 Slate 层 |
| K4 | WorkBuddy 机制反直觉 | 1 | 2026-04-27 | 手改 `mcp.json` 不热扫描，必须走左侧栏「连接器」启用 |
| K5 | 子进程环境不继承 shell | 1 | 2026-04-27 | spawn MCP 时裸 `python` 找不到，得写 python.exe 绝对路径 |

> [!NOTE] 计数来源是 `LOG.md` 的历史条目，非本会话现踩。后续每次真跑 MCP 命中同类 → 在这里 +1。
> — ai 2026-07-07

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

---

## 维护

- 新坑先进台账；毕业条目搬到本节并考虑反哺 `../AI-BRIEF.md`
- 台账 > 8 行或经验 > 5 条 → 考虑拆分 / 归并到跨项目 MEMORY
