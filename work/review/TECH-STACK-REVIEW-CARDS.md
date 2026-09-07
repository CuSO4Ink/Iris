# 技术栈基础概念复习卡

> 用途：面试前自查。每个领域给出【核心概念】【关键细节】【典型追问】【薄弱提示】。
> 从 PROJECT-INTERVIEW-MAP.md 进入项目过程复习。本文是待校正的概念草稿，不代表个人掌握程度。
> 创建：2026-08-25（review 项目）。

## 0. 图形管线与图形 API

### 核心概念
- 光栅化管线阶段：IA 输入装配 → VS 顶点着色 → （曲面细分 HS/DS、几何 GS）→ 光栅化（三角形→片元）→ PS 像素着色 → OM 输出合并（深度测试、混合、写 RT）。
- 延迟渲染：几何 pass 把材质属性写入 G-Buffer（UE5：A=世界法线，B=金属度/高光/粗糙度，C=BaseColor+AO，D=Custom Data，E=预计算阴影），光照 pass 逐光源读 G-Buffer 计算。优点：光照成本与几何解耦；缺点：带宽大、半透明难处理。
- 前向渲染：每物体每光源直接着色；UE 中半透明走前向。
- D3D12 显式 API 要点：Command Queue/Allocator/List、PSO（管线状态对象，编译期固定）、Root Signature（参数绑定契约）、Descriptor Heap（资源视图池）、资源状态与 Barrier（显式转换读写状态）、GPU-based validation。
- Compute Shader：独立于图形管线的通用计算；`[numthreads(x,y,z)]` 定义线程组；`SV_DispatchThreadID` 全局 ID；组共享内存 LDS + `GroupMemoryBarrierWithGroupSync()`；原子操作 `InterlockedAdd`（候选池注册的关键）。
- Wave/warp：GPU 以 32 线程（NVIDIA）为最小调度单位；divergence（分支分歧）会让 wave 串行执行两路分支。

### 关键细节
- GPU 性能两大类瓶颈：**带宽受限**（读写显存多：纹理采样、原子竞争、大 buffer 搬运）与 **ALU 受限**（计算多）。先判断哪类再优化。
- Occupancy（占用率）= 常驻 wave 数 / 硬件上限；寄存器用太多会降低 occupancy。
- 经典并行原语：prefix scan（前缀和，Hillis-Steele/Blelloch）、scatter（按扫描结果写紧凑数组）、radix sort（基数排序，GS 深度排序用）。

### 典型追问
- 延迟渲染为什么半透明麻烦？→ G-Buffer 只能存一份表面属性，半透明要叠加多层，只能走单独的前向 pass（Translucency pass）。
- Compute 里原子操作为什么慢？→ 大量线程竞争同一地址会串行化；缓解：局部聚合、按 tile 分桶、减少竞争面。

### 项目关联与待自查
- GaussianVolume 的"count → prefix scan → scatter 紧凑全局池"就是上面三个原语的组合，面试讲候选池时直接关联。

## 1. UE 渲染架构

### 核心概念
- 三线程模型：GameThread（逻辑/UObject）→ RenderThread（场景代理、渲染命令生成）→ RHIThread（提交 GPU）。`ENQUEUE_RENDER_COMMAND` 把 lambda 投递到渲染线程；UObject 只能在游戏线程访问。
- Scene Proxy：游戏线程对象（PrimitiveComponent）在渲染线程的镜像（FPrimitiveSceneProxy），两线程间靠代理隔离。
- RDG（Render Dependency Graph / RenderGraph）：声明式建图。`FRDGBuilder` 创建 transient 资源、`AddPass` 声明读写，框架自动做资源池复用、barrier 排布、剔除无用 pass。`RDG_EVENT_SCOPE_STAT` 注册 GPU stat 分组。
- Global Shader：全局唯一的 C++ shader 类（`DECLARE_GLOBAL_SHADER`/`IMPLEMENT_GLOBAL_SHADER`），用 `SHOULD_COMPILE_PERMUTATION` 控制排列组合，不走材质系统。自定义体积/后处理 pass 的标配。
- USF/USH：Unreal Shader File / Header，HLSL 源码 + UE 宏（如 `float3 View.WorldCameraOrigin`）。
- SceneViewExtension：`FSceneViewExtensionBase` 派生类，挂进渲染流程的钩子（PreRenderViewFamily/PostRenderViewFamily），在引擎管线里插自定义 pass。GaussianVolume 与 NeuralVolumeProxy 插件都靠它接入。
- StructuredBuffer：结构化缓冲，CPU 上传结构化数据给 shader 用（PLY 点云、神经权重）。
- Shader 编译与 DDC：shader 排列组合爆炸是 UE 痛点；PSO 缓存、DerivedDataCache。

