# blender · LOG

### 2026-08-14 19:00 — [决策] 定位为 AI-DCC 执行层
BlenderAgent 与 UEAgent 统一 `Intent -> Plan -> Execute -> Readback -> Verify -> Save` 语义；当前
不抽取共享运行时，也不把聊天式任意 `bpy` 执行当默认路径。

### 2026-08-14 19:00 — [发现] 第二代上游的实际边界
`blender-ai-mcp` 的 guided 小入口面属实但实现很重；`glonorce/Blender_mcp` 的主线程、作业与检查
代码有参考价值且 499 项离线单测通过，但 raw code 仍是首要工具，`tools/list` 仍暴露全量 schema，
且仓库 MIT `LICENSE` 与 `pyproject.toml` 的 `Proprietary` 元数据冲突，暂不复制其代码。

### 2026-08-14 19:00 — [决策] 从一个可观测切片生长工具面
首个验收只覆盖创建、回读、度量、断言、截图和保存；15 个候选接口及
`prepare_game_asset` 不预建，等真实工作流证明需要后再加入。

### 2026-08-14 19:35 — [决策] Blender 路径使用机器级参数
各端以用户环境变量 `BLENDER_PATH` 保存完整可执行文件路径，不把绝对路径写入仓库；当前机器
已用该参数通过 Blender 5.2.0 LTS 的 factory-startup 后台 `bpy` 检查。
