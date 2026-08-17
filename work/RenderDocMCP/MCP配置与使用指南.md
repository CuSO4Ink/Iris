# RenderDoc MCP 配置与使用指南

> 本文是 **分析工作区** `C:\Work\AI\Iris\work\RenderDocMCP\` 的接入入口。
> 真正的 MCP Server 与 qrenderdoc 扩展代码在另一个同名目录：
> `C:\Work\AI\RenderDocMCP\`。不要把两者混为同一个项目。

## 两个同名目录

| 目录 | 职责 | 是否在此配置 MCP |
| --- | --- | --- |
| `C:\Work\AI\Iris\work\RenderDocMCP\` | 分析工作区：捕获、交付、日志、定制 RenderDoc、Skill | 否；本文只提供指针与操作说明。 |
| `C:\Work\AI\RenderDocMCP\` | MCP Server、qrenderdoc 扩展、安装脚本、`.mcp.json` | 是；所有安装和代码修改均在此目录完成。 |

## 架构

```text
AI 客户端（stdio）
        ↓
renderdoc-mcp（Python + FastMCP）
        ↓  文件 IPC：%TEMP%/renderdoc_mcp/
RenderDoc qrenderdoc 扩展（RenderDoc MCP Bridge）
```

RenderDoc 内置 Python 缺少 `socket` 模块，因此这里使用文件 IPC，不是网络 Socket 连接。

## 首次配置（四步）

以下命令均以 `C:\Work\AI\RenderDocMCP\` 为工作目录。

1. 安装 qrenderdoc 扩展。

   ```powershell
   cd C:\Work\AI\RenderDocMCP
   python scripts/install_extension.py
   ```

   该脚本把扩展复制到 `%APPDATA%\qrenderdoc\extensions\renderdoc_mcp_bridge`。

2. 在 RenderDoc 中启用扩展。

   打开 RenderDoc → `Tools` → `Manage Extensions` → 勾选 **RenderDoc MCP Bridge**。

3. 安装 MCP Server，并让命令进入 PATH。

   ```powershell
   cd C:\Work\AI\RenderDocMCP
   uv tool install .
   uv tool update-shell
   ```

   重开终端后，用 `renderdoc-mcp` 验证命令可被找到。开发时可使用
   `uv tool install --editable .`，使 Server 源码改动无需重复安装。

4. 配置 AI 客户端。

   通用 MCP 配置为：

   ```json
   {
     "mcpServers": {
       "renderdoc": {
         "command": "renderdoc-mcp"
       }
     }
   }
   ```

   Claude Code 可写入项目 `.mcp.json`；Claude Desktop 写入其配置文件。WorkBuddy 需要把同一配置写到
   `~/.workbuddy/mcp.json`，再在左侧“连接器”面板启用，并新开对话建立调用通道。

## 使用顺序

1. 启动 RenderDoc，并在 UI 中打开目标 `.rdc`。
2. 确认 **RenderDoc MCP Bridge** 仍启用。
3. 在已启用连接器的 AI 对话中调用工具，如 `get_capture_status`、`get_draw_calls`、
   `get_draw_call_details`、`get_shader_info`、`get_pipeline_state`、`get_texture_info`、
   `get_texture_data`、`open_capture`。

## 必须记住的坑

- **改扩展源码后必须重新安装**：修改 `C:\Work\AI\RenderDocMCP\renderdoc_extension\` 后，先重跑
  `python scripts/install_extension.py`，再到 `Tools > Manage Extensions` 取消勾选/重新勾选。仅重勾不会更新
  `%APPDATA%` 下的扩展副本。
- **`renderdoc-mcp` 找不到**：通常是没有执行 `uv tool install .` / `uv tool update-shell`，或当前终端尚未重开。
- **WorkBuddy 看不到工具**：检查连接器是否已启用；启用后新开对话。
- **大捕获会使回放压力很大**：打开 3–4 GiB 的 `.rdc` 前先退出游戏，避免回放和游戏同时占用 GPU 导致 Device Lost。

## 事实来源

- 外部代码库安装说明：`C:\Work\AI\RenderDocMCP\README.md`（日文原文）
- 外部代码库客户端样例：`C:\Work\AI\RenderDocMCP\.mcp.json`
- 扩展/MCP 的实现与开发约束：`C:\Work\AI\RenderDocMCP\CLAUDE.md`
- TLOU2 定制截帧（不是 MCP 安装）：`TLOU2-RenderDoc注入排查操作记录.md`