### 关键细节
- 一个自定义 GPU feature 的完整接入链：C++ 插件（模块 Build.cs）→ SceneViewExtension 注册 → RDG pass 声明资源 → Global Shader（USF）→ 结果合成回 SceneColor 或单独 RT。
- UE GPU 调试：`ProfileGPU`（Ctrl+Shift+,）、`stat gpu`、RDG event 在 ProfileGPU 里显示为层级条目。

### 典型追问
- 为什么不能在渲染线程碰 UObject？→ UObject 的 GC/属性系统只保证游戏线程安全。
- RDG 相比手写 barrier 的好处？→ 自动资源池（transient 复用降显存）、自动 barrier（防漏转换）、pass 剔除。

### 项目关联与待自查
- [A] 这是你两个插件（GaussianVolume、NeuralVolumeProxy）的地基，必须能把"插件怎么接进引擎渲染"这条链完整讲出来。

## 2. 材质、光照与风格化渲染

### 核心概念
- PBR 核心公式（Cook-Torrance 镜面项）：`f = D·G·F / (4·N·L·N·V)`。
  - D：法线分布函数，业界标准 GGX/Trowbridge-Reitz，由 roughness 控制。
  - G：几何遮蔽项（Smith 形式），处理微表面自遮挡。
  - F：菲涅尔，Schlick 近似 `F0+(1-F0)(1-cosθ)^5`；金属 F0 带颜色，电介质 F0≈0.04。
- IBL 与 Split-Sum：环境光积分拆成 预过滤环境贴图（按粗糙度 mip）× BRDF LUT（二维查找表），实时近似。
- UE 材质系统：材质表达式图 → 编译成 shader 代码；材质属性（BaseColor/Roughness/Normal/Emissive/Opacity…）；Material Instance 只改参数不重编译；Shading Model 决定光照公式分支（Default Lit/Subsurface/ClearCoat/Hair/SingleLayerWater…）。
- 卡通渲染配方：
  - Ramp/Curve：N·L 查表替代连续光照，得到分阶色。
  - MatCap：视图空间法线 xy 查球形贴图，廉价"环境反射"。
  - SDF 脸部阴影：预计算脸部方向 SDF，光方向查值决定阴影边界，避免法线噪声造成的碎阴影。
  - Kajiya-Kai 头发高光：沿发丝切线偏移的双高光瓣（主/副）。
  - 边缘光 Rim：Fresnel 项或反转法线。
- 描边两大家族：
  - 后处理边缘检测：深度/法线图 Sobel/Roberts 算子找不连续；受距离和参数影响，需要轮廓颜色可控。
  - 反转面外扩（inverted hull）：复制网格沿法线外扩、渲染背面纯色；开销与顶点数成正比，硬边会断线。
- Tonemapping：HDR→LDR 映射；ACES 近似曲线；LUT 做风格化调色。
- Substrate：UE 5.4+ 实验性材质系统，BSDF 分层组合；UE 5.8 有实验性 **Toon BSDF + Toon Profile**（你的 NPR_rendering 主线）。

### 关键细节
- Translucency Before Water：半透明物体在水体之前渲染的排序开关，解决水面与半透明互相遮挡的排序问题。
- 溶解（Dissolve）：噪声纹理 + 阈值裁剪（OpacityMask），边缘发光用阈值带宽度控制。
- Decal：延迟贴花投影到 G-Buffer；颜料扩散类效果常用动态 Decal + 流动噪声。

