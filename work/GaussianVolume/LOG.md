# GaussianVolume · LOG

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

<!-- 新条目追加在下方 -->

### 2026-05-29 15:50 — [决策] 启动 Gaussian volume 预研

先按 Don't Splat your Gaussians 的论文结构做工程验证，暂时抛开最终精度，重点看 Gaussian volume primitive 的 runtime 结构、解析透射率、遍历/加速和 UE 落地可优化点。

### 2026-05-29 15:58 — [决策] 收窄 MVP 范围

第一版不追完整 VDB 拟合和多次散射；先用手工/程序化 Gaussian cloud 验证体积感、ray-Gaussian 积分、single scattering 与 primitive traversal 成本曲线。

### 2026-05-29 16:24 — [决策] MVP 通过标准

MVP 只回答三件事：能否形成基本体积感、解析 transmittance 是否替代大量固定步 raymarch、primitive traversal/candidate 数是否可控；通过后再接 VDB block → Gaussian primitives。


### 2026-06-05 16:30 — [发现] MVP 复现跑通，三问有结论

standalone CPU renderer（mvp/，纯 NumPy）跑通：手工 Gaussian cloud + ray-Gaussian 解析 optical depth（erf 区间积分，零固定步 raymarch）+ front-to-back single scattering。
① 体积感：✅ N=1024 出连续云团、明暗柔和、无硬边噪点。
② 解析 transmittance 替代 raymarch：✅ 每个 primitive 一次 erf 即得整段 tau，view/light 两个方向都解析。
③ traversal 可控性：⚠️ brute-force bounding sphere 的 candidate/ray 随 N 近似线性（稳定 ~45%，N=8192 时均值 3677），是后续头号瓶颈。

### 2026-06-05 16:30 — [决策] 下一步优先做加速结构

MVP 结构成立，瓶颈定位在 traversal。下一步先上 uniform grid / macro cell 把 candidate 比例从 ~45% 压下来，再谈精度与 VDB→primitive 转换。性能基线：N=1024、200x150、纯 Python 约 85s（355 ray/s），后续可向量化/分块加速。

### 2026-07-07 16:41 — [决策] 项目重新激活

从 archive 取回 work/。MVP 三问已有结论，结构成立。重新激活后首要任务不变：加速结构（uniform grid / macro cell）降低 candidate/ray 比例。

### 2026-07-07 16:57 — [发现] Uniform grid 加速结构实验结论

实现 uniform grid + Amanatides-Woo DDA 遍历，正确性验证通过（Python 版 color diff=0）。但性能结论反转预期：
① 纯 Python 下 grid 比 brute-force 慢（0.66x）——NumPy 向量化的全量 bounding sphere 测试比 Python 逐 cell DDA 循环快。
② Numba JIT 编译后 BF 获 ~20x 加速（270→5347 ray/s@N=256），但 grid 仍比 BF 慢（0.23x-0.78x）。
③ 根因：grid 不能减少 actual candidate 数（ray-primitive 相交是几何属性），只减少被测试的 primitive 数。而真正的性能瓶颈是 compositing 中的 O(n_cand^2) 光照衰减循环——每个 candidate 要对其他所有 candidate 算光源方向 tau。
④ Numba grid 版有并行竞争 bug（prange 共享 buffer），修复后仍有 diff=0.81 的正确性问题待查。

### 2026-07-07 16:57 — [决策] 加速方向转向 compositing 优化

uniform grid 对当前场景（密集 cloud、~45% candidate rate）不是正确的加速路径。下一步优先：
① 预计算光源方向 tau 矩阵（O(n_cand^2) 一次算完，避免逐 candidate 重复）
② early termination 已有（T<1e-3），考虑 tighter threshold
③ Numba BF 已达 2097 ray/s@N=1024，可作为短期可用基线
④ Grid 保留代码但降优先级，等 VDB→primitive 转换后数据稀疏时再评估

### 2026-07-07 19:10 — [发现] tau 矩阵预计算实现，6.7x 加速

实现 `precompute_light_tau_matrix`：光源方向固定时一次性算 (N,N) tau 矩阵（chunked einsum），shade_ray 中 O(M²) 逐 candidate `ray_gaussian_taus` 调用替换为 O(M) 查表 `tau_light[idx[k], idx].sum()`。
① 正确性：color max diff = 0.00e+00，与原始路径完全一致。
② 性能：N=1024 200x150，旧路径 54.67s（549 ray/s）→ 新路径 8.16s（3675 ray/s），6.70x 加速。precompute 仅 0.18s（占 2%），amortized 3535 ray/s。
③ N scaling：256→4.81x、512→5.16x、1024→5.90x，加速比随 N 增大（M² 项主导）。
④ 纯 NumPy 3675 ray/s 已接近 Numba BF 基线（2097 ray/s@N=1024），叠加 Numba 后预期可达 1万+ ray/s。

### 2026-07-07 19:20 — [发现] Numba + tau 矩阵集成，prange 竞争修复，76万 ray/s

实现 `numba_renderer.py`：全管线 Numba JIT（candidate 查找 + tau 积分 + compositing + tau 矩阵查表），prange 并行每像素。
① prange 竞争修复：上一版 diff=0.81 的根因是线程写共享 color/od/trans/cand buffer。修复方案——每线程写唯一像素索引 j*W+i，无交叉。
② 正确性：tau 矩阵 NB vs NP diff=2.8e-9，color diff=1.5e-11，candidate diff=0。PASS。
③ 性能：N=1024 200x150，NB 0.04s（76万 ray/s）vs NP 6.41s（4682 ray/s），154x 加速。precompute NB 0.004s。
④ N scaling：256→320万、512→214万、1024→76万 ray/s。N=1024、200×150 单帧约 `0.04 s`（约 `40 ms`），原 `0.04 ms` 为单位错误，不能据此声称目标分辨率实时。
⑤ 结论：prange 竞争 bug 已修，grid 版降优先级（BF+tau+Numba 已足够快，grid 不减少 actual candidate）。

### 2026-07-07 19:30 — [发现] VoGE 交叉阅读完成

阅读 VoGE（ICLR 2023, arXiv:2205.15401）论文+源码，提取 4 个可落地模块：
① 数学一致性确认：VoGE CUDA kernel 中 `hit_length = m_sig_k/k_sig_k`（= t_star）、`hit_activation = C - B²/A`（= -2×peak），与本项目 `ray_density_integral.md` 完全吻合。
② Top-K 选择：VoGE 不做全 candidate compositing，每 ray 取最近 K=20 个（bubble sort insert in CUDA kernel），比本项目 early termination 更激进。
③ Coarse-to-fine：screen-space tile rasterization（2D projection → bin assignment）→ fine ray trace，适合 GPU 并行，不适合当前 CPU/Numba。
④ 闭式 cross-activation：用 erf-based mutual occlusion 替代 front-to-back 累积，O(K²) 闭式计算，无序可并行，但与 single scattering 有序 compositing 冲突。
⑤ VDB→Gaussian 启示：VoGE 的 surface converter 不直接适用，但 percentage 参数和 neighbor-based sigma 估计有参考价值。

### 2026-07-07 19:50 — [发现] Vol3DGS 交叉阅读完成

阅读 Vol3DGS（CVPR 2025 Highlight, arXiv:2412.03378）论文+源码，回答 backlog 问题：
① **analytic alpha + rasterization 可作 view ray transmittance 实时近似**——Vol3DGS 在 3DGS rasterizer 框架内用解析 erf 积分替换 splatting alpha，drop-in replacement，速度持平 3DGS。
② **不可替代 shadow ray/single scattering**——Vol3DGS 不涉及光照，本项目的 tau 矩阵优化仍必要。
③ 数学一致性：γ_j=t_star, β_j=1/√A, peak=G_j(γ·d)——与本项目完全一致。
④ 关键差异：Vol3DGS 用无限积分限 `[-∞,+∞]`（适合 surface），本项目用有限积分限 `[t_near,t_far]`（体积云必需，更精确）。
⑤ Non-overlapping 假设：Vol3DGS 假设 Gaussian 不重叠（alpha blending 精确条件），本项目云 Gaussian 有 overlap，需逐步 compositing 而非 alpha 链。

### 2026-07-07 20:10 — [发现] 3DGEER 交叉阅读完成，三篇交叉阅读全部结束

阅读 3DGEER（ICLR 2026, Bosch Research, arXiv:2505.24053）论文+源码：
① **PBF（Particle Bounding Frustum）是三篇中最有价值的 candidate reduction 方案**——per-Gaussian closed-form angular bounds + tile intersection，不依赖 BVH，3DGEER 证明比 BVH 方法快 5×，接近 3DGS 帧率。
② **canonical space transmittance** 与本项目 A/B/C 分解数学等价（各向同性化 → perpendicular Mahalanobis distance² = C - B²/A）。
③ **"maximum response" t_star 被 3DGEER 证明是 projective-exact**（非启发式近似），间接验证本项目数学正确性。
④ **无限积分限**（同 Vol3DGS）不适用于体积云 overlapping Gaussian，本项目保留有限积分限。
⑤ **三篇横向对比表**已整理在 `notes/3dgeer_cross_reading.md` 第 5 节。
⑥ Action items：短期实验 PBF-style candidate reduction + Top-K 截断；中期 GPU 化采用 PBF-CSF tile association。

### 2026-07-07 20:40 — [实现] VDB to Gaussian 转换器

实现 mvp/vdb_converter.py，将 VDB voxel density grid 转换为 Gaussian volume primitives：
1. 双输入模式：pyopenvdb.Grid（真实 VDB 读取）+ NumPy dense array（测试 fallback）。
2. 转换逻辑：每个 active voxel -> 一个 Gaussian。center = voxel world pos，sigma_t = density * density_scale，scale = voxel_size * sigma_max_scale / 2。
3. 各向异性模式：梯度方向 = 密度变化最快方向（有限差分），沿梯度方向 scale 压缩为 ratio * base（类似 VoGE normal-based anisotropy）。
4. max_primitives 限制：按密度降序保留 Top-K，用于控制渲染成本。
5. 测试结果：24^3 grid（13312 active voxels）-> 7928 prims（1.7x 压缩），各向异性 scale [0.06, 0.20]。渲染 N=512, 120x90, 0.5s, 21K ray/s。iso vs aniso color diff = 0.012。
6. 待完善：VDB 空间稀疏性利用、merge 相邻低密度 voxel、pyopenvdb 实际 .vdb 文件测试。

### 2026-07-07 20:55 — [调研] UE 集成方案完成

编写 
otes/ue_integration_plan.md，完成 UE5 集成方案调研：
1. 推荐 Compute Shader 方案（FSceneViewExtension + RDG pass），理由：per-pixel ray-Gaussian 天然适合 CS thread-per-pixel，PBF-CSF tile association 可直接映射到 CS thread group。
2. 数据传输：GaussianCloud -> StructuredBuffer<float4>（5 float4 per Gaussian：center_sigma_t / scale_quat / rotation / albedo）。
3. 渲染管线：PostOpaqueRenderDelegate -> RDG CS pass -> half-res ColorOutput + DepthOutput -> temporal upsample -> depth composite。
4. HLSL 伪代码已写（含 A/B/C -> erf transmittance + front-to-back compositing + single scattering）。
5. 5 阶段实施路线图：Plugin Scaffold(1-2d) -> Data Upload(1d) -> Ray Tracing Renderer(2-3d) -> Optimization(2-3d) -> Polish(1-2d)。
6. 性能优化路径：half-res + TAA、PBF-CSF candidate reduction、GPU bitonic sort、tau 矩阵 CS 并行。
7. 风险评估：RDG 集成复杂度中等、erf 在 HLSL 有 intrinsic、大 N 用 PBF 替代排序。
8. BACKLOG 全部清零。

### 2026-07-08 — [决策] UE 集成启动，Phase 1/2 完成

在 Abyss 项目（UE 5.7 源码版）中创建 `GaussianVolume` 插件，按 5 阶段路线图推进。

**Phase 1 (Plugin Scaffold)**：
- 创建 Runtime plugin，模块 `FGaussianVolumeModule`
- `FWorldSceneViewExtension` 注册到 World
- `FGaussianVolumeRayTraceCS`（GlobalShader, SM6, 8×8 thread group）
- `AddShaderSourceDirectoryMapping("/GaussianVolume")` → shader 目录映射
- 验证：CS pass 输出到 RDG texture 并 composite 到场景

**Phase 2 (Gaussian Data Upload)**：
- `UGaussianVolumeComponent`（UActorComponent）持有 `TArray<FGaussianVolumePrimitive>`
- GPU 打包格式：4 × FVector4f per Gaussian（center_sigma_t / scale_quatW / quatXYZ / albedo）
- CPU→GPU 管线：`PackPrimitive()` → `ENQUEUE_RENDER_COMMAND` → `CreateStructuredBuffer`
- `AGaussianVolumeActor` 持有 Component，`OnRegister()` 自动创建 SVE + push data
- 调试默认 Gaussian：scale=300, sigma_t=2.0, 暖橙色
- 验证通过：品红色/暖橙色调试画面出现 = pipeline OK

### 2026-07-08 — [发现] HLSL SM6 不暴露 erf() 内置函数

SM6 shader model 不暴露 `erf()` intrinsic。原集成方案假设"HLSL 有 erf intrinsic"有误。
修复：手写 Abramowitz-Stegun 7.1.26 多项式近似（max abs err ~1.5e-7），对体积渲染足够精确。
另外 `Platform.ush` include 路径需用 `/Engine/Public/Platform.ush`（非 `Engine/Platform.ush`）。

### 2026-07-08 — [发现] UE 5.7 ViewToWorld 矩阵列映射

UE5 `FViewMatrices::GetInvViewMatrix()` 的列映射（经实际验证确认）：
- `GetColumn(0)` = forward（相机前方）
- `GetColumn(1)` = right（相机右方）
- `GetColumn(2)` = up（相机上方）
与 OpenGL 约定一致。所有相机向量需 `GetSafeNormal()` 归一化。

### 2026-07-09 — [决策] Phase 3 三项关键修复

Phase 3 ray tracing renderer 代码完成后，代码审查发现三个问题并修复：

**Fix #1 渲染钩子**：`PostRenderBasePassDeferred` → `PrePostProcessPass_RenderThread`
- 原钩子在天空 pass 之前执行，天空渲染覆盖 Gaussian 输出
- `PrePostProcessPass` 在所有场景渲染（含天空/大气）完成后、后处理之前执行
- 通过 `FPostProcessingInputs::ViewFamilyTexture` 获取完整 SceneColor
- 需在 `Build.cs` 添加 Renderer 模块 `Internal`、`Internal/PostProcess`、`Private` include 路径

**Fix #2 Composite 方式**：`AddDrawTexturePass`（全屏覆盖）→ 自定义 Composite PS（alpha blend）
- `AddDrawTexturePass` 直接覆盖，非命中像素输出近黑色 (0.02,0.03,0.05)
- CS 输出 RGBA16F，alpha = 1 - T
- PS 执行 `finalColor = GaussianColor * alpha + SceneColor * (1 - alpha)`
- 使用 `AddDrawScreenPass` + `RENDER_TARGET_BINDING_SLOTS`，`ELoad` 保留未命中像素

**Fix #3 像素映射**：`ViewRect` → `UnconstrainedViewRect`，相机向量 `GetSafeNormal()`
- Screen Percentage 下 `ViewRect` 与实际渲染分辨率不匹配，导致球随视角漂移
- CS 用 view-rect-relative 坐标，PS 用 `SvPosition - ViewRect.Min` 反算

### 2026-07-09 — [发现] UE 5.7 API 变更清单

实际开发中遇到的 UE 5.7 API 差异（相对旧文档/教程）：
- `FSceneView::ViewRect` → `UnconstrainedViewRect`
- `SceneViewExtension.h` include 不带 `Engine/` 前缀
- `FRDGTextureDesc` 继承自 `FRHITextureDesc`，获取尺寸用 `.Desc.Extent`
- Live Coding 不编译 shader、不重新执行 `StartupModule`，必须完整关闭编辑器重新编译

### 2026-07-09 — [发现] ThirdPersonMap 材质重定向器损坏导致 PSO Fatal 崩溃

编辑器启动时 `ThirdPersonMap` 中 `M_Wave_Base_Inst`、`M_OutLine_Inst` 材质实例重定向失败，触发 PSO Fatal 崩溃。
临时绕过：`Saved/Config/WindowsEditor/EditorPerProjectUserSettings.ini` 设 `LoadLevelAtStartup=None`，编辑器启动到空白状态。
待修复：Content Browser 中 Fix Up Redirectors in Folder。

### 2026-07-09 — [回滚] SceneColorInput SRV 方案

曾尝试将 SceneColor 作为 SRV 传入 CS（CS 直接读取场景颜色做 composite），但担心 SRV/UAV 冲突（同一纹理既读又写）。
回退为：CS 输出独立 OutputTexture → Composite PS（alpha blend）写回 SceneColor。更安全且 RDG 友好。

