# EffectPipeline · BACKLOG

> 待办清单。顺手加，做完打勾。详细分析见 `notes/`。

## 当前最高优先

- [x] ZibraVDB Personal Key 已到位，授权阻塞解除
- [x] 外包返包首轮验收扫描（6/9 已上传：C30/C50/C60/D20/E20/E40）
- [x] C30/C60 World Partition 文件夹豁免确认（2026-07-07 用户同意保留）
- [x] E40 空 Actor 版本接受确认（2026-07-07 用户同意不挂接 ZibraVDB）
- [ ] 外包继续上传 A45/B20/C80（3 个尚未到）
- [ ] 全部到齐后统一复核 + 进入主工程导入

## 首轮验收发现的问题（6 个已上传工程）

### ✅ 整体改善
- 6 个工程均有 uproject + Config + Content 三件套
- C30 已改为公版 UE 5.5（不再是 GUID 自定义引擎）✅
- 无 StarterContent / Developers 残留 ✅
- 目录结构统一到 `FX_<镜头号>/` 下 ✅
- 命名基本含镜头号前缀 ✅

### ❌ 待整改问题

**P0 — 必须处理：**
- [ ] **C50 插件声明严重超标**：uproject 启用 25+ 个插件（OpenXR/VirtualScouting/nDisplay/DMX/PixelStreaming/Composure/MediaIO/LiveLink 等），绝大多数与特效无关，违反规范 §1.3
- [ ] **D20 ZibraVDB Volume 缺 `.zibravdb` 源**：Volume\Assets\ 有 10 个 cloud uasset（总 ~6.3GB），但无 `.zibravdb` 源文件，无法在主工程侧重建
- [ ] **D20 关卡内 36 处 ZibraVDB 引用未验证**：需打开关卡确认是否已补齐 Volume 或删除无效 Actor
- [ ] **E40 无 Houdini 源说明**：原 `baiying_E40_pop4.hip` 不在工程内，且无 Houdini 源文件说明
- [ ] **E20 ZibraVDB 缺 `.zibravdb` 源**（⚠️ 2026-07-07 修正）：外包备注说明截图证实 E20 实际使用 ZibraVDB（ZebraVDB Playback 轨道 + ZebraVDB Actor），原扫描误判为 SparseVolumeMaterial；E20 也须补交 `.zibravdb` 源
- [x] ~~**C50 缺 `.zibravdb` 源**~~ → ✅ **已交付（2026-07-07 实测确认）**：6 个 `.zibravdb` 源已放入 `Volume/` 目录，与 uasset 成对交付
- [x] ~~**全部 ZibraVDB 镜头 `.zibravdb` 源均未随工程交付**~~ → ⚠️ **修正（2026-07-07 实测）**：C50 已交付源；实际缺源的是 D20/E20/E40 三个

**P1 — 应处理：**
- [x] ~~**C30/C60 使用 World Partition**~~ → ✅ **已豁免（2026-07-07）**：用户确认 __ExternalActors__/__ExternalObjects__ 是 WP 场景设置自动生成，Actor 全保存在这两文件夹下，在提交范围内保留
- [ ] **C30 目录名大小写不一致**：`Fx_C30`（小写 x）vs 规范 `FX_C30`
- [ ] **C60 Volume 无 ZibraVDB 声明却启用 ZibraVDB 插件**：C60 Volume 资产是 UE 原生 SparseVolumeTexture（SVTM），不应启用 ZibraVDB 插件
- [ ] **E20 插件含 ImagePlate**：与特效无关，应删除
- [ ] **E40 插件含 ImagePlate**：同上
- [ ] **D20 插件含 ImagePlate**：同上
- [ ] **C50 无 Sequence 资产**：只有 `C50_gk.umap`（64KB），无 Sequence 文件
- [x] ~~**C50 zibravdb 源体积极小**（280~405KB）~~ → 保留确认项：源已交付但体积异常小，仍需确认是否为正式效果资产还是占位/测试
- [ ] **E40 缺 Sequence 资产**：只有 `E40_gk.umap` + `E40_Sequencer.uasset`，但 Sequencer 命名不规范（应为 `E40_Sequence`）
- [ ] **Sequence 命名不统一**（⚠️ v1.2 新增）：C30/C60 用 `*_Sequence`，D20/E20/E40 用 `*_Sequencer`，须统一为 `*_Sequence`

**P2 — 建议处理：**
- [ ] **多个工程存在空目录**：C30 的 Geo/Material/PointCache 空；E20 的 Geo/Material/PointCache 空；C50 的 Geo/Material/Mesh/Niagara/PointCache/Texture 全空
- [ ] **全部 6 个工程均无 DELIVERY_NOTE.md**：规范 §6 要求每个镜头附带交付说明
- [ ] **Volume 目录结构不统一**：C30/D20/E20/E40 用 `Volume/Assets/` 子目录，C50/C60 用 `Volume/` 根目录
- [ ] **ZibraVDB 前后景遮挡问题**（⚠️ 2026-07-07 新增）：外包备注指出 ZibraVDB 会后景遮挡前景粒子，需通过调整 Volume Translucency Sort Priority 解决，主工程侧导入后需逐镜头检查
- [ ] **E40 ZibraVDB 主工程侧挂接**（⚠️ 2026-07-07 新增）：外包侧因内存不足崩溃，交付空 Actor 版本；主工程侧需自行挂接 ZibraVDB + 在 Sequence 添加 playback 轨道

## 返包验收通过后

### 阶段 2 · 试点导入 + Sequence 对齐

- [ ] 选择 1-2 个返包样本做主工程导入试点。
- [ ] 执行引用闭包检查：缺失引用 / Redirector / 跨工程 ExternalActors / 插件依赖。
- [ ] 放入主工程关卡，绑定对应 Sequence 时间轴。
- [ ] 离线渲染验证：画面与外包预览 mov 对齐。
- [ ] 沉淀导入 + Sequence 对齐 Checklist / 脚本。

### 阶段 3 · 批量执行

- [ ] 按清单批量导入剩余特效 → 对齐各自 Sequence。
- [ ] Fix Up Redirectors + 引用校验 + 视觉回归。
- [ ] 后续：统一材质替换（母材质 MI）——继续降优先，Sequence 对齐之后再做。

## 已完成（近期）

- [x] 需求澄清：形态混合 / 已有主工程 / 母材质+MI / 保留 Houdini / 20+ 个。
- [x] 外包归档实勘：15 工程完整度分级（见 `notes/外包归档清单.md`）。
- [x] 引擎版本统计：基本 UE 5.5，C30 为 GUID 自定义关联。
- [x] D20 Volume None 根因定位：资产与 `.zibravdb` 源缺失（见 `notes/ZibraVDB排查结论.md`）。
- [x] BYDC 逐工程详查：9 个工程输出不统一问题汇总（见 `notes/外包归档清单.md`）。
- [x] 外包特效交付规范 v1.0（见 `notes/外包交付规范.md`）。
- [x] 核实并修正 A45/C50/0623 三处误判：A45/C50 源存在但在工程外平级目录；0623 含 288GB `0623.7z`。
- [x] 生成 `外包整改执行说明.md`：逐镜头问题与整改动作。
- [x] 生成 `漫行者外包BYDC交付规范与整改清单.pdf`：可发外包的 PDF 版整改清单。
- [x] 生成 `FX_镜头目录结构示范.zip` + `目录结构示范/`：可发外包的空目录样板。

---

完成超 2 周的项移除；有保留价值的写进 LOG.md。