### 典型追问
- 为什么金属没有漫反射？→ 金属折射光被吸收，能量几乎全在镜面反射；F0 高且带颜色。
- Toon 和 PBR 混合怎么做分层？→ 角色 Toon BSDF，环境 PBR；同一场景不同 Shading Model 并存，光源两者都响应。
- 描边 Pass 的性能成本在哪？→ 后处理是全屏分辨率成本 + 深度/法线带宽；反转面是顶点翻倍 + overdraw。

### 项目关联与待自查
- 自定义 Shading Model/描边是 **UE5.5 历史能力（B/C 级）**，源码不在 Iris；面试必须分开讲"历史实现 vs 当前 UE5.8 原生 Toon"，不能混成一套。
- GGX、Fresnel 等基础概念需连接到实际材质选择；个人掌握情况待问答确认。

## 3. Niagara 粒子系统

### 核心概念
- 层级：System → Emitter → Module；数据流是属性（Attribute）表，Module 是读写属性的节点。
- GPU Compute Sim：粒子全部常驻 GPU buffer，更新用 CS 执行；CPU 不可逐粒子访问（读回昂贵）；要求 Fixed Tick（固定步长）保证确定性。
- Simulation Stage：可编程迭代阶段，可对每粒子执行任意逻辑，支持多轮迭代——PBF 约束求解、邻域 gather 都放这里。
- Data Interface（数据接口）：Niagara 与引擎资源的桥：
  - Grid2D/Grid3D Collection：网格化读写（原子写入归约，SSPR 的 Stage A 用它做密度累加）。
  - NeighborGrid3D / NeighborQuery：空间网格邻域查询；`AddParticleWithRadius` 注册、按半径 gather 邻居（SSPR RecordPoint 候选）。
  - Render Target：粒子写像素（生成 SDF/密度图）。
  - Particle Attribute Reader：跨 Emitter 读取粒子属性（封装 `SSPR_Reader` 读 Position/Velocity 的机制）。
- 事件（Events）：粒子间/位置事件驱动生成与销毁。

### 关键细节
- GPU sim 的性能模型（SSPR 用的口径）：投影 O(N)，邻域处理 O(q·G·k)（q 邻域遍历次数、G 处理像素数、k 平均邻居数），材质解析 O(G)。
- GPU sim 的坑：粒子属性无 CPU 可见性；System 级 DI 在 5.8 有限制（SSPR 被迫用 Emitter 级）；side-effect-only `AddParticle` 有引擎警告。

### 典型追问
- GPU 粒子怎么做邻域查询？→ 均匀网格：cell 尺寸≈作用半径；先注册（原子写桶），再 gather（读九宫格/27 宫格）。
- Simulation Stage 和普通 Module 的区别？→ Stage 可迭代、可读写外部资源（RT/Grid）、可自定义调度粒度。

### 项目关联与待自查
- [A] 这是你实习（NeighborGrid3D/Boids）和个人项目（slime、SSPR）的共同主干，邻域查询必须讲到原子/网格粒度。
- Boids 三规则（分离/对齐/聚合）+ 邻域查询成本，是实习段必考题。

## 4. 流体：SPH、PBF、SDF 与 Marching Cubes

### 核心概念
- SPH（光滑粒子流体）：粒子携带物理量，用光滑核 W 插值：密度 ρᵢ=ΣmⱼW；压力由状态方程得到；显式积分易不稳定。
- PBF（Position Based Fluids，Macklin & Müller 2013）：实时向的选择。流程：
  1. 预测位置（重力外推）；
  2. 建邻域网格；
  3. 迭代求解：密度约束 `Cᵢ = ρᵢ/ρ₀ − 1`，算 λᵢ（拉格朗日乘子），按 spiky 核梯度移动粒子；
  4. 人工压力 s_corr 防粒子聚簇；
  5. 更新速度，XSPH 粘性、涡度约束（vorticity confinement）补回细节。
  - 关键参数：静止密度 ρ₀、核半径 h（决定网格 cell 大小）、迭代次数、子步数。