### 2026-07-09 20:41 — [发现] Phase 3 看不到画面根因：usf 里 UV-ramp debug 短路

通读插件全链路（SVE/usf/Component/Actor/Shaders）后定位：编译早已通过（build_clean3.log Result: Succeeded），问题纯在运行时。
根因：GaussianVolume.usf 的 MainCS 开头有一段临时 debug——`if (DebugMode > 0.0) { OutputTexture = float4(uv.x,uv.y,0.3,1.0); return; }`，配合 SVE 里硬编码 `DebugMode=1.0f` + `AddCopyTexturePass` 全屏覆盖，导致整个视口被一层 UV 渐变色盖死，ray tracing 循环根本没执行。

### 2026-07-09 20:41 — [回滚] 删除 usf 中 UV-ramp debug 短路

删掉该短路后，DebugMode=1 正确落到循环内的 albedo 纯色路径（命中=暖橙 albedo，miss=亮绿并 return）。预期验证画面：绿背景 + 中央一颗暖橙球。原文件已备份为 GaussianVolume.usf.bak。CopyTexture 全覆盖 + in-shader composite 经复核为自洽方案（DebugMode=0 时 usf 末尾已做 color*alpha+scene*(1-alpha)），无需改动。下一步：编辑器放置 GaussianVolumeActor，仅改 usf 走 shader 热重载即可验证。

### 2026-07-09 21:09 — [发现] 真正病根：PrePostProcessPass 写 ViewFamilyTexture 被后处理覆盖

红色探针 + 全量 recompileshaders 后屏幕仍无任何变化（连 miss 绿背景都没有），证明 shader 是新的、CS 在跑，但输出没上屏。查引擎 PostProcessInputs.h 坐实根因：Inputs.ViewFamilyTexture 不是当前 SceneColor，而是"后处理最终输出容器"，在 PrePostProcessPass 阶段（后处理链最前）尚未填充；CS 把红色 copy 进它后，随后的 tonemap/后处理用自己的 SceneColor 重新写满该纹理，把红色整个覆盖。旧注释"ViewFamilyTexture is the complete scene color"是错的。

### 2026-07-09 21:09 — [回滚] 弃用 PrePostProcessPass，改用 SubscribeToPostProcessingPass(Tonemap) 回调

重构 SVE：删 PrePostProcessPass_RenderThread，改 override SubscribeToPostProcessingPass，在 EPostProcessingPass::Tonemap 注册回调 PostProcessCallback_RenderThread。回调用 Inputs.GetInput(SceneColor) 拿到 tonemap 后的最终画面（FScreenPassTexture，含真实 ViewRect），CS 读它+写同 extent 的 OutputTexture，返回 OutputTexture 接入后处理链——这才会真正上屏（UE 官方全屏后处理标准姿势）。配套：Shaders.h/usf 新增 ViewRectMin 参数，usf 用 outPix=pixel+ViewRectMin.xy 处理"输出纹理是全 extent、视口在子区域"的偏移。CopyFromSlice/GetInput API 已核对引擎源码确认。所有原文件已 .bak 备份。需重新编译 C++（改了 .h/.cpp），再 recompileshaders。

### 2026-07-09 21:25 — [决策] Phase 3 看不到画面的真正根因：渲染钩子写在 tonemap 之前被覆盖

红色探针实测确认：把 SceneViewExtension 钩子从 PrePostProcessPass 改到 SubscribeToPostProcessingPass(EPostProcessingPass::Tonemap) 之后，屏幕立即全红——证明之前所有"什么都看不到"的根因是：在 tonemap 之前写 SceneColor，成果被后续 tonemap/后处理整个覆盖。新方案在 Tonemap pass 之后拿到最终上屏颜色，PostProcessCallback 返回 OutputTexture 接回后处理链（先 AddCopyTexturePass 保留场景，再 CS 覆盖命中像素），写入才真正显示。

### 2026-07-09 21:25 — [回滚] 修复 UE5.7 编译错误 + 移除红色探针

编译修复：(1) GaussianVolumeSceneViewExtension.h 前向声明 class FScreenPassTexture → struct（UE5.7 把 class/struct 不匹配从警告升为 C4099 error）；(2) .cpp 中 GetInvViewMatrix() → GetViewToWorld()（C4996 弃用，语义相同）。确认 ViewRectMin 参数在 .h/.usf 均已声明，无遗漏。编译通过，红探针验证输出链打通后已移除，shader 回到真实 ray tracing（DebugMode=1：命中=暖橙 albedo，miss=亮绿）。.h/.cpp/.usf 均有 .bak 备份。下一步：重编 shader 看暖橙球，若相机没对准球则调几何（注意 log 中 TanHalfFov=1.0 存疑）。

### 2026-07-09 21:58 — [发现] 球渲染成椭圆且随视角夸张变形：射线 FOV 构造错误

Phase 3 打通后球被命中，但各向同性球（scale 300³）显示为椭圆、转视角时长宽比夸张拉伸。根因：射线方向用 CameraRight*ndc.x*tanHalfFov + CameraUp*ndc.y*(tanHalfFov/aspect)，即只取水平 tanHalfFov 再除 aspect 硬凑垂直角度。UE GetTanHalfFov() 返回 FVector2f 已含各轴 tan(halfFov)，正确做法是 X 用 .X、Y 直接用 .Y，不该除 aspect。

### 2026-07-09 21:58 — [回滚] 改用引擎 per-axis tanHalfFov 修正射线

C++: CameraDirs 由 (tanHalfFovX, aspect) 改为 (tanHalfFovX, tanHalfFovY)。usf: ray_dir 的 Y 分量由 ndc.y*tanHalfFov/aspect 改为 ndc.y*tanHalfFovY。预期球恢复为正圆、视角变化不再夸张变形。仅改 usf 需 recompileshaders；改了 .cpp 需重编 C++。

### 2026-07-09 22:05 — [发现] 球被拉成横向细长柳叶：宽屏 aspect 未补偿

截图确认：各向同性球在 2104x1099 宽屏(aspect~1.9)视口下被拉成横向细长柳叶。根因：ray_dir 的 X/Y 都用 tanHalfFov 且未按 aspect 配比，ndc.x/ndc.y 同归一化到[-1,1]，导致水平方向每单位 ndc 对应角度被压缩~2x -> 横向拉长。另注意 GetTanHalfFov() 对正交投影返回1.0（解释早前 TanHalfFov=1.0）。

### 2026-07-09 22:05 — [回滚] X 方向乘 aspect 修正宽屏拉伸（待验证方向）

C++: CameraDirs 改回 (tanHalfFovX, aspectWH)。usf: ray_dir X 分量 * aspect。使 X:Y 射线扩张比 = aspect:1，各向同性球应恢复为圆。若验证仍非圆（方向判断反），改为 Y 分量 / aspect。需重编 C++ + shader。

### 2026-07-09 22:14 — [发现] 斜楔形畸变排查：quat打包正确，怀疑相机基向量非正交

拿 Python 黄金参考 gaussian_volume.py 逐行比对：quat 打包 (Quat.W->sq.w, XYZ->rq.xyz) 与 usf QuatToRotMatrix 一致，默认球 FQuat(0,0,0,1)->恒等 R，SigmaInv 各向同性，数学上应为正圆。aspect 补偿改了无效，说明畸变不来自射线 FOV。斜楔形高度怀疑 CameraRight/Up 用 InvViewMatrix.GetColumn(1)/(2) 取到非正交/错误轴。

### 2026-07-09 22:14 — [回滚] shader 内 cross 现算正交基 + alpha 可视化探针

usf: 弃用 C++ 传的 CameraRight/Up，改用 fwd + cross(fwd, worldUp=(0,0,1)Z-up) 现算正交基（与 Python render() 同款）。另加 DebugMode alpha 可视化探针（命中输出 tau 灰度）。仅改 usf，recompileshaders 即可。若楔形消失变正圆->基向量确为病根；若仍畸变->查 SigmaInv 数值尺度。

### 2026-07-09 22:16 — [决策] Phase 3 运行时验证通过！调试球稳定渲染为正圆

X 方向乘 aspect 修正后，各向同性调试球在任意视角下均为正圆，Phase 3 ray tracing renderer 运行时验证正式通过。整条管线打通：Component 数据上传 -> StructuredBuffer -> SubscribeToPostProcessingPass(Tonemap) 回调 -> RayTrace CS(ray-Gaussian erf 解析相交) -> 输出接回后处理链上屏。

本轮排障链条（供复盘）：
1. 编译早已通过(build_clean3)，问题全在运行时；
2. 看不到画面根因=渲染钩子写在 PrePostProcessPass(tonemap前)被后处理覆盖 -> 改 SubscribeToPostProcessingPass(Tonemap后)，红探针验证秒变全红；
3. UE5.7 编译修复：class->struct FScreenPassTexture 前向声明(C4099)、GetInvViewMatrix->GetViewToWorld(C4996)；
4. 球被拉成横向柳叶=宽屏 aspect(~1.9)未补偿 -> ray_dir X 分量 *aspect -> 恢复正圆。

下一步（Phase 3 收尾 -> Phase 4）：
- 关闭 DebugMode(SceneViewExtension.cpp: CsParams->DebugMode=1.0f 改 0)，验证 single scattering + powder 光照；
- 清理各源码 .bak 备份与 usf 内残留调试注释；
- 进 Phase 4：half-res + temporal upsample、PBF-CSF tile association、depth composite、N×N light tau GPU 化。

### 2026-07-09 22:26 — [发现] 光照环境下球随视角反向漂移：手搓相机基不可靠

DebugMode=0 进真实光照后暴露：球随视角反向移动（视角右移球左移）。根因：shader 手搓 cross-basis 射线（right=cross(fwd,worldUp)）与 UE 实际相机投影不一致——worldUp 固定(0,0,1)俯仰大时退化、UE clip 空间轴翻转约定、ndc.y flip 方向等叠加，导致投影镜像。纯绿底无参照看不出，有场景才暴露相对运动反了。

### 2026-07-09 22:26 — [回滚] 改用 UE 逆投影矩阵(ClipToWorld)反算射线

彻底弃用手搓基：Shaders.h + usf 新增 ClipToWorld(FMatrix44f)，C++ 传 GetInvViewProjectionMatrix()。usf 用 mul(float4(ndc,0,1), ClipToWorld) 反投影远平面点(reverse-Z: far z=0)得世界坐标，ray_dir = normalize(worldFar - camPos)。与 UE 相机 100% 一致，自动处理 FOV/aspect/朝向/屏幕坐标约定，一劳永逸消除 basis/符号/aspect 所有坑。需重编 C++ + shader。若球上下颠倒或朝后，只需调 ndc.y flip 或 reverse-Z 的 z 值。

### 2026-07-09 22:43 — [回滚] 射线反投影改双点法(near+far)，鲁棒于 reverse-Z 约定

上一版单点(far z=0)反投影后球消失/全屏糊。改为反投影 near(z=1)+far(z=0) 两个 clip 点，ray_o=wNear、ray_dir=normalize(wFar-wNear)，方向不依赖 z 端约定。仅改 usf。注意：ClipToWorld 参数是上一版新增到 .h/.cpp 的，验证前必须确认 C++ 已重编（否则参数为空导致反投影全错，才是球消失真因，而非 z 值）。

### 2026-07-09 22:47 — [发现] 球消失真因：反投影无限远平面(z=0)除零 NaN

查引擎 SceneView.h 确认：(1) ClipToWorld = GetClipToView()*GetViewToWorld() 是绝对世界坐标（非 translated），与 Gaussian center 一致，方案正确；(2) UE 注释明确 clip 空间 Z=1 近平面、Z=0 是 INFINITE 远平面。故反投影 clipFar(z=0) 时 w->0，wFar.xyz/=w 除零得 NaN -> ray_dir 全废 -> 球消失/全屏糊。非矩阵传递/主序问题。

### 2026-07-09 22:47 — [回滚] 射线改用 near(z=1)+mid(z=0.5) 有限深度两点

避开无限远平面：ray_o=wNear(z=1), ray_dir=normalize(wMid-wNear)(z=0.5)，均有限、不除零。仅改 usf，recompileshaders 即可。预期球回来、圆、有光照、视角焊定。若仍漂移则查 ClipToWorld 行列主序(mul 顺序)。

### 2026-07-10 10:43 — [Phase 3 完成] 球显示成功，射线/投影全对，加 Tick 让球跟随 actor

用户确认情况 A：球显示出来、圆、有明暗光照、焊在世界里不随视角反向漂。**射线反投影、投影矩阵、渲染管线全部正确**，Phase 3 渲染目标达成。唯一残留问题：拖动 actor 时球不跟着移动（因 OnRegister 只取一次位置）。

**修复**：Component 加 TickComponent，每帧更新 Gaussians[0].Center = GetOwner()->GetActorLocation() 并重推数据。.h 声明、.cpp 实现、构造函数改 bCanEverTick=true。重编 C++ 后球将跟随 actor 移动。

**Phase 3 总结**：
- ✅ 射线生成：ClipToWorld 逆投影（绝对世界坐标，near z=1 + mid z=0.5 避开无限远除零）
- ✅ 正圆：投影严格对齐 UE 相机，无椭圆
- ✅ 光照：明暗渐变、powder effect、ambient
- ✅ 视角稳定：焊死世界坐标，不反向漂移

下一步：重编 C++ 验证球跟随 actor；验证通过后清理 .bak 文件、更新 BACKLOG、规划 Phase 4。

### 2026-07-10 11:01 — [决策] Phase 3 运行时验证 100% 完成

球跟随 actor 移动验证通过。Actor 加 PostEditMove override，编辑器拖动时实时更新 Gaussians[0].Center 并重推渲染线程。Phase 3 全部验证项达成：
1. ✅ GaussianVolumeActor 放入关卡即渲染
2. ✅ 调试球正圆、不畸变
3. ✅ 视角转动球焊定世界坐标（ClipToWorld 逆投影）
4. ✅ 拖动 actor 球实时跟随（PostEditMove）
5. ✅ DebugMode=0 光照正常（single scattering + powder + ambient）

Phase 3 关闭。下一步进 Phase 4：half-res + temporal upsample、PBF-CSF tile association、Depth composite with scene、N×N light tau 矩阵 GPU 化。

### 2026-07-10 12:00 — [决策] 收缩产品假设，保留 GaussianVolume 内核

讨论结论：GaussianVolume 目前没有证明相较 ZibraVDB、普通 raymarch、Niagara 或 3D texture 的通用生产优势；“Gaussian 体积渲染器”不作为产品定位，也不承诺替代成熟 VDB 方案。已完成的解析 ray-Gaussian 积分、tau/transmittance、VDB 转换和 UE Compute Shader 链路仍然保留为底层技术资产。

下一步将产品假设收缩为 **structured Gaussian Field FX**：用 spline/field 生成稀疏、方向性的 Gaussian 体积带，优先验证极光、能量丝带、魔法轨迹等结构化 VFX。验证重点不是宣称绝对更快，而是比较同一 field 是否能同时服务体积渲染、光束衰减、Niagara/材质 query 和 LOD。若相较 Niagara Ribbon、普通 raymarch/3D texture 没有可测量优势，则将项目收束为研究型渲染内核，不继续扩展通用功能。


### 2026-07-12 15:51 — [决策] Spec 五项默认确认，按 Gate 顺序连续落地

确认交叉三维磁拱为 Hero demo、共享 Field 优先 Niagara 且允许光束/Probe 降级、RTX 5060 以 64 primitives / 1080p / <=2 ms 为初始预算；G1 先用 view-dependent index buffer，当前阶段继续 post-tonemap hook。范围保持 Spec，未开启 manager、VDB、PBF 或通用资产框架。

### 2026-07-12 15:51 — [实现] UE 5.8 G0-G2 已运行验证

UE 5.8 Editor target 编译并重新链接成功，Gaussian shader 无编译错误。已落地 premultiplied 合成、SceneDepth 截断开关、每 View front-to-back index buffer、输入保护、Actor local-space 上传、Spline 的 1-128 primitive 生成与六种 Debug View；TechLab 中两条 64-primitive 磁拱可交叉并受实体墙深度遮挡。

### 2026-07-12 15:51 — [发现] 共享 Field Probe 已通过 PIE 实测

新增轻量 Probe Actor 通过 `SampleDensityAtWorldPosition` 查询同一 Gaussian field 驱动 Point Light；PIE 中光强随查询位置约从 95.6 变为 83.8，证明消费者未复制独立 Spline。该实现是 Spec 允许的 renderer 外消费者降级，未引入 Niagara Data Interface。

### 2026-07-12 15:51 — [决策] 后续只收集 G3/G4 证据，不提前优化

下一步固定 TechLab 机位，记录 1/32/64/128 primitive 的 GPU 主 pass、composite、CPU upload、buffer 大小与 candidate 数据，并补齐 Ribbon A/B。只有固定 profile 超出 64 primitives / 1080p / <=2 ms 初始预算，才评估 half-res 或 candidate 加速。


