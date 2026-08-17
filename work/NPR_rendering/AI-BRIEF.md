<!-- iris-project-kind: ue -->
# NPR_rendering

> **UEAgent first.** Before reading or changing live Unreal state, read
> [UEAgent](../UEAgent/AGENTS.md) and the
> [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md), then locate the target project's
> `Saved/UEAgent/route.json` and run `compact_context.ps1` without loading either file unless it fails. Stop on `CACHE_READ`; on
> `NEEDS_DOCTOR`, run the routed `doctor.ps1` once and use its receipt. Offline
> source/cache/config/log analysis may skip MCP but must not claim live Editor state.

## State

`waiting`

## Contract

- **Problem**: 尚未验证 UE 5.8 中最小、可维护的风格化渲染路径；直接复制商业游戏
  传闻或 fork Renderer 都会把未知美术目标变成长线引擎债务。
- **Goal**: 用同一验证场景比较干净动画、渐变电影化和写实混合三类风格，确定可量产基线。
- **Non-goals**: 复刻商业游戏专有 Shader/贴图；在出现实测硬阻塞前修改 UE Renderer；
  一次性搭建完整角色、天气或跨平台管线。
- **Mature baseline / proven pattern**: UE 5.8 原生实验性 Substrate Toon BSDF + Toon Profile；
  Face SDF 仅作为原生脸部阴影失败后的可选 Probe。
- **Smallest end-to-end pass**: 一个 Hero 角色、一个环境资产、三套 Toon Profile，在固定
  灯光/曝光下与 Default Lit 做画面及性能 A/B。
- **Pass**: 目标 RHI 上通过脸/发/材质、Local Light/Sky Light/Lumen GI、运动稳定性与预算门槛，
  且无需复制 Renderer 或角色母材。
- **Stop / rollback**: 原生 Toon 若无硬阻塞则停止扩张；若目标平台不支持或核心画面稳定失败，
  保留测试证据后再比较插件 Pass 与 `Aether/` 源码分支。

## Implementation

- **Canonical path**: 原生 Toon BSDF/Profile → 失败时才加入 Face SDF → 有硬阻塞才评估
  自定义 Pass/源码 SM；当前不考虑描边。
- **Reused foundation**: UE 5.8 Substrate Toon、Material Instance、Texture Group/Device Profile。
- **Module boundaries**: 角色 Toon 材质与环境 PBR 基线；不预建描边或第二套 Renderer。

## Current Gate

Abyss live route 已通过；VRM4U 导入的 `AvatarSample_A` 已整理到
`/Game/Neow/NPRRendering/Characters/VRoid/AvatarSampleA`。G1 权威检查确认 35,137 三角形、
24,290 顶点、23 个材质区、UV0/法线/蒙皮有效；源 VRM 无切线、无 UV1，头发 UV 的 U 最大
1.503 属有意 Wrap。35 张贴图以 Base Color 为主，只有 3 张真实法线，未提供 ORM、各向异性、
SSS、Ramp、Style 或 Face SDF。G0 尚需冻结平台/RHI、输出设置和 Toon 增量 GPU 预算，G1
还缺用户目标参考图及运行时切线/远近景视觉确认。

## Truth

- **Implementation truth**: 已在 `/Game/Neow/NPRRendering/Materials/Character` 创建并保存
  `M_NPR_CharacterToon`、`M_NPR_CharacterLitBaseline` 与 `M_NPR_CharacterClothPBR`。Face/Body/Hair
  的 12 个导入实例保持原生 Toon；11 个 Cloth 叶子实例直接改挂 `M_NPR_CharacterClothPBR`，形成
  皮肤/头发风格化、服装偏写实的混合基线，分类实例 `MI_Lit_AvatarSampleA_Cloth` 保持旧基线父级。
  T__12–T__22 各有独立 `PartNormal` 与 `PackedPBR`；鞋子另有独立 `MicroNormal`。N 为切线空间
  Normalmap；P 固定 R=AO、G=Specular、B=Metallic、A=Roughness。母材当前为 27 个表达式、25 条内部
  连线和 8 个输出：Meso 与 Micro 分别缩放解码后的 XY、重建 Z，再以
  `normalize(float3(Nmeso.xy + Nmicro.xy, Nmeso.z * Nmicro.z))` 合成，不使用 Lerp。
  `PartNormalStrength`、`MicroNormalStrength`、`RoughnessStrength` 和 `MetallicStrength` 均可由实例调节；
  母材默认 `MicroNormalStrength=0`，没有独立 Micro 的其余 Cloth 实例外观不变。
  `SlimeColor`、`PerInstanceCustomData`、`PackedNMR`、`DetailNormal` 和旧 Toon Specular 分支已清除；
  各槽独立 Base Color 与 `SK_AvatarSample_A` 的 23/23 绑定均保留。
  Toon 母材复用项目内成熟的
  `SubstrateToonBSDF` 图，当前使用引擎内建 Profile 0；显式三套 `UToonProfile` 和验证关卡尚未创建。
