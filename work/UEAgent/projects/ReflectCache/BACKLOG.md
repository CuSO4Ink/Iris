# ReflectCache BACKLOG

## 待办

- [ ] 处理资产 rename/delete 后的旧 sidecar。
- [ ] 在 bootstrap 构建出的干净测试项目中，对五类资产各做一次受控保存，验证 sidecar
      no-op、失败路径和格式版本；完成前 doctor 继续报告 `PRESENT_UNVERIFIED`。
- [ ] 只有在真实任务需要时，再为外部 Niagara module/function script 增加独立 cache。

## 已完成

- [x] 2026-08-01 将完整 VibeUE 差异固化为 `patches/vibeue-ueagent.patch`，由 bootstrap
      默认应用并以 SHA256 写入项目 route。
- [x] 2026-07-29 将 MaterialInstance、Blueprint 和 NiagaraSystem 生成器接入统一 rebuild
      与 package-save handler；Blueprint 复用 graph DSL，Niagara 支持 embedded-module。
- [x] 2026-07-29 Wave 全目录盘点：55 个包、37 个 active-name、18 个备份；完成 6 Material、1 MaterialFunction、4 MaterialInstance、2 Blueprint、1 NiagaraSystem，共 14 份 sidecar。
- [x] 2026-07-29 完成 MaterialFunction 整编、自动测试、真实 `MF_CoastlineWave` 回填与重复 no-op 验证；99/108、9,271 bytes，源资产未改。
- [x] 2026-07-29 用真实 Wave 确定 Blueprint/Niagara cache 边界，拒绝 Niagara raw graph text 和 Blueprint 巨型默认属性 dump。
- [x] 2026-07-29 借鉴上游 Niagara compile-diagnostics 遍历，扩展 `list_scratch_modules` 与 scratch graph 校验/apply：识别 legacy system-embedded module subobject，同时拒绝外部 packaged script。
- [x] 2026-07-29 验收 v2 code IR：稳定别名、真实 Wave/Cloud `## Logic`、独立 output roots 与跨进程无改写。
- [x] 2026-07-29 完成 v2 编译、renderer 自动测试、真实 rebuild 与两次 save-hook 端到端验证。
- [x] 2026-07-29 将 cache 改为 `.uasset.ai.md` source sidecar，并把 UEAgent 材质读取改为 cache-first。
