# UEAgent · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 摸底实测：用 `execute_unreal_command` / `execute_python_script` 跑几个真实操作，确认链路稳定

## 待办

- [ ] 给 29 个工具建一份 `notes/tool-inventory.md`，逐个标注：✅ 可用 / ⚠️ 部分可用 / ❌ 坏了（和对应的绕过方案）
- [ ] [低优先级] 修复 `get_all_scene_objects`：`handlers/basic_commands.py` 里把 `EditorLevelLibrary.get_level()` 换成 `EditorLevelLibrary.get_all_level_actors()` 或 `UnrealEditorSubsystem().get_editor_world()`
- [ ] [低优先级] 修复 `handshake_test`：把 `unreal.SystemLibrary.get_engine_version()` 调用包到 game thread（或直接改成读 `unreal.SystemLibrary` 以外的 API）
- [ ] 沉淀"常用工作流"模板：例如"创建一个 Character Blueprint + 加跳跃 + 编译保存"这类高频组合操作的标准指令序列
- [ ] 确认 `execute_python_script` 的等待机制是否稳定（插件里用了 `time.sleep(0.5)` 硬等，复杂脚本可能要更长时间）

## 已完成（近期，便于回忆）

- [x] 2026-04-27 对比 UnrealMCPBridge 与 UnrealGenAISupport 源码，选定后者
- [x] 2026-04-27 外部 Python 依赖装配：`fastmcp` `mss`（fastmcp 3.2.4 实测可用，未降级）
- [x] 2026-04-27 WorkBuddy mcp.json 配置（`command` 用 python.exe 绝对路径）
- [x] 2026-04-27 UE 插件编译并启用
- [x] 2026-04-27 UE 内手动跑 `unreal_socket_server.py` 成功监听 9877
- [x] 2026-04-27 WorkBuddy 左侧栏「连接器」启用 `unreal-genai`，29 个工具上线
- [x] 2026-04-27 链路体检通过：`execute_unreal_command "stat fps"` 成功返回

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。
