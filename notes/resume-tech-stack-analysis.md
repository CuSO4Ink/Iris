# 技术美术简历技术栈分析

> 状态：简历主张与历史证据参考；面试复习主入口为 [项目过程与技术挖掘](../work/review/PROJECT-INTERVIEW-MAP.md)  
> 最近核验：2026-08-25（补丁所载核验记录；本次未重新核验外部资产）  
> 适用范围：简历技能栏、项目描述、作品集说明和面试复习  
> 不包含：个人联系方式、投递记录和与技术证据无关的自我评价

## 结论

当前最准确的候选人定位是：

> 以 Unreal Engine 实时渲染为主线，能够把材质、Niagara GPU、PCG/Landscape、
> 动态表面重建、海洋、体积云、Gaussian 体积代理、图形调试和 AI/MCP 工具链
> 组合成可验证、可分析性能的技术美术方案。

核心技能栏可收敛为：

`Unreal Engine 4/5 · C++ · HLSL/Compute Shader · Niagara GPU · PBR/NPR · PCG/Landscape · Houdini · RenderDoc/ProfileGPU · Python/MCP · VDB/3DGS`

不要把所有底层算法和依赖库堆进技能栏。PBF、Marching Cubes、DGSM、RDG、
SceneViewExtension、FastMCP 等更适合放在对应项目描述或面试展开中。

## 证据口径

本文使用三级证据，避免把“简历写过”“项目讨论过”和“实现已验证”混成同一强度。

| 等级 | 含义 | 可用于什么表述 |
| --- | --- | --- |
| A · 已验证 | 有源码、配置、资产引用审计、UEAgent `LIVE_READ`、运行回读或冻结测量 | 可写“实现、完成、搭建、优化”，同时保留明确边界 |
| B · 有支持 | 有当前项目 Brief、缓存、技术记录或可恢复实现说明，但缺完整运行态或部分资产 | 可写“负责、搭建、接入、参与”，避免过细参数和绝对性能结论 |
| C · 简历/历史口径 | 只有简历文字、历史能力图或已退出方案；源码和当前资产证据不足 | 只能作为待补证据的经历描述，不能把推测说成已验证事实 |

发生冲突时按以下顺序判断：

1. 当前源码、资产与同一 Editor epoch 的权威读取；
2. 已保存资产审计、Reflect Cache 和冻结测量；
3. 当前项目 `AI-BRIEF.md`、规格和最终报告；
4. 历史日志、旧计划和能力映射；
5. 简历原文。

时间也属于证据：后期 `Landscape2` PCG 的资产引用与 `LIVE_READ` 可以覆盖早期
“不用 Landscape、不用 PCG”的范围决策，但不能自动证明关卡实例覆盖和最终运行点集。

## 来源登记

### 外部输入

| 来源 | 位置 | 说明 |
| --- | --- | --- |
| 原始简历 | `C:/Users/mafuyuena/Downloads/resume-review-pack/resume.pdf` | SHA-256 `B155B9757EE61F58D7570EF394931B8C17F000F8F1AA0EC6E3A90F4370C1FE02`（补丁记录于 2026-08-25 在来源机器复验一致） |
| 复习包 | `C:/Users/mafuyuena/Downloads/resume-review-pack/` | 轻量离线证据包，不含 `.uasset`、`.umap` 和完整运行数据；本机仍使用原登记路径，补丁来源机器使用 `C:/Users/violina/Downloads/` |
| PCG 在线读取 | `cache/pcg/pcg-live-read.md`（相对复习包） | 5 个 Graph 的节点、边、设置和 Weighted Mesh Selector 资产 |
| PCG 汇总 | `cache/pcg/pcg-verified-summary.json`（相对复习包） | 关卡引用、Graph 状态和剩余缺口 |
| 复习卡 | `resume-review.md`（相对复习包） | 按面试顺序整理的技术讲解卡与高频追问 |
| 证据索引 | `evidence-index.md`（相对复习包） | 项目、Reflect Cache 与证据缺口索引（394 条 manifest，`/Game/Bifrost` 265 条） |

### Iris 内部依据

