# EffectPipeline · BACKLOG

> 待办清单。顺手加，做完打勾。详细分析见 `notes/`。

## 当前最高优先

- [ ] **特效对齐离线渲染 Sequence** — 将外包特效正确导入主工程并对上离线渲染 Sequence
  - 不优先关心材质替换，优先保证特效在 Sequence 中正确播放
  - 可用样本：D20（HoudiniNiagara 已跑通）、B20（ZibraVDB uasset + .zibravdb 源闭包最完整）、A45（ZibraVDB uasset 完整但缺独立源，License 待激活）
  - 关键路径：特效资产导入 → 放入关卡 → 对齐 Sequence 时间轴 → 离线渲染验证

## 进行中

- [ ] 深扫 B20 完整样本：资产依赖簇 + .zibravdb 源 + umap 引用关系（作为 ZibraVDB 完整闭包参照样本）
- [ ] 复核 A45：ZibraVDB uasset 完整但缺独立 .zibravdb 源，确认 License 激活后是否可直接用于渲染验证

## 待办

### 阶段 0 · 摸底（部分完成）
- [x] 外包归档实勘：15 工程完整度分级（见 `notes/外包归档清单.md`）
- [x] 引擎版本统计：统一 UE 5.5（C30=GUID自定义）
- [x] D20 Volume None 根因定位（见 `notes/ZibraVDB排查结论.md`）
- [x] BYDC 逐工程详查：9 个工程输出不统一问题汇总（见 `notes/外包归档清单.md` §2、§5）
- [ ] 确认是否有 UE 5.5 公版引擎（决定 Migrate 能否走通）
- [ ] 找外包补交 D20 的 ZibraVDB Volume / .zibravdb 源
- [ ] E40 解压 .7z 后补充检查内容
- [ ] 抽样审查 5 个特效的散材质，归纳共性参数

### 阶段 1 · 规范定义
- [x] 外包特效交付规范 v1.0（见 `notes/外包交付规范.md`）
- [ ] 主工程目录/命名规范（FX/<EffectName>/，见 notes/外包归档清单 §6）
- [ ] 设计母材质 M_FX_Master（普通粒子族 + 体积族两套）—— 降优先，先保证 Sequence 对齐
- [ ] 材质映射表：散材质参数 → 母材质 MI 参数 —— 降优先

### 阶段 2 · 试点导入 + Sequence 对齐
- [ ] D20 特效导入主工程 → 放入关卡 → 对齐离线渲染 Sequence（HoudiniNiagara 已跑通，首选试点）
- [ ] B20 完整 ZibraVDB 闭包导入 + Sequence 对齐（uasset + .zibravdb 源均存在，待 ZibraVDB License 激活）
- [ ] A45 导入 + Sequence 对齐（ZibraVDB uasset 存在但缺独立 .zibravdb 源，待 License 激活验证）
- [ ] 验证 Houdini Engine / ZibraVDB 依赖在主工程正常
- [ ] 沉淀导入 + Sequence 对齐 Checklist / 脚本

### 阶段 3 · 批量执行
- [ ] 按清单批量导入剩余特效 → 对齐各自 Sequence
- [ ] Fix Up Redirectors + 引用校验 + 视觉回归
- [ ] 后续：统一材质替换（母材质 MI）

## 已完成（近期）
- [x] 需求澄清（形态混合/已有主工程/母材质+MI/保留Houdini/20+个）

---

完成超 2 周的项移除；有保留价值的写进 LOG.md。
