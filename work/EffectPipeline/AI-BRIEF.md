# EffectPipeline

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

把外包交付的、形态不统一的 Houdini/UE 特效（20+ 个）规范化导入到主 UE 工程，对齐离线渲染 Sequence。

## 当前状态

活跃 — 阶段0摸底完成，转入试点导入+Sequence 对齐

## 当前焦点

**最高优先：特效正确导入主工程并对上离线渲染 Sequence。** 材质替换降优先。
- D20 HoudiniNiagara 已跑通，作为首选试点
- B20 是当前最完整 ZibraVDB 闭包（uasset + .zibravdb 源）；A45 有完整 uasset 但未发现独立源，二者均需 ZibraVDB License 激活后验证
- BYDC 9 工程详查完成，交付规范 v1.0 已制定

## 关键事实（实勘）

- 外包归档：`J:\vendors\漫行者\Final最终归档`（只读），1022GB，15个uproject 均 UE5.5
- 主工程：自研 UE5.7.3（JY_SRC），跨版本+跨引擎，ZibraVDB 预编译 ABI 不可跨引擎复用
- 公版5.7.3源码已编译：`C:\Work\UEEngine\UnrealEngine`
- 黄金法则：插件未全部装好启用前，绝不保存任何关卡/资产（None会永久写盘）

## 技术栈与硬约束

- 引擎：Unreal Engine（主工程已存在，特效全部并入，不新建工程）
- 插件：保留 Houdini Engine（含 HoudiniNiagara），目标工程统一安装匹配版本
- 离线渲染：特效需对齐 Sequence 时间轴，通过离线渲染管线输出
- 材质：统一母材质 + MI（降优先，先保证 Sequence 对齐）
- 规模：20+ 个外包特效项目，形态混合（独立 uproject / 散装 Content / Houdini 源 / FBX 素材混杂）
- 一切导入须遵循统一命名规范与目录约定，不污染主工程既有资产

## 术语表

- **散材质**：外包各自创建、命名/参数不统一的 Material 资产
- **母材质 / Master Material**：项目统一的基础材质，开放参数供 MI 调
- **MI**：Material Instance，基于母材质实例化、只调参数
- **形态混合**：各外包项目交付物结构不一致（有的带 uproject，有的只有 Content）

## 文档地图

- `AI-BRIEF.md` — 本文件，项目身份
- `BACKLOG.md` — 待办清单
- `LOG.md` — 决策流水
- `需求分析.md` — 需求拆解与导入规范方案主文档
- `notes/外包归档清单.md` — BYDC 9 工程逐工程详查 + 不统一问题汇总 + 源文件分布
- `notes/外包交付规范.md` — 外包交付规范 v1.0（工程完整性/目录结构/命名/依赖/自检清单）
- `notes/ZibraVDB排查结论.md` — Volume None 根因 + 三层判读法 + ABI死结

## 协作约定

- 批量操作前先在少量样本（1-2 个特效）上验证流程，再放量
- 导入/材质替换均保留可回滚路径，不直接覆盖主工程资产

---

## 维护

- 阶段切换 / 术语变更 / 技术栈升级 → 更新本文件
- ≤ 100 行，超了拆到 notes/ 或新文件
- 项目归档时本文件随迁，保留