- PBD：位置基动力学通用框架（约束投影），PBF 是它的流体特化；实习的"PBD 粒子碰撞"即同类约束投影思想。
- 粒子 → SDF：把粒子集合写成连续标量场。对每个网格点累加核贡献 `Σ w(|x−p|/h)`，平滑核选两端导数为零的（Hermite smoothstep `t²(3−2t)`），避免尖锐 `t³` 造成块状明暗；等值面即表面。
- Marching Cubes：遍历每个体素立方体，8 角场值符号得 256 种情况（对称归并为 15 类），查边交点插值出三角形。问题：经典表存在拓扑歧义（case 3/6/13 等），需 Asymptotic Decider；法线用场梯度（中心差分）。
- SDF 法线：`n = normalize(SDF(x+d) − SDF(x−d))`；**单边差分会引入方向偏差→块状明暗带**（slime 项目实际踩过，改中心差分解决）。

### 关键细节
- slime 项目实测链：Niagara GPU `PBFSim` → `WriteToSDF`（64³ 网格，平滑支持半径 `ParticleRadius×SmoothIntensity×1.35`）→ `MarchingCube` 生成网格 → Default Lit 材质；PIE 基线帧 P50 15.75 ms、GPU P50 14.82 ms、Niagara GPU Compute 约 1.28 ms。
- 完整链：粒子模拟 → 密度/SDF 场 → Compute → Mesh → 材质渲染，每段的分辨率/网格尺寸都要能报。

### 典型追问
- 为什么选 PBF 不选 SPH？→ 隐式约束投影无条件稳定、可大时间步、易控预算；SPH 压力显式积分易爆。
- Marching Cubes 为什么会有洞或裂缝？→ 歧义情形处理不当、场不连续、网格与体素边界不对齐。
- SDF 分辨率怎么定？→ 按表面最薄特征尺寸定体素大小；64³ 是性能与细节的折中（你的实测口径）。

### 项目关联与待自查
- 先解释粒子数、迭代次数、网格分辨率分别影响什么；具体运行规模按需查原记录。

## 5. PCG 与 Landscape

### 核心概念
- PCG（Procedural Content Generation）：PCGGraph 资产 + 场景里 PCGComponent/PCGVolume 执行。节点图：采样 → 过滤 → 变换 → 生成。
- 关键节点：Surface Sampler（按表面积密度出点，可取 Landscape）、Volume Sampler（体采样）、Filter by attribute（高度/坡度/法线）、Transform Points、Intersection/Union、Static Mesh Spawner。
- Mesh Selector：`PCGMeshSelectorWeighted` 按权重随机选网格（你的五张图统一用它）。
- Landscape：Component 网格 + 高度图 + 层权重贴图（Layer/Weightmap）；LOD 分块；`bLandscapeUsesMetadata=True` 让 PCG 直接读 Landscape 层数据而不是射线采样。
- 实例化渲染：ISM/HISM（层级实例化）合并 draw call；PCG Spawner 输出进实例组件；`CullingCellSize` 控制剔除粒度。
- CPU vs GPU PCG：`bExecuteOnGPU=False` 表示全 CPU 执行生成；GPU PCG 目前覆盖面有限。

### 关键细节（你的五张图）
- CliffScatter/FloorDebris/CoastalWetland/Groundcover：Landscape → Surface Sampler → 高度/坡度过滤 → Spawner；Groundcover 多次向下 Raycast 贴地；CliffMossAccent：Volume Sampler → 四向 Raycast 找崖壁 → Merge/Rotation/Intersection → 双 Spawner。
- 公共设置：CPU、2D Grid256、Landscape metadata、Weighted Selector、CullingCellSize=2048、统一实例合并。

### 典型追问
- PCG 为什么拆多张图？→ 按地表语义分职责，独立调密度/资产/性能，避免单图耦合。
- 生成结果怎么验证？→ 关卡组件覆盖、生成点数量、剔除后实例数——**这正是你没导出的部分**。

### 项目关联与待自查
- 先讲图结构、生成规则与参数效果；实例数按需查阅，不要求主动讨论证据导出。

## 6. 海洋与岸线

