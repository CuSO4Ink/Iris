# Screen Space Particle Reconstruction · BACKLOG

> 只保留当前尚未验证的执行项；完成与失败结论进入 `LOG.md`。

## 当前

- [ ] 在完全相同的近景相机下，分别抓取包含 Niagara 场景渲染的 Dense G5 与 Sparse V2 ProfileGPU。
- [ ] 对原始粒子 Renderer 候选执行 Apply / Compile / Save / Reinitialize，确认原始粒子与 G5 重建可同时对照。

## Gate 之后

- [ ] 根据同机位 A/B 决定保留、重做或放弃 Sparse V2；不得由理论候选数直接宣称性能收益。
- [ ] 只有 A/B 仍暴露追帧问题时，才评估是否持久化 `fx.Niagara.SystemSimulation.MaxTickSubsteps`。
- [ ] 完成冷启动回归：单活动实例、Main/Aux 非零、零编译错误、动态画面稳定。
- [ ] 视觉与性能 Gate 都通过后冻结一个最终回滚点，再按依赖清理旧 Probe 与实验资产。
