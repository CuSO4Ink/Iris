<!-- iris-project-kind: ue -->
# slime

> **UEAgent first.** Before reading or changing live Unreal state, read
> [UEAgent](../UEAgent/AGENTS.md) and the
> [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md), then locate the target project's
> `Saved/UEAgent/route.json` and run `compact_context.ps1` without loading either file unless it fails. Stop on `CACHE_READ`; on
> `NEEDS_DOCTOR`, run the routed `doctor.ps1` once and use its receipt. Offline
> source/cache/config/log analysis may skip MCP but must not claim live Editor state.

## State

`waiting`

## Goal

- **Problem**: 当前史莱姆效果混合 GPU PBF、Marching Cube、材质、Render Target 和多个实验分支，性能成本与画面贡献尚未量化。
- **Outcome**: 在保留史莱姆流动感、体积感和交互反馈的前提下，找出真实瓶颈并用可复现的前后对比优化性能与表现。
- **Smallest working feature**: 对当前主路径完成一次固定场景基线测量，实施一个最小优化，并留下性能数据与画面 A/B。

## Current Focus

等待同机位截图，确认中央差分法线与收紧后的高光是否消除块状明暗带；
性能优化保留为后续 A/B，不作为当前主瓶颈。

## Truth

- **Implementation truth**: 当前主链为 `GM_Slime` → `BP_SlimeCharacter` → `NS_SlimeWorld`；
  后者启用 GPU `PBFSim` 与 `MarchingCube`，并通过组件覆盖绑定 `RTV_SDF`。
- **Visual implementation truth**: 当前生效的 `WriteToSDF` 将粒子平滑支持半径设为
  `ParticleRadius * SmoothIntensity * 1.35`，并将密度衰减从尖锐的 `t³` 改为两端导数为零的
  Hermite smoothstep `t²(3-2t)`；未提高 64³ 网格分辨率。`PCACalculate` 仍关闭，
  因而现有 `User.SmoothRadius` / `User.SmoothStrength` 不控制当前渲染表面。
  `M_MarchingCubeStudy` 保持 `Default Lit` 并启用 Normal Curvature to Roughness；它只改为调用
  本地 `MF_SlimeMarchingCube`，原插件函数不变。本地函数把硬编码 1/64 的单边 SDF 法线差分改为
  对称的中央差分，以消除有方向偏差的块状明暗带。实例颜色为 `(0.015, 0.16, 0.24)`、
  Roughness 0.38、Specular 0.32。首版 `SingleLayerWater` 在当前厚实网格和强日照下产生大块
  灰白/深蓝分区，已依据用户截图撤回。
- **Runtime / external truth**: 固定 `L_Demo`、1962×1080、Epic 质量、RTX 5060 的 120 帧 PIE
  基线为帧 P50 15.75 ms、GPU P50 14.82 ms；Niagara GPU Compute 约 1.28 ms。
  用户画面参考显示当前首要问题是 Marching Cube 表面起伏/面皮感，以及材质缺少层次、湿润感和体积感。
  SDF、材质函数、父材质和实例均已保存；Niagara 为 `UpToDate`，材质诊断编译成功且无错误。
  中央差分把每次法线梯度采样由 4 次增至 6 次，性能影响保留到最终 A/B；审美结果待用户再次
  在视口确认。

## Implementation

- **Canonical path**: `D:/Work/Personal/Project/Abyss/Abyss.uproject`；资产根为
  `/Game/Effects/Slime`，当前优化目标为 `NS_SlimeWorld`。
- **Reused foundation**: 现有 UEAgent 快照/性能采样、Niagara 反射缓存和当前效果资产；不另建性能框架。

## Constraints

- 每次只优化一个已测量瓶颈，并复测性能与画面。
- 结构正确性由工具验证；最终审美由用户在 Unreal 视口确认。
- 不用 Computer Use 操作 Unreal UI。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/slime/`.

## Document Map

- `AI-BRIEF.md`: goal and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