### 2026-07-12 15:55 — [决策] 画面验证改为用户文字回传，避免多模态 token 成本

后续需要视觉或编辑器运行结论时，助手只提供可观察的验证清单（机位、开关、预期画面和需抄录的数值），由用户在 UE 中执行并文字反馈。除非用户明确要求，不自行截图、读图或通过桌面自动化采集画面；代码、编译和日志验证仍由助手执行。

### 2026-07-12 16:50 — [发现] 场景遮挡根因是深度视口选错矩形（已修）

15:51 记的"实体墙深度遮挡验证通过"是误判：当 screen percentage=100% 时恰好不暴露。真实 bug 是 SVE 在 post-Tonemap hook 里用 `FSceneView::UnscaledViewRect`（输出/上采样后分辨率）去映射 SceneDepth，而 SceneDepth 停在 primary（screen-percentage 缩放后）分辨率。比例错误在屏幕中心≈0、越靠边角越大，高斯推到角落时采到别处物体的深度 → 假遮挡。修复：改用 `FViewInfo::ViewRect`（需 include Renderer/Private 的 `SceneRendering.h`，`bIsViewInfo` 守卫后 static_cast）。判据：不同 `r.ScreenPercentage` 下遮挡边界都正确且一致。

### 2026-07-12 16:50 — [发现] 单 Actor 内高斯顺序需逐 ray t_star 排序（已修）

原实现按"高斯中心到相机距离"在 CPU 排一个全屏共用的全局序（`SortedIndices`），对交叉各向异性弧错误：沿某条 ray 的真实近远序由各自的 `t_star`（该 ray 上密度峰值位置）决定，逐像素不同。修复：shader 改为 gather 候选 → 按 `t_star` 插入排序 → 再 front-to-back 合成（VoGE 式 Top-K，`MAX_GAUSSIAN_HITS=64`）。CPU 中心序对正确性不再起作用。仍是离散近似（交叉重叠体积非严格积分），作品集尺度足够。

### 2026-07-12 16:50 — [发现] 跨 Actor 遮挡在当前架构下不可能正确（待决）

每个 `UGaussianVolumeComponent` 在 `OnRegister` 各自 `NewExtension` 一个 SVE，即每个 Actor 是一个独立全屏后处理 pass、只知道自己的 primitive。多 Actor 时后处理链串行执行，靠后的 pass 把"含前一个 Actor 的整幅画面"当作不透明背景合成，于是**注册靠后的 Actor 无条件渲染在前**，与近远/交叉无关（表现为"永远一个在上面"）。15:51 记的"两条磁拱交叉受遮挡验证通过"同为误判（两 pass 叠加观感）。选项：路线1 两条弧合并进单 Actor/单 field（符合 SPEC 非目标，零架构改动）；路线2 改 SVE 为 World Subsystem 单例聚合所有 Component（违反 SPEC "不做多 Actor manager"）。注意 `RebuildFromSpline` 用 `Out.Reset` 会清空数组，单 Actor 暂无法叠两条 spline 弧。

### 2026-07-12 16:50 — [修复] ProbeActor 灯改 Movable，消除 GPU Scene Lights stale ensure

ProbeActor 每帧 `SetActorLocation` + `SetIntensity`，但 Point Light 默认非 Movable，被 GPUScene 缓存后断言"每帧不变" → 触发 `GPU Scene Lights is stale` ensure（非致命，不 crash、不影响画面）。构造函数加 `SetMobility(EComponentMobility::Movable)`。已放置的旧实例需重放或手动改 Mobility。

### 2026-07-12 17:01 — [发现] 单 Actor 内 t_star 排序验证通过；[决策] 跨弧走路线1

用户实测：单 Actor 内手填 primitive 的近远遮挡正常 → 逐 ray `t_star` 排序修复确认有效。跨 Actor "ActorA 稳定盖 ActorB" 复现，确认为每 Actor 独立 SVE pass 所致。决策走路线1（符合 SPEC，不建多 Actor manager）：改 `AGaussianVolumeActor::RebuildFromSpline` 为遍历该 Actor 上所有 `USplineComponent`，各自 `AppendArcFromSpline` 追加进同一 `Gaussians` 数组（一个 SVE、一个 pass，跨弧遮挡由 shader t_star 排序自然正确）。每条 spline 各 `PrimitiveCount` 个、RNG 按 arc index 偏移。用户在编辑器给 Actor 再加一条 Spline 摆成交叉、点 Rebuild 即可。

### 2026-07-12 17:15 — [决策] 改走路线2：共享 World Subsystem 渲染器（覆盖路线1）

路线1 强制两条弧共用 Actor 级参数（Thickness/Density/Color/Emission），不满足 per-arc 需求；且发现编辑器删 Actor 不触发 `EndPlay`，SVE 未清理导致已删 Actor 的 Gaussian 残留渲染。决策改用路线2并更新 SPEC 非目标：

- 新增 `UGaussianVolumeWorldSubsystem`（每 world 一个），持有唯一共享 SVE。
- `UGaussianVolumeComponent` 不再各自 `NewExtension`，改为在 `OnRegister` 向 subsystem 登记、`OnUnregister`/`EndPlay` 注销；`PushGaussianDataToRenderThread` 把自己打包好的 primitive 交给 subsystem，subsystem 按 `TMap<WeakPtr,Packed>` 合并成单一 buffer、单一 pass。
- 效果：一条弧一个 Actor、各自独立参数与拖动编辑，跨 Actor 遮挡由合并 buffer + shader t_star 排序统一解决；per-arc 外观（albedo/sigma_t/emission/transform）随 primitive 进入合并集，仅光照为 pass 级全局（last-writer-wins）。
- 顺带修复删 Actor 残留：注销即从合并集移除并重建 buffer；WeakPtr key 令未显式注销的死 Component 自动剔除。
- 保留路线1 的多 spline append（正交、无害）：单个 Actor 仍可用多条 spline 生成自己的 field。

### 2026-07-12 19:07 — [决策] G3 不搭 Niagara Ribbon 对照场景，改口头说明

作品集取舍：不再实现"同一 spline 路径的 Niagara Ribbon 并排对比"这一交付物，对比差异在讲解时口头说明。影响：G3"观众无需看代码即可辨认差异"的验收全部依赖 Gaussian 自身画面（侧绕厚度、内部观察、逆光透射、交叉遮挡），这几个镜头的说服力权重上升。BACKLOG 的"对比基准 vs Niagara Ribbon"降级为口头项；G4 profiling 仍保留 Gaussian 自身的 GPU 成本矩阵，只去掉 Ribbon 一列。

### 2026-07-12 19:15 — [实现] 合成迁到 HDR/bloom 前，解决交叉处死白（SPEC §13 Q5）

现象：两条互补色（青+品红）发光弧交叉处糊成硬边死白 = 通道相加爆 + 合成在 post-Tonemap 被硬 clamp。将 SVE hook 从 `EPostProcessingPass::Tonemap`（BL_SceneColorAfterTonemapping）改为 `MotionBlur`（BL_SceneColorBeforeBloom）：此点 SceneColor 为 post-TSR output 分辨率的 HDR scene-linear，`AddAfterPassForSceneColorSlice(EPass::MotionBlur)` 无条件触发（不受 motion blur 开关影响）。合成逻辑与深度映射（`FViewInfo::ViewRect`，深度仍 primary）不变。效果：交叉处 overshoot 走 tonemapper 滚降 + bloom → 明亮带色柔和高光，非硬白。副作用：emission/lightcolor 现在经过 exposure+tonemap，数值需重新调（原为 post-tonemap 显示域调的，迁移后偏亮/偏色）；六种 Debug View 输出也会被 tonemap 轻微改观感。兑现了 SPEC Q5 "正式成片前迁移到 HDR/tonemap 前合成"。

### 2026-07-12 19:45 — [发现] self-shadow 对光方向几乎无响应；[实现] §10 跨 primitive 光照

用户实测：调光照几乎看不出变化。根因（可证明）：旧 `LightGaussianTau` 只从 primitive 自身中心沿光方向穿过自己积分，对各向同性高斯 `≈ sigma_t·scale·√(π/2)`，与光方向无关；且发光项常压过光照。故光方向不可见、交叉处无前后阴影——即 SPEC §10 缺陷。实现 §10：新增 `FGaussianVolumeLightTauCS` 前置 compute pass，每 primitive 沿光方向穿过**所有** primitive 累计 optical depth → 存 `exp(-tau)` 到 `LightTauBuffer`（O(N²) 计算、O(N) 存储）；主 CS 改为 `LightTransmittance[gaussianIndex]` 的 O(1) 查表。N≤256 每帧跑可忽略，省失效判断。效果：一条弧能给另一条投阴影、朝光侧亮/背光侧暗、光方向可见。待重编重启验证。

### 2026-07-12 20:00 — [决策] G3 渲染技术前提收尾，转入 G4 profiling

G3 所需的四项渲染正确性工作（跨 Actor 共享渲染器、HDR 前合成、§10 跨 primitive 光照、共享 field 消费者 ProbeActor）均已实现，前三项中场景遮挡/单 Actor 排序/跨 Actor 遮挡已用户实测确认，HDR 合成与 §10 待下一次重编重启统一验证。按 SPEC gate 顺序，下一步是 **G4：固定机位性能基准**（1080p，1/32/64/128 primitive，测 LightTau prepass / 主 pass / composite / upload ms，对照 64 primitives/≤2ms 初始预算），只有超预算才决定 half-res / PBF / tile 等优化优先级，不提前优化。G3 的 7 个展示画面（正面/侧绕/内部/逆光/交叉/遮挡/Debug 分解）录制可与 G4 并行推进。
### 2026-07-12 20:23 — [实现] G4 稳定性与 64-hit 截断修复

128 primitive TechLab 的 PIE 压测发现 ProbeActor 每帧更新 Movable PointLight 会触发 UE 5.8 `GPU Scene Lights is stale` ensure。Probe 已收缩为 BeginPlay 单次解析密度采样并驱动灯光：保留共享 field 第二消费者证据，同时移除对 profiling 的逐帧 GPUScene 干扰。重编译后 128 primitive PIE 连续运行无 ensure、fatal 或 shader error。

主 pass 仍使用 64-hit 有界 per-ray 工作集，但满载策略已从“保留遍历先遇到的 64 个”改为“始终保留 `t_star` 最近的 64 个”。这消除了跨 Actor 合并后结果依赖 CPU traversal order 的错误，不扩大数组和寄存器压力；超过 64 个显著近场命中的极端像素仍作为已知上限。FGaussianVolumeRayTraceCS 已在 UE 5.8 重编译并通过 128 primitive PIE smoke test。
### 2026-07-12 20:30 — [决策] 当前落地状态与低风险性能收口

GaussianVolume 已达到作品集原型可落地状态：UE 5.8 编译、TechLab 加载、128 primitive PIE smoke test 均通过；G3 渲染技术前提收尾。Ribbon 并排场景正式取消，差异通过三维厚度、内部观察、逆光透射、交叉遮挡和口头说明表达。

在正式 G4 性能取证前先完成两项静态可证明优化：删除主 pass 前重复的全屏 SceneColor copy；删除已不参与正确性、且 shader 会按 ray 重新排序的 CPU 中心深度排序。未提前引入 persistent buffer、half-res、tile candidate 或 LightTau cache：它们分别涉及跨帧 RHI 生命周期、画质/时域策略、候选架构和缓存失效条件，留给最终 profile 决定。

### 2026-07-21 17:45 — [落地] 论文 Smoke 资产导入 UE；[发现] 835 规模主 pass 明显超预算

以 Meta `volumetric_primitives` 官方预拟合 `resources/smoke.ply` 为可信论文资产，新增二进制 PLY → `GaussianVolume.Primitives.v1` JSON 转换器，并给 `AGaussianVolumeActor` 增加 JSON 导入与关卡重载时自动恢复。TechLab 中 `Paper Smoke 835` 已持久化并在重启后独立读回确认：835 primitives、debug default=false、rendering=true；插件通过 Editor/Development、Game/Development、Game/Shipping 构建。

固定 1920×1080 GPU profile（TechLab 合计 963 primitives）：GPU frame 30.66 ms，`GaussianVolume LightTau Prepass` 0.22 ms，`GaussianVolume RayTrace CS` 23.31 ms。瓶颈不是 O(N²) LightTau，而是主 pass 每像素遍历全部 primitive；half-res 理论上单独只能将 23.31 ms 降到约 5.8 ms，仍高于 2 ms 目标。下一步优先做 PBF/tile candidate reduction，再结合 half-res/temporal；不把当前 835 规模实现宣称为实时。

官方拟合脚本在现行 Mitsuba 3.9/3.7.1 可运行但所有优化变量梯度为零，因此未把 no-op 拟合冒充成功。本轮使用官方预拟合 PLY 完成渲染落地，旧 Mitsuba 分支复现作为独立上游兼容问题保留。

### 2026-07-21 20:08 — [落地] OpenVDB `smoke2` 原生转换与 2K/4K TechLab；[发现] 视觉规模可用但实时路径必须先做 candidate reduction

接入 UE 5.8 自带 OpenVDB 13，仅在 Editor target 启用读取、RTTI 和异常；Game/Shipping 不链接 OpenVDB，只消费已生成的 `GaussianVolume.Primitives.v1` JSON。`AGaussianVolumeActor` 新增一次性 VDB 转换入口：自动选择 `density` FloatGrid、读取 active voxel 与 grid transform、按索引空间占用网格聚合并以密度加权中心保留覆盖，避免 Top-K 只留下高密度核心。聚合单元密度按自身峰值归一化，使 `OpenVdbPeakSigmaT` 与实际输出峰值一致。组件渲染开关同时修正为动态注册/注销，可可靠做 2K/4K A/B。

官方 OpenVDB `smoke2.vdb`（2,826,407 个有效 density voxels）生成两档：2K 目标得到 1,983 primitives（cell=15），4K 目标得到 3,510 primitives（cell=12）；整数网格尺寸导致数量不精确命中目标。两档最长轴覆盖约 982–983 cm，峰值 `sigma_t=0.04`，JSON 有限值/计数自检通过。TechLab 保留 `Smoke2 VDB 2K Diagnostic`（默认关闭）与 `Smoke2 VDB 4K Hero`（默认开启），旧 64/64/835 组默认关闭，关卡已保存。

固定 1920×1080 profile：2K 档 GPU frame 55.72 ms、LightTau 0.38 ms、主射线 48.35 ms；4K 档 GPU frame 93.56 ms、LightTau 0.70 ms、主射线 85.89 ms。结论进一步强化：瓶颈是全屏逐 primitive traversal，LightTau 不是当前矛盾；4K 是 Hero 画质诊断而非实时档。插件独立 `BuildPlugin` 已通过 UnrealEditor Development、UnrealGame Development、UnrealGame Shipping。下一步只做 PBF/tile candidate reduction，之后再评估 half-res/temporal。

### 2026-07-21 20:40 — [落地] 32×32 tile candidate 与 10K/30K 自适应 VDB；[发现] 全局 primitive 数已不再线性控制主 pass

主渲染改为 GPU per-frame 保守投影：每个 Gaussian 的 3σ sphere 写入覆盖的 32×32 screen tile，主 CS 只遍历当前 tile 的候选并继续按每 ray `t_star` 保留最近 64 hits。固定表每 tile 上限 1,024，构建成本 1080p 为 0.43 ms；这是本轮最小 PBF-style association，未提前实现 CSR count/prefix/scatter。高于 4,096 primitives 时关闭 O(N²) `LightTauCS`，以 1.0 光透射降级；若高细节档的跨体积阴影成为画质瓶颈，再做 light-space candidate，而不是让诊断档被 N² 拖垮。

VDB 转换改为一层自适应细分：先建立 coarse/fine 两级占用网格，用父块密度范围与中心差分梯度评分，只拆高分父块直到目标数量。`smoke2` 精确生成 10,000（base=16/fine=8，split=1,498）与 30,000（base=10/fine=5，split=4,010）两档；JSON 计数、有限值、空间覆盖、峰值 `sigma_t=0.04` 与双尺度分配自检通过。TechLab 批次 tag 为 `GAUSSIAN_VDB_ADAPTIVE_BATCH_20260721`，默认只开启 `Smoke2 VDB 30K Adaptive Hero`，10K 与 4K 留作同位置 A/B。

固定 1920×1080 profile：10K 为 GPU frame 30.18 ms、tile build 0.43 ms、主射线 22.52 ms；30K 为 30.32 ms、0.43 ms、22.57 ms。相较旧 3.5K 全量遍历的主射线 85.89 ms，30K primitive 增加约 8.5 倍但主 pass 降约 74%；10K/30K 成本相同，表明当前成本由局部重叠与 64-hit 排序主导，不再由全局 primitive 数线性决定。视觉细节是否足够仍需用户在 live viewport 做 4K/10K/30K 审美 A/B；结构和性能不能替代该结论。独立 BuildPlugin 再次通过 Editor Development、Game Development、Game Shipping。

