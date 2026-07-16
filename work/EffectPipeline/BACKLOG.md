# EffectPipeline · BACKLOG

> 待办清单。顺手加，做完打勾。详细分析见 `notes/`。

## 当前最高优先

- [x] ZibraVDB Personal Key 已到位，授权阻塞解除
- [x] 外包返包首轮验收扫描（6/9 已上传：C30/C50/C60/D20/E20/E40）
- [x] C30/C60 World Partition 文件夹豁免确认（2026-07-07 用户同意保留）
- [x] E40 空 Actor 版本接受确认（2026-07-07 用户同意不挂接 ZibraVDB）
- [ ] 外包继续上传 A45/B20/C80（3 个尚未到）
- [ ] 全部到齐后统一复核 + 进入主工程导入

## Git LFS 5GB 上限 — 工程分诊（2026-07-15）

> 返包目录 `J:\vendors\漫行者\Final最终归档\BYDC\BYDC文件重新整理\` 实测大小。
> 分"云雾效果"和"金沙效果"两个大类，共 33 个工程。Git LFS 单文件上限 5GB，超限工程需 cp 回本地切分返工。

### ❌ 超过 5GB — 必须 cp 回本地切分返工（22 个）

| 工程 | 类别 | 大小(GB) | 备注 |
|------|------|---------|------|
| E40 | 云雾 | 51.54 | 含 7z 未解压，最重 |
| C11 | 云雾 | 46.14 | |
| C30 | 云雾 | 31.54 | WP 工程，跨引用 E40 |
| C10 | 云雾 | 27.80 | |
| C60 | 云雾 | 27.05 | WP 工程，跨引用 C30+E40 |
| F50 | 云雾 | 20.16 | |
| B10 | 云雾 | 15.22 | |
| A45 | 云雾 | 14.17 | 完整 ZibraVDB 闭包 |
| B20 | 云雾 | 14.02 | 完整 ZibraVDB 闭包，GPU Hung 风险 |
| D20 | 云雾 | 13.12 | ZibraVDB 缺源，重风险 |
| D40 | 云雾 | 11.68 | |
| C80 | 云雾 | 10.47 | |
| E30 | 云雾 | 9.25 | |
| D30 | 云雾 | 8.97 | |
| D60 | 云雾 | 7.72 | |
| E20 | 云雾 | 7.23 | ZibraVDB 缺源 |
| D70 | 云雾 | 5.14 | 略超线 |
| D20 | 金沙 | 17.96 | |
| C30 | 金沙 | 12.79 | |
| E40 | 金沙 | 35.29 | |
| E20 | 金沙 | 11.08 | |
| C60 | 金沙 | 5.83 | 略超线 |

### ✅ 未超过 5GB — 可正常导入（11 个）

| 工程 | 类别 | 大小(GB) | 备注 |
|------|------|---------|------|
| D10 | 云雾 | 4.51 | |
| B30 | 云雾 | 2.78 | |
| B40 | 云雾 | 2.00 | |
| A50 | 云雾 | 1.98 | |
| D50 | 云雾 | 1.22 | |
| B60 | 云雾 | 0.89 | |
| C40 | 云雾 | 0.88 | |
| B55 | 云雾 | 0.30 | |
| B50 | 云雾 | 0.22 | |
| C50 | 云雾 | 0.01 | 已导入主工程（试点完成） |
| C80 | 金沙 | 2.42 | |

> ⚠️ 注意：C30/C60/E20/E40/D20 各有两个类别条目（云雾+金沙），合计超限 22 项（去重 17 个镜头代号）。
> ⚠️ 部分工程（如 A45/B20）虽然超 5GB，但若已用 `.zibravdb` 源在主工程侧重导而非 LFS 推送 uasset，则不受此限。需逐个确认导入路线。

## 首轮验收发现的问题（6 个已上传工程）

### ✅ 整体改善
- 6 个工程均有 uproject + Config + Content 三件套
- C30 已改为公版 UE 5.5（不再是 GUID 自定义引擎）✅
- 无 StarterContent / Developers 残留 ✅
- 目录结构统一到 `FX_<镜头号>/` 下 ✅
- 命名基本含镜头号前缀 ✅

### ❌ 待整改问题

**P0 — 必须处理：**
- [ ] **B20 迁移崩溃/掉引用：9 个 Volume 全部 Custom Version GUID 不兼容**（2026-07-13 实锤）：日志确认走了 Migrate/直拷 uasset 路线，复现 A45 老坑（5.5→5.7 GUID 不匹配）。修复：删除现有 9 个坏 uasset，用 `.zibravdb` 源在主工程侧重新导入（非 Migrate）。待确认源文件是否已拷入主工程。
- [ ] **B20_cloud_04_v03 单独触发 GPU Hung 崩溃**（2026-07-13 定位）：该体积体素量占B20全部9个体积总量的56%（8.8亿体素，是第二大v04的2.3倍），显存超预算77MB炸的元凶就是它。其余8个体积体素量都小，不需要一起压画质。修复：仅对 v03 单独设 Volume Resolution（先试0.8），且要等 .zibravdb 重导完成、GUID问题修好之后再调，顺序不能反。
- [x] ~~**B20 疑似应归入 heavy_shots**~~ → ✅ **已确认并执行（2026-07-13）**：崩溃日志实锤GPU Hung后，已将 shot_config.json 的 B20 从 spawnable_shots 移入 heavy_shots，脚本会拦截自动转 Spawnable。
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

## 镜头导入进度总览

| 镜头 | 状态 | 备注 |
|------|------|------|
| C50 | ✅ 已完成 | 试点，Spawnable 路线全流程跑通 |
| C40 | ✅ 已完成 | Spawnable + Scale Y=-1 恢复 |
| B20 | ✅ 已完成 | v03 切分为 11 段，Spawned Track 互斥帧段 |
| D10 | ✅ 已完成 | Spawnable 转换，注意保存崩溃风险 |
| A45 | ❌ 阻塞 | GUID 不兼容，需 .zibravdb 重导 |
| D20 | ❌ 阻塞 | ZibraVDB 缺 .zibravdb 源 |
| E20 | ❌ 阻塞 | ZibraVDB 缺 .zibravdb 源 |
| E40 | ❌ 阻塞 | 空 Actor 版本，需主工程侧挂接 |
| A50 | ⬜ 待导入 | 1.98G，已拷入主工程 |
| B10 | ⬜ 待导入 | 15.22G，超 5GB LFS 限制 |
| B30 | ⬜ 待导入 | 2.78G，已拷入主工程 |
| B40 | ⬜ 待导入 | 2.00G，已拷入主工程 |
| B50 | ⬜ 待导入 | 0.22G，已拷入主工程 |
| B55 | ⬜ 待导入 | 0.30G，已拷入主工程 |
| B60 | ⬜ 待导入 | 0.89G，已拷入主工程 |
| C10 | ⬜ 待导入 | 27.80G，超 5GB LFS 限制 |
| C11 | ⬜ 待导入 | 46.14G，超 5GB LFS 限制 |
| C30 | ⬜ 待导入 | 31.54G，WP 工程，超 5GB |
| C60 | ⬜ 待导入 | 27.05G，WP 工程，超 5GB |
| C80 | ⬜ 待导入 | 10.47G(云雾)+2.42G(金沙) |
| D30 | ⬜ 待导入 | 8.97G，超 5GB LFS 限制 |
| D40 | ⬜ 待导入 | 11.68G，超 5GB LFS 限制 |
| D50 | ⬜ 待导入 | 1.22G，已拷入主工程 |
| D60 | ⬜ 待导入 | 7.72G，超 5GB LFS 限制 |
| D70 | ⬜ 待导入 | 5.14G，略超线 |
| E30 | ⬜ 待导入 | 9.25G，超 5GB LFS 限制 |
| F50 | ⬜ 待导入 | 20.16G，超 5GB LFS 限制 |

**汇总：已完成 4 · 阻塞 4 · 待导入 15 · 总计 23**

## 阶段 2 · 试点导入 + Sequence 对齐（2026-07-08 启动）

> ⚠️ 2026-07-08 17:20 路线更新：C50 试点已改走 **Spawnable 路线**，推翻下方原 Data Layer + 逐条重绑方案（划线项为废弃，保留作历史参照）。详见 LOG 2026-07-08 17:20。

### ✅ 已完成镜头

#### C50（试点，2026-07-08 完成）
- [x] C50 关卡+资产已拷贝到主工程 `Content/FX/C50/`（直接拷贝代替 Migrate，C50 无跨工程引用故等价）
- [x] C50 `.zibravdb` 源已交齐，Volume 重导后 Actor 指向正确资产
- [x] 外包 C50_Sequence 特效 Actor（ZibraVDB / Niagara）在 C50_gk 上下文里 Convert → Spawnable Actor（自包含，绕开 WP 下 GUID 红轨问题）
- [x] 删除外包 Sequence 内相机 + Camera Cuts（相机/后处理由主工程 Shot 自带）
- [x] 主 Sequence 对应 Shot 加 Subsequences Track 引用外包 C50_Sequence，时间对齐
- [x] ZibraVDB 隐患排除：转 Spawnable 后体积正常显示，template Volume 引用有效
- [ ] 引用闭包检查：缺失引用 / Redirector / 插件依赖（C50 无跨引用，快速确认即可）
- [ ] 离线渲染验证：画面与外包预览 mov 对齐，查 ZibraVDB 前后景遮挡（调 Translucency Sort Priority）
- [ ] 批量脚本 integrate_fx_shots.py 落地：转 Spawnable + 清相机 + 挂 Subsequence（待引擎组确认 5.7.3 convert to spawnable 的 Python API 签名）

#### C40（2026-07-15 完成）
- [x] C40 关卡+资产拷入主工程，Spawnable 转换完成
- [x] Scale 保留验证通过（Y 轴 -1），ZibraVDB 组件 Relative Scale 控制运行时缩放
- [x] Sequence 对齐

#### B20（2026-07-16 完成）
- [x] B20 .zibravdb 源重导完成（修复 GUID 不兼容）
- [x] v03 按体素分辨率切分为 11 段（000_050 ~ 501_534），通过 Spawned Track 互斥帧段避免同时加载爆显存
- [x] GPU TDR 超时问题解决（按体素分辨率切分而非仅按时间）
- [x] Sequence 对齐

#### D10（2026-07-16 完成）
- [x] D10 Spawnable 转换完成
- [x] 注意：保存超大 ZibraVDB 资产触发 32 位数组索引溢出（2147483648），需谨慎保存
- [x] Sequence 对齐

### ~~原 Data Layer + 逐条重绑路线（2026-07-08 废弃，Spawnable 路线更优）~~
- [x] ~~C50 拷入主工程 Content/FX/C50/~~
- [ ] ~~复制粘贴 Actor 进 WP 主关卡（OFPA，GUID 必然变）~~
- [ ] ~~新建 Data Layer DL_C50，把搬入 Actor 加入该层~~
- [ ] ~~主 Sequence C50 Shot 加 Data Layer Track 控制 DL_C50 显隐~~
- [ ] ~~外包 Sequence 嵌套挂入后逐条重新绑定失效红色轨道~~
- 废弃原因：Spawnable 路线不需要 Actor 进 WP 主关卡、不需要 Data Layer、不需要逐条重绑，批量脚本化难度更低。
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