- [AIEffectFoundry capability map](../archive/AIEffectFoundry/AIEffectFoundry_CapabilityMap.md)
- [NPR rendering brief](../work/NPR_rendering/AI-BRIEF.md)
- [Slime brief](../work/slime/AI-BRIEF.md)
- [SSPR brief](../work/SSPR/AI-BRIEF.md)
- [Bifrost archived brief](../archive/Bifrost/AI-BRIEF.md)
- [Bifrost historical brief](../archive/Bifrost/HISTORICAL-BRIEF.md)
- [GaussianVolume final brief](../archive/GaussianVolume/AI-BRIEF.md)
- [GaussianVolume performance report](../archive/GaussianVolume/PERFORMANCE-VDB-VS-G35-G37-20260731.md)
- [UE Neural Render Lab brief](../work/UE-NeuralRender-Lab/AI-BRIEF.md)
- [RenderDocMCP index](../work/RenderDocMCP/README.md)
- [UEAgent brief](../work/UEAgent/AI-BRIEF.md)
- [UEAgent stack manifest](../work/UEAgent/STACK-MANIFEST.json)
- EffectPipeline progress（记录已删除，历史见 Git `45e55bb`）
- [Abyss asset reference audit](../research/abyss-assets/Abyss_Asset_Reference_Audit_2026-08-14.xlsx)

## 技术栈总表

### 引擎、编辑器与内容系统

- [A] Unreal Engine 4、Unreal Engine 5；当前个人工程证据具体到 UE 5.8/5.8.1。
- [A] UE Material、Material Instance、Blueprint、Animation Blueprint、Sequencer。
- [A] Niagara、GPU Compute Sim、Simulation Stage、Grid Data Interface、Render Target。
- [A] PCG Graph、Landscape Data、Surface/Volume Sampler、World Raycast、Weighted Static Mesh Spawner。
- [B] Houdini、SideFX Labs；用于树木资产、法线流程、VAT/VDB/VDM 等内容管线。
- [A] RenderDoc、ProfileGPU；项目规格还使用 Unreal Insights 作为帧序列证据工具。

### 编程、Shader 与渲染扩展

- [A] C++、HLSL、Custom HLSL、USF、USH、Compute Shader、Vertex/Pixel Shader。
- [A] UE RHI、RDG、RenderCore、Renderer、Global Shader、SceneViewExtension、StructuredBuffer。
- [A] D3D12、Shader Model 6、DXGI；RenderDoc 项目还涉及 NVAPI 与 NVIDIA Streamline。
- [A] Python、PowerShell、Unreal Build Tool `Build.cs`、JSON/NDJSON。
- [A] HTTP/JSON、SSE、UTF-8/Base64、SHA-256，用于 UEAgent Gateway 和可靠执行协议。

### 材质、光照与风格化渲染

- [A] PBR、NPR、PBR/NPR 混合材质。
- [A] UE 5.8 Substrate Toon BSDF、Toon Profile、角色 Toon 与 Cloth PBR 分层。
- [B] 自定义 Shading Model、自定义光照模型、材质属性和 Light 参数扩展。
- [B] Outline Pass、屏幕空间边缘光、ToneMap/ACES/LUT、Translucency Before Water。
- [A] 后处理、溶解、Decal、材质实例参数化、环境 Uber Material。
- [B] SDF 脸部阴影、Kajiya 头发高光、MatCap、ILM、Ramp/Curve Atlas 配方。
- [A] Ground/Shore/Cliff/Moss 语义分层、Biplanar、湿润/风化/覆盖层等环境材质思想；
  其中简历中的精确自动分层终态仍应与最终 UE 资产截图一起保存。

### 粒子、流体与动态表面

- [A] Niagara GPU 粒子、PBF、SDF 场与 Marching Cubes 表面链。
- [B] PBD、SPH 路线判断与约束求解经验。
- [A] NeighborGrid3D、Grid3D/NeighborQuery、粒子分桶、邻域查询和 Boids/Flocking。
- [A] VAT、RBD VAT、顶点动画播放和场景破坏管线。
- [A] 粒子 → 密度/SDF → Compute Shader → Mesh → 材质渲染。
- [A] 屏幕空间粒子投影、Particle G-buffer、Raw Moments、各向异性 Gaussian Splat。
- [B] KDE、线段/胶囊距离、MLS/RBF、双边/曲率流等可替换连续场方法。
- [A] Render Target、RGBA16F、Grid2DCollection、Front/Mean/Sigma Depth 等数据合同。

