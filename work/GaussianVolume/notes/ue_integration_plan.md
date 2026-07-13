# UE 集成方案调研

> 目标：将 GaussianVolume renderer 集成到 Unreal Engine 5，作为 VDB 体积云的中远景 LOD / proxy 方案。

## 1. 现有 UE5 体积云生态

### 1.1 UE5 原生 Volumetric Cloud

UE5 内置的 `VolumetricCloud` 组件使用 **ray marching** 渲染体积云：
- 基于 `RealTimeSky` + `VolumetricCloud` actor
- 多分辨率 ray marching（half-res → full-res upsample）
- 支持 phase function (Henyey-Greenstein)、multi-scattering approximation
- 数据来源：程序化噪声（curl noise + weather map），不支持外部 VDB

**与 GaussianVolume 的关系**：UE5 原生云是 ray marching 密度场，GaussianVolume 是 ray tracing Gaussian primitives。两者可以共存——GaussianVolume 作为远景 LOD proxy，近处仍用原生 ray marching。

### 1.2 unreal-vdb 插件

- 仓库：https://github.com/c0rvus-ix/unreal-vdb（原 Eidos Montreal）
- 功能：读取 OpenVDB / NanoVDB 文件，在 UE5 中渲染 sparse volume
- 实现：`SparseVolumetrics` 插件，使用 ray marching + 3D texture
- 需要光线追踪支持（`r.RayTracing=True`）

**与 GaussianVolume 的关系**：unreal-vdb 是 **直接渲染 VDB**，GaussianVolume 是 **VDB → Gaussian 转换后渲染**。两者的目标场景互补：
- unreal-vdb：hero 云（近处、高精度、少量）
- GaussianVolume：中远景 LOD（多团云、低 cost per cloud）

### 1.3 UE5 Gaussian Splatting 插件

已有多个 3DGS → UE5 集成方案（如国产全链路插件），核心做法：
- Gaussian 数据存为 `StructuredBuffer<float>`（center, scale, rotation, color, opacity）
- Compute Shader 做 tile-based sorting + rasterization
- 输出到 render target，与场景 depth composite

**与 GaussianVolume 的关系**：3DGS 插件的 **数据传输和 composite 管线可直接复用**，但渲染算法需要替换（splatting → ray tracing volume density）。

---

## 2. 集成架构方案

### 2.1 方案选型

| 方案 | 描述 | 优势 | 劣势 |
|------|------|------|------|
| A. Compute Shader | 全 GPU compute pass，StructuredBuffer 存 Gaussian，CS 做 ray tracing + compositing | 最高性能，完全自主管线 | 需要自建 RDG pass，与 UE5 渲染管线集成复杂 |
| B. Pixel Shader | Fullscreen pass，在 PS 中对每 pixel 做 ray tracing | 集成简单（PostOpaqueRenderDelegate） | 性能不如 CS（branching overhead） |
| C. Niagara GPU particle | 用 Niagara 的 GPU particle 模拟 Gaussian，自定义 renderer | 利用 UE5 现有 particle 系统 | 不适合 per-pixel ray tracing，更适合 splatting |
| D. Custom mesh + Material | 每个 Gaussian 一个 instanced mesh，材质中做 ray marching | 最简单 | 完全不适合（draw call 爆炸） |

**推荐：方案 A（Compute Shader）**，理由：
1. GaussianVolume 的核心是 per-pixel ray-Gaussian intersection + compositing，天然适合 CS 的 thread-per-pixel 模型
2. 3DGEER 的 PBF-CSF tile association 可以直接映射到 CS thread group
3. VoGE 的 CUDA kernel 结构提供了直接的 CS 实现参考
4. StructuredBuffer 已有成熟模式（3DGS 插件验证）

### 2.2 数据传输

```
C++ Side:
  GaussianCloud → StructuredBuffer<float4>
  每个 Gaussian = 5 个 float4：
    float4 center_sigma_t;    // xyz = center, w = sigma_t
    float4 scale_quat;        // xyz = scale, w = quat.w  (or separate buffers)
    float4 rotation;          // quat.xyz (w in scale_quat.w)
    float4 albedo_padding;    // rgb = albedo, a = padding

  Light tau matrix → StructuredBuffer<float> (N×N, 可选，大 N 时省略)

GPU Side:
  RWStructuredBuffer<float4> GaussianData;  // SRV
  RWTexture2D<float4> ColorOutput;          // UAV
  RWTexture2D<float> DepthOutput;           // UAV (for depth composite)
```

### 2.3 渲染管线

```
1. [C++] FSceneViewExtension → hook PostOpaqueRenderDelegate
2. [C++] RDG pass: "GaussianVolumeRender"
   a. Upload Gaussian StructuredBuffer (if dirty)
   b. Dispatch CS: thread group = tile (8×8 or 16×16)
   c. CS output: ColorOutput RT + DepthOutput RT
3. [C++] Composite: blend ColorOutput into scene at half-res, upsample with temporal
4. [Material/PS] Optional: depth-aware composite in a fullscreen PS pass
```

