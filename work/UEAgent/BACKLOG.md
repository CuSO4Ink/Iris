# UEAgent · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 摸底实测：用新栈（`abyss-ue` / `editor_toolset.*`）跑几个真实操作，验证 `SceneTools`/`ActorTools`/`AssetTools` 常用工具在本项目内的表现
- [ ] 隔离验证 VibeUE `PerformanceService.frame_timing` 的可靠采样方式；在异步/trace 或独立指标对齐前禁入性能证据

## 待办

- [ ] 沉淀"常用工作流"模板：例如"创建/摆放 Actor + 打 batch tag + Outliner folder"这类高频组合操作的标准指令序列（新栈版）
- [ ] 探索 `ProgrammaticToolset.execute_tool_script` 批量脚本工作流，替代旧栈"万能二兄弟"的角色
- [ ] 仅对官方缺口做 VibeUE A/B：优先 `TransactionService`、Niagara Scratch Pad 与高阶领域服务；不重复封装官方 CRUD

## 已完成（近期，便于回忆）

- [x] 2026-07-23 将安装、固定版本 VibeUE、MCP 项目配置、gateway 与静态/在线验收收口进 UEAgent；移除运行期对本机绝对路径和外置 Access Pack 的依赖
- [x] 2026-07-22 将 VibeUE `271f487` 安装到 `Abyss`、完整编译并在线验证：10 个顶层工具、30 个 service toolset、35 个核心 skill；只做只读/可逆探针，未创建或保存资产
- [x] 2026-07-15 在 UEAgent 内创建 `skills/ue-mcp-workflows/`，首版固化 Core、材质、蓝图与场景编辑 SOP，并保留平台迁移边界
- [x] 2026-07-09 从旧栈（UnrealGenAISupport / TCP 9877）迁移到新栈（UE 官方 MCP 插件 / streamable-http :8000），详见 `AI-BRIEF.md` 与 `LOG.md`

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。旧栈遗留待办已随迁移清空，历史见 LOG.md。