### 2026-07-21 20:55 — [发现] Editor 200 ms 来自 30K Details 展开；[决策] 主 Pass 优化转向每像素固定工作量

30K Actor 的 `Gaussians` 是 `EditAnywhere TArray<FGaussianVolumePrimitive>`；选中时 Details/Slate 为 30,000 个结构体生成属性树，Editor `Game` 飙到约 200 ms，进程工作集约 23.8 GB。取消选中后工作集回落到 4.49 GB，且组件只在 transform 变化时重传数据，故该问题与 Gaussian GPU Pass 分离。后续隐藏数组但保留序列化，Details 仅暴露摘要。

GPU 侧 10K/30K 均约 22.5 ms，说明 PBF-style tile 已解决全局 N 扩展，却留下每像素最多 1,024 candidates、64-hit 插入排序和 post-TSR 输出分辨率的固定地板。下一批先做无损低风险优化：球体/深度剔除前置，CPU 预计算 inverse covariance/bound radius；同机位复测后才决定 16×16 tile 与 half-res/TSR，不用盲目降低 candidate cap 换假性能。

### 2026-07-21 21:07 — [落地] inverse covariance CPU 预计算将 30K 主 Pass 降至 8.5 ms；[否决] 16×16 tile

GPU packing 保持每 primitive 4×float4，但把 `scale+quat` 改为 CPU 预计算的对称 inverse covariance 六分量 + 3σ radius；shader 删除每候选四元数矩阵、平方倒数和未使用 self-shadow helper，并在解析积分中直接乘 packed covariance。随机 1,000 组 scale/quaternion 与旧公式等价，worst error `5.684e-14`；BuildPlugin 的 Editor Development、Game Development、Game Shipping 全通过。

固定 1920×1080/30K profile 两次为：tile build 0.42/0.43 ms，主 Pass 8.55/8.49 ms；相对 22.57 ms 基线下降约 62%，整帧由约 30.3 ms 降至约 16.2 ms。16×16 tile A/B 的主 Pass 仅到 8.45 ms，但 build 升至 1.67 ms，净变慢约 1.2 ms且索引内存增加，故恢复 32×32。下一瓶颈是 post-TSR 全分辨率与逐像素 64-hit 排序，不再继续细化 tile。

### 2026-07-21 21:35 — [落地] 运行时密度标定曲线

`UGaussianVolumeComponent` 增加 `DensityMultiplier` 与 `DensityGamma`，在既有 CPU packing 入口按组件最大 `sigma_t` 归一化后调 Gamma，再统一缩放 extinction；默认 `1/1` 保持旧结果，渲染与 `SampleDensityAtWorldPosition` 共用同一曲线，无需改 JSON 或 shader。Editor Development 编译通过，`GaussianVolume.DensityCurve` 自动化测试通过。TechLab 30K Hero 暂设 `3.0/0.65` 并保持关卡 Dirty，等待用户 live viewport 确认；未将密度调节误当成高数量自阴影缺失的修复。

### 2026-07-22 — [发现] 方格来自 tile candidate 静默溢出；[否决] 继续扩大固定容量

用户在 30K Hero、密度 `3.0/0.65` 下观察到与屏幕 tile 对齐的方格，换视角后仍出现。代码复核确认：构建 pass 先对 `TileCandidateCounts` 原子加一，但只在 `slot < MaxTileCandidates` 时写索引；主 pass 又把 raw count 截到容量，因此溢出项静默丢弃。相邻 tile 的原子到达顺序不同，会保留不同 Gaussian 子集；提高密度不会增加候选数，但会把原本不明显的遗漏放大为可见边界。现有 CandidateCount debug 只统计截断后的逐 ray sphere hits，不能直接显示 raw overflow。

将 `MaxTileCandidates` 从 1,024 临时提高到 2,048 并通过 `LiveCoding.CompileSync` 生效。用户 A/B 结果：换角度仍能看到方格，同时 Draw 与 GPU Time 升至几十毫秒。原因是每个相关像素现在最多扫描 2,048 candidates，并继续做 sphere test、Gaussian 数学与最多 64-hit 插入排序；索引表也翻倍。`stat unit` 的 Draw 是 render-thread 时间而非 draw-call 数，GPU 饱和时 RHI/present 回压会令 Draw 与 GPU 一同上升。`r.VSync=0`、`r.VSyncEditor=0`、`t.MaxFPS=0`，排除显式帧率上限。

决策：2,048 是失败的诊断 A/B，不作为稳定配置。下一批按最小路线执行：恢复 1,024；让现有 CandidateCount debug 在 raw count 超容量时直接标红；针对 30K LightTau 已关闭、albedo/emission 一致的均质烟雾，用顺序无关的 optical-depth 累积移除 64-hit 插入排序；仍有 overflow 再只细分过载 32×32 tile；最后才做 half-res/temporal。完整 CSR 或 BVH 暂不进入本轮。

### 2026-07-22 — [实现] 1,024 + raw overflow 诊断 + 均质 optical-depth 快路径

源码把 `MaxTileCandidates` 恢复为 1,024。未增加新 Debug enum：复用 CandidateCount，在 raw `TileCandidateCounts[tile]` 超容量时直接输出纯红整 tile，未溢出区域继续显示原 candidate-count 颜色。这样一次 live viewport A/B 即可区分“固定 tile 溢出”与 Gaussian/VDB 自身结构。

高数量路径新增自动 uniform 检测：GPU packed 数据中每个 primitive 的 `albedo.rgb + emission` 在容差内完全一致，且数量高于 4,096（此时 LightTau 本来就降级为 1）才走均质快路径。它仍遍历 tile candidates 并做解析 tau，把所有有效 tau 累加后一次计算 `T=exp(-sumTau)` 与散射；powder 用总 tau 近似。异质外观与低数量场景继续走原逐 ray 排序，避免改变交叉弧的遮挡语义。GPU event 标为 `GaussianVolume RayTrace CS Uniform`，便于后续 profile 确认实际选择。

新增 `GaussianVolume.UniformAppearance` 小型自动化测试，覆盖一致外观命中与不同 albedo 回退。初版把快路径做成独立 shader permutation 1；C++ Live Coding 虽成功，却不会为运行中的 GlobalShaderMap 补齐新 permutation，首次调度即触发 `Failed to find permutation 1 of shader type FGaussianVolumeRayTraceCS` 断言。修复采用最小安全基线：删除静态 permutation，在原 permutation 0 内用 `bUseUniformFastPath` 动态分支跳过插入排序；因此当前仍声明 64-hit 数组，只先验证排序 ALU 的收益。动态版本已经以 `AbyssEditor Win64 Development -NoHotReloadFromIDE` 冷编译并成功链接。Restore Packages 后确认当前关卡为 TechLab，组件保持 `3.0/0.65/Final/enabled`，新进程日志无 permutation、assert 或 shader compile error。`GaussianVolume.UniformAppearance` 在独立 `AbyssEditor-Cmd -NullRHI` 和主 Editor 中均为 Success。主 Editor 因当前布局/焦点持续只有 3 FPS，ProfileGPU 仍只捕获 Slate 1.15 ms，不作为 Gaussian 性能证据；未截图、未保存正式关卡。下一步必须先让 Level Viewport 成为可见活动标签，再做 CandidateCount overflow 观察和固定机位 GPU profile。

恢复验证完成后，组件临时切到 `CandidateCount` 并读回成功，密度仍为 `3.0/0.65`、渲染开启；当前 Dirty 未保存。用户需要在 Level Viewport 观察：整 tile 纯红代表 raw candidates 超过 1,024，非红区域保留原 candidate-count 色带。观察后恢复 `Final`，再决定是否只细分 overflow tile。

### 2026-07-22 — [发现] 全屏 overflow 来自近相机包围球 fallback

用户确认旧 CandidateCount 向右转时红色减少，向左转时增加直到全屏。代码追踪定位到 `BuildTileCandidatesCS`：只要 `depth <= radius`，3σ 包围球就跳过投影并覆盖全屏；当视角使大量 Gaussian 的 forward depth 变小时，会产生与真实屏幕覆盖无关的全屏 candidates。局部 16×16 无法降低这种候选，因此未直接实现第二套 tile 表。

根因修复复用已有 `WorldToClip + CameraDirs`，按水平/垂直 2D 球切线角计算保守 NDC bounds；仅相机确实位于对应投影圆内时覆盖整轴。CandidateCount overflow 同时改为黄≈1×、红≈2×、紫≈4×以上。两次 `recompileshaders changed` 完成，第二次无 warning/error；组件保持 `3.0/0.65/CandidateCount/enabled`、Dirty 未保存，等待用户在同一左右视角复测。

### 2026-07-22 — [落地] 30K/10K/4K 运行时屏幕尺寸 LOD

切线角投影修复后，用户确认转视角时热力图稳定为黄色，但相机拉远会从黄变红/紫。该现象来自固定 30K 体积在远距收缩到更少 screen tiles 后的真实 candidate 集中，而非方向相关的假全屏投影。采用最小落地方案：Hero 继续持有 30K；现有禁用 10K/4K 组件只作为序列化数组来源，三档统一使用 Hero transform、`DensityMultiplier=3` 与 `DensityGamma=0.65` 重新 packing。

LOD 以高档包围球的水平 NDC 半径选择，阈值为 High `0.35`、Medium `0.12`，相对滞回 `15%`；选择发生在 render thread 创建 StructuredBuffer 前，因此每帧仍只上传一档、构建一套 tile candidates、执行一个主 pass。未增加随机抽样、第二套 tile 表、CSR 或新 draw。当前单一共享 renderer 使用一个 LOD 状态；若未来同时显示多个独立 LOD 体积，再升级为 per-component 描述符与选择。

新增 `GaussianVolume.ScreenSizeLod` 自动测试，覆盖三档初选和双阈值滞回；NullRHI 结果 Success。Editor/Game/Shipping 独立 BuildPlugin 与 `AbyssEditor Win64 Development -NoHotReloadFromIDE` 冷编译通过。TechLab Hero 已接入 30K/10K/4K，保持 `CandidateCount/enabled`；远处 4K、近处 30K、恢复机位约 10K 的三档冒烟均无 permutation、assert、fatal 或 shader error。相机已恢复，关卡 Dirty 未保存；画质与热力图仍由用户 live viewport 确认。

用户复测确认 GPU 已基本无负载且 LOD 不来回闪烁，但旧 CandidateCount 用整 tile 纯色替换画面，无法知道紫色是否覆盖真实云。诊断输出改为在正常最终合成上半透明叠加负载色：当前 ray 没有命中候选时保留场景，命中后按实际体积不透明度增强叠加。该改动不增加 candidate 遍历；两次 `recompileshaders changed` 完成，第二次无 shader error/warning。后续只在紫色与可见云重合且 Final 模式出现方格/缺失时处理局部 overflow；云外保守 3σ candidate 溢出且 GPU 低负载不作为优化理由。

### 2026-07-22 — [发现][修复] 可编辑同类组件引用导致 Details 栈溢出

选中 `Smoke2 VDB 30K Adaptive Hero` 时编辑器立即崩溃。CrashContext 明确为 `Unhandled Exception: EXCEPTION_STACK_OVERFLOW`；调用栈反复循环于 PropertyEditor 的 `GenerateChildrenForPropertyNode`、`OnGenerateChildren` 与 `GenerateLayout`，崩溃时进程只占约 4.6 GB、系统仍有约 17.6 GB 可用，排除 30K 数据、GPU 与 OOM。

根因是 LOD 把 `MediumLodSource`/`LowLodSource` 暴露成 `EditInstanceOnly TObjectPtr<UGaussianVolumeComponent>`。`UActorComponent` 带 `DefaultToInstanced`，因此 Details 会把这种属性当作内联实例对象继续生成同类属性树；当前跨组件引用图由此递归到线程栈耗尽。工程规则：跨 Actor 选择组件数据源时，不直接暴露 `DefaultToInstanced` 组件指针；优先暴露普通 Actor Picker，再在运行时取得其组件，需要通用组件寻址时才使用 `FComponentReference`。

最小修复把两个来源改为 `TObjectPtr<AGaussianVolumeActor>`，packing 仍读取来源 Actor 的 `GaussianVolumeComponent->Gaussians`，不改 LOD、GPU 数据布局或渲染算法。新增 `GaussianVolume.LodSourceProperty` 反射测试，锁定两项属性必须指向 Actor 且不能带 `CPF_InstancedReference`。`AbyssEditor` 冷编译与测试通过；TechLab 重新接入 Hero→10K/4K、切回 `Final` 后实际选中 Hero 并保持 8 秒以上，编辑器响应正常、工作集约 4.1 GB、日志无 stack overflow/fatal，选中对象读回为 `GaussianVolumeActor_6`。关卡保持 Dirty，未保存正式关卡。

### 2026-07-22 — [决策][落地] 用当前 LOD 全量容量建立无截断基线

用户在 Final 画面确认仍有严重的 32×32 方格后，调整验证顺序：不再从 1,024 缓慢上调猜平衡点，而是先取消 candidate 截断，确认 renderer 在完整候选集下的正确画质，再向下回退找容量边界。新增 `r.GaussianVolume.MaxTileCandidates`；值为 `0` 时容量解析为当前活动 LOD 的 `NumGaussians`（High=30K、Medium=10K、Low=4K），正数则取 `min(requested, NumGaussians)`。因此 exact 模式下每个 Gaussian 对一个 tile 最多写入一次，raw count 不可能超过容量；它是 correctness reference，不是生产性能方案。

`AbyssEditor Win64 Development -NoHotReloadFromIDE` 冷编译通过，`GaussianVolume.ScreenSizeLod` 自动化测试新增 exact/capped/clamped 三项并为 Success。TechLab 新进程已恢复 Hero→10K/4K、`Final`、密度 `3.0/0.65` 与原相机，CVar 读回为 `0`；编辑器持续响应，日志无 shader permutation、assert、GPU crash 或 fatal。关卡保持 Dirty，未保存。下一步只在用户确认 exact 画面无方格、断层或轮廓缺失后，按 8,192→4,096→2,048→1,024 回退；首个失败容量再进入局部 overflow tile 细分，不提前实现第二套表。

### 2026-07-22 — [发现][决策] exact 方格消失；容量 A/B 固定 High 30K

用户确认 CVar=0 exact 下屏幕方格完全消失，因此 tile candidate 截断根因成立；同时拉近/拉远出现一次性闪变。现有 `SelectScreenSizeLod` 的 15% 滞回只阻止阈值附近反复切换，不能让不同的 30K/10K/4K 密度场连续过渡，故该现象归为硬切档 pop，而非 overflow 或 TSR 闪烁。

为保持容量回退只改变一个变量，未提前增加双档渲染或时域 cross-fade；直接复用 `bEnableScreenSizeLod` 将 Hero 固定为 High 30K，Medium/Low Actor 引用继续保留。随后通过编辑器控制台把 `r.GaussianVolume.MaxTileCandidates` 从 exact 调为 8,192，组件读回为 `Final`、`3.0/0.65`、LOD disabled，CVar 读回为 8,192；编辑器响应正常且日志无 shader/GPU/fatal。关卡 Dirty 未保存。用户确认 8,192 画质后再进入 4,096。

用户在 8,192 下拉到很远时再次观察到方格；截图显示方格与缩小后的云覆盖重合，判定该档失败。由于 8,192 相对 exact 30K 是一次过大的下降，未直接实现局部细分，改用反向二分将 CVar 调为 16,384；固定 High 30K、Final 与 `3.0/0.65` 均保持不变，读回和日志正常。下一步由用户复测同一远距离机位：16,384 通过则向 12,288 收窄，失败则向 24,576 收窄。

### 2026-07-22 — [落地] 屏幕尺寸 LOD 双档 cross-fade

超级远距离仍会把固定 30K 压进少量 tile，继续提高全屏固定 candidate 表不是合理扩展方式。恢复现有 30K/10K/4K LOD，并把有状态硬切选择替换为按屏幕半径计算的连续权重：High 阈值 `0.35`、Medium 阈值 `0.12`，原 `15%` hysteresis 作为 blend half-band；带外只渲染一档，带内分别渲染相邻两档的完整 HDR 合成结果，再用 `FGaussianVolumeLodBlendCS` 线性过渡。这样 10K/4K 始终低于当前 16,384 cap，远处不会因固定 30K 集中而截断；双倍主 Pass 只存在于两个短过渡带。

