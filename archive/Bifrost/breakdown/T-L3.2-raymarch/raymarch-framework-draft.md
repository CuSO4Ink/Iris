# T-L3.2 天象体积框架 · Raymarch 骨架草稿

> **定位**：`PIPELINE.md` §3 拍板了"一套 raymarch 框架喂多种介质"，但目前没有一行 shader —— 这份是**纯设计草稿**（伪代码/HLSL 骨架），供你审阅/裁剪后再在 UE 材质编辑器里实现。不碰引擎、不碰 MCP，可与 GaussianVolume 并行。
> **状态**：草稿，未拍板，未实现。落地时人在 UE 材质图里连节点，本文件只给"该连成什么形状"。

---

## §1 范围澄清（先划边界，避免和已有结论重复造轮子）

`D3-KERNEL.md` §3 已经写死一件事：**god-rays / 大气散射不需要自定义 raymarch**，走标准 Directional Light + Sky Atmosphere + Volumetric Fog 就有，这套体积框架**不用管它们**。

真正需要这套自定义 raymarch 框架的只有两个消费者：

| 消费者 | 状态 | 密度/发射源 |
|---|---|---|
| **体积云**（PIPELINE §3，基底） | W3 目标，本草稿主力 | 3D 噪声密度场（domain warp，风格化贝母云） |
| **极光**（PIPELINE §3，点缀） | W4 目标 | 沿磁力线分布的发射介质（无消光，纯 additive） |

两者共享**同一套 ray-AABB + 步进循环骨架**，但光照/输出逻辑不同（云要消光+散射，极光是纯发射不消光）。下面先讲共享骨架，再分岔两个专用分支。

---

## §2 共享骨架（云 · 极光都复用这部分）

### 2.1 Ray-AABB 求交（确定步进区间 `[t0, t1]`）

```hlsl
// 输入：ray 原点 O（相机位置）、方向 D（归一化）、体积 bounding box（BoxMin, BoxMax）
// 输出：t0, t1（进入/离开体积的射线参数），若不相交 t1 < t0

float2 RayBoxIntersect(float3 O, float3 D, float3 BoxMin, float3 BoxMax)
{
    float3 invD = 1.0 / D; // 注意 D 分量为 0 时需保护（除零 -> inf，HLSL 下通常安全但建议 clamp 极小值）
    float3 t0s = (BoxMin - O) * invD;
    float3 t1s = (BoxMax - O) * invD;
    float3 tsm = min(t0s, t1s);
    float3 tbg = max(t0s, t1s);
    float t0 = max(max(tsm.x, tsm.y), tsm.z);
    float t1 = min(min(tbg.x, tbg.y), tbg.z);
    t0 = max(t0, 0.0); // 相机可能在体积内部，t0 不能是负的
    return float2(t0, t1);
}
```

- 云层：AABB = 一层薄壳（云带高度范围），或用球壳近似天空盒内一层。
- 极光：AABB = S3 上空一个竖直薄片区域（沿磁力线的弧形范围，可先用简单 box 近似，日后按视觉调整）。

### 2.2 步进循环骨架（固定步数 + jitter 去 banding）

```hlsl
// N_STEPS：固定步数（性能预算的主要旋钮，云建议 32-64，极光更薄可以 16-24）
// jitter：per-pixel 蓝噪声或 InterleavedGradientNoise 抖动起始点，去掉步进条带

float t0_t1 = RayBoxIntersect(CameraPos, RayDir, BoxMin, BoxMax);
float t0 = t0_t1.x, t1 = t0_t1.y;
if (t1 <= t0) return NoHit; // 射线完全没穿过体积

float stepSize = (t1 - t0) / N_STEPS;
float jitter = InterleavedGradientNoise(ScreenPos) * stepSize;
float t = t0 + jitter;

float3 accumColor = 0;
float  accumTransmittance = 1.0; // 云用；极光可以不衰减，见 §4

for (int i = 0; i < N_STEPS; i++)
{
    float3 p = CameraPos + RayDir * t;

    // ↓ 分岔点：云走 §3，极光走 §4
    // SampleDensity / SampleMagneticMask(p) 在这里插入

    t += stepSize;
    if (accumTransmittance < 0.01) break; // 云的 early-out，极光通常不需要
}
```

### 2.3 深度早出（性能关键，两者都要）

- 步进前先采样场景深度，若体积的 `t1` 已经超过场景深度（被前景遗迹/地形遮挡），直接把 `t1` clamp 到场景深度对应的 t，避免在被遮挡的部分白算。
- 云层高度范围如果明显高于走廊内任何遗迹巨构，这一步基本恒定生效（省一大截）；极光在 S3 上空同理。

---

## §3 云专用分支：密度场 + 单次散射（single scattering，PIPELINE 已定调"克制"）

```hlsl
// 密度场：复用层 1 恒星材质同一套 domain-warp 3D 噪声骨架（不同参数实例，风格统一）
float SampleCloudDensity(float3 p)
{
    float3 warped = p + DomainWarpNoise(p * WarpFreq, Time * WarpSpeed) * WarpStrength;
    float density = FBM_Noise(warped * BaseFreq, Octaves) ;
    density = saturate((density - DensityThreshold) * DensitySoftness); // 阈值化，避免糊成一片雾
    return density * DensityMultiplier;
}

// 单步内的消光 + 简化光照（Beer-Lambert + 假 powder/ambient，不做多次散射）
float density = SampleCloudDensity(p);
if (density > 0.001)
{
    float extinction = density * ExtinctionCoeff;
    float stepTransmittance = exp(-extinction * stepSize);

    // 极简光照：只朝主光源方向做一次浅层"光穿透"近似（不是真正 light-ray raymarch）
    float sunAtten = exp(-density * SunAttenCoeff); // 越厚，光穿透越弱 → god-rays 的"体积云版本"
    float powderTerm = 1.0 - exp(-density * PowderCoeff * 2.0); // 假 powder，边缘增亮，出"贝母"质感
    float3 litColor = SunColor * sunAtten * (1.0 + powderTerm * PowderIntensity) + AmbientColor;

    accumColor += accumTransmittance * (1.0 - stepTransmittance) * litColor;
    accumTransmittance *= stepTransmittance;
}
```