### PCG 与 Landscape

`Bifrost Landscape2` 当前有 5 个被 `/Game/Bifrost/Maps/L_Bifrost` 引用的
`PCGGraph`，并有 UEAgent `LIVE_READ` 的节点、边和设置证据：

| Graph | 职责 | 关键链路 | 证据 |
| --- | --- | --- | --- |
| `PCG_Bifrost_Landscape2_CliffScatter` | 悬崖岩石 | Landscape → Surface Sampler → 高度/坡度 → Transform → Spawner | A；资产内 Spawner disabled，关卡覆盖未导出 |
| `PCG_Bifrost_Landscape2_FloorDebris` | 地面碎石 | Landscape → Surface Sampler → 高度/低坡过滤 → Spawner | A |
| `PCG_Bifrost_Landscape2_CliffMossAccent` | 崖壁苔藓 | Volume Sampler → 四向 Raycast → Merge/Rotation/Intersection → 双 Spawner | A |
| `PCG_Bifrost_Landscape2_CoastalWetland` | 海岸湿地 | Landscape → 双高度过滤 → 低坡过滤 → Spawner | A |
| `PCG_Bifrost_Landscape2_Groundcover` | 地被植被 | Landscape → 过滤 → 多次向下 Raycast 贴地 → Spawner | A |

共同设置：

- CPU PCG，`bExecuteOnGPU=False`；
- 2D `Grid256`；
- `bLandscapeUsesMetadata=True`；
- `PCGMeshSelectorWeighted`；
- `CullingCellSize=2048`；
- 统一实例组件合并策略；
- 已读取悬崖岩石、碎石、Ivy、湿地植物、草、蕨和灌木资源及权重。

另外，UEAgent 记录了 Bifrost 中已加载的 `505×505 Landscape` Actor，并通过
`LandscapeService.ListLandscapes` 读到其分辨率、Transform、材质和 Layer。

尚未导出的部分：

- `L_Bifrost` 内各 PCG Component 的实例覆盖；
- CliffScatter 在关卡中是否覆盖启用；
- 当前生成点、剔除结果和最终实例数量；
- 固定镜头下的最终画面和性能基线。

因此简历可以写“搭建分层 PCG 散布与统一 Weighted Spawner 管线”，但暂不宜写
“五张图全部在最终关卡以某个固定实例数稳定运行”。

### 海洋与岸线

- [A] FluidFlux 代号海洋方案、SingleLayerWater、Niagara 分级平面和远景低模。
- [A] VDM 卷曲波、海岸 SDF/Height、泡沫、法线、WPO 和近远景采样。
- [A] `M_Wave_Base`、`MF_CoastlineWave`、`NS_InfiniteMesh` 及水材质表达式缓存。
- [B] 海面、岸线、Height Capture 与关卡接线；轻量包不含完整 `.umap` 运行态。

“FluidFlux”在本项目中不是需要依赖商店同名插件才能成立的表述。Bifrost 记录说明它是
基于 `/Game/Materials/DemoPublic/Wave` 改造并沿用内部代号的海洋方案。简历宜写成
“改造 FluidFlux/SingleLayerWater 海洋方案”，避免被理解成只会调用现成插件。

### 体积云与大气

- [A/B] UE Native Volumetric Cloud、体积材质 Master/Nubis/LookDev 实例缓存。
- [B] 语义密度图集、天气图、3D 噪声、多频侵蚀体和运行时形状组合。
- [B] Domain Warp、相函数、多重散射、AABB/SDF 空域裁剪和 Conservative Density 跳步。
- [A] Directional Light、SkyLight、Sky Atmosphere、Volumetric Fog 与云参数控制方向。

当前缓存能证明材质图结构和参数方向，但不能独立恢复全部云纹理、关卡引用和天气状态。
面试时可以讲设计与材质链，不应把未导出的纹理关系说成已在离线包完整留证。

### Gaussian、VDB 与神经渲染

