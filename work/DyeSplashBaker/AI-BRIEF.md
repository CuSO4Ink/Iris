# DyeSplashBaker

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

基于 Niagara GPU 模拟的染料飞溅烘焙工具，用于生成动态流体感的贴花材质。

## 当前状态

**活跃**。主线方案（FloodStep v2 到达时间场烘焙）稳定，2026 年 5-6 月推进了**配套运行时贴花系统**（地面+墙面双通道 Decal，含多射线障碍遮挡、墙面流挂/团块材质、Progress 反向阈值动画），与烘焙纹理链路完全打通。

## 当前焦点

FloodStep v2 扩散平滑参数调优、Normal 边界凹底。运行时端：墙面流挂材质调参（团块阈值、流挂缕参数、GravityUV 对齐）。中长期：Domain Warp 噪声贴图替换、墙面 Height 图烘焙版替代程序化流挂。

## 技术栈与硬约束

- 引擎：UE5.7.4（自编译），团队共享版本 UE5.7.3
- 模拟：Niagara Scratch Pad + Grid2D Collection
- 输出：R16f RT → DBuffer Decal（≤8s 用 R16f，>8s 用 R32f）
- 材质域：Deferred Decal，Blend Mode 走 DBuffer 家族
- 接收面材质必须配 Decal Response（Color / Normal / Roughness）
- 跨版本迁移：Migrate 不保存原路径，5.7.4→5.7.3 风险高（Niagara Scratch HLSL）

## 术语表

- **到达时间场**：Grid2D 单属性 GradientValue（1=seed, 0=未到达），运行时材质 `step(Progress, G)` 扫描动画
- **FloodStep v2**：当前主力求解器（一度被扩散方程路径取代又回归），本质是各向异性测地距离场
- **SWE**：已否决，烘焙场景下过度工程；保留接口兼容预留未来动力学可能性
- **AngleFade**：解决径向对称性的机制
- **Layer A / Layer B**：分层合成架构中的 Base Shape 层与 Emergent Detail 层
- **CFL 条件**：D·dt/dx² < 0.25，SWE 时代的稳定性约束（现不再使用）
- **Saffman-Taylor**：黏性指状不稳定性，染料路径关键视觉特征
- **Coffee Ring**：染料边缘浓缩环，L4 视觉阶梯的核心证据；需要 Normal 凹底 + Roughness 压暗 + Opacity 软过渡三件套
- **拓扑边界判据**：`SelfAlive × NeighborHasVoid`，阈值自动跟随 OpacityThreshold
- **Domain Warp**：两层 fBm 嵌套产生有机流动形态，候选用于替换当前 NoiseSampler
- **7 层视觉元素阶梯**：L0 BaseColor → L7 时间演化干湿过渡，90% 贴花效果卡在 L2 Roughness
- **GravityUV**：世界向下 (0,0,-1) 经 UnrotateVector 逆变换到贴花本地 UV 平面的方向向量，材质里用它替换固定 UV.y 做流挂向下，保留 Decal Rotation 对齐 SplatDir 喷溅朝向
- **GroundAnchorUV**：墙地接缝在贴花 UV 的位置（常为底边 (0.5,1.0)），WallCoreScale 缩放的支点——只缩远端锥形，接缝处不动保地面对齐
- **Blob Threshold（团块斑块化）**：低频噪声经 smoothstep(ClumpThreshold, ClumpThreshold+ClumpSoft, blob) 切成离散斑块，乘进 height 破碎边缘出"一滩滩"，替代连续噪声减法（会糊成一层）

## 文档地图

- `SWE-TechSpec.md` — 技术方案主文档
- `AI-BRIEF.md` — 本文件
- `LOG.md` — 决策流水
- `BACKLOG.md` — 待办清单
- `../../archive/FloodStep/` — 前代方案归档

## 协作约定

- HLSL / Material 代码给完整可粘贴片段，不用伪代码
- 物理公式用 LaTeX，不拿 Unicode 符号凑
- 文档批注走工作区通用的 `[!Q] / [!NOTE] / [!TODO] / [!FIX]`
- 染料（Dye）与墨水（Ink）材质差异走 InkVsDye slider 统一支持

---

## 维护

- 阶段切换 / 术语变更 / 技术栈升级 → 更新本文件
- ≤ 100 行，超了拆到 notes/ 或新文件
- 项目归档时本文件随迁
