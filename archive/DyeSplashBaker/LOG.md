# DyeSplashBaker · LOG

> 决策流水。追加式，新条目加在**文件末尾**。由 `/log` 命令维护。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签（可选，加在标题前）

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

### 2026-04-20 — [回滚] FloodStep v2 方案废弃
本质是各向异性测地距离场，缺流体要素（时间演化、质量守恒、非线性反馈），扩散表现死板重复。迁至 archive/FloodStep/，后续方案见 SWE-TechSpec.md。

### 2026-04-20 — [决策] 架构改为分层合成（Layer A + Layer B）
Layer A 走 SDF+FBM 或 Houdini 烘焙，可控高质量零台阶；Layer B 走 Niagara 粒子飞溅→Splat RT，负责涌现细节。两层输出厚度场合成，法线只从 FinalHeight 算。

### 2026-04-20 — [发现] 染料 vs 墨水视觉决定性三要素
① 干燥后 Roughness 是否回归基材（染料回归、墨水保持膜光泽）② 边缘类型（染料 Coffee Ring、墨水 normal bulge）③ 覆盖曲线（染料线性、墨水 pow(t,0.3)）。

### 2026-04-21 — [决策] 升级路径选路径 2（扩散方程 + Source/Decay + 厚度反馈）
∂h/∂t = D·∇²h + S - λh。推荐初值：D=0.2, SourceRate=2.0, DecayRate=0.3, dt=1/30, Substep=3, Kappa=0.5。CFL 条件 D·dt/dx² < 0.25 必须遵守。

### 2026-04-21 — [发现] Normal 边界判据应用拓扑而非梯度幅度
原版用 `gradMag` 做边界判定，对均匀缓坡失效（内部与边界 grad 量级接近）。改为 `SelfAlive × NeighborHasVoid` 拓扑判据（H_Center 可见 × H_MinNeighbor 接近 0），阈值自动跟随 OpacityThreshold。单阈值 Delta 版在中心峰顶会误判为边界。

### 2026-04-21 — [发现] ddx/ddy 屏幕空间导数不能用于 Decal 边界检测
Decal 材质里必须用邻域 texel 差分（UV+TexelSize 采样）算法线，屏幕空间导数会跨 RT 边界平均抹开信号。TexelSize 必须用 `TextureObject→GetTextureSize→1/size` 生成，不能硬编码像素值。

### 2026-04-21 — [回滚] SWE 实时方案重度受阻，回退到 FloodStep v2
SWE Stage 2 在 Niagara Grid2D 上连续踩坑：假 Jacobi（stale neighbor）、中心差分对发散速度场丢料、Stage 1 每帧覆盖 Stage 2 输出、Previous 读取对邻居固定返回本 cell 值等。核心认知转变：**当前是烘焙场景，不需要动力学，只需要"到达时间场"**——这正是 FloodStep v2 早就在做的事。SWE 烘焙到稳态是用冲击钻拧螺丝。

### 2026-04-21 — [决策] 架构核心转向"到达时间场"
Grid2D 只保留单一属性 GradientValue（1=seed，0=未到达），删除 h/vx/vy/arrival。运行时材质端 `step(Progress, G)` 做扫描式蔓延动画。与 FloodStep v2 天然对齐，未来真需要实时动力学再加 SWE Stage（接口兼容：都写 Grid2D.h/G，材质侧不变）。

### 2026-04-21 — [发现] Niagara Custom HLSL 里 `return` 早退会让 Set 节点跳过
代码顶部 `if (...) { ...; return; }` 会导致后续 Grid2D.SetFloatValue 不执行。必须改为完整 if/else 包裹，避免早退。这是调试 SWE 时连带发现的 Niagara 通用坑。

### 2026-04-21 — [发现] FloodStep 棱角感来自算法本质，非参数问题
max() 离散选择 + 无曲率概念 + 8 方向偏好 → 天然多边形轮廓。单加 noise 或翻转调制方向都治不了。两条出路：①迭代末尾加扩散平滑（`lerp(MaxCandidate, NeighborAvg, 0.15)` + `max(_, CurrentValue)` 保单调），②换 domain warp 噪声贴图让指状更有机。

### 2026-04-21 — [否决] 加独立模糊 Stage
会破坏 FloodStep 的 max() 单调性（均值不是 max，下一轮可能让 T 变小 → 蔓延倒退或振荡）。正确做法是在同一 Stage 主计算后加扩散平滑并 clamp 不低于 CurrentValue，把单调性保进同一次迭代内。

### 2026-04-21 — [发现] Niagara Simulation Stage 的 Num Iterations 是真 Jacobi
手写 HLSL for 循环 + stale neighbor 是假 Jacobi，质量误差积累；Stage 面板的 Num Iterations 在每次 iteration 之间自动翻转 Previous/Current，才是真 Jacobi。FloodStep 下这个设置直接等价于"每帧推进多格"。

### 2026-04-23 — [发现] EUW + Niagara 参数刷新的正确方式
用 `Set Editor Property` 给任意参数设值，会触发编辑器级参数变更通知 → Auto Reset → Niagara 自动从头重跑。这是最正确的 EUW 控制 Niagara 的方式。比 `Reset System` / `DestroyComponent` 更轻量更稳定。Reset 会断开 Grid2D 的 RT 绑定导致全黑，Destroy+Recreate 需要重设所有参数。`Set Editor Property` 走的是和"手动在 Details 面板改值"完全相同的路径。