- [A] VDB、OpenVDB、NanoVDB/PNanoVDB、UE Sparse Volume Texture。
- [A] VDB density → dense NPY → 多视角 teacher → 标准 3DGS 训练。
- [A] 自适应 densify/prune 几何、shared opacity、六轴静态 transport。
- [A] Compact PLY、GPU preprocess、排序、Hardware Quad Raster、DGSM、Joint Bilateral Composite。
- [A] C++ Runtime Plugin、SceneViewExtension、RDG/RHI、Global Shader。
- [A] PyTorch、CUDA、ONNX、triplane、tiny MLP、latent texture、FP16 导出。
- [A] NumPy、SciPy、Numba、OpenCV、OpenEXR/Imath、Pillow、plyfile、Matplotlib、tqdm。

GaussianVolume 最终冻结口径：

| 指标 | GS | UE SVT | 准确表述 |
| --- | ---: | ---: | --- |
| Feature time | `1.093 ms` | `3.241 ms` | GS 为 SVT 的约 `1/2.97` |
| 单体积净新增 RHI working set | `66.476 MiB` | `305.566 MiB` | 降低 `78.245%`，约为 `1/4.597` |
| PLY payload | `19.043 MiB` | 不同口径 | 不能冒充完整 GPU working set |

适用边界：静态云、中远景、单方向光加天光、既定 UE/SVT 对照；不扩展到近景 Hero、
动画、多光源、动态 GI、Shipping headline 或通用 VDB 替代。

### 图形调试、MCP 与自动化

- [A] RenderDoc Replay API、qrenderdoc Python 扩展、Draw Call/Shader/Texture/Pipeline State 读取。
- [A] Python + FastMCP、stdio MCP、文件 IPC 和报告生成。
- [A] 定制 RenderDoc C++：D3D12/DXGI Hook、NVAPI 放行与 Streamline Interposer 兼容。
- [A] UE Native MCP、EditorToolset、VibeUE、ToolsetRegistry。
- [A] UEAgent route、Reflect Cache、Doctor、Gateway、command queue、OCC、lease、receipt、
  scoped one-use save capability 和独立回读。
- [A] ProfileGPU、固定上下文采样、GPU median/p95、RHI working-set 和显存口径拆分。

### DCC、缓存与资产管线

- [B] Houdini 树木资产生成、法线平滑/插值到引擎的自动化流程。
- [B] FluidFlux VDM 迁移和八方向光照云管线。
- [A/B] ZibraVDB/VDB、Niagara SimCache/PointCache、Sequencer、World Partition 资产迁移。
- [A/B] 大资产写盘、切分、迁移、引用修复和缓存唯一性检查。
- [A] PLY、VDB、NPY、JSON、FP16 binary、Render Target、`.rdc` 等数据格式。

## 项目—技术—证据映射

| 简历方向 | 权威项目/记录 | 当前可证明 | 主要限制 |
| --- | --- | --- | --- |
| 自定义卡通渲染 | AIEffectFoundry、NPR_rendering | 历史 UE5.5 能力图；UE5.8 原生 Toon/PBR 当前资产与缓存 | 旧 Custom Rendering patch 不在 Iris；当前 NPR 不含 Outline |
| 实习空气墙/可复用材质 | AirWall（archive，2026-07-02）、EffectPipeline（已删除，历史见 `45e55bb`） | Spline+Niagara+碰撞代理系统方案、迁移上下文与设计文档 | 归档只保留方案；EffectPipeline 记录需从 Git 取回；公司 UE 资产与源码不在 Iris |
| PBF 动态表面 | slime、AIEffectFoundry | Niagara GPU PBF、SDF、Marching Cubes、材质和性能记录 | 完整 UE 资产在外部 Abyss 工程 |
| 屏幕空间粒子重建 | SSPR | 投影、Grid/RT、Raw Moments、NeighborQuery、HLSL 与性能/失败记录 | 最终视觉主线仍有未通过分支 |
| PCG/Landscape 环境 | Bifrost Landscape2、复习包 PCG `LIVE_READ` | 5 Graph、关卡引用、节点/边/参数、Weighted 资产列表 | 关卡覆盖和最终生成结果未导出 |
| 海洋与岸线 | Bifrost、水材质 Reflect Cache | SingleLayerWater、波形、岸线、无限网格和材质图 | 完整关卡运行态未进入轻量包 |
| 原生体积云 | Bifrost、云 Reflect Cache | Master/Nubis/MI 图结构和参数方向 | 13 个数据/纹理资产缺当前 sidecar |
| Gaussian 云代理 | GaussianVolume | 训练、C++/Shader、视觉 Gate、GPU/显存冻结数据 | 结论只覆盖冻结测试窗口 |
| 神经材质/神经云 | UE-NeuralRender-Lab | PyTorch/CUDA、tiny MLP/triplane、FP16、UE Global Shader | R4c UE 修正后最终 A/B 尚待复测 |
| RenderDoc 自动拆解 | RenderDocMCP | Replay API、文件 IPC、MCP、定制 RenderDoc 截帧 | 大捕获依赖外部 `.rdc` |
| Unreal AI 工具链 | UEAgent | 路由、缓存、可靠写入、回读、性能采样源码与测试 | 不等于具体项目视觉效果 |
| 实习特效迁移 | EffectPipeline（已删除，历史见 `45e55bb`） | VDB、Niagara 缓存、Sequencer、迁移和崩溃根因记录 | 记录仅存于 Git 历史；公司 UE 资产与源码不在 Iris |

