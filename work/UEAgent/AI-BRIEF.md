# UEAgent

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

用 AI + MCP 协议通过自然语言操控 Unreal Engine（`study` 工程）编辑器进行开发——把"打开编辑器点鼠标敲菜单"换成"跟 AI 说一句话"。当前走 UE 官方 MCP 插件新栈（streamable-http /:8000），旧栈（WorkBuddy + UnrealGenAISupport / TCP 9877）已作废。

## 当前状态

**活跃** · 2026-07-09 起已从旧栈（UnrealGenAISupport 插件，TCP 9877）迁移到新栈：UE 官方 MCP 插件（streamable-http，:8000）。旧栈判定作废，不再维护。

## 当前焦点

用新栈跑通实际开发需求，摸清 `editor_toolset.*` 常用工具集；探索 `script.execute` 批量工作流。旧栈相关待办已随迁移清空，历史见 `LOG.md`。

## 技术栈与硬约束（新栈；权威源见下方「外部权威包」）

- **UE 项目**：`C:\Work\UEProject\Study\study\study.uproject`
- **MCP 端点**：`http://127.0.0.1:8000/mcp`（streamable-http），UE 侧是官方 ModelContextProtocol 插件
- **协议形态**：顶层只有 3 个 meta tool —— `list_toolsets` / `describe_toolset` / `call_tool`；真实工具（`editor_toolset.toolsets.*`）必须经 `call_tool` 间接调用，任何宿主都不会自动展开出二级工具
- **常用 toolset**：`SceneTools` / `ActorTools` / `AssetTools` / `ProgrammaticToolset`（内含 `execute_tool_script` 跑批量脚本）
- **接入方式**：原生支持 MCP 的宿主（如本项目）直连 `mcp.json`；不支持的宿主走 PowerShell gateway 兜底
- **硬规则**：不假设可 `import unreal`；不假设可直接新建空白关卡；多 Actor/重复调用走 `script.execute`；生成内容必须带 batch tag + semantic tag + Outliner folder + cleanup 方案；delete/move/save/merge 属高风险操作，需先限定 tag/folder 范围
- **旧栈（已作废，仅存历史参考）**：UnrealGenAISupport 插件 + TCP 9877 + 29 工具直接展开，UE 5.7.3。技术细节不再维护，历史记录见 `LOG.md`；通用踩坑经验已沉淀进 `notes/mcp-pitfalls.md`

## 外部权威包（跨项目共享，只引用不复制）

```
D:\Work\AI\UE_MCP_Access_Pack
```

- `AI_QUICK_START.md` —— 接入判断分支（原生直连 vs gateway 兜底）+ 逐平台自检清单
- `references/mcp_sop.md` —— 标准调用 SOP（action 列表、请求/响应包络）
- `references/toolsets.md` —— 已知工具集与能力边界
- `references/friction_log.md` —— 踩坑上报处；发现新坑先记这里，不擅自改 Pack 脚本，等用户批准

## 术语表

| 术语 | 含义 |
|---|---|
| **meta tool** | 顶层仅暴露的 3 个间接路由工具：`list_toolsets` / `describe_toolset` / `call_tool` |
| **toolset** | 按领域分组的真实工具集合，如 `editor_toolset.toolsets.scene.SceneTools` |
| **gateway** | `mcp_gateway.ps1`，给不支持原生 MCP 的宿主用的 PowerShell 兜底调用脚本 |
| **batch tag** | 批量生成 Actor 时必须打的统一标签，用于后续查找/清理 |

## 文档地图

- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水，凡是选了/否决了/踩坑/发现 都在这里追加
- `BACKLOG.md` — 待办
- `notes/mcp-pitfalls.md` — MCP 调用踩坑台账 + 已毕业经验（E1/E2 通用，长期有效，跨旧新栈）

## 协作约定

- **先自检再选接入方式**：原生支持 MCP → 直连 `mcp.json`；不确定 → 走 gateway，不要自己实现握手/SSE 解析
- **参数复杂用 `-ArgumentsFile`**：避免 shell 转义坑，别硬凹 `-ArgumentsJson`
- **踩坑先报不擅自改**：Pack 脚本/文档发现问题 → 写 Pack 的 `friction_log.md`，等用户批准再改；本项目自己的踩坑记 `notes/mcp-pitfalls.md`
- **截图类操作先问用户，不擅自跑** → 见 `notes/mcp-pitfalls.md` E2（唯一详情源，不在此复述）

---

## 维护

- 阶段切换 / 插件补丁合入 / 新增常用工作流 → 更新本文件
- ≤ 100 行，超了拆到 notes/