### 2026-05-27 — [决策] 运行时贴花系统架构落地：地面+墙面双通道 + 多射线障碍检测
从烘焙工具延伸到运行时端：GuanziActor(罐子) → VFX Manager → Niagara 飞溅 + Ground Decal + Wall Decal。地面 7 射线 ForLoop + CutDist0_3/CutDist4_7 打包做障碍遮挡；墙面用中心射线 Index=(RayCount-1)/2 判墙(Abs(ImpactNormal.Z)<0.5)。双 MID 分流（地面/墙面各一个 MI 资产烘死静态参数，蓝图只 SetScalar Progress/WallNoiseOffset 等动态参数）。材质侧 Progress 当反向阈值扫 height 图（大=消失 小=扩散），与你到达时间场 `step(Progress,G)` 语义完全对齐——Progress 即 threshold，不需要第二个参数。

### 2026-05-27 — [发现] 墙面贴花定位必须用线-面交点，ProjectPointOnPlane 会落地面
用地面贴花中心 + 中心射线方向 与墙面平面求交求墙脚锚点：`t=Dot(WallHitPoint-GroundCenter,WallNormalN)/Dot(ForwardN,WallNormalN)` → `WallFootPoint=GroundCenter+ForwardN*t`，再沿 WallUp 抬升到贴花中心。ProjectPointOnPlane 会把点投回地面高度，是死路。

### 2026-05-27 — [发现] 墙面旋转 X 轴锁死 -WallNormal（投射方向），Z 用 SplatDir（喷溅朝向）
`MakeRotFromXZ(X=-WallNormalN, Z=SplatDir)`。之前改顺序让贴花消失是动了 X 导致贴花被墙法线压缩。左右翻转校正用 WallRight 做 Dot(SplatDir,WallRight)<0 时 SplatDir*=-1，不能用 WallDown（Dot 永远 0 无效）。

### 2026-06-02 — [发现] Progress 语义是反向阈值，流挂靠代码生成不靠烘焙梯度图
用户实际流程：Progress 1→0.2（铺开扩散）→0.2→2.5（消退结束），Progress 大=消失、小=最大扩散。定论：Progress 就是唯一的 threshold，不要额外 Threshold 参数。墙面复用地面径向衰减 Height 图（中心=1 向外均匀衰减），流挂拖尾在 Custom 里程序化生成：lane 竖条分缕 + fall=1-down/DripLength + band 横向收束 → drip。与径向图 max 合成，zero 烘焙成本。

### 2026-06-02 — [决策] 墙面流挂方向不改旋转：蓝图 UnrotateVector(DecalRotation,(0,0,-1)) 得 GravityUV 传材质
旋转必须保留 SplatDir（喷溅朝向不能牺牲），流挂的"下"在材质里通过 GravityUV 逆变换解决：材质里 `down=dot(UV-ImpactUV, GravityUV)` 替换固定 UV.y。方案 B（世界空间直算）物理更准确但要改世界尺度量纲，先走 A。

### 2026-06-02 — [决策] 墙面锥形收缩：支点从核心 ImpactUV 换到墙地接缝 GroundAnchorUV
`WallCoreScale` 等比例缩会让墙地接缝一起变小脱开。正确改法：`sampUV=(UV-GroundAnchorUV)*WallCoreScale+GroundAnchorUV`，支点=墙地接缝 → 接缝不动/远端缩。SpreadTex 采样必须设 Clamp。GroundAnchorUV 是手填常量=(0.5,1.0)（撞击顶/流到底，v=1 贴地），DebugMode 输出 UV.y 可验证。

### 2026-06-02 — [发现] 团块噪声要用阈值化成离散斑块，连续噪声减法产生"糊一层"效果
旧版 `height -= (1-clump)*ClumpInfluence` 是均匀削边，无"随机大小团块"。修复：低频噪声经 `smoothstep(ClumpThreshold±ClumpSoft, blob)` 切出非黑即白离散斑块，`height *= lerp(1.0, clumpMask, ClumpInfluence)` 斑块外 height 压低 → Progress 扫时先消失边缘破碎。ClumpScale 控团大小（小值=大团，大值=碎团）。

### 2026-06-02 — [发现] 障碍遮挡"墙前空白"根因：cutDist 烘短了 + edgeNoise 双向向内啃
`edgeNoise*2-1` 把 [0,1] 变 [-1,1]，一半样本把前沿向撞击点拉近 Amp 距离。30 秒判定：Amp=0 试跑，空白消失=噪声主因，空白还在=cutDist 本身偏短。修法① cutDist 采样后 `+= ObstacleReach`（正值往墙推）；修法② 删 `*2-1` 让噪声只向外凸不向内缩；修法③ softness 过渡翻到内侧 `1-smoothstep(cut-soft, cut, along)`。

### 2026-06-15 — [发现] SpawnDecalAtLocation 的 DecalComponent Outer 是 Level 非 Actor
DestroyActor 不会级联销毁 decal。对颜料系统是利好（罐炸了贴花继续播 Progress 消退动画），但需要独立管理者推 Timeline 到 2.5 后 DestroyComponent。保险 LifeSpan=动画总时长+1s。

### 2026-06-15 — [发现] FinalAlpha 接 Decal Opacity（非 OpacityMask），Blend Mode=Translucent
OpacityMask 是 Masked 硬剪裁，会废掉 smoothstep 软边。BaseColor 不乘 alpha（纯颜料色，覆盖强度全交给 Opacity）。湿边额外算 EdgeMask→Emissive: `smoothstep(Progress-Soft,Progress,height)-smoothstep(Progress,Progress+Soft,height)`。

<!-- 新条目追加在下方 -->