## 历史项目状态快照（不用于当前复习进度）

> 快照日期：2026-08-25（含后续局部补记），并非当前核验。2026-09-07 已发现 UEAgent 协议、RenderDocMCP 位置与 NPR 后续过程过时；现状以各项目 Brief 为准。
> 面试复习表述必须与本表状态一致：归档项目只能作离线证据引用，waiting 项目的
> “待复测/待验收”部分不能说成已通过。

| 项目 | 位置 | 状态 | 支撑的复习方向 | 复习时注意 |
| --- | --- | --- | --- | --- |
| NPR_rendering | `work/` | `waiting` | 自定义卡通渲染（UE5.8 原生 Toon 一侧） | 三风格 A/B 未跑完；Outline 不在当前路线，描边表述属历史 UE5.5 能力 |
| slime | `work/` | `waiting` | PBF 动态表面重建 | 中央差分法线修正等同机位截图确认；PIE 基线帧 P50 `15.75 ms`/GPU P50 `14.82 ms` 可引用 |
| SSPR | `work/` | `active` | 屏幕空间粒子重建 | 2026-08-12 已回退 Gather-only 干净基线；HQ/Streamline 等全部为冻结失败证据，不可再引用 |
| UE-NeuralRender-Lab | `work/` | `waiting` | 神经材质/神经云 | R4c 离线数值 Gate 通过（held-out PSNR `33.983 dB`、FP16 `68,744 B`）；Z 向修正后 UE 复测与正式 GPU A/B 未完成 |
| UEAgent | `work/` | 工具主线 | Unreal AI 工具链 | 是所有 UE live 证据的入口；复习时按 route/cache/doctor/gateway 结构讲 |
| RenderDocMCP | `work/` | 工具主线 | 图形调试自动化 | 另有 TLOU2 截帧注入排查与瀑布水体拆帧记录可作展开素材 |
| EffectPipeline | 已删除 | `removed`（2026-09-05） | 实习特效迁移 | 记录只存于 Git `45e55bb`；公司资产不在 Iris，只讲迁移流程与崩溃根因方法论 |
| Bifrost | `archive/` | `archived`（2026-08-17） | PCG/Landscape、海洋、原生体积云 | W0 Weather Spine 未完成；天气系统表述只能讲设计与冻结重启条件，不能讲已交付 |
| GaussianVolume | `archive/` | `archived`（2026-08-12） | Gaussian 云代理、VDB/3DGS | 只引用 G35/G37/G38 冻结口径；结论不得扩展到近景/动画/多光源 |
| AIEffectFoundry | `archive/` | `archived` | 历史能力映射（含 UE5.5 自定义渲染） | 能力图为 C/B 级证据来源，不作当前实现主张 |

## 简历表述登记

### 可以保留

- “使用 PCG 分层散布植被并统一 Spawner。”
  - 证据等级 A；建议展开为 5 个按地表语义拆分的 Landscape2 Graph。
- “以 VDB 多视角数据训练标准 3DGS，烘焙六方向光传输并在 UE 中完成 GPU 渲染与 DGSM 重光照。”
  - 证据等级 A；必须带冻结测试边界。
