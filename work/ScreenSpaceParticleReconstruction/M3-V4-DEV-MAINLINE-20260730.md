# M3 V4 开发主线快照（2026-07-30）

## 用途

以已经调好参数的 V4 作为冻结源，复制出独立的 M3 开发主线。后续效果和性能优化只改 M3，不回写 V4 冻结目录，也不回退旧 Ping-pong 主线。

## 主线资源

- 根目录：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev`
- 验证关卡：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/L_SSPR_AnisotropicSplat_V4_Dev_Validation`
- Niagara System：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/NS_SSPR_AnisotropicSplat_V4_Dev.NS_SSPR_AnisotropicSplat_V4_Dev`
- 显示材质：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/M_SSPR_AnisotropicSplat_G5_V4_Dev`
- MI：`/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/MI_SSPR_AnisotropicSplat_G5_HQ_V4_Dev`
- 材质函数：7 个，全部位于主线 `Functions/` 子树内

## 引用链

验证关卡中的 `SSPR_ParticleTrails_Main` 已绑定 M3 Niagara System；其外部 Actor 包为：

`/Game/__ExternalActors__/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/L_SSPR_AnisotropicSplat_V4_Dev_Validation/0/SX/WEXYCMSTXP4EC11WS3CQET`

Niagara Renderer 1 已绑定 M3 MI，并保持：

- `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget`
- `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`
- `SourceMode=Emitter`
- `SpriteSizeBinding=Fountain.SpriteSize`

## 完成的校验

- 主线根目录资源数：11
- 材质函数闭包：7/7，未发现 M2 或 V4 源函数引用
- MI Parent：M3 `M_SSPR_AnisotropicSplat_G5_V4_Dev`
- Material：Compiled，零错误
- Niagara System：Compiled，零消息
- Fixed Tick Delta：开启，`0.01667s`
- 主 Actor：可见、Tick 开启、绑定 M3 System
- 活动 RT 原始 Gate：通过；Main/Aux 均有非零覆盖、无 NaN/Inf、未画满

## 冻结源与备份

- V4 冻结源：`/Game/SSPR_Validation/Versions/V4_AnisotropicSplat_20260730`
- V4 修改前备份：`Saved/CodexBackups/v4_before_dev_copy_20260730`
- M3 当前状态备份：`Saved/CodexBackups/v4_dev_partial_20260730`

## 后续开发入口

后续优先在 M3 的 MI、显示材质和独立材质函数上继续优化；Niagara 数据链、2048 分辨率、Fixed Tick 和 Main/Aux RT 绑定先保持不变。