删除不再需要的单视图 `CurrentLod_RT` 状态，`GaussianVolume.ScreenSizeLod` 改为覆盖 High-only、High↔Medium 50%、Medium-only、Medium↔Low 50%、Low-only，并连同 candidate capacity 测试为 Success。`AbyssEditor` 冷编译通过；新 D3D12 编辑器已恢复用户超远机位、Hero→10K/4K、`Final`、`3.0/0.65`、LOD enabled 与 CVar=16,384，持续响应且日志无 Shader/permutation/assert/GPU/fatal。关卡 Dirty 未保存；结构正确不代替用户对连续拖动的审美确认。

### 2026-07-22 — [否决][归档][决策] Spline/Structured Gaussian Field FX 从主线移除

用户确认 Spline 驱动的体积能量带、极光和魔法烟流路线此前已经验证且不适合作为本项目落地方向；再次把它建议为下一步属于项目决策链丢失。该方向未证明相较 Niagara Ribbon、普通 raymarch 或 VDB 的可测量画质、性能或工作流优势，现作为失败分支归档。旧 Spec 与产品假设移至 `notes/archive/failed_spline_field_fx_spec.md` 和 `notes/archive/failed_spline_product_direction.md`；历史 LOG 保留事实，但不得据此恢复为当前任务。除非用户明确重开，后续 AI 不得继续建议 Spline/Structured Gaussian Field FX。

主线改为验证论文 volumetric primitives 的实时工程扩展：离线优化各向异性/有限支撑 kernel 拟合，运行时保留解析主射线并采用近似光传输，产品边界限定为 VDB 中远景代理、显存降级、编辑器预览和多体积并存，近景 Hero 保留原 VDB。当前 30K/1080p 主 Pass 约 8.5 ms 已证明运行时内核可行，但 block/adaptive 聚合画质不足；下一 Gate 是多视角 transmittance、轮廓与梯度约束的层级拟合。拟合质量通过前，不继续堆 primitive 数或扩展渲染器功能。

### 2026-07-22 — [发现] Gabor Fields 直接覆盖旧拟合与 LOD Gate

SIGGRAPH 2026《Gabor Fields》是《Don't Splat Your Gaussians》的直接后续：Gaussian 低频基底 + Gabor 高频残差、分层回归、频率/方向裁剪和单资产连续 LOD，正面解决当前 30K 仍模糊及多档 cross-fade 问题。官方 MIT 代码含 Windows 安装、VDB 转换、训练与 Gaussian baseline；论文同时承认优化 voxel grid 更快、拟合需 0.1–2h、存在负密度/halo 与 traversal 瓶颈。

### 2026-07-22 — [回滚][决策] 暂停纯 Gaussian 层级拟合，转为 Gabor × UE 实时验证

原多视角纯 Gaussian 层级拟合、Epanechnikov A/B 与三套资产连续 LOD 不再作为研究主线；现有 30K/10K/4K renderer 保留为可运行保底和基线。下一 Gate 先复用官方训练资产，只在 UE 接入 Gaussian base + 一个 Gabor 频率层的 primary transmittance；通过等误差 GPU/画质验证后再做连续 LOD。可能的原创上探仅限 UE tile/candidate 成本感知拟合或调度，当前仍是工作假设。

### 2026-07-22 — [回滚][审计] Gabor 自动升格不进入正式主线

全量作品集审计确认：上一条“转为 Gabor × UE”没有足够的本人拍板与 UE 实验，属于 AI 基于新论文发现自动改线。论文发现保留为相关工作线索，但 Gabor 只可作待核验基线/候选，不触发训练、数据扩展或引擎实现。当前只继续 `SPEC.md` 的表示质量与 matched-error Gate；唯一研究候选为多视角 transmittance＋silhouette 层级拟合目标，仍需本人明确确认后才能实施。

### 2026-07-22 — [修正] 产品声明与证据边界

30K 主 Pass 约 8.5 ms 只证明 UE 内核优化，不证明相较 VDB 的等误差优势；inverse covariance 的 `5.684e-14` 只证明该变换等价，不代表整条路径无损。高数量档关闭 `LightTauCS`，故“可重光照”未成立。30K/10K/4K cross-fade 已接线，但现有用户画面确认记录互相冲突，正式视觉与过渡带峰值验收保持未完成。固定 High 30K/8,192 远景失败；exact 只作 correctness reference。Spline/Structured Gaussian Field FX 的归档决定继续有效。

### 2026-07-23 — [落地][修复] Q2 高保真 Hero、紧凑候选池与可见性

Q2 10K 导出 9,944 primitives。此前 any-hit 解析积分直接计算 `C-B²/A`，在远相机和小尺度 primitive 上发生灾难性消减；稳定 evaluator 改为显式最近点与非负垂距后，8 个未见视角、512×512、64 spp 得到 full-T `48.60 dB`、foreground-T `36.93 dB`、τ `28.07 dB`、silhouette IoU `0.629`、negative-τ fraction `0`。bundled PTX any-hit 在重新生成前默认关闭。Q2 已超过 Q1 4K 的 `36.11/24.22 dB` full/foreground-T 下限，作为当前高保真上限。

TechLab 只保留 `Smoke2 GFields Q2 10K High Fidelity` 一个 Gaussian Actor；fixed 3σ、screen-size LOD disabled，固定相机为 `GaussianVolume Q2 Hero Camera`，位置 `(165,0,124)`、朝 `-X`、FOV 100、Player 0 自动激活。RTX 5060、D3D12、1920×1080、固定相机的 300 帧稳态结果为：GPU median/P95/P99=`9.34/9.87/9.97 ms`，frame median/P95=`9.83/10.92 ms`。该数据证明 60 FPS，但尚未隔离 Gaussian volume pass。

固定 per-tile candidate matrix 已替换为 GPU `count → prefix scan → scatter` 紧凑全局池；默认容量 `4,194,304 IDs`，索引池 `16 MiB`、元数据约 `32 KiB`。Q2 Hero 读取 9,944 gaussians，requested/granted=`471,937/471,937`、overflow=`0`。这只建立 candidate 子系统的分配收益，尚不能替代对同画质 SVT/NanoVDB 总 GPU working set 的测量。

用户确认默认云密度过淡后，UE 展示档保存为 `DensityMultiplier=20.0`；所有 Q2 PSNR 仍严格对应 `1.0` 原始拟合输出。Actor 关闭 Visible 后仍显示的根因是共享 SceneViewExtension 未读取 Actor/根组件可见性；组件现统一检查 runtime Hidden、editor Hidden 与根组件 Visible，并在状态变化时更新渲染注册。冷编译成功，既有 AdaptiveSupport、DensityCurve、LodSourceProperty、ScreenSizeLod、UniformAppearance 五项自动化测试通过，editor Hidden 与根组件 Visible 的 live toggle 均验证且最终恢复可见。

下一 Gate 保持不变：补 NanoVDB 同源基线，测量 SVT/NanoVDB/Gaussian 的 matched-quality 总 working set 与 pass breakdown，再做 opacity/error-aware support 相对 fixed-3σ 的 matched-error A/B。高数量路径仍关闭 O(N²) `LightTauCS`，不声明实时重光照。

### 2026-07-23 — [落地][取证] UE 5.8 GaussianVolume GPU stat

此前各计算 Pass 只有 `RDG_EVENT_NAME`，可进入 `ProfileGPU` 事件树，但没有可供 `stat gpu` 汇总的 GPU stat。UE 5.8 已将旧 `RDG_GPU_STAT_SCOPE` 废弃为空操作；根修复是在 Gaussian 渲染公共入口注册 `DECLARE_GPU_STAT_NAMED(GaussianVolume, ...)`，并用 `RDG_EVENT_SCOPE_STAT` 包住完整 Count→Prefix→Scatter→LightTau→RayTrace→可选 LOD Blend 链路。未新增自定义计时系统或重复逐 Pass stat。

独立 BuildPlugin 的 Editor/Game/Shipping 和项目 `AbyssEditor Win64 Development` 冷编译链接均成功。重启编辑器、加载 TechLab、执行 `stat gpu` 后，采集 `frame,cpu,gpu,log` Insights trace；`gaussian_volume_gpu_tag.utrace` 实际包含 `GaussianVolume` scope，证明新 DLL 与 GPU tag 已运行。验证时 Q3 外部训练占满同一 GPU，因此只签字 scope 可见性，不把当时数值作为性能证据；编辑器随后关闭，把 GPU 归还 Q3。

### 2026-07-23 — [落地][基线] 独立 SVT 对照关卡与总显存取证方法

Q3 24K GPU 训练继续运行时，并行完成不依赖训练输出的基线工作。UE NullRHI 命令行验证同源 SVT U8/F16 均为 `191×610×178`、1 帧、7 mip，frame transform scale=`0.1`；生成 `L_GaussianVolume_EmptyBaseline`、`L_GaussianVolume_SVT_U8`、`L_GaussianVolume_SVT_F16` 三个独立关卡。两个 SVT 关卡各只保留一个 Heterogeneous Volume，统一缩放 `16.393443`，得到 `(156.56, 500.0, 145.90) cm` extent，并与 Gaussian actor 的 padded-volume 中心 `(-390,0,300)` 对齐；空关卡不含 Gaussian/SVT actor。NullRHI 保存和边界断言通过。

总 GPU working set 不再依赖磁盘资产大小或单一子系统估算。每个方案将用独立冷进程加载同环境关卡，以 EmptyBaseline 作差；`rhi.DumpMemory` 记录实际总 RHI allocation，`rhi.DumpResourceMemory ... Transient=all` 做资源归因，SVT 同时使用引擎原生 `SparseVolumeTexture Memory` 的 page table、tile data 和 total GPU memory。GPU 仍由 Q3 占用，当前只完成可复现关卡与取证方法，不提前写入显存结论。

显存采集入口已固化为 `mvp/capture_memory_baselines.ps1`：各方案使用独立冷编辑器进程，统一 1920×1080、D3D12、离屏渲染，预热 300 帧后由 `capture_memory_probe.py` 输出带边界标记的 RHI/SVT 统计。脚本默认检测并拒绝与 VolPrim GPU 训练并发，避免把训练进程的显存压力带入对照。

### 2026-07-23 — [落地][基线] NanoVDB Fp8/FpN＋HDDA UE reference

直接复用 UE 5.8 源码树随附的 NanoVDB 32.9.0、OpenVDB、Boost、TBB、Blosc 与 zlib，编译官方 `nanovdb_convert`，没有引入新的第三方包。同源 `smoke2` 生成 Fp8 与 absolute-error=`0.001` 的 FpN；容器文件分别为 `7,048,392` / `4,821,128` bytes，UE 实际上传的 raw grid 分别为 `7,048,192` / `4,820,928` bytes。FpN 叶节点平均 `3.2 bits/value`。这些是资产/buffer 字节，不代替总 GPU working-set 结论。

GaussianVolume 插件增加独立 `NanoVDB Volume Baseline` Actor/component：运行时读取无压缩 `.nvdb`、只上传 raw grid，compute shader 使用官方 `PNanoVDB` HLSL accessor，支持 Float/Fp8/FpN，并以 HDDA 跳过稀疏空节点；Pass 注册为 `NanoVDBBaseline` GPU tag。生成并保存 `L_GaussianVolume_NanoVDB_Fp8`、`L_GaussianVolume_NanoVDB_FpN` 两个关卡，与 SVT/Gaussian 使用相同中心、1000 cm 最长轴和 `10/610` 初始 extinction scale。`AbyssEditor` 冷编译通过，NullRHI 实际解析两种 grid、保存关卡且 0 shader/脚本错误；快速切图暴露的 queued render-command teardown 生命周期问题已通过 subsystem deinitialize 前 `FlushRenderingCommands` 修复。D3D12 live 画面、transfer function 和性能仍等待 Q3 释放同一 GPU 后签字。

显存采集入口随之扩展为六个独立冷进程：Empty、Gaussian Q2、SVT U8/F16、NanoVDB Fp8/FpN。

### 2026-07-23 20:32 — [进度] Q3 训练与 UE 基线同步

Q3 使用 24,576 Gaussian、240 次 Gaussian optimization，明确关闭 Gabor 优化；同步时 PID 60916 健康运行，进度 `87/240`，尚未导出、评估或导入 UE。Empty、SVT U8/F16、NanoVDB Fp8/FpN 独立关卡及 NanoVDB HDDA/GPU tag 已完成 Editor/NullRHI 验证；D3D12 live 画面和六方案冷进程总显存取证仍待训练释放 GPU，因此尚无“同画质显存优于 SVT/NanoVDB”的结论。

### 2026-07-23 21:57 — [修复] UE 5.8 NanoVDB 全局 Shader 启动失败

`PNanoVDB.ush` 原样复制了 UE 随附的 C 头文件，其中 `PNANOVDB_GRID_TYPE_CAP=32`，但六个类型表与 constants table 只有 28 个显式初始化项；C/C++ 会隐式补零，UE 5.8 的 DXC/HLSL 拒绝该写法，导致 `FNanoVdbRayMarchCS` 全局 Shader 编译失败并阻止编辑器启动。插件副本现将 capacity 定义为当前实际表长 `PNANOVDB_GRID_TYPE_END + 1`，未改 NanoVDB ABI、数据布局或采样逻辑。启用 GaussianVolume 的 D3D12/SM6 冷启动已重新编译 `FNanoVdbRayMarchCS` 并完成引擎初始化，日志无 array、Shader compiler、assert 或 fatal 错误；此前“该问题不属于当前项目、临时禁用插件”的判断作废。

### 2026-07-24 — [否决][Gate] Q3 24K@120 不晋升

Q3 在原训练进程生成 120 checkpoint 后立即冻结为 `smoke2_q3_gaussian_24k_at120`；PLY SHA256=`30884AF46D11A8C6B4188A536C27F252A795B94BBB93BAFA14125434D4F5605D`。使用与 Q2 完全相同的 8 个 held-out Halton 视角、512×512、64 spp 与 reference cache 评估：Q3 full-T=`34.59 dB`、foreground-T=`22.42 dB`、τ=`5.65 dB`、τ MAE=`0.04547`、IoU=`0.686`；Q2 分别为 `48.60/36.93/28.07 dB`、τ MAE=`0.01022`、IoU=`0.629`。Q3 只有轮廓 IoU 提升 `0.057`，transmittance 与 optical depth 明显退化，质量 Gate 否决。

曾按预案从 checkpoint 继续 60 次以确认 180 是否值得等待，但恢复脚本重新进入学习率 warmup，实际 step 很快回到分钟级；结合 held-out 负结果，不再消耗数小时。训练进程已停止，Q2 保留为主线，Gabor 未启动。Q3 的临时 UE JSON 已删除，checkpoint 与评估结果仅保留为负实验。

### 2026-07-24 — [修正][取证] 显存采集必须进入真实 Play

首轮六关卡冷进程采集使用普通编辑器世界；虽然关卡资产加载成功，但没有稳定进入 Play，Gaussian candidate pass、NanoVDB ray march 与 SVT streaming 的 runtime 统计不能同时成立。该轮 Empty 差分数字作废，不进入结论。

`mvp/capture_memory_baselines.ps1` 已改为六个独立 `-game` D3D12 进程，统一 1920×1080、固定关卡与 warmup；外部读取 Windows `GPU Process Memory` 的 per-process dedicated/shared counters。插件新增只在明确 console command 下启用的延迟 memory dump，等 300 个 game tick 后记录 `rhi.DumpMemory`、带 transient 的命名资源汇总与 `stat dumpnonframe SparseVolumeTextureMemory`。进程总 dedicated memory 仍受 UE 大块 heap 与冷启动波动影响，必须以延迟资源归因和子系统原生统计解释，不能只看 Empty 差分。

### 2026-07-24 — [落地][内存子 Gate] 512K candidate 池

基于当前 Hero requested=`141,719` 与历史已观测峰值 `471,937`，默认 candidate pool 从 1M IDs 收到 `524,288 IDs`，索引分配从 `4 MiB` 降至 `2 MiB`；保留 `r.GaussianVolume.CandidatePoolCapacity` 可调入口与 GPU overflow readback。D3D12、1920×1080、固定 Q2 Hero 实测：9,944 gaussians、requested/granted=`141,719/141,719`、capacity=`524,288`、overflow=`0`。telemetry 现直接报告 candidate=`2,097,152`、primitive=`636,416`、auxiliary=`72,428 bytes`，逻辑缓冲总计 `2,805,996 bytes`（`2.676 MiB`）。`AbyssEditor` 冷编译成功，`GaussianVolume.ScreenSizeLod` 自动化测试 Success。

同一 fixed-Hero warm-frame 取证：

- Gaussian Q2：逻辑表示＋遍历缓冲 `2.676 MiB`；带共同输出纹理的 RHI `GaussianVolume` 命名资源共 `19.57 MiB`；
- NanoVDB FpN：raw grid `4,820,928 bytes`（`4.598 MiB`）；同一自定义 post-process 路径的 `NanoVDB` 命名资源共 `29.94 MiB`；
- UE SVT U8：引擎原生 runtime GPU memory `12.402 MiB`，其中 tile data=`12.312 MiB`、page table=`0.090 MiB`；源 frame streaming payload 另为 `2.976 MiB`，不拿它冒充 runtime GPU memory。

