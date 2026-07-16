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

## 踩坑记录（qrenderdoc 扩展开发）

- **改扩展源码后必须重装才生效**：源码在 `C:/Work/AI/RenderDocMCP/renderdoc_extension/`，但 RenderDoc 实际加载的是复制到 `%APPDATA%/qrenderdoc/extensions/renderdoc_mcp_bridge/` 的独立副本。改完源码必须重跑 `python scripts/install_extension.py`（会清理 `__pycache__`），再去 RenderDoc 里 Tools→Manage Extensions 取消勾选/重新勾选。仅做后一步、不重装，代码不会更新（曾实测两次仅重载扩展开关无效，重装后才生效）。
- **RenderDoc API 版本变化**：`PipeState.GetConstantBuffer()` 已废弃，改为 `GetConstantBlock(stage, index, arrayIdx)`，返回 `UsedDescriptor`，取值要走 `.descriptor.resource` / `.descriptor.byteOffset` / `.descriptor.byteSize`（不是直接 `.resourceId`）。
- **bridge 客户端大文件读取需防非原子写**：`mcp_server/bridge/client.py` 的响应文件由扩展端 `json.dump()` 直写，大纹理（30MB+ base64）会被读到"写一半"状态导致 `JSONDecodeError`。已修复为轮询文件大小连续稳定后才解析。
- **游戏内建 shader 变量名可能未被剥离**：修复常量缓冲区读取后，本项目验证过的一款游戏（死亡搁浅：导演剪辑版）常量缓冲区里的变量名是原始引擎命名（如 `mWetness`/`mPrecipitation`/`mWindSpeed`），未被 strip，读取价值远超预期，遇到新捕获值得优先尝试。
- **全帧反查工具很慢**：`find_draws_by_texture` / `find_draws_by_resource` 逐 draw 扫描全部资源绑定，实测 80+ 秒一次，容易触发外部调用超时，需要放宽超时或改用"先按 marker/pass 缩小范围再逐个查 pipeline_state"的手动方式。

## 文档地图

- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水
- `BACKLOG.md` — 待办清单
- `RenderDocMCP-方案.md` — 完整技术方案（架构、工具集设计、API 映射、实现计划）
- `瀑布水体渲染实现方案技术参考.md` — **正式交付文档**，供团队参考做自己项目瀑布效果，去除分析过程叙事，按架构/机制/复用建议组织。核心机制一"水幕主体的流动视觉"（第2节）是瀑布效果本身，务必优先看这一节
- `死亡搁浅瀑布实现方案-美术TA向.md` — 分析过程存档（含勘误记录），面向美术/TA的第一版叙事性文档。**注意**：这份文档只分析了地形湿润和水花公告板两个辅助效果，遗漏了水幕主体（瀑布本身），已在开头加纠正说明并指向正式交付文档
- `frame55458-死亡搁浅纠偏与瀑布分析.md` — 分析过程存档，游戏身份纠偏 + 底层证据链

## 协作约定

- **先跑通再优化**：最小闭环优先（加载→Draw Call→Shader 反汇编），再逐步补全工具集
- **文档先行**：方案文档是单一真相源，代码实现与文档保持同步
- **MCP 经验复用**：参考 [UEAgent MCP 坑册](../UEAgent/notes/mcp-坑册.md) 的踩坑经验（子进程路径、自报成功不可信等）

---

## 维护

- 阶段切换 / 工具集扩展 / API 变更 → 更新本文件
- ≤ 100 行，超了拆到 notes/