- **Runtime / external truth**: 2026-08-14 UEAgent 在 Editor epoch
  `057C7FF7-4483-6E26-10CA-CC94DC00328C` 完成鞋子 V8.2.1 接入、编译、保存和缓存回读；UE 资产名继续沿用
  V8_2，避免创建无意义的版本资产。鞋实例的已保存基线有
  8 个有效覆盖：`BaseColorTexture`、`PartNormal`、`MicroNormal`、`PackedPBR` 以及四个强度参数，
  制作基准均为 1。绑定资产为
  `T_AvatarSampleA_Shoes_N_Meso_V8_2`、`T_AvatarSampleA_Shoes_N_Micro_V8_2` 和
  `T_AvatarSampleA_Shoes_P_V8_2`；两张 N 使用 `TC_Normalmap`、关闭 sRGB、Normal Mip 归一化与
  CharacterNormalMap 组，P 使用 BC7、关闭 sRGB 与 CharacterSpecular 组。保存后的母材和鞋实例缓存
  均为 fresh；母材图 SHA1 为 `f8f73a369c478ba4dadf54442abb11a67c8fb1fc`。
  V8.2.1 以 8 个正交视角的 Triangle ID、深度、UV 和软语义提示生成整鞋
  `Vamp / ToeCap / Rand / Outsole / Collar / Guard / Strap / Hardware / Print`，再依次生成独立
  PartID、MaterialID、Meso、Micro 与 PBR。BaseColor 语义证据先按 UV 光栅约定翻转对齐，Alpha 覆盖
  重叠率为 92.592%；ToeCap/Rand 只在三维候选内使用该证据收紧，颜色不进入 Height。PartID 与
  MaterialID 不再一一绑定，深色前掌回归 PU、灰色护边为 TPU、鞋底为 Rubber、绑带为 Textile。
  覆盖互斥误差为 0；Meso/Micro 平均斜率分别为 0.02542/0.05086；Vamp/ToeCap/Rand/Outsole 的
  Micro 平均斜率分别为 0.08038/0.02570/0.03024/0.04571，Outsole Meso 为 0.014。
  Hardware 只有紧凑高亮候选进入 Metal，当前占 0.338%；Print 高度为零；
  AO 在没有网格烘焙时保持 1，Cavity 独立输出。TextureStreamingData 属派生数据，正式 Cook 前仍需
  重建并验证。PBR 数值和语义区域仍须用户在固定灯光下做视觉 Gate。原有四个 BLEND 叠层仍由
  Masked Toon 路径承载；UE 5.8 Toon 的目标画面与性能尚未验证。
  2026-08-16 的单变量 A/B 已将整鞋异常变黑锁定到 Micro 运行分支：
  `PartNormalStrength=1, MicroNormalStrength=0` 恢复正常明暗。最后一次实时快照中鞋实例为未保存状态，
  `PartNormalStrength=1`、`MicroNormalStrength=0`、PBR 两个强度为 1；母材和 Micro Texture2D 保持干净。
  从 UE 导出的 Micro PNG 与磁盘源图逐像素 100% 相同，RGB 均值为
  `(127.743, 127.744, 254.912)`，因此不是黑图或导入源丢失。以两张源法线复现当前母材合成式时，
  最小 Z 为 0.9404、负 Z 为 0，源数据和理论公式也不会产生翻面。未解范围已收窄到
  UE GPU 纹理资源/采样或已编译的 Micro 材质分支；尚未修改母材。UEAgent 随后确认 Editor 离线，
  GPU 资产预览需等待 Editor 重新打开。
- **Compatibility truth**: Abyss 中 47 个仍序列化 `MSM_CustomToon` 的旧资产已备份并重存为
  `MSM_DefaultLit`；移除临时 Enum Redirect 后 47/47 可加载、哈希不再变化，项目内旧枚举标记为零；
  5.8.1 `UnrealEditor` 已完整重建，清除了旧 Renderer DLL 对已删除 Shader 的残留引用。

## Current Focus

V8.2.1 的语义分层与下鞋连续性已通过技术检查，当前只处理 Micro 运行分支变黑。
Editor 恢复后先读取 GPU 资产预览：若 Texture2D 资源异常，修复导入/资源重建；若资源正常，
则检查已编译的 Micro 采样与法线合成分支，只在根因确定后改母材。修复前鞋实例保持
`MicroNormalStrength=0`，不再调整灯光或金属度来遮盖该问题。贴图仍负责浅接缝、压槽、细缝线、
浅折痕、鞋底小沟槽、PU/TPU/橡胶/织带微表面、Roughness/Specular/Metallic、Print 与 Cavity。

模型提升范围只保留会改变轮廓、侧壁、遮挡、叠压或投影的结构：大面积胫部 Guard 护板的厚度与间隙；
厚 Strap/锚点的截面、悬空、压叠和受力；Outsole/Heel 的宏观分层与 Hero 防滑块；改变轮廓的扣具、
铆钉和连接件。Collar 包边仅在近景轮廓或开缝失败时升级；ToeCap/Rand 默认继续使用现有网格体积和
Meso，只有轮廓、侧壁或间隙无法通过 Gate 时才模型化。源 VRM 每只鞋主体约 388 个三角形且护板未
独立建模，禁止直接复制原三角形挤出；模型路径固定为实例轮廓 → 细分/重拓扑 → 贴合 →
Solidify/Bevel → Skin Weight Transfer。

## Constraints

- 原生 Toon 依赖 Substrate Blendable GBuffer (legacy)，官方未给完整平台矩阵。
- Default Lit 兼容迁移只恢复资产可编辑性，不等价于保留旧 Toon 外观或完成原生 Toon 转换。
- 当前范围明确不含描边；Toon Profile 不应运行时修改。
- 不在已加载子实例时热切换共享中间材质实例父级；UE 5.8 不会同步递归刷新其后代 Uniform Expression Cache。
- 任何实时 UE 工作必须先通过 UEAgent route/compact context gate。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/NPR_rendering/`.

## Document Map

- `AI-BRIEF.md`: contract and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.
- `RESEARCH.md`: UE NPR 路线、参考作品、原生 Toon 对比和资产规范。
- `SPEC.md`: 原生 Toon 原型的资产合同、实现边界、Gate 与验收标准。

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