### 2.4 Compute Shader 结构（参考 VoGE + 3DGEER）

```hlsl
// GaussianVolume.usf

StructuredBuffer<float4> GaussianData;    // 5 float4 per Gaussian
RWTexture2D<float4> OutputColor;
RWTexture2D<float> OutputDepth;

cbuffer RenderParams {
    float4 CameraPos;
    float4 CameraDir;   // forward
    float4 CameraRight;
    float4 CameraUp;
    float2 InvResolution;
    float Fov;
    uint NumGaussians;
    float4 LightDir;
    float4 LightColor;
    float4 Ambient;
};

[numthreads(8, 8, 1)]
void MainCS(uint3 DTid : SV_DispatchThreadID) {
    uint2 pixel = DTid.xy;
    if (pixel.x >= ResolutionX || pixel.y >= ResolutionY) return;

    // 1. Generate ray
    float2 uv = (pixel + 0.5) * InvResolution;
    float2 ndc = uv * 2.0 - 1.0;
    float3 ray_dir = normalize(CameraDir + CameraRight * ndc.x * tanHalfFov + CameraUp * ndc.y * tanHalfFov);

    // 2. Candidate filtering (bounding sphere or PBF)
    //    For now: brute-force all N (small N) or tile-based (large N)

    // 3. For each candidate: compute A, B, C → t_star, peak, erf integral
    float3 color = 0;
    float transmittance = 1.0;
    float depth = 1e8;

    // Sorted front-to-back (pre-sort on CPU or GPU bitonic sort)
    for (uint i = 0; i < NumGaussians && transmittance > 0.001; i++) {
        // Fetch Gaussian
        float4 cs = GaussianData[i * 5 + 0];     // center.xyz, sigma_t
        float4 sq = GaussianData[i * 5 + 1];     // scale.xyz, quat.w
        float4 rq = GaussianData[i * 5 + 2];     // quat.xyz

        // Build Sigma^{-1} from scale + quat
        float3x3 R = quat_to_rot(rq.xyz, sq.w);
        float3x3 Sinv = { 1/sq.x, 0, 0, 0, 1/sq.y, 0, 0, 0, 1/sq.z };
        float3x3 SigmaInv = mul(mul(R, Sinv), transpose(R));

        // Ray-Gaussian intersection
        float A = dot(ray_dir, mul(SigmaInv, ray_dir));
        float B = dot(CameraPos - cs.xyz, mul(SigmaInv, ray_dir));
        float C = dot(CameraPos - cs.xyz, mul(SigmaInv, CameraPos - cs.xyz));

        float t_star = -B / A;
        float peak = -0.5 * (C - B*B/A);
        if (peak < -10.0) continue;  // too far from ray

        // Bounding interval (finite integral limits)
        float sigma_r = 3.0;  // 3-sigma cutoff
        float dt = sigma_r * rsqrt(A);
        float t_near = t_star - dt;
        float t_far = t_star + dt;
        if (t_far < 0) continue;  // behind camera

        // Analytic transmittance via erf
        float z0 = sqrt(A/2) * (t_near - t_star);
        float z1 = sqrt(A/2) * (t_far - t_star);
        float tau = cs.w * exp(peak) * sqrt(PI/(2*A)) * (erf(z1) - erf(z0));
        float alpha = 1.0 - exp(-tau);

        // Single scattering (simplified)
        float light_A = dot(LightDir, mul(SigmaInv, LightDir));
        float light_tau = ...; // similar erf for light direction
        float3 scatter = albedo * LightColor * exp(-light_tau) * (1.0 - exp(-tau));

        color += scatter * transmittance;
        transmittance *= (1.0 - alpha);
        depth = min(depth, t_star);
    }

    color += Ambient * (1.0 - transmittance);

    OutputColor[pixel] = float4(color, 1.0 - transmittance);
    OutputDepth[pixel] = depth;
}
```

---

## 3. 性能优化路径

### 3.1 分辨率策略

- **Half-res render + temporal upsample**：GaussianVolume 在 960×540 渲染，TAA upsample 到 1920×1080。体积云是低频内容，half-res 质量损失极小。
- **Adaptive resolution**：远处云降为 quarter-res，近处 hero 云升为 full-res。

### 3.2 Candidate Reduction（GPU 化时）

参考 3DGEER 的 PBF-CSF tile association：
1. 每帧对每个 Gaussian 计算 camera-space angular bounds (θ_min, θ_max, φ_min, φ_max)
2. Tile (8×8 pixel) 对应一个 Camera Sub-Frustum (CSF)
3. CS-GS association：一个 compute pass 输出 per-tile candidate list
4. Render pass：每 pixel 遍历自己 tile 的 candidate list