- “RenderDocMCP 通过 Replay API 和文件 IPC 对接 MCP，提取帧事件与管线信息。”
  - 证据等级 A。
- “UEAgent 负责路由、缓存、任务门禁和回读。”
  - 证据等级 A；可进一步说明可靠命令队列和 scoped save。
- “Niagara GPU PBF → SDF → Marching Cubes 实时表面重建。”
  - 证据等级 A/B；工程记录充分，完整资产仍在外部 UE 工程。

### 需要限定

- “自定义 Shading Model 与描边 Pass”属于历史 UE5.5 能力记录；当前 UE5.8 NPR 路线使用原生
  Substrate Toon，不能把两者描述成同一当前实现。
- “FluidFlux”应说明为改造/迁移方案，不要暗示只是调用商店插件。
- “显存降低三分之二”可用，但优先改成冻结 A/B 的 `78.245%`，并说明是净新增 RHI working set。
- “GPU 计算消耗减少至十分之一”必须注明比较对象。最终 GS 对 UE SVT 的冻结数据是约
  `1/2.97`；若十分之一来自早期实现，应另给早期基线、分辨率和测量方式。
- 云的语义图集、多频侵蚀体和运行时关系目前是 B 级证据，不要声称轻量包可完整复现关卡。
- 光子 R 实习中“预研以标准 3DGS + Relight 替代 VDB 体积云”：面试需说明结论只覆盖
  中远景静态云窗口，不写成通用 VDB 替代或已完成全面替换；简历原文“预研…技术路线”
  表述可保留。
- 光子 R 实习中“探索高斯椭圆模拟粒子系统生成高精度流体效果（不依赖流体模拟）”
  对应 SSPR 预研；当前视觉主线存在未通过分支且 2026-08-12 已回退 Gather-only 基线，
  只能讲探索/预研与数据层验证，不讲已产出最终效果。

### 必须修正

- 简历中的“`gpt 计算消耗`”应改为“`GPU 计算开销`”。
- 简历小标题“高性能**中近景**高斯云替代”应改为“**中远景**”：冻结结论只覆盖中远景
  静态云，近景 Hero 被明确排除在承诺外，原文与证据边界直接冲突。
- 不再使用“Bifrost 没有 Landscape/PCG”的判断。那是 2026-07-07 的早期范围决策，
  已被后期 Landscape2 资产引用、`505×505 Landscape` 读取和 PCG `LIVE_READ` 覆盖。

## 历史证据缺口（非面试复习待办）

这些缺口供具体主张核实时查阅。2026-09-07 起不作为 review 主线或完成度依据，不要求为了面试重做测量、背倍率或补截图：

1. 导出 `L_Bifrost` 的 PCG Component 覆盖和最终生成点/实例统计；
2. 保存五张 PCG Graph 的关卡截图、调试点视图和固定机位性能数据；
3. 找回或重新冻结 UE5.5 Custom Shading Model/Outline 的最小源码证据；
4. 为“GPU 开销十分之一”指定比较基线，或改用 GaussianVolume 已冻结数据；
5. 导出体积云全部数据纹理、材质引用和关卡组件接线；
6. 为 PBF/Marching Cubes 保存固定粒子量、迭代数、SDF 分辨率和目标帧率；
7. 补 R4c NeuralVolumeProxy 修正后的 UE GPU A/B 和 Z 向世界锚定复测。

## 维护规则

- 本文件是简历技术栈与证据口径正本；项目自己的实现真值仍由各项目 Brief、源码和资产拥有。
- 新增或修改简历主张时，同步更新“项目—技术—证据映射”和“简历表述登记”。
- 只有证据发生变化时才更新“最近核验”日期；不要因文字润色伪造新验证时间。
- 后期权威读取覆盖早期计划时，保留时间线与适用范围，不删除旧决策的历史语境。
- 外部复习包若移动或删除，先更新来源路径并标记不可用；不要把缺失外部文件误写成项目事实失效。
- 不在本文复制大段运行日志、缓存或二进制清单；只保留结论、边界和权威入口。
- 从本文生成的 PDF/DOCX 放入 `output/resume-review/`；本文 Markdown 正本始终留在 `notes/`。
- 文件名和新目录继续遵守英文命名规则，正文可以使用中文。