因此固定 Hero 的内存子 Gate 首次成立：Gaussian 逻辑缓冲相对 NanoVDB FpN raw grid 低 `41.8%`，相对 UE SVT U8 runtime GPU memory 低 `78.4%`；Gaussian 与 NanoVDB 的同路径命名 RHI 资源低 `34.6%`。但最终作品集 Gate 仍未通过：SVT/NanoVDB transfer function 与用户画面尚未匹配签字，512K 池也尚未完成连续相机 P50/P95/峰值 overflow 与 1/4/16 实例曲线。当前可以说“内存方向有已运行的证据”，不能说“同画质全面优于 VDB”。

### 2026-07-24 — [取证] 512K pool 性能无回退

沿用此前完全相同的 500-frame CSV capture，并取最后 300 个有效稳态 frame。当前 `epsilon_tau=1e-5` adaptive support＋512K pool 得到 GPU median/P95/P99=`7.35/7.51/7.59 ms`，frame median/P95/P99=`7.88/8.64/9.10 ms`。相同 DLL、关卡与相机，只通过 CVar 把 pool 改回 1M IDs，得到 GPU=`7.34/7.51/7.62 ms`、frame=`7.85/8.73/9.32 ms`；差异在运行噪声内，因此 4 MiB→2 MiB 缩容没有可测性能代价。

旧 4M-ID、fixed-3σ 基线的 GPU median=`9.34 ms`，当前组合低 `21.3%`；但这同时包含 opacity/error-aware support 将 Hero candidates 从历史 `471,937` 降到当前 `141,719` 的收益，不能归因给 pool 容量。fixed-3σ 与 adaptive support 的 matched-error 画质/GPU A/B 仍是下一项，当前只签字“512K 缩容不伤性能”。

### 2026-07-24 — [落地] tight PBF、空间公平 overflow 与 128K pool

tile coverage 从裁剪后椭球的 `max_scale` 球形投影改为保守 tight Particle Bounding Frustum。相同 Q2 视图关闭 tight PBF 时 requested candidates=`183,039`，开启后=`107,633`，减少 `41.2%`；该优化不增加第二份常驻 bounds 数据。默认 candidate pool 随后从 512K IDs 进一步收到 `131,072 IDs`（`0.5 MiB`），当前 requested/granted=`108,691/108,691`、overflow=`0`，保留约 `20.6%` 余量。

overflow 不再用线性写入导致后半屏 tile 被整体饿死。scan 阶段按各 tile requested count 分配比例配额，并在总容量内分配余数；强制 64K pool 时 requested/granted=`107,633/65,536`、max tile=`4,797`、truncated tiles=`167`、max dropped/tile=`1,877`，证明过载会空间公平降级。telemetry 扩展为 requested、granted、capacity、max tile、truncated tiles 与 max dropped/tile 六项。

### 2026-07-24 — [落地] 精确 32 B primitive 与 local-space 解析积分

常驻 GPU primitive 从 64 B 压到精确 32 B：position 保留 FP32；scale、extinction、support 与 emission 使用 FP16；rotation 使用 SNORM8 单位四元数；albedo 使用 UNORM8。shader 直接把 ray 旋转并缩放到 Gaussian local space，不为每个 candidate 重建 inverse covariance，也不保留 64 B 解包副本。Q2 primitive buffer 从 `636,416 B` 降到 `318,208 B`。

CPU packing 自动化测试覆盖结构大小、中心、half 字段、四元数方向与外观量化。D3D12 500 帧对照中，旧 64 B 版本 `GPU/GaussianVolume` median=`1.8834 ms`；32 B/local-space 版本=`1.5344 ms`，约快 `18.5%`，在减半字节的同时没有 decode 性能回退。

### 2026-07-24 — [落地] 原位 scene-color 合成把自定义 working set 压到 0.88 MiB

详细 RHI dump 定位到旧 Gaussian 命名资源中的主要浪费不是 candidate pool，而是两个跨帧保留的 `GaussianVolume.Output` 全屏纹理，各约 `8.4375 MiB`。主 Compute 每个 thread 只读写同一个 pixel、无跨像素依赖，因此默认 `r.GaussianVolume.InPlaceComposite=1` 直接把已有 scene color 绑定为 UAV，删除独立输出；`=0` 仍保留 copy 后计算的安全回退。D3D12/RDG 运行无 assert、resource hazard、shader error 或 GPU crash。

原位主线的命名资源只剩 candidate、primitive、LightTau、tile scan/count/range 与 telemetry，总计约 `0.88 MiB`；旧路径为 `17.76 MiB`。对照 UE SVT U8 原生 runtime GPU memory=`12.402 MiB` 和 NanoVDB FpN raw grid=`4.598 MiB`，当前自定义 Gaussian working set 分别约小 `14.1×` 与 `5.2×`。500 帧结果为完整 GPU median/P95=`6.9685/7.0853 ms`、`GPU/GaussianVolume` median/P95=`1.5357/1.5977 ms`，删除输出没有性能回退。该比值仍需用户完成相同 transfer function 的画面签字，才能成为 matched-quality 作品集 headline。

### 2026-07-24 — [实验][待人工画面签字] pool-free analytic raster

实现默认关闭的 `r.GaussianVolume.PoolFreeRaster` 最小分支：instanced tight ellipsoid proxy 在 pixel shader 中计算解析 optical depth，以统一 source radiance 的次序无关 premultiplied blend 直接写 scene color，因此不生成 count/scan/scatter 或 candidate pool。它只覆盖 extinction/统一介质，不声称解决异质单散射或完整体积光照。

该分支已在 D3D12 编译执行；原位模式下自定义资源理论上只剩约 `0.3125 MiB` primitive buffer，但测得 GPU tag 约 `0.06 ms`，低到可疑，不能在确认代理实际覆盖云之前视为成功。用户负责在 live viewport 中切换开关并肉眼判断；失败立即删除分支，不由助手恢复固定机位截图或自动微调。

### 2026-07-24 — [范围裁决] 用户接管画面与截图，助手只推进云本体

固定机位、自动截图 sweep 和截图微调从当前执行链路删除。用户在 UE live viewport 中移动相机、对齐 transfer function、判断画面并自行截图；助手只负责云表示、shader、显存、性能、telemetry、构建与离线数值正确性。Epanechnikov 与 Gabor residual 都保持条件项：只有当前 Gaussian-only 在用户签字后仍缺细节或预算时才启动，不能为了“把路线做全”而增加第二个研究赌注。

六个 Gaussian/SVT/NanoVDB 基线关卡中残留的 `GaussianVolume Q2 Hero Camera` 已全部删除，原创建脚本也一并移除；这些相机此前会自动激活 Player 0，现不会再抢占用户视角。云 Actor 和基线 Actor 均未改动。

### 2026-07-24 — [落地][边界] 1/4/16 平移实例共享

`UGaussianVolumeComponent` 新增 `AdditionalInstanceOffsets`。对 `>4K` 且 albedo/emission 统一的云，renderer 只保留一份 32 B primitive buffer；每个平移副本增加一个 32 B 的 offset/range。count/scatter 改为 instance×primitive 二维 dispatch，candidate ID 使用 20 bit primitive＋12 bit instance；超过 `<1,048,576` unique primitives 或 `<4,096` instances 会显式拒绝，不静默截断。该最小路径不承担旋转、缩放、异质外观或独立 Actor 自动去重。

D3D12 临时关卡实测：

- 1 份：unique/virtual=`9,944/9,944`，primitive=`318,208 B`，instance=`32 B`，逻辑 working set=`897,048 B`；
- 4 份：unique/virtual=`9,944/39,776`，primitive 仍为 `318,208 B`，instance=`128 B`，working set=`897,144 B`；
- 16 份：unique/virtual=`9,944/159,104`，primitive 仍为 `318,208 B`，instance=`512 B`，working set=`897,528 B`。

因此 16 份表示只比 1 份增加 `480 B`，没有线性复制 9,944 个 primitives。固定 128K candidate pool 不随实例扩容：4 份 requested/granted=`197,798/131,072`、overflow=`66,726`；16 份=`701,025/131,072`、overflow=`569,953`。这如实暴露同屏覆盖过高时的质量降级边界，不能宣称“16 份仍同画质”。临时 benchmark 关卡测试后已删除。

最终 `AbyssEditor` 冷构建成功，5 项 `GaussianVolume.*` 自动化测试通过；默认 TechLab D3D12 smoke 为 unique/instances/virtual=`9,944/1/9,944`、capacity=`131,072`、overflow=`0`，无 shader、RDG、GPU crash 或 fatal。

### 2026-07-24 — [修正][落地] RHI allocation 粒度审计与 uniform LightTau 删除

首次实例实现虽然逻辑上只有 `32 B/instance`，详细 RHI dump 却显示单独 `GaussianVolume.InstanceBuffer` 实际分配 `64 KiB`；若只报逻辑字节会夸大多实例优势。主线现改为：单实例通过常量参数提供 offset/range，并把已有同 stride Gaussian buffer 作未读取的兼容绑定，因此默认云不再创建 instance buffer；只有 `NumInstances>1` 才创建外置表，并把 D3D12 的 `64 KiB` 最小 allocation 计入真实 RHI working set。

同一审计还发现 Q2 uniform fast path 完全不读取 per-primitive LightTau，却仍分配 9,944 floats。该路径现只绑定并初始化 1 个 dummy float；异质或低数量路径保持原 LightTau 行为。1280×720 telemetry 的 auxiliary 从 `54,552 B` 降到 `14,748 B`，逻辑总计从 `897,048 B` 降到 `857,244 B`。按 1080p 的 2,040 tiles 计算，最终逻辑工作集为 `875,164 B`（`0.835 MiB`）。

最终 D3D12 resource dump 已确认：没有单实例 `InstanceBuffer`；GaussianBuffer=`0.3125 MiB`、candidate pool=`0.5 MiB`、LightTau=`16 B` allocation report、其余 tile/telemetry 按分辨率增长。1080p 命名资源约 `0.844 MiB`，相对旧 `17.76 MiB` 约降低 `21×`。1/4/16 最终逻辑曲线为 `857,244/857,372/857,756 B`；真实 RHI 曲线必须额外说明 4/16 共用同一个 `64 KiB` instance allocation，不能写成只增加数百字节。

### 2026-07-24 — [修复] 非 UAV SceneColor 自动回退

用户在编辑器打开 TechLab 时触发 RDG assertion：`PostDOFTranslucency.SceneColor` 没有 `TexCreate_UAV`，但原位路径仍无条件调用 `CreateUAV`。根因修复集中在共享 post-process callback：只有 CVar 请求开启且输入 texture flags 包含 UAV 时才原位合成；否则自动复用现有 copy-to-UAV-output 回退。无需用户关闭 CVar。

`AbyssEditor` 冷构建成功；D3D12 编辑器模式连续运行 481 帧，没有再次出现 `Attempted to create UAV`、assert 或 fatal。正式 `-game` resource dump 仍没有 `GaussianVolume.Output`，证明支持 UAV 的 runtime 路径继续使用原位合成，约 `0.844 MiB` 的 runtime working-set 结论不变。编辑器回退会重新分配全屏输出，因此不得用编辑器进程显存冒充作品集 runtime headline。

### 2026-07-24 — [修复] 自由镜头 tile 格与消失

用户自由转动编辑器视角时，云只在屏幕最右侧闪出并呈现明显 tile 方块。数据与 Actor 可见性均正常；telemetry 先确认旧 128K 固定机位为 requested/granted=`99,694/99,694`，但主射线使用 `ClipToWorld`，tile culling 却错误地从 `ViewToWorld.GetColumn(1/2)` 构造 right/up。两套坐标不一致，只有错误 candidate tile 与真实 ray footprint 偶然重叠时才会出现碎块。现已用 UE 官方 `InView.GetViewRight()/GetViewUp()` 统一 basis。

正确投影后同一编辑器视角 requested 立即从错误的 `99,694` 变成 `136,764`，暴露 128K 池 overflow=`5,692`、truncated tiles=`213`。默认池因此恢复为原路线建议的 `524,288 IDs`（`2 MiB`），而不是继续为固定机位 headline 压到 128K。最终 D3D12、1920×1080 runtime requested/granted=`142,979/142,979`、overflow=`0`、truncated tiles=`0`；RHI 命名资源为 candidate `2.000 MiB`、primitive `0.3125 MiB`、四个 tile buffer 各 `0.007782 MiB`，合计 `2.344 MiB`。冷构建、Map Check 0/0 与无 fatal 运行通过；旧 128K／错误 basis 的画质、tight-PBF 与 500 帧性能数字不再作为最终证据。

### 2026-07-24 — [落地][取证] Pool-free 低分辨率光深与原位 resolve

用户确认 full-resolution pool-free 路径真实覆盖云、近景没有 candidate tile 格，但贴近体积时 GPU 可超过 `50 ms`。根因是紧椭球代理的屏幕覆盖面积随距离暴涨，属于 fill-rate/overdraw，而不是 Gaussian 数量或 candidate pool。最小修正没有引入 BVH 或第二套表示：proxy pixel shader 只向 R16F target 加法累积解析 optical depth；随后一个全分辨率 compute resolve 从总 `tau` 一次性恢复 `T`、alpha、统一介质光照与 powder，再合成 SceneColor。`r.GaussianVolume.PoolFreeResolutionScale` 提供 `[0.25,1]` 的线性内部尺度，当前默认 `0.5`。

第一次实现无条件分配 full-resolution output，会重新吃回约 `8.4 MiB`，与项目显存目标冲突。根修复复用既有 UAV capability 检查：正式 runtime 直接读写同一个 SceneColor UAV；编辑器或不支持 UAV 的输入才创建 copy fallback。最终 1920×1080 `-game` RHI dump 只有 `GaussianVolumePoolFree.Tau=1.1875 MiB` 与 `GaussianBuffer=0.3125 MiB`，合计 `1.50 MiB`；没有 candidate/tile/LightTau 或额外 output。运行到 300 warm ticks 无 RDG assertion、fatal 或 GPU crash。

同一 runtime 视角完成 full-res 与 0.5× 各 500 帧 CSV，最后 300 个稳态样本为：pool-free pass P50/P95=`1.9661/2.1377`→`0.5996/0.6007 ms`，完整 GPU P50/P95=`6.8625/7.5071`→`5.4609/5.5104 ms`。pass 中位数下降 `69.5%`，证明优化命中 fill cost。该视角不是用户报告 `50+ ms` 的贴脸最坏情况；当前编辑器以 0.5× 打开，最终由用户自由移动相机签字细节与 worst-case。Gabor 未被取消，但只在该实时底座通过后作为稀疏高频 residual 进入同预算 A/B。

### 2026-07-24 — [Gate 失败][回退] pool-free close-up 收口

用户完成真实贴脸视角验收：full-resolution pool-free 的细节可接受，但 GPU 超过 `50 ms`；0.5× 虽降低 fill cost，贴脸仍约 `25 ms`，且细节不通过。0.25× 可能继续提速，但画质只会比已失败的 0.5× 更差，因此不再测试。pool-free 在当前架构下形成“提高分辨率则性能失败、降低分辨率则画质失败”的死结，close-up Gate 正式否决；已有实现和数值只作为负实验，不进入主线或作品集优势结论。

temporal、BVH 与自适应 raster 会构成新的执行架构，不在本轮收口范围；Gabor 只能增加表示精度，不能修复 proxy fill-rate，因此也不以 pool-free 为底座。项目主线回退已经成立的 512K compact-pool Compute：先完成 Gaussian／SVT／NanoVDB 的 matched-quality、总 working set、带宽与实时预算闭环；Compute Gate 通过后，才做同预算稀疏 Gabor residual A/B。Q3 与 Epanechnikov 继续冻结。

### 2026-07-24 — [边界][取证] 512K Compute 贴脸全屏 candidate 截断

用户关闭 pool-free 后在同一贴脸视角观察到整屏 32×32 格。GPU telemetry 确认 resolution=`1173×957`、requested/granted=`1,362,172/524,288`、overflow=`837,884`、max tile requested=`3,312`、truncated tiles=`1,110`、max tile drop=`2,038`；37×30 恰为全部 `1,110` tiles，因此格子来自全屏公平截断 `61.5%` candidates，不是 Q2 或 Gabor 的表示细节。当前 `GaussianVolume Max≈14 ms`、queue Max≈`16 ms` 是只处理 38.5% candidates 的假性能，不能签字。

按该视角实际 requested 计算，无截断 candidate buffer 至少 `5.196 MiB`，连同 32 B primitives 与 auxiliary 的最低逻辑 working set=`5.517 MiB`，已经高于 NanoVDB FpN raw grid=`4.598 MiB`；完整遍历还会高于当前截断性能。决策是不扩池挽救近景、不把 Gabor 用作遮盖 traversal 问题：近景继续使用原 VDB，Gaussian Compute matched-quality 与实时 Gate 严格限定在中远景产品范围。