### 3.3 Tau 矩阵 GPU 化

当前 CPU NumPy 版的 tau 矩阵预计算是 O(N²)，在 GPU 上可以用 compute shader 并行计算：
- N ≤ 1024：直接 O(N²) in CS，一个 dispatch 搞定
- N > 1024：需要分块或 shared memory tiling

### 3.4 排序

- Front-to-back 排序：GPU bitonic sort（O(N log²N)）或 radix sort
- 或：不排序，用 VoGE 的闭式 cross-activation（O(K²) per pixel，K ≤ 20）

---

## 4. 与 UE5 场景的 Composite

### 4.1 Depth Composite

GaussianVolume 输出 per-pixel depth（最近 Gaussian 的 t_star），需要与场景 depth buffer composite：

```hlsl
// Composite.usf (fullscreen PS)
Texture2D SceneColor;
Texture2D SceneDepth;
Texture2D GaussianColor;    // half-res
Texture2D GaussianDepth;    // half-res

float3 CompositePS(float2 uv : TEXCOORD) {
    float sceneDepth = SceneDepth.Sample(PointSampler, uv);
    float gaussianDepth = GaussianDepth.Sample(PointSampler, uv).r;

    float3 sceneColor = SceneColor.Sample(PointSampler, uv);
    float4 gaussianColor = GaussianColor.Sample(PointSampler, uv);

    // Gaussian 在场景物体后面 → 直接 blend
    if (gaussianDepth > sceneDepth) {
        return lerp(sceneColor, gaussianColor.rgb, gaussianColor.a);
    }
    // Gaussian 在场景物体前面 → 被 occlude
    return sceneColor;
}
```

### 4.2 Lighting Integration

- **Sun light**：从 UE5 `DirectionalLight` 获取 light direction 和 color
- **Ambient**：从 UE5 `SkyLight` 或 `VolumetricCloud` ambient 获取
- **Shadow**：GaussianVolume 自身的 single scattering 已包含 self-shadow（tau 矩阵），但需要考虑场景物体对云的 shadow（可采样 UE5 的 shadow map 或 DFS）

---

## 5. 实施路线图

> **环境**：UE 5.7 源码版（`D:/Work/Personal/UnrealEngine`），项目 `Abyss.uproject`
> **插件路径**：`Abyss/Plugins/GaussianVolume/`

### Phase 1: Plugin Scaffold ✅ 已完成
1. ✅ 创建 UE5 plugin（Runtime type），模块 `FGaussianVolumeModule`
2. ✅ 实现 `FWorldSceneViewExtension`，注册到 World
3. ✅ 创建 compute shader pass（`FGaussianVolumeRayTraceCS`），输出到 RDG texture
4. ✅ 验证 CS 输出可以 composite 到场景

**文件**：
- `GaussianVolume.uplugin`、`GaussianVolume.Build.cs`
- `Public/GaussianVolume.h`、`Private/GaussianVolume.cpp`（shader source mapping `/GaussianVolume`）
- `Public/GaussianVolumeShaders.h`、`Private/GaussianVolumeShaders.cpp`
- `Public/GaussianVolumeSceneViewExtension.h`、`Private/GaussianVolumeSceneViewExtension.cpp`

### Phase 2: Gaussian Data Upload ✅ 已完成
5. ✅ 定义 `UGaussianVolumeComponent`（UActorComponent），持有 `TArray<FGaussianVolumePrimitive>`
6. ✅ 实现 CPU→GPU 数据管线：`PackPrimitive()` → `TArray<FVector4f>` → `ENQUEUE_RENDER_COMMAND` → `CreateStructuredBuffer`
7. ✅ GPU 打包格式：4 × float4 per Gaussian（`GaussianVolumeTypes.h`）
   - `[0]` center.xyz, sigma_t
   - `[1]` scale.xyz, quat.w
   - `[2]` quat.xyz, pad
   - `[3]` albedo.rgb, pad
8. ✅ `AGaussianVolumeActor` 持有 Component，`OnRegister()` 自动创建 SVE + push data
9. ✅ 调试默认 Gaussian：scale=300, sigma_t=2.0, 暖橙色 albedo
10. ✅ 验证通过：品红色/暖橙色调试画面出现 = pipeline OK

**文件**：
- `Public/GaussianVolumeTypes.h`（GPU pack format）
- `Public/GaussianVolumeComponent.h`、`Private/GaussianVolumeComponent.cpp`
- `Public/GaussianVolumeActor.h`、`Private/GaussianVolumeActor.cpp`

### Phase 3: Ray Tracing Renderer ✅ 代码完成，待运行时验证
11. ✅ Ray generation：camera pos/forward/right/up + tanHalfFov + aspect → per-pixel ray dir
    - UE ViewToWorld 矩阵：`InvViewMat.GetColumn(0)` = forward, `(1)` = right, `(2)` = up
