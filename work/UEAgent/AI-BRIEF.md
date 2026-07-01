# UEAgent

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

用 WorkBuddy AI + MCP 协议通过自然语言操控 Unreal Engine 5.7.3 编辑器进行开发——把"打开编辑器点鼠标敲菜单"换成"跟 AI 说一句话"。

## 当前状态

**活跃** · 链路调通阶段刚结束，进入实际使用阶段。

## 当前焦点

用 `execute_unreal_command` + `execute_python_script` 两个万能工具跑通第一个实际开发需求，摸清哪些工具能用、哪些要绕过。

## 技术栈与硬约束

- **UE 版本**：5.7.3（Python 3.11）——插件里若出现 `EditorLevelLibrary.get_level()` 这类旧 API 会直接报错，新 API 是 `get_all_level_actors()`
- **UE 项目**：`C:\Work\UEProject\Study\study\study.uproject`
- **插件**：`Plugins/UnrealGenAISupport/`（第三方开源 + 另一 AI 修过一轮的 fork）
- **MCP 服务端**：外部 Python 进程 `mcp_server.py`（FastMCP）走 stdio，UE 内 `unreal_socket_server.py` 走 TCP 9877
- **WorkBuddy 客户端约定**：MCP 叫「连接器」，左侧栏配置；工具前缀 `mcp__connector-proxy__unreal-genai_<name>`
- **线程规则**：Unreal Python API 必须在 game thread 调——handler 里若直接在 socket 接收线程调 `unreal.SystemLibrary` 等会翻车

## 术语表

| 术语 | 含义 |
|---|---|
| **连接器** | WorkBuddy 对 MCP 的别名 |
| **unreal-genai** | 本项目注册的 MCP server 名字 |
| **handler** | 插件 `Content/Python/handlers/` 下的各个 `*_commands.py` 模块，承载每个 MCP 工具的实现 |
| **dispatcher** | `unreal_socket_server.py` 里的 `CommandDispatcher`，按 `type` 分发请求到 handler |
| **万能二兄弟** | `execute_unreal_command`（控制台命令） + `execute_python_script`（任意 Python）——其他工具坏了就走这两个 |

## 文档地图

- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水，凡是选了/否决了/踩坑/发现 都在这里追加
- `BACKLOG.md` — 待办
- `notes/tool-inventory.md` — **（待建）** 29 个工具逐个实测状态

### 跨项目关键记忆（在 `~/.workbuddy/memory/MEMORY.md`）
- "MCP / 连接器接入备忘" 段：完整的启动依赖链、已知插件缺陷、链路健康验证命令
- "UE / Niagara 技术备忘" 段：UE 资产 Rename=Move、Niagara Custom HLSL 约束等历史经验

## 协作约定

- **先用再修**：能用 `execute_python_script` 绕过的插件 bug 不修；高频且绕不过的才打补丁
- **补丁只改 handlers**：`mcp_server.py` 和 `unreal_socket_server.py` 验证过没问题，别动
- **链路健康体检命令**：`execute_unreal_command "stat fps"`——能跑就说明 MCP→UE 全链路活的
- **调用前确认前置**：UE 项目开着 + 在 UE Python 命令栏跑过 `py "...unreal_socket_server.py"` + 看到 "socket server started on port 9877"

---

## 维护

- 阶段切换 / 插件补丁合入 / 新增常用工作流 → 更新本文件
- ≤ 100 行，超了拆到 notes/