### 2026-07-24 — [决策][实现中] 切换 quality-first Gabor 与重光照 reference

用户明确改为先拉满细节、实现 Gabor 与重光照，再考虑优化。quality reference 因此把 candidate pool 默认改为 exact tile matrix、support 改为固定 3σ，并扩展 48 B primitive 以保存 FP32 `omega` 与 signed extinction；UE shader 接入有限段 Faddeeva Gabor 解析积分，Q2 9,944 Gaussian＋4,096 Gabor 训练已启动。Q3、Epanechnikov、pool-free 主线和固定机位截图仍冻结。

### 2026-07-24 — [验证][进行中] 512² Gabor quality 训练改用内置视角 SGD

首轮 32 视角 full-batch 实测约 `243 s/step`，1200 步 ETA 约 80 小时，10 步前无断点且已停止。保持 512×512、32 个 reference cameras、8192 spp reference、Q2 9,944＋Gabor 4,096 与 1200 步不变，仅启用训练器已有 `cam_subsample=4`；实测约 `31–32 s/step`，ETA 约 10.7 小时，最终质量仍以全部 32 视角评估。checkpoint 周期缩短为 20 步。重复的 32 视角初始诊断图改为存在即复用；该图不进入损失、梯度或最终资产。

方向光与天光改为显式关卡 Actor 引用；Gaussian-base `LightT` 对高数量不再置 1，只在 primitive 数据或方向光变化时执行 O(N²) 重建并跨帧缓存。当前目标是最高画质与静态重光照正确性，首次重建成本和完整 frame 只记录，留到画质签字后优化。

### 2026-07-25 — [检查点][待人工画面签字] Gabor step 720 预览已配置

训练并未按最初约 `10.7 h` 的粗略 ETA 完成：检查时仍停留在 `719/1200` 后的 step-720 全视角 clean-PSNR／checkpoint 阶段，训练进程保持运行且 GPU 利用率为 `100%`。实际慢点是 `checkpoint_every=20` 同时触发昂贵的 best-checkpoint clean evaluation，不能继续用纯优化 step 时间估算总时长。

已在不终止训练的前提下冻结 step-720 PLY，并导出 `9,944 Gaussian + 4,096 Gabor = 14,040` primitives；其中 `3,354` 个 Gabor 为负权重 residual。导出器的 4 项自检通过，UE NullRHI 导入和关卡保存通过。TechLab 现在保留两名同 transform Actor：`Smoke2 GFields Q2 10K High Fidelity` 已关闭渲染，`Smoke2 GFields Q2 10K + 4K Gabor Preview Step 0720` 已启用，固定 `3σ` support、关闭 screen-size LOD，其他密度与光照参数从 Q2 Actor 复制。

当前没有启动 D3D12 viewport：训练仍占用约 `4.3 GiB` 显存和满 GPU，任何此时的 UE 帧时都无效且可能造成显存压力。`frames_pyr1/image_0720.exr` 只是该 step 最后一个随机 camera batch，不可与固定 reference tile 冒充配对画质证据；最终仍由用户在训练释放 GPU 后于 live viewport 做 Q2/Gabor A/B。

### 2026-07-25 — [落地][验证] 真实 smoke2 VDB 解析转换并部署 7DRGS

依据实现记录逆向完成 7DRGS PLY loader、方向切片、GPU preprocess/sort、硬件 raster 与 composite。新增 `lift_volprim_to_7drgs.py`，把同源 `smoke2_vdb.npy` 以 block=`4` 聚合为 `64,815` 个空间样本，再以 6 个轴向光照叶片展开为 `388,890` 个 7D Gaussian；最终 sharp 资产使用 angular sigma=`0.5`、spatial sigma=`0.55`、ambient=`0.12`。转换器自检覆盖输出行数、字段完整性和方向响应。

UE runtime 新增 `RefreshRenderingParameters()`，解决 Python/editor property 已改变但 render thread 仍使用旧参数的问题；`LoadFromFile()` 保留项目相对 PLY 路径，避免 TechLab 保存绝对机器路径。`AbyssEditor` 冷构建成功（15.24 秒），TechLab 已保存 `7DRGS Smoke2 VDB B4 389K Sharp 6-Light` Actor。隔离显示确认原先被误判为 7DRGS 伪影的“大灰壳”本来就存在于同源 SVT 受光结果；此前异常主要来自 SVT、Q2、Gabor 与 7DRGS 四套体积叠加。当前代理整体轮廓和密度层级已接近 SVT，细边界仍更颗粒；`+X/-X` 手动光方向产生明确响应。

### 2026-07-25 — [取证][负结论] 解析 7DRGS 未胜过同源 UE SVT U8

在同一 TechLab、同机位、同分辨率下短暂进入 PIE，并用 UE 原生 `ProfileGPU` 分别隔离采样。7DRGS 帧为 `9.19 ms`，顶层 `GaussianSplatting 7DRGS 388890` 为 `1.799 ms`：Slice=`0.356 ms`、Preprocess=`0.103 ms`、Sort=`0.249 ms`、HW Raster=`1.039 ms`、Composite=`0.007 ms`。关闭 7DRGS CVar 后，同源 SVT U8 帧为 `8.43 ms`，HeterogeneousVolumes 合计约 `1.070 ms`，其中目标组件约 `0.992 ms`。

因此当前高细节解析 7DRGS 的体积范围比 UE SVT U8 慢约 `0.73 ms`，整帧也慢约 `0.76 ms`；该结果不能包装为性能优势。7DRGS 的 world scene view extension 当前不服从 SceneComponent visibility，公平基线通过 `r.GaussianSplatting.Enable=0` 隔离；最终关卡已恢复 CVar=`1` 并保存所有 Actor 的正常 runtime visibility。

### 2026-07-25 — [训练][自动跟进] Gabor 从 step 720 续跑至 1200

断点 `optimized_asset_pyr1/npy_data/opt_state/meta.json` 确认 7 个 Adam 参数组均在 step `720`。原恢复路径会把 Gabor 迭代编号和学习率 warmup 重新从 0 开始，且每 20 步 checkpoint 都触发一次约 49 分钟的全 32 视角 clean-best 评估；这正是此前总耗时失控的主因。

恢复路径现延续绝对迭代 `720..1199` 与原 1200-step 学习率调度，保留每 20 步断点，恢复阶段关闭重复 best 评估；训练结束仍执行一次完整 32 视角 clean render/PSNR 并导出最终资产。首次恢复 step 实测 `43.14 s`，GPU=`100%`、显存约 `3.8 GiB`，预计优化约 `5 h 45 min`、最终评估约 `50 min`，总计约 `6–7 h`。已建立 04:45 自动跟进：完成后继续最终导出、TechLab 配置、Q2/Gabor 与 SVT/7DRGS A/B 和文档收尾；Q3、Epanechnikov、pool-free 主线与固定机位截图继续冻结。

### 2026-07-26 — [用户画质否决][归档] Gabor 结束，主线切换为 7DRGS

Gabor 从 step 720 完成全部 480 个恢复步，总优化耗时 `5 h 38 min`；最终 32 视角 clean PSNR=`31.1497955 dB`。导出 JSON 自检通过：`14,040` primitives=`9,944 Gaussian + 4,096 Gabor`，其中 `3,544` 个 Gabor 为负权重 residual，SHA256=`A2276E77230A8E2BF8C909ADED64C410FF44BA727509BA08E48D35D81A42162E`。

最终资产已在 UE 载入为 `Smoke2 GFields Q2 10K + 4K Gabor Final Step 1200`，用户直接判定画质太差并否决继续投入。Gabor 路线因此正式归档：训练资产、JSON、Actor、shader 与脚本保留为负实验证据，但不再进行灯光调参、性能 A/B、预算消融或 runtime 优化。Gabor 自动跟进任务已删除。

项目唯一主线改为 7DRGS。TechLab 已关闭所有 GaussianVolume/Gabor 与 SVT 显示，恢复 `r.GaussianSplatting.Enable=1`，仅显示 `7DRGS Smoke2 VDB B4 389K Sharp 6-Light` 并保存关卡。后续 Gate 是先解决真实 VDB→7DRGS 的细节与方向重光照，再优化点数、方向叶片、Slice/Sort/HW Raster；当前解析版本 `1.799 ms` 仍慢于同源 SVT U8 约 `1.070 ms`，该负结论保持有效。

### 2026-07-26 — [换源][最高质量部署] CC0 Hero Congestus 50 B2 Ultra

用户指出 WDAS cloud 有一半像被削平。对 `wdas_cloud_quarter.npy` 检查后，active bbox 只有极少数边界 voxel，转换器没有裁掉半边；视觉问题来自源云本身偏平的底部与轮廓。该资产因此退出最终展示 Gate，不再继续生成 WDAS 更高档。

公开资产改用 CGHEVEN `Hero Congestus Cloud VDB - 50`，页面标记为 CC0。下载包 `Hero_Cloud_02_v50.rar` SHA256=`C892217D115DDC9CBA4C9737C96476A1C88B1FD20D3E85A2DF75494960497A7C`。原 VDB 的 `readAll()` 会被附带内容触发 abort，但单独读取 `density` 正常；已重写为单 grid `Hero_Cloud_02_v50_density_only.vdb`，SHA256=`4511FAF0531D1FA02919C573415C368796B52E27660D6AF2615F9EA58421AAE4`。有效分辨率=`238×264×403`、active voxels=`8,536,415`、density range≈`[8.35e-7,1]`。

转换前六面各加 `8 voxels` 空白，dense grid=`254×280×419`，六个外表面 density 均为 `0`；active longest axis 按 `403 voxels=1000 cm` 对齐同源 SVT。最高细节档采用 block=`2`、spatial sigma=`0.48`、angular sigma=`0.5`、density scale=`0.04`、ambient=`0`，生成 `1,112,674` 个独立空间样本和 `6,676,044` 个六方向 points。PLY=`2,136,336,393 B`，SHA256=`FD1E5F2B1895742611E1CD20452A76ABCB06B3BB42E8D231168BA6A3C7792A73`；header／payload size、10 万点 finite sample、方向响应 `[0,1]` 与 3 项转换测试均通过。

7DRGS runtime 增加显式 SkyLight ambient：组件读取 SkyLight color×intensity×`AmbientLightIntensityScale`，通过 render parameters 和 composite shader 加入环境填充；DirectionalLight 继续由 editor tick 实时刷新。当前部署使用 dual HG，`g1=0.65`、`g2=-0.2`、blend=`0.1`、phase intensity=`0.35`。`AbyssEditor` 冷构建成功。

NullRHI 部署成功并保存 TechLab：可见 Actor=`7DRGS CGHEVEN Hero Congestus 50 B2 Ultra 6.68M`，point-count readback=`6,676,044`；默认隐藏的同源 A/B=`CGHEVEN Hero Congestus 50 UE SVT U8 A-B`，SVT resolution=`238×264×403`、最长轴=`1000 cm`。DirectionLight=`Light Source`、SkyLight=`SkyLight` 均已绑定。下一步仍是用户 live viewport 画质与场景灯签字；签字前不做点数/叶片优化，也不沿用 smoke2 的 GPU 性能数字。该 PLY 仍是解析抬升代理，不等同于论文训练结果。

### 2026-07-26 — [修复][D3D12 验证] 6.68M wrapped dispatch

B2 Ultra 第一次在 D3D12 TechLab 打开时，`FGS7DSlicingCS` 以 `6,676,044 / 64 = 104,313` 个 X 组派发，超过 D3D12 单维 `65,535` 上限并触发 `ValidateGroupCount` ensure。根因不在资产或显存，而是 Slice 仍假设点数不超过约 `4.19M`。

Slice 与 Preprocess 统一改用 UE 原生 `FComputeShaderUtils::GetGroupCountWrapped`；对应 shader 通过 `GetUnWrappedDispatchThreadId` 恢复线性索引。`AbyssEditor Win64 Development -NoHotReloadFromIDE` 冷编译成功（13.31 秒）。重启后直接打开 `L_GaussianVolume_TechLab`，进程保持响应、工作集约 `8.5 GiB`，日志无 dispatch ensure、shader compilation failure、GPU crash 或 fatal；编辑器保持打开供用户 live viewport 验收。

### 2026-07-26 — [签字][决策] B2 细节／重光照通过，冻结训练 Spec

用户确认 B2 Ultra 空间细节已无问题、方向重光照可用；轻微全局色差暂不阻塞。正式训练前按 `SPEC.md` 第 2.13 节先修复 stage、B2 geometry warm start、完整 resume、checkpoint/validation 解耦和确定性 contribution prune，再以 `500–1000` iterations 短程试跑验证；训练当前尚未启动。Gabor、Q3、Epanechnikov、pool-free 与固定机位截图继续冻结。

### 2026-07-26 — [决策] 确定性正收益优化前置到 7DRGS 基线

用户要求不要等预算训练结束才补做明确有正收益的优化。训练流程现固定为一个 `1.112M` 主检查点依次派生 `800K`、`600K`，不做三次独立重训；Stage 1 冻结参数从 optimizer param groups 移除，不创建 gradient/Adam state；checkpoint 与完整 held-out evaluation 解耦；Stage 1 在训练/验证集累计的 visibility/radiance/edge/residual score 复用于后续确定性裁剪，最终测试集保持不可见。正式 GPU A/B 前，UE Slicing 按资产、Component transform、时间、灯光方向和切片参数做失效缓存，静态输入不再每帧全量切片。

多尺度／频域 loss、directional/spatial split、FP16/量化 packing、visible-only compaction 与 cluster culling 仍需误差或 profiler 证据，不伪装成确定收益。既有 Gabor runtime 实验画质已被用户否决，不接入 7DRGS 基线；只保留“低频基底＋局部残差”的误差驱动思想。

### 2026-07-26 — [训练][Gate 通过] 111.2 万点 smoke 完成并启动 Stage 1

已建立独立 Python 3.11／PyTorch 2.8.0+cu128 环境，并编译官方 `diff-gaussian-rasterization` 与 `simple-knn`。训练器现支持明确 stage、B2 spatial Cholesky 热启动、完整 model/optimizer/RNG/camera-stack resume、便宜 checkpoint、确定性 stable-sort prune 和最小中断恢复检查；恢复链已由 65,536 点 500-step 连续/250-step 恢复对照验证，iteration、stage、point count 与 finite PLY 均通过。

真实 Hero Congestus density 生成 8 views×6 signed-axis lights×256、256 ray steps 的线性 `J/TView/depth/mask` 数据。全量 `1,112,674` 点 Stage 0 完成 500 steps，用时 `172 s`（约 `2.90 iter/s`）；最终 train total loss=`0.1635`、TView L1 EMA=`0.1672`，独立 held-out camera＋held-out light 的 J L1/PSNR=`0.03905 / 21.13 dB`。两个 checkpoint 各约 `1.02 GB`，最终 PLY=`271,494,101 B`、61 fields、点数准确且无 NaN/Inf。UE 同时打开时整卡峰值约 `7,584 MiB / 8,151 MiB`，余量仅约 `313 MiB`。

Smoke 还暴露了一个冻结语义问题：空间和方向 Cholesky 原本共用 optimizer tensor，500 步已改变 B2 空间块。Stage 1 入口现从 `init_points.ply` 恢复前三个 spatial diagonal/off-diagonal，清零对应 Adam moments，并用 gradient mask 固定该空间块；xyz、scale、rotation、opacity 继续不进入 Stage 1 optimizer。当前已从 checkpoint 500 启动目标 step 15,000 的渐进 relight fit，PID=`39460`，约 `2.86 iter/s`，5K/10K/15K 才做完整 held-out 验证；不启用 densification、RAP、GNS、MU、Gabor 或自动截图。

### 2026-07-27 — [训练完成][方向 Gate 失败] 15K held-out 与 UE 预览

Stage 1 从 step 500 完成至 15,000，总耗时 `1:32:29`。最终训练 EMA loss/TView=`0.00729/0.00478`；held-out J PSNR 在 5K/10K/15K 为 `20.85/21.39/21.61 dB`，训练视角则达到 `48.10 dB`，泛化差距明确。最终 checkpoint 与 271,494,101 B PLY 均为 `1,112,674` 点、61 fields、零 NaN/Inf；spatial Cholesky diagonal/off-diagonal 相对 B2 init 的最大误差均为 `0`。

独立完整 held-out 协议使用 2 个未见相机和 1 个完全留出的轴向光：J full/foreground PSNR=`21.43/16.54 dB`，TView full/foreground=`18.54/14.83 dB`，foreground τ L1=`3.806`，Mask IoU=`0.9505`，inverse-depth foreground L1=`0.00319`。相对 step 500，TView foreground 从 `10.79` 提升至 `14.83 dB`，但 J foreground 只从 `16.18` 提升至 `16.54 dB`。结论是空间、轮廓和训练链成立，当前 5-train/1-heldout 光向覆盖不足；继续同数据迭代不会替代方向监督，暂不进入 800K/600K。

