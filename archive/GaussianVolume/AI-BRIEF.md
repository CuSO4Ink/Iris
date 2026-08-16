<!-- iris-project-kind: ue -->
# GaussianVolume

> **UEAgent first（归档条件块）.** 本项目归档后只允许离线查阅。若未来恢复 live
> Unreal 工作，先把项目移回 `work/`，再读
> [UEAgent](../../work/UEAgent/AGENTS.md) 与
> [HOTPATH](../../work/UEAgent/skills/ue-mcp-workflows/HOTPATH.md)，读取目标
> `Saved/UEAgent/route.json` 并运行 `compact_context.ps1`。停止于 `CACHE_READ`；
> `NEEDS_DOCTOR` 时只运行一次 routed `doctor.ps1`。离线分析不得声称 live Editor 状态。

> [!ARCHIVED] **归档说明（2026-08-12）**
> - **原因**：G35 视觉、G37 性能与 G38 显存闭环已完成；其余实验支线停止。
> - **保留**：最终报告、复盘、源码、测试、插件快照、补丁和可提交证据已恢复归档；
>   只排除自动缩略图、活动 BACKLOG、运行目录和未晋升生成物。
> - **后续**：只有出现明确的新产品问题、基线、预算和验收 Gate 时才移回 `work/`。

## 最终结论

- 冻结基线：标准 3DGS 自适应几何、单记录 shared-opacity 六轴静态 transport、DGSM。
- 已验证范围：当前静态云、中远景、单方向光加天光、既定 UE/SVT 对照条件。
- 最终实测：GS feature `1.093 ms`，RHI 净新增 `66.476 MiB`；同条件 SVT 分别为
  `3.241 ms` 与 `305.566 MiB`。
- 结论不得扩展到近景 Hero、动画、多光源或通用 VDB 替代。

## 保留的方法

- [summary/PROJECT-RETROSPECTIVE.md](summary/PROJECT-RETROSPECTIVE.md)：完整阶段与失败分支复盘。
- [IMPLEMENTATION-AND-OPTIMIZATION-LEDGER.md](IMPLEMENTATION-AND-OPTIMIZATION-LEDGER.md)：G1–G39 实现账本。
- [PERFORMANCE-VDB-VS-G35-G37-20260731.md](PERFORMANCE-VDB-VS-G35-G37-20260731.md) 与
  [VRAM-COLD-G37-VS-SVT-20260731.md](VRAM-COLD-G37-VS-SVT-20260731.md)：最终性能和显存依据。
- [SOP-VDB-TO-GS-G35.md](SOP-VDB-TO-GS-G35.md)：冻结生产路径。
- [HISTORICAL-BRIEF.md](HISTORICAL-BRIEF.md)、`SPEC.md`、`LOG.md`、`CLOUD_VERSIONS.md`：
  完整合同、事实与版本记录。
- `mvp/`、`training/`、`ue-plugin/`、`patches/`、`evidence/`：可复现源码、测试和证据。
- [项目进度方法论](../../notes/project-progress-methodology.md)：共享执行方法。

## 资产边界

最终 VDB、PLY、checkpoint、UE 地图、Actor 实例覆盖、构建目录和运行日志没有进入 Iris
Git，也不在本归档中。它们的路径、参数和哈希由历史 Brief、SOP 与复盘保存；恢复 live
现场仍依赖外部 UE 项目，不能把本归档描述为可独立还原完整关卡。
