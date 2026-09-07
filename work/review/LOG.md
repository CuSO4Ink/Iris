# review · LOG

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.

### 2026-08-29 — [决策] 图谱重构为通用岗位体系
按用户要求重写 `TA-KNOWLEDGE-GRAPH.md`：从「个人证据映射」改为「图形 TA 必须熟练
掌握的行业通用知识体系」。四层 18 域，每域只留核心节点与熟练掌握判定标准；个人
自评/证据/盲区全部回归复习卡与正本，本文件不再维护。原盲区清单随重构移除。

### 2026-08-29 — [决策] 新增 TA 知识图谱文档
建立 `TA-KNOWLEDGE-GRAPH.md`：16 个知识域 + 深度分级 L1–L4 + 7 条跨域主干边 +
盲区清单。定位为岗位全景/深度标准，与证据向复习卡互补；图谱不做证据判定，
不回填正本证据等级。识别盲区：阴影/GI、数学白板推导、颜色科学链路。

### 2026-08-25 — [决策] 正本落位 notes/，新增当前项目状态整合
基于用户提供的 `resume-tech-stack-analysis.md`（原核验 2026-08-23）建立
`notes/resume-tech-stack-analysis.md` 正本，并对照 14 项 Iris 内部依据与各活跃/归档
项目 Brief 新增「当前项目状态整合」章节；最近核验更新为 2026-08-25。

### 2026-08-25 — [决策] 简历原文逐字核对完成，新增两处表述风险
用户提供简历全文（`c:/Users/violina/Downloads/refrence/彭典-技术美术简历.pdf`）后逐条
对照：新增必须修正“中近景→中远景”（与 GaussianVolume 冻结边界直接冲突）；新增
限定 3DGS 替代 VDB 只限中远景窗口、SSPR 高斯椭圆流体只能讲预研；映射表新增
AirWall 实习空气墙行；来源登记补登复习卡与证据索引。

### 2026-08-25 — [发现] 复习包已迁移到本机并复验通过
`resume-review-pack` 实际位于 `C:/Users/violina/Downloads/resume-review-pack/`，含
resume.pdf、PCG/cloud/water 缓存与 source-cache manifest；`resume.pdf` SHA-256 与登记
完全一致。正本来源登记已改为本机路径，外部证据链恢复可用。

### 2026-08-25 — [发现] 外部复习包登记路径与当前用户目录不一致
正本来源登记为 `C:/Users/mafuyuena/Downloads/resume-review-pack/`，当前机器用户目录为
`C:/Users/violina/`；输入文件实际位于 `C:/Users/violina/Downloads/`。复习包本体是否
存在需确认，已列入 BACKLOG；确认前不把缺失外部文件写成项目事实失效。

### 2026-09-07 — [决策] review 改为逐项目面试技术挖掘
按用户要求，将目标由简历证据核对改为过完整项目过程、挖全技术点；旧 7 项补证据退出当前待办，旧 85% 与背倍率优先级撤销。
新增 PROJECT-INTERVIEW-MAP 为主入口；证据参考、通用概念、岗位图谱分工保留，用户掌握程度只由实际问答判断。

### 2026-09-07 — [发现] 旧复习遗漏与状态混淆
首轮目录/Brief 盘点补入 DyeSplashBaker、NiagaraGridBounds、lightning、test 两题、BlendderMcp、Kinesis 等来源；SSPR 双目录主线待对齐。
RenderDocMCP 已有归档入口，UEAgent 已到 Protocol 3.0，NPR 后续材质排查未进入旧摘要；当前只完成提纲盘点，不宣称全技术点已挖完。