训练 PLY 已复制为 `CGHEVEN_HeroCongestus50_7DRGS_Trained15K_1p112M.ply`，SHA256=`BE486466F872C3F4640FA6FE0CCAEE659ACE1969F02EC686C6EA3C488C31923A`。UE TechLab 无保存加载成功：Actor=`7DRGS CGHEVEN Hero Congestus 50 Trained 15K 1.112M PREVIEW`，point readback=`1,112,674`，场景 DirectionalLight、Dual SH 与可见性有效，SVT 暂时隐藏；编辑器稳定，无 shader error、GPU crash 或 fatal。该状态只供用户 live viewport 验收，尚未保存关卡。

### 2026-07-27 — [用户否决][根因审计][改线] 15K 不恢复，改为 B2 teacher distillation

用户在 UE live viewport 确认 15K 训练版存在严重颗粒噪声和细节模糊，画质 Gate 失败。训练 PLY 的 `TView SH degree=1` 而预览曾继承为 `0`，部署脚本和当前预览已改为 `1`；修正后噪声仍在，因此不是 UE 抗锯齿、显卡或单一预览参数问题。B2 解析版保持完整，15K checkpoint/PLY 只作为负证据保留，禁止续跑、warm start 或进入点数裁剪。

代码审计发现 `_write_init_from_b2` 只复制 xyz/scale/rotation/spatial Cholesky，并从六方向展开数据选第一组 `vertices[indices]`；B2 opacity、`J`、`TView`、`mu_d`、lambda 和 directional covariance 全部丢失。relight stage 又把统一冷启动为 `0.1` 的 opacity 冻结，迫使 appearance/conditional covariance 代偿。`lambda_sh_reg`、`lambda_sigma_reg` 虽有参数定义，但没有进入主训练 loop；静态 timestamp 恒为 `0` 时 temporal/cross covariance 仍可训练，light direction 还能改变有效 spatial mean/covariance。

checkpoint `500→15K` 证据与此一致：xyz/scale/rotation/opacity 完全不变，opacity 始终 `0.1`；`J` DC std=`0.169→1.146`、最大系数=`10.236`，directional/full Cholesky diagonal p99 约 `2.081→106.747`、抽样最大=`4269.5`，`TView` DC std=`0.210→0.764`。训练 J PSNR=`48.10 dB`，held-out foreground J/TView 只有 `16.54/14.83 dB`，属于错误初始化与无约束过拟合，不能再归纳为“只需增加光方向”。

公开方法横向审计后保持 7DRGS 主线但收紧边界：公开 7DGS 条件是 time/view direction，不是 light；BiGS 的 fixed geometry、light/view appearance 和物理/未见方向约束值得借用，但完整约 `1089 params/primitive` 不适合 1.112M 点；RNG/GS³ 需要 neural shader 或 hybrid pass；LightGaussian/PUP 类压缩都先得到高质量 teacher，再 prune/recover。项目不整体切换 BiGS 或第二套 renderer，改为解析 B2 teacher＋VDB ground-truth anchor 的固定几何 distillation。

下一 Gate 固定为：聚合全部六叶片并保留/拟合 density、`J/TView` 与方向响应；冻结 temporal block 和 spatial-condition cross covariance；把 SH/covariance/能量/未见方向约束真正接入 main loop；以约 `16 cameras×24 lights×512` 为正式数据目标、`sh_degree=1` 起步，先做 `1–2K` smoke。只有参数健康、held-out 指标和用户 UE 画质同时通过，才训练 1.112M matched-quality student，并依次尝试 `900K→800K`；600K 不再预设。Gabor、Q3、Epanechnikov、pool-free 与固定机位截图继续冻结，所有改动保持未提交。

### 2026-07-27 — [修复][全量资产验证] 六叶片 teacher 初始化与静态条件链

`_write_init_from_b2` 不再抽取第一叶片：现在按 `1,112,674` 个空间点验证六叶片几何／TView 一致性，按 UE 的 `opacity × exp(-0.25 λq)` 语义重建六个轴向 teacher 响应，再将精确 alpha composite 的 `J` 拟合为 degree-1 light SH。Python slicing 同步修正为 UE 指数；训练 renderer 用 light direction 评估 `J`，camera direction 只评估 `TView`。静态训练从 optimizer 移除 temporal／directional covariance，cross-covariance 固定为零。

主训练 loop 已接入 SH、teacher-anchor 与 `J∈[0,1]` 能量有界项；恢复训练会从 init PLY 重载 teacher anchors，不把副本塞进 checkpoint。6 项最小测试、`py_compile` 与 2→4 iteration 小规模 resume 均通过；小链健康检查为 geometry max error=`0`、cross covariance max=`0`、lambda max≈`1e-8`、所有字段 finite。

全量初始化已写入 `artifacts/hero_b2_distill_smoke/init_points.ply`：`1,112,674` 点、53 fields、`235,888,349 B`、SHA256=`B65F489AC60A2E426C970F5C093A58D57B18CE43666F37E79D97EEBC34DDCC62`；cross covariance max=`0`，六方向 SH anchor RMSE=`0.0373711`、max error=`0.2875644`。UE shader 的 `J` light-direction 修复以可通过 `git apply --check` 的项目内 patch 保存，尚未修改外部插件。UE 编辑器当前约占 `6 GiB / 8 GiB` 显存，因此不与其并发启动全量 `1–2K` smoke；先等待用户保存并关闭 UE。

### 2026-07-27 — [训练][数值 Gate 通过][待 UE] 111.27 万点 1K teacher smoke

用户关闭 UE 后完成三次同数据短对照。首轮弱约束 smoke 虽把 held-out J PSNR 提到 `23.60 dB`，但 opacity 最高漂到 `0.9978`、六轴 `J` 越界率升到 `20.42%`，再次违反静态 density teacher，明确判负。第二轮冻结 opacity 并提高边界权重后，静态参数零漂移，但 teacher 约束仍偏松，六轴越界率=`12.21%`。

源 B2 的 TView SH 实测恒为零色（DC=`-0.5/C0`、rest=`0`），真实视线透射由白背景上的静态 opacity 合成；此前所谓 TView 训练实际只能靠 opacity 漂移降低 loss。最终口径因此冻结 opacity、TView、几何、temporal 与 cross-covariance，静态 smoke 只训练 light-conditioned `J`，并跳过对任何可训练参数都无梯度的 mask/depth/TView loss。teacher-anchor 默认提高到 `10`、energy 默认提高到 `1`。

最终全量 1K 用时约 `78 s`、约 `12.9 iter/s`，GPU 总占用约 `4.73/8.15 GiB`。输出为 `1,112,674` 点、56 fields、全部 finite；所有静态参数最大误差=`0`、cross covariance=`0`、activated lambda≤`1e-8`、opacity=`[1.56e-6, 0.17119]`。held-out/train J PSNR=`21.93/24.98 dB`，gap=`3.06 dB`；六轴 anchor drift RMSE=`0.01282`、越界率=`8.54%`（teacher 初始=`7.49%`），系数绝对值 p99/max=`1.7407/1.7641`。

最终 PLY=`249,240,491 B`，SHA256=`488A90FD81BD80ABA9507DD1FA427F3A758024531D725734B40E3E54AED1A0AE`；`health.json` 与 `metrics.json` 位于 `artifacts/hero_b2_distill_smoke/run_1k_teacher/`。数值健康 Gate 通过，但尚未宣称画质通过：下一步必须先把 `patches/7drgs-j-sh-light-direction.patch` 应用到 UE runtime，再由用户 live viewport 验收；未签字前不扩正式 16×24 数据、不裁剪。

### 2026-07-27 — [UE 部署][待用户签字] 1K teacher preview

用户明确授权修改外部 Abyss 插件后，将 `J` SH 的评估方向从 camera `ShDirOCV` 改为组件传入的 light direction；`TView` 继续使用 camera direction。修改前 shader 已备份到 `artifacts/runtime_backups/2026-07-27/`。`AbyssEditor Win64 Development` 构建成功；D3D12 启动实际重编译 `FGS7DSlicingCS` 1 次并成功完成，无 shader error、ensure、GPU crash 或 fatal。

最终 1K PLY 已复制到插件 `Content/Data/CGHEVEN_HeroCongestus50_7DRGS_Teacher1K_1p112M.ply`，复制后 SHA256 与训练输出一致。自动化 readback 成功：level=`L_GaussianVolume_TechLab`、Actor=`7DRGS CGHEVEN Hero Congestus 50 Teacher 1K 1.112M PREVIEW`、points=`1,112,674`、Dual SH=`true`、TView degree=`1`、saved=`false`。AbyssEditor 以持久 D3D12 窗口保持打开，进程响应正常，GPU 总占用约 `5.60/8.15 GiB`；下一步只等待用户 live viewport 画质签字。

### 2026-07-27 — [Degree-2][数值 Gate 通过][待用户签字] 零增量升级与 1K 选择

按用户确认的顺序，先固定渲染数学与当前画面，再只扩展 `J`。训练器新增可选 init PLY 和立即激活最大 SH degree 的入口；degree-1 PLY 中旧 4 个系数原样载入 degree-2，新增 5 个系数为零。teacher anchor 改为只约束 anchor PLY 实际存在的系数前缀，不会把新增 degree-2 系数压回零。7 项最小测试与 `py_compile` 通过；全量 parity PLY 为 `1,112,674` 点，全部旧字段 max error=`0`、新增系数 max abs=`0`。

从已通过视觉 Gate 的 degree-1 1K PLY 启动 3K、只训练 `J` 的对照。1K/2K/3K held-out J PSNR=`22.03/21.89/21.75 dB`，train=`26.22/26.85/27.26 dB`；2K 后训练继续改善而 held-out 持续下降，因此选中 1K checkpoint，不部署更晚版本。选中 PLY 为 61 fields、`271,494,101 B`、全部 finite，静态参数 max error=`0`，新增 degree-2 系数绝对值 p95/p99/max=`0.03586/0.05223/0.08440`，SHA256=`0071EAAEAF2A4540333A0EE9FD54AEC8C4A5E7B25104DFEEC8408673148A5ADC`。

PLY 已复制到插件 `Content/Data/CGHEVEN_HeroCongestus50_7DRGS_Degree2_1K_1p112M.ply`，源/目标哈希一致。TechLab 自动 readback 成功：Actor=`7DRGS CGHEVEN Hero Congestus 50 Degree 2 1K 1.112M PREVIEW`、points=`1,112,674`、phase=`dual HG 0.65/-0.2 blend 0.1, intensity 0.35`、saved=`false`。AbyssEditor 响应正常，日志无 shader error、ensure、GPU crash 或 fatal；下一 Gate 只由用户 live viewport 确认画面。
### 2026-07-27 — [H9][修复][待用户签字] 50K 任意方向内部透射／自阴影

根因是高数量 uniform 路径虽然消费 `LightTransmittance`，但旧 O(N²) `LightTauCS` 在 50K 不可执行，方向光移动后没有可用的逐核内部光程。H9 离线从同源 density grid 为每个 kernel 烘焙 local `±X/±Y/±Z` 六个 FP16 光程，运行时把世界灯向旋回资产局部空间并连续插值；六值复用 48 B primitive 的既有 `Data2.yzw`，不增加每核字节。50K 高数量路径只绑定单元素 dummy LightTau，不再构建 O(N²) 缓冲；`≤4096` 的旧精确路径保留。

烘焙资产为 `artifacts/hero_tau_recovered50k_h9_directional/GaussianVolume_Hero_TauRecovered50K_Directional.json`，50,000 centers 全部位于源 grid，六轴 τ median=`3.450/3.403/4.582/4.800/3.024/3.359`。NumPy self-check、Python compile、`AbyssEditor Win64 Development -NoHotReloadFromIDE` 冷构建、shader compile 与 NullRHI `GaussianVolume.UniformAppearance` 自动化测试均通过。TechLab 已部署 `GaussianVolume Hero Directional Tau 50K H9 PREVIEW`，SVT 的 editor hidden/root visible 状态前后不变；物理强度 `1.0` 过暗，当前视觉校准 `DirectionalShadowDensityScale=0.3`。最终 Gate 只等待用户在 live viewport 移动灯光确认。

用户随后发现太阳转入地平线下时场景已黑、Gaussian 仍被照亮。现场确认 `Light Source` 为 `AtmosphereSunLight=true`、朝光方向 `Z=-0.7869`，插件却仍把 `4.0548×0.2` 的直射强度送入 shader；六轴光程方向本身没有错，错误是把下半球镜像方向当成仍有能量。共享光照入口现按 Atmosphere Sun 标记做上半球门控：`Z≤0` 直射为零，地平线上约 3° 内平滑恢复；普通非太阳 Directional Light 保留从下方照明。冷构建与新增 horizon 自动化断言通过；重启并恢复同一机位后 H9 已由白亮变成只剩很暗的 SkyLight 蓝色填充，SVT 可见性未改变。

### 2026-07-27 — [H11][训练完成][待 UE 视觉 Gate] H4 Directional24 D2 续训至 4K

按用户要求先训练 H4，不修改结构、点数或 UE 对比场景。从同一个 H2 1K teacher 基线按 H4 原始 Directional24 协议重跑至 4K，只优化 light-conditioned `J`；几何、opacity、TView、temporal/cross covariance 保持冻结，densification、剪枝、LAS/EAS/RAP/MU/GC 均关闭。训练用时约 `7m20s`，保存 2K/2.5K/3K/3.5K/4K 五个 checkpoint。

同一 4 个完全留出灯向的 PSNR 在 2K/2.5K/3K/3.5K/4K 为 `22.715/22.853/22.975/23.069/23.181 dB`，L1 为 `0.03109/0.03040/0.02972/0.02922/0.02864`，4K 仍未出现泛化回退，因此选择 4K。最终 PLY 为 `1,112,674` 点、61 fields、`271,494,101 B`、全部 finite，静态参数最大误差=`0`，SHA256=`1D7D06DF674F26221DA006319655FBAA9A6B40E471497F8D7018B66E89FA7694`。资产已复制到插件 `Content/Data/CGHEVEN_HeroCongestus50_7DRGS_Directional24_Degree2_4K_1p112M.ply`；编辑器当前关闭，未改 H0/H4/H6/SVT 的现有场景可见性。

用户在 UE 中完成 H11 视觉检查；恢复 `Dual SH=true`、SkyLight scale=`0.1` 与正式 phase 参数后，仍没有可辨认的内部自阴影。该结果否定“继续同一 image-space J loss 即可学出自阴影”：沿视线的逐点 J 可以互相代偿，PSNR 改善主要反映整体图像拟合，并未唯一约束每点到光源的光程。H11 标记为视觉 Gate 失败，禁止继续原协议迭代；若继续 H4，必须改为直接监督逐点 light-space τ/T，再以图像 loss 微调。

### 2026-07-27 — [H12/H13][训练／烘焙完成][待用户视觉 Gate] H4 点级光照与 H6 六轴光程

H12 不再续跑 H11 的 image-space loss：固定 H4 的 `1,112,674` 个点及全部静态字段，直接从同源 density grid 计算 24 个灯向的逐点 light-space transmittance，以前 20 个方向闭式拟合 degree-2 `J` SH，并用后 4 个方向留出验证。最终 train MAE/RMSE=`0.04679/0.07677`，held-out MAE/RMSE=`0.08067/0.13218`，静态字段最大误差=`0`；degree-3 direct-T held-out RMSE=`0.18472`、degree-2 optical-depth held-out RMSE=`0.22260`，均否决。选中 PLY 为 `271,494,101 B`，SHA256=`9460AE185DFD7F4AE268F3B453D963A3AFDD8FA9A197C6E147204C34AAB861FD`。

H13 从 H6 exact 50K initializer 直接烘焙 local `±X/±Y/±Z` 六轴 optical depth，不改变 kernel 数量或 48 B/kernel 运行时布局。50,000 centers 全部位于源 grid，六轴 τ median=`3.455/3.404/4.583/4.798/3.029/3.356`；JSON=`21,648,913 B`，SHA256=`1B61B863ACF222B7557F44FD23EA8B5931ACA9543FCC5C41C44B7B689F69486D`。

TechLab 已在不保存关卡的情况下把 H11/H6 替换为 `H12 | H4 PointwiseLight24 D2 1.112M` 与 `H13 | H6 Adaptive 50K Directional Tau`；两者和 SVT 均保持可见。重开时 H13 Actor 的 `Use Scene Lights=false` 且带旧的实例覆盖值，现已恢复用户确认的 Density=`0.416`、Gamma=`1.515627`、Direct/Sky=`0.5/0.1`、Scene Depth/Lights=`true`，方向阴影强度用 `0.3` 预览。当前关卡中没有 H0 Actor，本次未隐藏或删除它。最终画质与自阴影 Gate 由用户在 live viewport 旋转方向光确认。
