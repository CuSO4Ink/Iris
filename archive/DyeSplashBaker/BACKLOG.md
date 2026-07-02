# DyeSplashBaker · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] FloodStep v2 扩散平滑参数调优（DiffuseStrength 起步 0.15）
- [ ] Normal 边界凹底实现（上半凸已通，下半凹待解）
- [ ] 墙面贴花流挂材质：团块阈值参数(ClumpThreshold/ClumpSoft) + 流挂缕参数(DripFreq/DripLength/DripStrength) + GravityUV 对齐（Blueprint UnrotateVector 传 Vector）

## 待办

- [ ] Domain Warp 噪声贴图离线生成（替换当前 NoiseSampler，追求更有机的指状）
- [ ] 多层 FloodStep 叠加（不同 NoiseScale 跑两轮，min/加权混合，获得自相似分叉）
- [ ] UE5.7.3 资产迁移验证（Niagara Scratch HLSL 风险点）
- [ ] Layer A（SDF+FBM）与 Layer B（FloodStep 时间场）合成链路打通
- [ ] 染料 vs 墨水材质的 InkVsDye slider 统一实现
- [ ] Coffee Ring 视觉完整化（Normal 凹底 + Roughness 边界压暗 + Opacity 软过渡三件套）
- [ ] 墙面贴花进阶：Height 图烘焙版替代程序化流挂（逻辑版偏规整，烘焙版上限高更自然）

## 已完成（近期，便于回忆）

- [x] √2 斜角步长比修正
- [x] 噪声调制机制
- [x] 力各向异性处理
- [x] AngleFade 径向对称性解决
- [x] Niagara GPU + Grid2D + R16f RT + DBuffer 全链路打通
- [x] FloodStep v2 归档（曾被扩散方程路径取代，现已回归主线）
- [x] Normal 边界检测（拓扑判据 `SelfAlive × NeighborHasVoid`，阈值跟随 OpacityThreshold）
- [x] 扩散方程 / SWE 路径深度调研与否决（烘焙场景下过度工程）
- [x] 架构核心转向"到达时间场"（Grid2D 单属性 GradientValue）
- [x] 材质端蔓延扫描动画（Progress 反向阈值扫 height，Custom HLSL 落地，地墙共用 `smoothstep(Progress±Soft, height)` 内核。详见 LOG 2026-05/06 条目）
- [x] 坛子打破效果的方向性扩散控制探索（运行时贴花系统完整落地：GuanziActor → VFX Manager → Ground+Wall Dual Decal，含多射线障碍遮挡、墙面检测/定位/旋转、流挂方向逆变换、锥形收缩、团块斑块化。详见 LOG 2026-05/06 条目）

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。