12. ✅ A/B/C → erf transmittance（从 `gaussian_volume.py` 移植到 HLSL）
    - `RayGaussianTau()`：erf 区间积分，有限积分限 [t_near, t_far]
    - **HLSL SM6 不暴露 `erf()` 内置函数** → 手写 Abramowitz-Stegun 7.1.26 近似（max err ~1.5e-7）
13. ✅ 3-sigma bounding sphere cull（per-pixel, brute force）
14. ✅ Front-to-back compositing + early termination（T < 0.001）
15. ✅ Single scattering：`LightGaussianTau()` per-primitive self-shadow
16. ✅ Powder effect：`1.0 - exp(-2.0 * tau) * PowderFactor`
17. ✅ Composite PS：alpha-blend Gaussian output onto SceneColor

**三项关键修复（代码审查后完成）**：
- **Fix #1 渲染钩子**：`PostRenderBasePassDeferred` → `PrePostProcessPass_RenderThread`
  - 原因：PostRenderBasePass 在天空 pass 之前，天空会覆盖 Gaussian 输出
  - PrePostProcessPass 在所有场景渲染（含天空/大气）完成后执行
  - 通过 `FPostProcessingInputs::ViewFamilyTexture` 获取完整 SceneColor
  - 需要在 `Build.cs` 添加 Renderer 模块 `Internal`、`Internal/PostProcess`、`Private` include 路径
- **Fix #2 Composite 方式**：`AddDrawTexturePass`（直接覆盖）→ 自定义 Composite PS（alpha blend）
  - `AddDrawTexturePass` 非命中像素输出近黑色 (0.02, 0.03, 0.05)，覆盖场景
  - CS 输出 RGBA16F，alpha = 1 - T
  - PS 执行 `finalColor = GaussianColor * alpha + SceneColor * (1 - alpha)`
  - 使用 `AddDrawScreenPass` + `RENDER_TARGET_BINDING_SLOTS`，`ELoad` 保留未命中像素
- **Fix #3 像素映射**：`ViewRect` → `UnconstrainedViewRect`，相机向量 `GetSafeNormal()`
  - 原因：Screen Percentage 下 `ViewRect` 与实际渲染分辨率不匹配，导致球随视角漂移
  - CS 用 view-rect-relative 坐标，PS 用 `SvPosition - ViewRect.Min` 反算

**当前状态**：
- `DebugMode=1`（纯 albedo 渲染，跳过光照计算，验证射线投射）
- 编译通过（UE 5.7 源码版）
- 编辑器可启动（已绕过 `ThirdPersonMap` 材质损坏崩溃）
- **待验证**：在编辑器中放置 `GaussianVolumeActor`，确认调试 Gaussian（暖橙色球）正确渲染并随相机移动

**已知问题**：
- `SceneColorInput` SRV 方案已回退（担心 SRV/UAV 冲突），当前 CS 输出独立 OutputTexture 后 composite 写回

### Phase 4: Optimization（待开始）
18. Half-res + temporal upsample
19. PBF-CSF tile association（如果 N > 512）
20. Depth composite with scene
21. N×N light tau 矩阵 GPU 化（当前仅 per-primitive self-shadow）

### Phase 5: Polish（待开始）
22. Material/Blueprint interface
23. VDB import pipeline（VDB → Gaussian → StructuredBuffer）
24. Performance profiling & tuning

---

## 6. 风险与 Mitigation

| 风险 | 概率 | Mitigation |
|------|------|-----------|
| RDG pass 集成复杂 | 已解决 | 实现 `PrePostProcessPass_RenderThread` + RDG CS + Composite PS |
| ~~HLSL 有 `erf()` intrinsic~~ | 已解决 | **SM6 不暴露 `erf()`**，手写 Abramowitz-Stegun 7.1.26 近似（err ~1.5e-7） |
| 渲染钩子选择 | 已解决 | `PostRenderBasePassDeferred` 被天空覆盖 → 改用 `PrePostProcessPass_RenderThread` |
| Composite 覆盖问题 | 已解决 | `AddDrawTexturePass` 全屏覆盖 → 自定义 PS alpha blend |
| Screen Percentage 漂移 | 已解决 | `ViewRect` → `UnconstrainedViewRect` + `GetSafeNormal()` |
| UE5.7 API 变更 | 已解决 | `ViewRect`→`UnconstrainedViewRect`；`SceneViewExtension.h` 无 `Engine/` 前缀；`FRDGTextureDesc.Extent` |
| 大 N 排序开销 | 后置 | N ≤ 512 不排序（brute-force + early termination）；大 N 用 PBF |
| 体积云与场景交互 | 后置 | Depth composite + 可选 shadow map 采样 |
