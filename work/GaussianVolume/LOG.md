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
④ N scaling：256→320万、512→214万、1024→76万 ray/s。N=1024 下 76万 ray/s 已达实时级（200x150 单帧 0.04ms）。
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