- **刻意不做**：多次散射、真正的 light-ray 二次步进（对每个采样点再朝光源方向 raymarch 一次）——PIPELINE 定调"MVP 光照保持克制"，这里跟 GaussianVolume 的"single scattering + fake ambient/powder"策略是一致哲学，两个项目在这一点上天然对齐。
- **贝母云质感**：`PowderTerm` 配合冷神性色域（`SunColor` 压 icy cyan、`AmbientColor` 压 pale azure）出贝母彩虹边缘感，具体色值留给你 LookDev。

---

## §4 极光专用分支：磁力线 mask + 纯发射（不消光，additive 叠加）

极光不是"遮挡光的介质"，是"自己会发光的介质"，所以完全不需要 §3 的消光/透射率逻辑，直接谈发射强度：

```hlsl
// 磁力线 mask：用一组参数化曲线（贝塞尔或简单正弦扭曲的竖直带）模拟磁力线形状
// 而不是真磁场模拟——纯视觉近似，成本可控
float SampleAuroraMask(float3 p)
{
    float fieldLineDist = DistanceToFieldLineCurve(p, FieldLineParams); // 到最近磁力线的距离
    float band = exp(-fieldLineDist * fieldLineDist * BandSharpness);   // 距离越近越亮，高斯衰减带
    float flicker = FBM_Noise(p * FlickerFreq + Time * FlickerSpeed);   // 时间演化，极光的"飘动感"
    return band * saturate(flicker);
}

// 纯 additive 累积，不用 transmittance
float mask = SampleAuroraMask(p);
if (mask > 0.001)
{
    float3 auroraColor = lerp(AuroraColorA, AuroraColorB, flicker); // 冷绿 ↔ 冷紫渐变
    accumColor += mask * auroraColor * stepSize * AuroraIntensity;
}
// accumTransmittance 保持 1.0，极光不衰减背景（不挡星光/云）
```

- **磁力线曲线来源**：可以先用 3-5 条手调参数曲线（弧形竖直带），不需要真磁场模拟——这和 §4 铁磁流体尖刺"只偷视觉不搬物理"是同一套哲学，`PIPELINE.md` 已经在铁磁流体上验证过这条路径可行。
- **因果链挂钩**：`DistanceToFieldLineCurve` 的曲线参数（弯曲方向/密度）可以手动对齐恒星磁极方向，视觉上"看起来"和恒星磁场相关即可，不需要真正驱动。

---

## §5 与 GaussianVolume 的可选复用点（仅供云层参考，不影响 D3 决策）

`GaussianVolume/ray_density_integral.md` 推导的是**各向异性高斯密度场沿射线的解析积分**（把固定步长 raymarch 换成解析 erf 积分，省掉步进循环）。这个思路**只对云层分支（§3）有潜在借鉴价值**：

- 如果云的密度场未来想换成"稀疏高斯 primitive 堆叠"而非连续 3D 噪声，可以直接抄 `tau = amp * sig1d * sqrt(2π) * 0.5 * [erf(z1)-erf(z0)]` 这套解析透射率公式，省掉 §2.2 的固定步进循环。
- **但这不是现在要做的事**：当前云层用连续噪声场 + 固定步进已经是标准且够用的方案，没有 R&D 必要现在就换栈。列在这里只是留一个"如果 GaussianVolume 那边验证出性能优势，未来云层有的抄"的备注，**不阻塞 T-L3.2 当前实现**，也不涉及恒星本体（D3 决策不受影响，恒星转真体积渲染已被 `D3-KERNEL.md` §1 明确否决，这里说的只是云天象的密度积分方式，是完全独立的技术点）。

---

## §6 性能预算占位（待 UE 里实测回填）

| 分支 | 步数 | 预估开销（占位，未实测） |
|---|---|---|
| 云（§3） | 32-64 步 | 待测，PIPELINE §3 目标"5-8ms 余量"内 |
| 极光（§3 对应 §4） | 16-24 步（薄层，S3 局部区域） | 待测，应远低于云（无消光计算、区域更小） |

> [!TODO] W3/W4 落地后回填实测值，同步更新 `D3-KERNEL.md` §4 的整体帧预算表（体积云那一行）。

---

## §7 落地时的实现路径建议（非拍板，供参考）

- **Post Process Material** 走法：适合云（全屏体积，depth-based 早出天然契合 PP 材质拿场景深度）。
- **Volume/Custom Shader 走法**：适合极光（区域小，S3 局部，用一个薄片 mesh + 半透明材质挂自定义 raymarch 函数即可，不用全屏 PP）。
- 两者共享 §2 的 `RayBoxIntersect` + 步进循环可以做成一个 **Material Function**（`MF_RaymarchCore`），云和极光各自的材质只需接不同的 `SampleXXX` 分支——这样"一套框架喂多种介质"在材质图层面也是字面意思的复用，不是文档口号。

---

## 维护
- 本文件是草稿，落地后把"已实现"部分的关键参数/节点图截图归档到本目录，草稿本身可保留作设计意图记录。
- 与 `PIPELINE.md` §3（拍板范围）· `D3-KERNEL.md` §3/§4（恒星侧的框架接入点与整体帧预算）互引。
