# RenderDocMCP

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

打造一套通用的 RenderDoc MCP 工作流——让 AI 能加载 `.rdc` 捕获文件、逐帧分析 Draw Call / Pipeline State / 资源绑定、反编译和反汇编 Shader，把"打开 RenderDoc 点鼠标看帧"变成"跟 AI 说一句话"。

## 当前状态

**活跃** · RenderDoc 扩展桥接与 MCP 已跑通，已完成真实 D3D11 `.rdc` 抓帧分析，进入工具完善与分析工作流阶段。

## 当前焦点

维护 `qrenderdoc` 扩展 + 文件 IPC 的可用桥接实现，完善真实帧分析工具，并沉淀 Pass/Draw/资源/Shader 的分析工作流。已验证：加载 `.rdc` → 获取帧统计 → 遍历渲染事件 → 查询 Pipeline State → 获取 GPU timings。当前样例帧流程图：`output/0679a345-0ada-4861-9cf5-222277160c16/zzz-frame10665-render-flow.svg`。

## 技术栈与硬约束

- **RenderDoc**：1.x（Python 3.6+），通过 `renderdoc` 模块（`renderdoc.pyd` / `renderdoc.so`）调用底层 Replay API
- **MCP SDK**：Python `mcp` 包（FastMCP），stdio 传输
- **核心 API 路径**：`OpenCaptureFile()` → `cap.OpenCapture()` → `ReplayController` → `GetDrawcalls()` / `GetPipelineState()` / `DisassembleShader()` / `GetCBufferVariableContents()`
- **Shader 反编译**：`controller.GetDisassemblyTargets(True)` 枚举可用格式（DXBC / SPIR-V / AMD GCN ISA 等），`controller.DisassembleShader(pipe, shaderReflection, target)` 输出反汇编文本
- **生命周期**：`InitialiseReplay()` 只调一次 → 所有操作 → `ShutdownReplay()`；`renderdoc.pyd` 必须与 RenderDoc 安装版本匹配，Python 版本也必须一致
- **平台**：Windows 为主（`renderdoc.pyd`），Linux 可选（`renderdoc.so`）

## 术语表

| 术语 | 含义 |
|---|---|
| **RDC** | RenderDoc Capture 文件格式 `.rdc`，包含一帧的完整 GPU 状态 |
| **Draw Call** | 一次绘制调用，是帧分析的最小单元 |
| **Pipeline State** | 管线状态对象（PSO），包含 shader 绑定、渲染目标、混合状态等 |
| **Disassembly Target** | 反汇编格式，如 DXBC、SPIR-V、AMD GCN ISA；首个总是合理默认值 |
| **Shader Reflection** | Shader 反射对象，包含输入/输出签名、资源绑定、常量缓冲区结构 |
| **ReplayController** | RenderDoc Python API 的核心控制器，所有分析操作都从它发起 |
| **CBuffer** | 常量缓冲区，`GetCBufferVariableContents()` 可递归获取所有变量及当前值 |

## 文档地图

- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水
- `BACKLOG.md` — 待办清单
- `RenderDocMCP-方案.md` — 完整技术方案（架构、工具集设计、API 映射、实现计划）

## 协作约定

- **先跑通再优化**：最小闭环优先（加载→Draw Call→Shader 反汇编），再逐步补全工具集
- **文档先行**：方案文档是单一真相源，代码实现与文档保持同步
- **MCP 经验复用**：参考 [UEAgent MCP 坑册](../UEAgent/notes/mcp-坑册.md) 的踩坑经验（子进程路径、自报成功不可信等）

---

## 维护

- 阶段切换 / 工具集扩展 / API 变更 → 更新本文件
- ≤ 100 行，超了拆到 notes/