### 核心概念
- SingleLayerWater：UE 水体 Shading Model——平面折射/吸收、深度衰减、反射（SSR/平面）、半透明排序；你的简历"半透明遮挡与远近景过渡"即此。
- 波形表示：Gerstner 波（解析位移波）、FFT 海洋（统计谱）、VDM（Vector Displacement Map，Houdini 烘焙的矢量位移贴图动画顶点）——你的 FluidFlux VDM 迁移属这类。
- 无限水面：相机跟随网格 + 顶点着色器按相机位置吸附网格/偏移 UV（`NS_InfiniteMesh` 思路），配合视距裁剪。
- 岸线处理：岸线距离场（SDF/Height）驱动波高衰减、泡沫强度、贴岸浪；`MF_CoastlineWave` 即此链路。
- 泡沫：波峰曲率/深度梯度生成泡沫遮罩，滚动噪声贴图。
- Height Capture：Niagara/RT 捕获水面高度供岸线交互（`BP_HeightMapCreate1`）。

### 关键细节
- 四条链要分开讲：水面形状（VDM/Gerstner）、岸线遮罩（SDF/Height）、泡沫法线细节、视距裁剪与远景低模。
- FluidFlux 是你改造的内部代号方案（基于 `/Game/Materials/DemoPublic/Wave`），不是商店插件调用。

### 典型追问
- VDM 相比高度图波的优势？→ 存 XYZ 矢量位移，能表现卷曲/翻卷波形（curl），高度图只有 Y。
- 远海面怎么省？→ 视距裁剪 + 远景低模/简化材质 + 降低采样频率。

## 7. 体积云与大气

### 核心概念
- 光线步进（Raymarching）：沿视线分步采样密度场，累积透射与散射。
- Beer-Lambert：透射率 `T = exp(−τ)`，光学深度 `τ = ∫σₜ ds`（消光系数沿路径积分）。所有体积渲染的数学地基。
- 相函数：散射角分布。Henyey-Greenstein：`p(θ) = (1−g²)/(4π(1+g²−2g·cosθ)^1.5)`；云常用双瓣 HG（前向 g≈0.6~0.8 + 后向 g≈−0.2）。
- 多重散射：完整解昂贵；常用近似：能量补偿/二次散射近似（Frostbite 方案的 powder 效应——薄云边缘更亮）。
- UE 原生 Volumetric Cloud：`AVolumetricCloudComponent` + 体积材质；屏幕空间 raymarch + 时域重投影复用历史帧；材质输出 CloudExtinction/CloudAlbedo/CloudPhase/CloudMultiScatterFactor/CloudLayerSampleCount 等属性。
- 云材质配方：3D 形状噪声（低频体）+ detail/erosion 噪声（高频侵蚀）+ Domain Warp（坐标扭曲）；语义密度图集控制大尺度形态。
- 优化技术：AABB/SDF 空域裁剪（跳过无云区域）、Conservative Density 跳步（用保守密度上界大步跳过稀薄段）、降低采样数 + 时域去噪。
- Volumetric Fog：froxel（视锥体素）体积雾，与云是不同系统。

### 典型追问
- 为什么云要时域重投影？→ 每帧全分辨率步数太贵，低采样 + 历史帧混合是画质/成本平衡点。
- 相函数 g 值对画面影响？→ g 越大前向散射越强，逆光云边缘越亮（银边效果）。
- 怎么控制云"消散"？→ 密度阈值/覆盖度参数 + 侵蚀噪声强度。

### 项目关联与待自查
- 你的云证据是 B 级（材质图结构 + 参数方向）；13 个数据纹理缺 sidecar。讲设计与链路可以，被问具体纹理资产接线要声明未导出。
- Bifrost 天气系统（W0）**未完成已归档**，不要提天气状态机已交付。

## 8. VDB / NanoVDB / SVT 与 Gaussian 体积代理

