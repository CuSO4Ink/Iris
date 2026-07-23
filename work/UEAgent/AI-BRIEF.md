# UEAgent

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

用 AI + MCP 协议通过自然语言操控 Unreal Engine 5.8（`Abyss` 工程）编辑器进行开发——把"打开编辑器点鼠标敲菜单"换成"跟 AI 说一句话"。当前以 UE 官方 MCP 插件为底座；VibeUE 已作为同端点、按需能力扩展完成接入验证，旧栈（WorkBuddy + UnrealGenAISupport / TCP 9877）已作废。

## 当前状态

**活跃** · 2026-07-23 已收口为路径无关的可迁移流程：仓库内包含安装、连接和验收入口，外部只依赖 UE 5.8 官方源码/安装与固定 commit 的 VibeUE。`Abyss` 在线验证基线仍为 VibeUE `271f487`、10 个顶层工具、30 个 service toolset、35 个核心 skill；数量只作历史观测，不作验收常量。

## 当前焦点

用真实开发需求验证“官方工具优先、VibeUE 补能力缺口”的分层；在项目内 `skills/ue-mcp-workflows/` 持续固化已验证 SOP。VibeUE `PerformanceService` 当前只能证明接口可调用，返回时序数据不可信，未进入作品证据链。

## 技术栈与硬约束

- **UE 项目**：任意本机 UE 5.8 `.uproject`；路径通过 `scripts/bootstrap.ps1 -UProject/-EngineRoot` 显式传入
- **MCP 端点**：`http://127.0.0.1:8000/mcp`（streamable-http），UE 侧是官方 ModelContextProtocol 插件
- **协议形态**：官方 Tool Search 的 3 个 meta tool（`list_toolsets` / `describe_toolset` / `call_tool`）仍在；VibeUE 同时直挂 7 个 direct tool，当前合计 10 个。数量是启动期发现结果，不再写死为协议常量
- **常用官方 toolset**：`SceneTools` / `ActorTools` / `AssetTools` / `ProgrammaticToolset`；VibeUE 只补 transactions、Niagara scratchpad、领域服务等官方缺口
- **接入方式**：原生支持 MCP 的宿主直连 UE 项目根目录 `.mcp.json`；不支持的宿主走仓库内 PowerShell gateway 兜底
- **Python 边界**：官方 `ProgrammaticToolset` sandbox 不可 `import unreal`；只有 VibeUE `execute_python_code` 已验证可导入。两者不可混淆，任一 mutation 都服从同一套验真、单写者、清理与保存规则
- **能力路由**：通用资产/Actor/场景/材质 CRUD 先用官方 typed tool；官方缺能力时再选 VibeUE service；任意 Python 仅作已发现、已限域的兜底，不作默认路径
- **硬规则**：不假设可直接新建空白关卡；多 Actor/重复调用走批量脚本；生成内容必须带 batch tag + semantic tag + Outliner folder + cleanup 方案；delete/move/save/merge 属高风险操作，需先限定 tag/folder 范围
- **旧栈（已作废，仅存历史参考）**：UnrealGenAISupport 插件 + TCP 9877 + 29 工具直接展开，UE 5.7.3。技术细节不再维护，历史记录见 `LOG.md`；通用踩坑经验已沉淀进 `notes/mcp-pitfalls.md`

## 安装与外部依赖

- `SETUP.md` 是跨设备安装唯一入口
- `scripts/bootstrap.ps1` 负责插件固定版本、项目配置与构建
- `scripts/mcp_gateway.ps1` 是非原生 MCP 宿主的仓库内兜底；不再依赖本机外置 Access Pack
- 外部仅保留稳定源码：UE 5.8 官方发行/源码，以及 VibeUE GitHub commit `271f48771d077179fb597dc285ab5b898c5e8038`
- 本机引擎分支和未提交 NiagaraToolsets 修改不是 UEAgent 基线依赖

## 术语表

| 术语 | 含义 |
|---|---|
| **meta tool** | 官方 Tool Search 保留的 3 个间接路由工具；安装扩展后不代表顶层只会有这 3 个 |
| **toolset** | 按领域分组的真实工具集合，如 `editor_toolset.toolsets.scene.SceneTools` |
| **VibeUE service** | VibeUE 暴露的领域服务；只在官方工具缺能力且 live discovery 确认 schema 后调用 |
| **gateway** | `mcp_gateway.ps1`，给不支持原生 MCP 的宿主用的 PowerShell 兜底调用脚本 |
| **batch tag** | 批量生成 Actor 时必须打的统一标签，用于后续查找/清理 |

## 文档地图

- `AI-BRIEF.md` — 本文件
- `SETUP.md` — 跨设备安装、固定依赖与验收入口
- `scripts/bootstrap.ps1` / `scripts/mcp_gateway.ps1` — 配置与连接实现
- `LOG.md` — 决策流水，凡是选了/否决了/踩坑/发现 都在这里追加
- `BACKLOG.md` — 待办
- `notes/mcp-pitfalls.md` — MCP 调用踩坑台账 + 已毕业经验（E1/E2 通用，长期有效，跨旧新栈）
- `skills/ue-mcp-workflows/` — UE MCP 工作流 Skill 主源；平台需要时再迁移，不在平台目录内主维护

## 协作约定

- **先自检再选接入方式**：原生支持 MCP → 读 UE 项目根目录 `.mcp.json`；不确定 → 走仓库内 gateway，不要自己实现握手/SSE 解析
- **参数复杂用 `-ArgumentsFile`**：避免 shell 转义坑，别硬凹 `-ArgumentsJson`
- **踩坑统一入项目**：连接器、gateway 与 UE MCP 问题都记 `notes/mcp-pitfalls.md`
- **真实任务后做摩擦检查**：仅在重复调用、猜参重试、手工恢复、payload/延迟或能力缺口实际发生时，按 `skills/ue-mcp-workflows/references/core.md` 的闭环记录或改进；项目内 Skill/探针/gateway 可验证后直接更新，UE/VibeUE 插件和生产资产仍需用户批准
- **截图类操作先问用户，不擅自跑** → 见 `notes/mcp-pitfalls.md` E2（唯一详情源，不在此复述）

---

## 维护

- 阶段切换 / 插件补丁合入 / 新增常用工作流 → 更新本文件
- ≤ 100 行，超了拆到 notes/