### 核心概念
- OpenVDB：稀疏层级网格。树结构：Root（哈希表）→ Internal 节点 → Leaf（8³=512 体素块）；只存有数据的 active 区域。
- NanoVDB：VDB 的线性化 GPU 布局；PNanoVDB 是 C/HLSL 访问层；Fp8/FpN 是叶子压缩编解码（FpN 按误差阈值自适应位宽，你的基线 absolute error=0.001）。
- HDDA：分层 DDA 光线遍历——按树的层级跳空区（empty space skipping），是 VDB raymarch 的效率核心。
- UE SVT（Sparse Volume Texture）：把 VDB 转成分页 3D 纹理（类似虚拟纹理：page table + 按需驻留 mip），引擎原生采样。
- 3DGS（3D Gaussian Splatting）：场景=各向异性高斯集合，每个高斯有 位置 μ、协方差 Σ=R·S²·Rᵀ（scale+旋转四元数）、不透明度 α、颜色（SH 系数）。
  - 渲染：投影到屏幕成 2D 高斯（Σ'=J·W·Σ·Wᵀ·Jᵀ），按深度排序，逐像素 α 混合 `C=ΣcᵢαᵢΠ(1−αⱼ)`。
  - 训练：可微渲染，loss=(1−λ)L1+λ·D-SSIM，Adam；densify/prune：2D 梯度大的克隆/分裂，低 opacity 剪枝。
  - 体积化（Don't Splat Your Gaussians 路线）：高斯表示密度场，沿射线有**解析积分**（一次算完光学深度，免逐步采样）——这是相对 VDB 采样的结构性优势。
- 你的 GaussianVolume 冻结管线：VDB density → dense NPY → 多视角 teacher → 标准 3DGS 训练（iteration_15000，311,993 点 64 B/点）→ 冻结几何烘焙六轴（±X/±Y/±Z）光程 τ → 紧凑 PLY → UE：GPU preprocess/sort → Hardware Quad Raster（每高斯一个四边形，G37 按 AlphaCutoff 收缩 quad）→ DGSM 方向光重光照 → Joint Bilateral Composite（G35 边界双边）。
- DGSM：项目内方向光阴影/重光照模块（配合 `bEnableRNGDGSM`）；面试前按 `SOP-VDB-TO-GS-G35.md` 复核精确展开名，避免现场说错全称。
- 神经渲染（Neural Render Lab）：teacher 光线步进 → student 用 triplane（三张正交特征平面，三线性采样拼接）+ tiny MLP（3 层宽 64）一次求值近似；FP16 导出权重进 UE Global Shader 实时推理；held-out 视角 PSNR 验证。

### 历史测量参考（按需查阅）
- GS feature `1.093 ms` vs SVT `3.241 ms`（约 1/2.97）；净新增 RHI `66.476 MiB` vs `305.566 MiB`（−78.245%）；整进程 2343.980 vs 2664.178 MiB（−12%）。RTX 5060、1080p、UE 5.8、Development `-game` 冷进程。
- PLY payload 19.043 MiB 只是资产体积，不是 working set——口径不能混。
- 边界：中远景静态云、单方向光+天光；近景、动画、多光源、通用 VDB 替代全部不承诺。
- 六轴 τ 的动机：静态方向光下每核预烘焙 6 方向光程，运行时按灯向插值，O(1) transport；代价 12 B/kernel。

### 典型追问
- 为什么高斯沿射线解析积分比 HDDA 采样省？→ 连续核一次闭式解 vs 每步三线性采样循环；但近景 overlap 爆炸时高斯反而吃亏。
- 3DGS 为什么要排序？体积化后还需要吗？→ splatting 混合顺序敏感；纯光学深度（optical depth）公式下可交换免排序，但运行时实现仍可含 sort。
- 六轴 τ 插值对任意灯向的误差怎么控制？→ angular sigma 控制插值核宽度；项目用 `angular_sigma=0.5`。

### 项目关联与待自查
- 优先解释体积数据、训练、渲染、重光照和优化的完整过程；数字按需查阅。
- 历史倍率留在简历参考中按需核对，不据此安排复习顺序或推断为笔误。

## 9. 性能分析与图形调试

### 核心概念
- ProfileGPU / `stat gpu`：UE 内置 GPU 层级计时；RDG event 注册让自定义 pass 可见。
- 测量口径分层：**单 pass 时间 < feature 时间（该功能全部 pass 之和）< 整帧 GPU 时间 < 整帧含 CPU**——简历数字必须声明在哪一层。
- 统计量：median（P50）抗异常，P95 看尾延迟；固定场景/机位/分辨率/硬件，冷进程（`-game` 重启）测显存避免编辑器噪声。
- RHI working set：`rhi.DumpMemory` 归因到具体资源；区分 常驻 vs transient、净新增 vs 整进程。
- Fill-rate / overdraw：像素成本 = 覆盖像素 × 每像素成本；贴脸爆炸的根因。
- RenderDoc：截帧 .rdc；Replay API（Python/qrenderdoc）枚举事件、读 Draw Call/Shader/Texture/Pipeline State，做自动化拆解（RenderDocMCP）；游戏注入涉及 D3D12 hook 与 NVAPI/Streamline 兼容。

### 典型追问
- 怎么判断一个 pass 是带宽瓶颈还是计算瓶颈？→ 减少采样次数看时间变化 / 换 ALU 换带宽；或看 GPU 计数器。
- 显存"节省"为什么必须分口径？→ 资源自身 ≠ RHI 增量 ≠ 整进程（你的 78.2% vs 12% 就是例子，主动讲是加分项）。

### 项目关联与待自查
- 用一次真实优化解释瓶颈、观测、修改与代价，不以背诵测量小数判断理解。

## 10. 工具链：MCP、UEAgent、Python 生态

### 核心概念
- MCP（Model Context Protocol）：JSON-RPC 2.0 over stdio/SSE；server 暴露 tools/resources/prompts；FastMCP 是 Python 快速实现框架。
- RenderDocMCP 架构：Replay API 读 .rdc → 文件 IPC 传大 payload → MCP server 暴露查询工具 → 生成报告。
- UEAgent：Native MCP 是 server，Gateway 是客户端，VibeUE 承载类型化执行。当前 Protocol 3.0 已移除普遍快照、OCC/hash 检查、签名保存 token 和重复发现检查；复习会话绑定、执行、按需缓存、针对性读回及简化原因，以项目当前 Brief 为准。
- Python 科学栈：PyTorch/CUDA 训练，NumPy/SciPy 数值，OpenEXR/plyfile 数据格式，Numba 加速。

### 典型追问
- 为什么用文件 IPC 不直接塞 JSON？→ MCP 消息尺寸与转义成本，大 payload 落盘传路径更稳。
- OCC 解决什么？→ 并发改同一资产时按版本号检测冲突，避免静默覆盖。

## 11. 实习段专项（PBD/Boids/VAT/Houdini/Grid3D）

### 核心概念
- Boids：分离（避撞）、对齐（速度一致）、聚合（向中心）三规则 + 邻域查询；大规模时邻域查询是主要成本（网格分桶）。
- VAT（Vertex Animation Texture）：把逐帧顶点位置/法线烘焙成纹理，运行时 VS 采样播放——便宜地播放复杂动画（布料、破碎）；RBD VAT 即刚体破碎烘焙。
- Grid3D 动态分配：按活跃区域动态分配网格块而非全量网格，降低内存与遍历成本（光子 R 实习优化点）。
- Houdini 管线：SOP 网络 + VEX；树木生成（L-system/空间分割生长）、法线平滑与插值烘焙、VDM/VAT 烘焙导出到引擎。

### 典型追问
- VAT 的代价？→ 纹理内存、无实时物理响应、动画固定；适合大量重复实例。
- Boids 一万只怎么保证帧率？→ GPU compute + 网格邻域 + 限制每粒子邻居数上限。

### 项目关联与待自查
- 实习内容证据等级 C/B（公司资产不在 Iris），讲方法论与流程，不讲具体项目内部数据；空气墙有 AirWall 归档方案可展开（Spline+Niagara+碰撞代理、视觉碰撞解耦）。

## 自查方法

1. 逐节自问：核心概念能不能不看卡讲 2 分钟？能否解释数据流、选择理由和一次排查？
2. 标出薄弱节后回到本文件对应的【典型追问】自测。
3. 所有涉及项目数字的表述，最终以正本 `notes/resume-tech-stack-analysis.md` 的证据等级与边界为准。
4. 发现新薄弱点，回 `work/review/BACKLOG.md` 加条目，或在 LOG 记录。

