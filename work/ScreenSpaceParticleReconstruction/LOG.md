# Screen Space Particle Reconstruction · LOG

### 2026-07-28 — [根因修复] RT 与粒子比例错位：ScreenPosition 节点存在但 UV 连线实际失败

用户观察到内部 SimRT 已经显示，但轨迹相对真实粒子同比例放大，体感像 Niagara 面片被推向摄像机。现场读取材质图确认 `MaterialExpressionScreenPosition` 节点存在，但 `TrajectoryTexture` Texture Sample 的 Connected Inputs 为空。创建脚本错误使用输入名 `Coordinates`；UE 5.8 的真实输入名是 `UVs`，而 `ConnectMaterialExpressions` 的失败此前未检查。已改为强校验连接 `ScreenPosition.ViewportUV -> TextureSample.UVs`，重编译并保存材质，运行时回读确认 Texture Sample 的输入源为 `MaterialExpressionScreenPosition`。因此显示采样与 Niagara `View.WorldToClip` 投影统一使用 Viewport UV，比例不再依赖面片世界深度和尺寸。

同次排查发现验证关卡同时运行两个不同位置的 `NS_SSPR_ParticleTrails_Main` Actor；激活脚本现优先保留 `SSPR_ParticleTrails_Main`，将重复实例设为不可见、关闭 Tick 和 Auto Activate，不删除资产。另修复 PIE 自动化的 Python 生命周期：所有验证脚本改为 `main()` 局部作用域，请求执行器改用独立 globals 并在 `finally` 中 clear + Python GC。连续两轮“进入 PIE -> 非零 RT 回读 -> 退出 PIE”均通过，UnrealEditor 与 MCP 保持存活，未再触发 `PlayLevel.cpp:553` 的旧 PIE Package 引用断言。

> 决策流水。追加式，新条目加在**文件末尾**。只记录决策、否决方案和重要发现。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

### 2026-07-22 16:47 — [决策] 先搭可插拔架构，不锁定密度算法
项目主干固定为粒子投影/分桶、场处理、Particle G-buffer、材质解析四层；KDE、各向异性 splat、MLS/RBF、深度平滑等都作为可替换 Field Operator。

### 2026-07-22 16:47 — [决策] 材质与场重建解耦
场处理层只产出标准化深度、厚度/密度、法线相关量和粒子属性；水、烟、能量、卡通等外观由 Resolve Material 组合，避免每种效果重写前端粒子管线。

### 2026-07-22 16:47 — [发现] 参考文档用于算法候选而非架构前提
RBF/各向异性 MLS 可用于特定线状点云边缘，但不应绑死基础设施；有序线链、无序点云和液体粒子的几何前提不同，应允许选择不同 Field Operator。

### 2026-07-22 16:47 — [决策] 保留每像素深度重建能力
相机朝向广告牌只作为材质载体，不把"跟随相机旋转"当作三维信息；需要立体感时由 RT 深度与逆视投影矩阵恢复视图/世界位置。

### 2026-07-22 17:00 — [发现] Niagara Fluids 有同构分层，但不是同一坐标域
Niagara Fluids 已有源粒子 scatter 到 Grid2D/Grid3D、Simulation Stages 处理、Renderer/Material 消费的分层；Grid3D Gas 和 FLIP 保留模拟域数据，公开资料未证明其通用模板采用每帧屏幕空间前后深度 G-buffer。
来源：Epic `fluid-simulation-in-unreal-engine---overview`、`niagara-fluids-reference`；80 Level 对 Epic TA Asher Zhu 的 Niagara Fluids 拆解。

### 2026-07-22 17:00 — [发现] Niagara 3D Liquid 是最近的表面重建参照
公开拆解包含 PIC/FLIP、粒子球 rasterizer、SDF/Jump Flood 与水材质路径，本质同样是"粒子 → 连续表面表示 → 材质"，但其目标是液体表面，不是通用的可插拔 Particle G-buffer。
来源：https://80.lv/articles/working-with-niagara-fluids-to-create-water-simulations

### 2026-07-22 17:00 — [发现] FluidNinja LIVE 更接近场缓冲与表现解耦
Fab 公开功能确认 LIVE 可把 Density、Velocity、Pressure 暴露到 Render Targets，支持 Niagara 双向数据流并驱动 Niagara/Volume 组件；其接口思想可直接参考，但公开资料不足以把它等同于"3D 粒子经相机矩阵投影为前后深度"。
来源：https://www.fab.com/ja/listings/80fcf53e-49f7-4635-a71c-ba81280c6618

### 2026-07-22 17:00 — [决策] 借鉴接口，不复制求解器
从 Niagara Fluids 借鉴 Grid/Simulation Stage/scatter/debug slice，从 FluidNinja 借鉴 RT 暴露、组件化和 Niagara 双向数据；项目仍保留独立 Projection 与 Field Operator 接口，不绑定 FLIP、2D Navier-Stokes 或某个商业插件的数据布局。

### 2026-07-23 11:34 — [发现] 与官方 Niagara 水渲染是同构而非一模一样
官方文档明确：3D FLIP 把粒子 splat 到模拟空间三维网格，再把网格作为表面 ray march；本项目则投影到当前视图的二维网格/RT，再用深度和密度解析 2.5D 表面。两者同为"粒子 → 连续场 → 材质"，但坐标域、信息保真度和多视图成本不同。

### 2026-07-23 11:34 — [发现] 单平面广告牌对应 Niagara 的另一条官方路径
Epic 文档明确 2D Gas 可始终朝向摄像机并模拟 3D 感，2D FLIP 的域通常也与摄像机对齐；这支持单层二维场作为实时特效方案，但它主要提供视角相关的 3D 感，不等价于带每像素深度重建的液体表面。

### 2026-07-23 14:40 — [决策] 用 UEAgent MCP 在 precisefluid 工程内做投影层活体验证
验证工程 `D:\Work\Company\Advance\Fluid\precisefluid`（UE 5.8 源码引擎 `C:\Work\UEEngine\UnrealEngine-5.8.0-release`）。经 UEAgent MCP（端点 127.0.0.1:8000）新建干净系统 `/Game/SSPR_Validation/NS_SSPR_ProjTest`（模板 DefaultSystem + Minimal 发射器 ProjParticles），隔离验证投影层，不混入 NiagaraFluids 模拟逻辑。已独立验真发射器切换为 GPUComputeSim。清理方式：整目录 `/Game/SSPR_Validation/` 可删。

### 2026-07-23 14:40 — [发现] 投影层不必自研 HLSL，UE 5.8 已内置 GPU 相机/投影函数
Niagara 内容库自带 `/Niagara/Functions/GBuffer/WorldPositionToScreenUV` 与 `ScreenUVToWorldPosition`（世界↔屏幕 UV 双向映射），以及 `/Niagara/Functions/Camera/` 下 GetClipSpaceTransformsGPU、ProjectionMatrix、GetViewPropertiesGPU、GetViewSpaceTransformsGPU。Projection layer 第一版可先用官方函数验证正确性，Custom HLSL 只在自定义分桶/场处理时再上，实现风险大幅下降。

### 2026-07-23 14:40 — [发现] 第一版投影用 Niagara 内置渲染 View 矩阵，多视图后置
Niagara GPU sim 取到的是当前渲染视图矩阵，编辑器单视口验证够用；多视图/VR 需显式传入指定相机 VP，列为后续 BACKLOG，不阻塞正确性基线。

### 2026-07-23 16:10 — [发现] Niagara Custom HLSL 里 `View.WorldToClip` 可用，投影管线编译通过
在 `NS_SSPR_ProjTest` 的 `ProjParticles` 发射器 ParticleUpdate 阶段建 scratch 模块 `SSPR_Projection`：MapGet 读 `Particles.Position` → Custom HLSL 做 `mul(float4(wp,1), View.WorldToClip)` → 透视除法得 NDC → `uv = ndc*(0.5,-0.5)+0.5`、`depth = clip.w` → MapSet 写回 `Particles.SSPR_ScreenUV`(vec2)/`Particles.SSPR_ViewDepth`(float)。ApplyChanges 返回 true，GetCompileMessages 为空。证实 Niagara HLSL dialect 直接暴露引擎 `View` uniform 的 `WorldToClip`，投影层第一版无需依赖官方 Function Script 节点即可编译通过。

### 2026-07-23 16:10 — [决策] 投影结果编码进 `Particles.Color` 做可视验证，绕开渲染器绑定缺口
VibeUE `NiagaraEmitterService` 的 renderer/module-input binding action 未 bound（issue #462），无法把自定义粒子属性直接绑到 Sprite 渲染器。因此在同一 scratch 模块内让 HLSL 追加输出 `OutColor`（R=U, G=V, B=depth ramp/5000, 屏幕外降亮 0.25），写回 `Particles.Color`，Sprite 默认消费该属性即出可视效果。整条"投影+可视化"图零错误编译通过，等待视口截图确认。

### 2026-07-23 16:10 — [发现] gateway 正确用法与全限定 toolset 名
`mcp_gateway.ps1` 用 `-Action {ping|tools.list|toolsets.list|toolset.describe|tool.call|script.execute|level.current}`；`tool.call` 传 `-Tool <全限定名> -ArgumentsFile <json>`。AssetTools 裸名会 not found，须用 `editor_toolset.toolsets.asset.AssetTools.*`；VibeUE 服务用 `VibeUE.NiagaraScratchPadService.*`。参数一律走 `-ArgumentsFile` 避免 PowerShell JSON 转义坑。

### 2026-07-23 后续 — [回滚] 推翻上面两条"编译通过=投影跑通/出效果"的结论
上面 16:10 两条把 `ApplyChanges=true`+`GetCompileMessages` 空当成"投影管线跑通、出效果"，是错的。真相：那个资产保存后**一打开编辑器就 Assert 崩溃**（Array.h:1339 数组越界，栈全在 NiagaraEditor），从未有任何可见效果，且反复保存成了"打开即崩"的坏档。教训见 E1——绝不能拿"自报/编译成功"当验收，验收只认"人能打开+能看到预期"。

### 2026-07-23 后续 — [否决] 用 MCP `NiagaraScratchPadService` 动态拼 scratch 图这条路
二分法坐实：空 scratch 模块、只加游离 Custom HLSL 节点都不崩；一旦执行 `AddPin`+`ConnectPins`（哪怕最保守的单输入 `WorldPos`+单输出 `OutDepth`+逐个加 pin），`ApplyChanges` 编译阶段即崩（资产全程关闭，排除 UI 因素，同一 Array.h:1339，栈底含 UnrealEditor-Niagara 编译帧）。即 MCP 这套动态拼 pin 会稳定产出让 Niagara 编译越界的畸形图，非操作顺序问题。→ 弃用此路（详见坑册 K11）。投影 scratch 的图/HLSL 改由**编辑器内手动搭建**，MCP 退回"只读核对+给 HLSL 代码"角色。骨架系统 `NS_SSPR_ProjTest`（Fountain+ProjParticles，Sprite renderer，已验证能打开、有粒子）保留为干净起点。

### 2026-07-23 后续 — [根因] VibeUE 崩溃三重根因（源码级坐实）
读 UE5.8 引擎源码坐实崩溃机制。崩点 = `UNiagaraNodeCustomHlsl::BuildParameterMapHistory`（编译期）用 `Signature.Inputs[i]/Outputs[i]` 按 pin 循环下标索引，守卫 `InputPins.Num()==Signature.Inputs.Num()+1 && OutputPins.Num()==Signature.Outputs.Num()+1`（+1=每方向一个 Add pin）。VibeUE `NiagaraScratchPadService` 三处偏离引擎正规流程：①`AddCustomHlslNode` 只 `CreateNode+Finalize+SetCustomHlsl`，节点没有 Add pin；②`AddPin` 用裸 `CreatePin` 绕过 `RequestNewTypedPin`，不维护 Add pin、不做名字 sanitize/唯一化；③自写 `RebuildCustomHlslSignatureFromPins` 遍历原始混排 `Pins` 按 Direction 分流，顺序与 `GetInputPins/GetOutputPins` 不一致。三者叠加使 signature 与 pin 索引失配 → `Signature.Inputs[i]` 越界（Array.h RangeCheck）。打开时 UI 用同一失配画面板同样越界，故"打开即崩"与"编译即崩"同源。

### 2026-07-23 后续 — [修复完成] 路 A：改引擎导出宏 + VibeUE 走引擎正规 API，已编译通过
引擎侧（UE5.8 源码，3 头）：`NiagaraNodeWithDynamicPins.h` 给 `RequestNewTypedPin`×2、`IsAddPin` 加 `NIAGARAEDITOR_API`；`NiagaraNodeCustomHlsl.h` 给 `InitAsCustomHlslDynamicInput` 加 `NIAGARAEDITOR_API`；`NiagaraNode.h` 把 `ReallocatePins`（原 protected，本已带导出宏）提为 public。VibeUE 侧（`UNiagaraScratchPadService.cpp`）：`AddCustomHlslNode` 建节点后调 `N->ReallocatePins()` 确保 Add pin 就位；`AddPin` 的 CustomHlsl 分支改走 `HlslDyn->RequestNewTypedPin(Dir,Type,Name)`（引擎内部维护 Add pin/唯一名/按 GetInputPins/GetOutputPins 顺序重建签名）；删除死代码 `RebuildCustomHlslSignatureFromPins`。`Build.bat precisefluidEditor Win64 Development` 增量编译 30 actions 全过，NiagaraEditor.dll + VibeUE.dll 链接成功，Result: Succeeded（~168s）。待重启编辑器后用 MCP 重跑投影 scratch 验证不再崩。踩坑：第一版用 `N->ReallocatePins()` 但它在 UNiagaraNode 是 protected → C2248，遂把声明提到 public。

### 2026-07-23 后续 — [验证通过] 路 A 修复经活体复现确认：越界崩溃根治
重启新编译的编辑器后，用 MCP 完整复现上次必崩序列（`AddCustomHlslNode` → `AddPin` WorldPos 输入 + OutDepth 输出（走新 `RequestNewTypedPin` 路径）→ MapGet/MapSet 通道 → `ConnectPins`×2 → `ApplyChanges`）。结果：`ApplyChanges` **正常返回、MCP 连接未断、编辑器进程存活**（端口 8000 通、UnrealEditor 进程 1）；上次此步直接 Assert 崩溃、连接强制关闭。判定修复成功——pin↔`Signature` 索引失配的越界（Array.h RangeCheck）已根治。`ApplyChanges` 返回 `false` 是因为进入了正常的 shader 编译并报错（不再是崩溃）。

### 2026-07-23 后续 — [发现] 占位投影 HLSL 在 CPUSim 下编译报错：`View`/`PrimaryView` 不可用
`GetSystemCompileState` 显示 ProjParticles 两个脚本 `Error`：`NiagaraEmitterInstance.ush(319/488): 'PrimaryView' undeclared` + `mul(vec4, )` 无匹配。根因：`ProjParticles` 是 CPUSim，Niagara VectorVM 环境不暴露渲染 `View` uniform（`View.WorldToClip`），只有 GPU sim shader 环境才有。这是与崩溃无关的、可预期的逻辑错误，证明链路已打通到 shader 生成阶段。下一步：把 ProjParticles 切 GPUComputeSim（此前已独立验证可切），或改用 `/Niagara/Functions/Camera/` 官方相机/投影函数，再重编投影段。

### 2026-07-23 后续 — [里程碑] 切 GPU sim 后投影 HLSL 零错误编译 + 编辑器可正常打开/scratch 可编辑
用 `NiagaraToolset_System.SetEmitterData`（`propertyValues:{"SimTarget":"GPUComputeSim"}`）把 ProjParticles 切 GPU，`GetEmitterSummary` 验真 `simTarget:GPUComputeSim`；再用 `SetSystemData` 启用系统级 Fixed Bounds（±5000，GPU sim 渲染前提）。`ApplyChanges` 返回 `true`（CPU sim 时为 false），`GetSystemCompileState`：`aggregateStatus:UpToDate`、`bHasErrors:false`，ProjParticles 新增 `ParticleGPUComputeScript` 且 UpToDate，之前 `'PrimaryView' undeclared`/`mul(vec4,)` 错误全消失——证实 `View.WorldToClip` 在 GPU sim 下可用。已保存。**用户实机确认**：资产正常打开不崩、粒子正常、且 scratch 模块**能双击进去、能看到 MapGet→HLSL→MapSet 连线**——即"崩溃"与"点不进去"两大痛点经路 A 修复同时根治，MCP 现在产出结构健康、可编辑的标准 scratch。下一步：把 depth/UV 编码进 `Particles.Color` 做可见验证。

### 2026-07-23 后续 — [发现] 颜色可视化做在错误的发射器上——系统是双发射器
在 `ProjParticles` 的 `SSPR_Projection` 里把投影结果编码进颜色：HLSL 追加输出 `OutColor`（R=屏幕U、G=屏幕V、B=归一化深度 clip.w/5000、屏幕外×0.25 压暗），加 `OutColor`(LinearColor) pin + MapSet 加 `Particles.Color` 写通道 + 连线，`ApplyChanges` 返回 true、`GetSystemCompileState` 全绿（新增连线共 6 条），已保存。但**用户打开后粒子仍是白色/无变化**。用户点破根因：系统里有 **两个发射器**——`Fountain`（视口里看到的喷泉粒子）和 `ProjParticles`（投影+颜色改动所在）。改的和看的不是同一批粒子，故喷泉不变色。教训：动手前先确认系统的发射器构成，别默认单发射器。

### 2026-07-23 后续 — [决策] 走 C-2：合并为单发射器（留 ProjParticles，删 Fountain，补 spawn）
用户在 C-1（把投影搬到 Fountain）/C-2（留 ProjParticles 补喷发模块，删 Fountain）/C-3 中选 **C-2**——因 ProjParticles 上 GPU sim+投影+颜色链路已就绪且验证不崩，改动最小。已完成：用 `NiagaraToolset_System.RemoveEmitter` 删除 `Fountain`，`GetSystemSummary` 验真系统现只剩 `ProjParticles`（GPU sim + Sprite renderer）。

### 2026-07-23 后续 — [进行中] 给 ProjParticles 补 SpawnRate，让其喷出可见粒子
`GetEmitterTopology` 查得 ProjParticles 模块栈：EmitterUpdate 仅 `EmitterState`（无 SpawnRate/Burst）、ParticleSpawn 仅 `InitializeParticle`、ParticleUpdate 为 `ParticleState`+`SSPR_Projection`——缺"生成粒子"模块，故粒子不显眼。`AddModule` 参数 = `moduleLocationRef`(emitter/scriptName)+`moduleAsset`(refPath)。已确认 SpawnRate 模块 asset 路径 `/Niagara/Modules/Emitter/SpawnRate.SpawnRate` 存在（`exists` 参数名是 `path` 不是 `assetPath`）。**待办**：AddModule 把 SpawnRate 加到 EmitterUpdateScript → 视需要调 InitializeParticle 的位置分布/大小/生命周期让粒子铺开 → ApplyChanges 编译 → 保存 → 用户打开验证粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度，转相机时颜色实时变=投影正确工作）。

### 2026-07-23 后续 — [里程碑] C-2 落地：ProjParticles 补齐 spawn+分布，单发射器投影链路编译级完整
按 C-2 给单发射器 `ProjParticles`（GPUComputeSim + Sprite renderer）补齐生成/分布：`AddModule` 加 `SpawnRate`（`/Niagara/Modules/Emitter/SpawnRate.SpawnRate`）到 `EmitterUpdateScript`、`SetStackInputData` 设 `SpawnRate=200`；`AddModule` 加 `ShapeLocation`（真实路径 `/Niagara/Modules/Spawn/Location/V2/ShapeLocation`，非旧 `.../Location/ShapeLocation`）到 `ParticleSpawnScript`、设 `Sphere Radius=300`（默认 Position Mode 是 `Simulation Position` 单点，故必须靠 ShapeLocation 铺开）；`InitializeParticle` `Lifetime=5`（稳态 ~1000 粒子）。最终模块栈：EmitterUpdate=`EmitterState`+`SpawnRate`、ParticleSpawn=`InitializeParticle`+`ShapeLocation`、ParticleUpdate=`ParticleState`+`SSPR_Projection`。`GetSystemCompileState` 全绿（aggregate UpToDate、无错无警、`ParticleGPUComputeScript` UpToDate），已 `save_assets`。**待用户视觉验收**：打开 `NS_SSPR_ProjTest` 确认①能打开不崩②球状粒子团喷出③粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度）④转动相机颜色实时变=投影正确。

### 2026-07-23 后续 — [发现] gateway 需 `-ExecutionPolicy Bypass`；AddModule/find_assets 参数名坑
本机 PowerShell 默认禁用脚本，调 `mcp_gateway.ps1` 必须加 `powershell -ExecutionPolicy Bypass -File ...`。`AddModule` 入参是 `moduleLocationRef`(system+emitterName+scriptName，其余 moduleName=""/rendererIndex=-1/inputNameStack=[] 占位)+`moduleAsset.refPath`；`GetEmitterTopology` 必填参数名是 `emitterRef`。AssetTools 查资产工具是 `.exists`(参数 `path`) 与 `.find_assets`(参数 `folder_path`+`name`+`recursive`，非 `path`/`name_pattern`)。

### 2026-07-24 — [里程碑·效果级通过] 基础投影验证经用户实机视觉确认
用户打开 `NS_SSPR_ProjTest` 确认四点全对：①能打开不崩 ②球状粒子团正常喷出 ③粒子按投影渐变色（R=屏幕U/G=屏幕V/B=深度）④**转动相机颜色实时变化**。第④点是关键判据——证明每帧取当前渲染 View 矩阵、`View.WorldToClip` 世界→裁剪空间投影链路真实工作，非静态贴图。项目首个经视觉验收的里程碑达成：投影层（Projection layer）从"编译级"正式升级"效果级通过"。下一步进 Field Operator A（最简各向同性粒子 splat 到 RT，作为正确性基线）。

### 2026-07-24 — [澄清·免改插件] VibeUE scratch 本就支持 DI 类型输入，先前"要改插件"判断错误
排查粒子写 RT 通路时先误判为"VibeUE 不支持 DI 类型 module input 需改插件"，根因是 `AddModuleInput` 传了全类名 `NiagaraDataInterfaceRenderTarget2D` 报 `Unknown TypeName`。读源码 `Plugins/VibeUE/Source/VibeUE/Private/PythonAPI/UNiagaraScratchPadService.cpp` 的 `ResolveType`（约 141 行）坐实：其类型白名单**已支持** DI 短名 `RenderTarget2D`/`DynamicRT`/`Grid2D`/`Grid2DCollection` 及各 `ArrayFloat*` DI，只是要用短名不用全类名。故**无需改插件**，改传 `RenderTarget2D` 即成功。教训：报"未知类型"先读 ResolveType 白名单，别急着下改插件结论。

### 2026-07-24 — [里程碑·MVP scatter 编译通] 粒子按 SSPR_ScreenUV 写入 RT 的通路搭通，全 MCP 落地不崩
建 `RT_SSPR_Occupancy`（256×256，Python `TextureRenderTargetFactoryNew`）。在 ProjParticles/ParticleUpdate 建 scratch 模块 `SSPR_WriteOccupancy`：`AddModuleInput` OccupancyRT(RenderTarget2D DI) → MapGet 读出 `Module.OccupancyRT`+`Particles.SSPR_ScreenUV` → `AddCustomHlslNode`（`GetRenderTargetSize`→`clamp(int2(UV*size))`→`SetRenderTargetValue(true,px.x,px.y,float4(1,0,0,1))`，`OutDummy=1`）→ AddPin 手动加 OccupancyRT/ScreenUV 输入+OutDummy 输出（`AddCustomHlslNode` 不自动解析变量成 pin，须手动 AddPin，走已修复的 RequestNewTypedPin）→ 连线 3 条 → MapSet 加写 `Particles.SSPR_WriteMark` 承接 OutDummy 维持执行链。`ApplyChanges` 返 true **未崩**（路 A 稳定复用），`GetCompileMessages` 空、`GetSystemCompileState` 全绿（含 ParticleGPUComputeScript），已保存。**RT DI 写入函数签名（UE5.8 源码坐实）**：`SetRenderTargetValue(bool Enabled,int IndexX,int IndexY,LinearColor Value)`（GPU only、bRequiresExecPin）、`GetRenderTargetSize()->(int W,int H)`。**待收尾**：把 OccupancyRT DI 绑定到 `RT_SSPR_Occupancy` 资产（经 `render_target_user_parameter` User Parameter 绑定，或直接开 DI 的 Preview Render Target），才能看到写入结果并做视觉验收。

### 2026-07-24 — [卡点·需UI收尾] DI-type User Parameter 绑定资产，MCP 与 Python 两路均不可自动化
用户选"规范绑定"（DI 落到真实 `RT_SSPR_Occupancy` 资产，供后续 Field Operator/材质采样，而非临时 Preview RT）。尝试两条自动化路均失败：①`NiagaraToolset_System.AddUserVariables` 传 RT2D DI 类型 user param（defaultValue 用 `NiagaraExt_VariableValue_DataInterface` + `Default__NiagaraDataInterfaceRenderTarget2D` 实例引用）返回 null，`GetUserVariables` 复查为空——MCP 对 DI 类型 user param 静默失败；②UE Python 侧 `NiagaraSystem` 不暴露任何 exposed/user parameter 编辑方法（`dir` 过滤 expose/parameter/user 全空、无 Niagara 编辑 subsystem、`find_all_objects_of_class` 不存在），拿不到 module 内 DI 实例。结论：**DI-type user parameter 绑定是当前 UEAgent 工具链硬边界，必须编辑器 UI 手动做**（属助手能力外的 UI 拖拽类操作）。scatter 写入图本身已编译通、已保存，仅差此绑定即可视觉验收。手动清单已交付用户。

### 2026-07-24 — [根因·坐实] scratch 模块"点不进去/Details空/无图标"= System 资产模式下脚本放错了 scratch 列表
彻底重启编辑器后 `SSPR_WriteOccupancy` 仍点不进、Details 空、无 scratch 图标——排除 UI 缓存。读引擎 `NiagaraScratchPadViewModel.cpp::GetOuterAndTargetScripts` 坐实根因：Niagara 编辑器按资产 edit mode 选 scratch 脚本列表——**SystemAsset 模式只扫 `UNiagaraSystem::ScratchPadScripts`（系统级）**，EmitterAsset 模式才用 `EmitterData->ScratchPads->Scripts`（发射器级）。`NS_SSPR_ProjTest` 是 System 资产，编辑器只认系统级列表。而 VibeUE `CreateScratchModule` 一律把脚本塞进 emitter 容器 → 脚本能编译、stack 有节点、`ListScratchModules` 能列出（底层数据在），但编辑器 ViewModel 扫不到 → 无 ScriptViewModel → UI 点不进。对照：能编辑的 `SSPR_Projection` 路径在系统级（`NS_SSPR_ProjTest:SSPR_Projection`），正是引擎正规流程产物。

### 2026-07-24 — [修复完成] 路B：改 VibeUE 让 System 资产模式下 scratch 脚本进系统级列表（免改引擎）
`UNiagaraSystem::ScratchPadScripts` 是 public 字段（`NiagaraSystem.h` 约 518 行，无 EDITORONLY/无需导出宏），故修复**纯在 VibeUE 内完成，未动引擎**。改 [`UNiagaraScratchPadService.cpp`](D:/Work/Company/Advance/Fluid/precisefluid/Plugins/VibeUE/Source/VibeUE/Private/PythonAPI/UNiagaraScratchPadService.cpp) 三处：①`CreateScratchModule` 增 `bSystemAssetMode = System->GetEmitterHandles().Num()!=1`，该模式下脚本 outer 用 `System`、加入 `System->ScratchPadScripts`（否则仍用 emitter 容器）；②`ListScratchModules` 查找集合并入 `System->ScratchPadScripts`，去掉"emitter 容器空即返回"限制；③`ApplyChanges` 对系统级 scratch 脚本也 `NotifyGraphChanged`+`MarkPackageDirty`。编辑函数走 `FindModuleNodeOnEmitter`（按 graph 节点名查，与脚本容器归属无关），不受影响。防崩校验 `ValidateScratchGraphsForCompile` 暂只校验 emitter 容器（少一层保护、不引错，保持最小改动）。`Build.bat precisefluidEditor Win64 Development` 增量编译 4 actions 全过，`UnrealEditor-VibeUE.dll` 链接成功，Result: Succeeded（~20s）。**待验证**：重启编辑器后删旧 `SSPR_WriteOccupancy`（emitter 容器里的坏模块）、用新逻辑重建，确认新模块在编辑器里有图标、可双击进图、Details 有 OccupancyRT 输入，再绑 RT 资产做视觉验收。

### 2026-07-24 — [修正] bSystemAssetMode 判据错误 → 改为无条件系统级
第一版补丁用 `bSystemAssetMode = System->GetEmitterHandles().Num()!=1` 判据是错的：误把引擎 `GetOuterAndTargetScripts` 里"EmitterAsset 模式内部按 emitter 数量选"抄成了顶层判据。`NS_SSPR_ProjTest` 只有 1 个 emitter → `!=1` 为 false → 又走回 emitter 容器，重建的 `SSPR_WriteOccupancy_1` 路径仍在 `NiagaraScratchPadContainer_0`、编辑器里仍无图标/点不进（但 Details 已有参数，说明系统级并入的 List/Apply 改动部分生效）。真相：edit mode 才是决定因素，emitter 数量只在 EmitterAsset 分支内部用；VibeUE 经 `LoadSystem` 编辑的恒为 System 资产 = SystemAsset 模式。故改 `const bool bSystemAssetMode = true;`（无条件系统级）。`ListScratchModules`/`ApplyChanges` 两处是"并入两个列表"，不受影响、无需再改。已删 `SSPR_WriteOccupancy` 与误建的 `SSPR_WriteOccupancy_1`，系统回到 `ParticleState`+`SSPR_Projection` 干净态。**待重编 VibeUE + 重启后重建验证**。

### 2026-07-24 — [约定] VibeUE 插件改动用 git 分支管理，基线固定 commit 保持可回滚
VibeUE 仓库（`Plugins/VibeUE`）由 bootstrap 固定在 detached HEAD `271f487`（Merge #520，5-8 分支）。为使插件改动可追溯/可回滚，新建分支 **`sspr-scratchpad-fixes`** 承载本项目所有 VibeUE 补丁，基于 `271f487`。首个提交 `8b43efa`（scratchpad 系统级归属修复，1 file +72/-67）。约定：后续每次改 VibeUE 源码，都在此分支按"改动本体"单独 commit（message 记根因+改动点），不直接在 detached HEAD 提交（会游离丢失）。回滚基线：`git checkout 271f487`。

### 2026-07-24 — [里程碑·插件修复验证通过] MCP 建的 scratch 模块现可在编辑器正常编辑
修正判据（`bSystemAssetMode=true` 无条件系统级）重编 `VibeUE.dll` 并重启后，用新逻辑重建 `SSPR_WriteOccupancy`：scriptPath 为系统级 `NS_SSPR_ProjTest:SSPR_WriteOccupancy`（不再带 `NiagaraScratchPadContainer`），完整重搭写入图（DI 输入 OccupancyRT + MapGet 读 SSPR_ScreenUV + Custom HLSL 写 RT + MapSet SSPR_WriteMark + 连线），`GetSystemCompileState` 全绿。**用户实机确认**：编辑器里 `SSPR_WriteOccupancy` ①有 scratch 图标 ②能双击进图（可见 InputMap→MapGet→HLSL→MapSet→Output 连线）③Details 有 OccupancyRT 输入——三点全对。插件补丁彻底修好"MCP 建可编辑 scratch"能力，后续所有场算子写入模块可全 MCP 自动搭建。git commit `8b43efa` 即为此正确版本。

### 2026-07-24 — [边界·确认] DI 输入绑定 RT 资产仍需 UI 手动，自动化不可达
插件补丁修的是"模块可编辑"，非"DI 输入可绑资产"。复查：①`GetStackInputData` 仍报 `Input 'OccupancyRT' not found`（官方 toolset 扫不到 scratch module 的 DI 输入命名空间）；②Python 虽能 `load_object` 拿到系统级 scratch script（`NiagaraScript`），但它不暴露 DI/rapid-iteration 编辑方法。故 OccupancyRT→RT_SSPR_Occupancy 绑定确定为 UI 手动步骤（但模块已可编辑，绑定入口正常出现）。绑定方式：System Overview 建 RenderTarget2D User Parameter 默认值设 RT_SSPR_Occupancy → 模块 OccupancyRT 输入 Link 到该 user param → 编译保存 → 打开 RT 看亮斑。

### 2026-07-24 — [修复] read-before-set 编译错误 = Interpolated Spawning 惹的祸，关掉即解
绑定前编译报错：`Particles.SSPR_ScreenUV was read before being set`（默认模式 Fail If Previously Not Set），报错点在 SpawnScript/UpdateScript/GPUComputeScript。根因：`SSPR_WriteOccupancy`（ParticleUpdate）读 `SSPR_ScreenUV`，而 GPU sim 的 **Interpolated Spawning** 会让 spawn 帧也插值执行 update 逻辑，此时投影尚未算出 → 读到未初始化属性。先试的 spawn 阶段初始化模块 `SSPR_InitAttrs`（MapSet 三属性 + 常量 HLSL 写 0）只消掉了 GPUComputeScript 报错（6→4 条），CPU 校验脚本仍报（MapGet 默认模式仍 Fail）。真正正解：`GetEmitterData` 读到 `InterpolatedSpawnMode: Interpolation`，用 `SetEmitterData`（propertyValues 须包在 `emitterData` 对象里）改为 **`NoInterpolation`** → spawn 帧不再跑 update 逻辑 → `GetCompileMessages` 空、`GetSystemCompileState` 全绿（UpToDate 无错无警）。全 MCP 自动完成，未动 UI。`SSPR_InitAttrs` 保留作双保险无害。已保存。**下一步**：UI 绑定 OccupancyRT→RT_SSPR_Occupancy 看亮斑，完成 MVP 视觉验收。

### 2026-07-24 — [根因·全黑] RT DI 绑定方式错：要绑 DI 的 Render Target User Parameter 字段，非 Link module input
首次绑定后打开 RT 全黑。`get_all_user_parameters` 查得用户建了 `OccupancyRTParam`（类型 TextureRenderTarget 引用，正确载体），但 `NiagaraDataInterfaceRenderTarget2D` 的 `render_target_user_parameter` 绑定为空 `{}`——即 DI 不知道写哪张 RT，写进了匿名临时 RT，故打开资产全黑。根因：用户上次做的"Link Inputs→User→OccupancyRTParam"绑的是 module input，而 RenderTarget2D DI 需要绑的是 **DI 内部的 `Render Target User Parameter` 字段** → 设为 OccupancyRTParam，再让该 user param 默认值指向 `RT_SSPR_Occupancy` 资产。诊断法：临时把写入 HLSL 改为"每粒子无条件在中心写 32×32 红块"（不依赖 UV），隔离绑定问题 vs UV 问题。

### 2026-07-24 — [里程碑·MVP scatter 效果通] RT DI 绑定正确后中心红块可见 = 粒子→屏幕空间 buffer 通路打通
用户按"绑 DI 的 Render Target User Parameter 字段=OccupancyRTParam"重绑后，打开 `RT_SSPR_Occupancy` **看到中心红块**——证明粒子经 scratch HLSL 的 `SetRenderTargetValue` 真实写入了目标 RT 资产，scatter 通路（粒子 → 屏幕空间 buffer）端到端打通。随即把测试 HLSL 恢复为正式按 UV 写入（`clamp(int2(ScreenUV*size))` → `SetRenderTargetValue`），编译无错、已保存。**待用户最终验收**：打开 RT 应见粒子按屏幕投影 UV 分布的红色散点，移动/转视角散点分布随之变化。此为 SSPR buffer 层首个效果级里程碑，此后可进 Field Operator A（各向同性 splat）。

### 2026-07-26 — [根因修复] RT 近似全黑 = 投影模块丢失 ScreenUV 写回
活体检查确认系统有效、ProjParticles 已启用且为 GPUComputeSim、SpawnRate=200、Lifetime=5，故排除无粒子/未激活。真正断点是 `SSPR_InitAttrs` 每粒子把 `SSPR_ScreenUV` 初始化为 `(0,0)`，而当时的 `SSPR_Projection` Custom HLSL 仅保留 `OutDepth`/`OutColor`，既没有 `OutUV` pin，也没有写回 `Particles.SSPR_ScreenUV`。于是 `SSPR_WriteOccupancy` 的所有粒子都算出像素 `(0,0)`；512×512 预览只有左上角一个像素，视觉上等同全黑。

### 2026-07-26 — [修复完成] 恢复 UV 数据链、拒绝非法写入并统一 RT/DI
已给 `SSPR_Projection` 恢复 `OutUV`(vec2)，连接到 MapSet 的 `Particles.SSPR_ScreenUV`；投影 HLSL 对相机后方和屏外粒子输出 `(-1,-1)`。`SSPR_WriteOccupancy` 重写为先检查 RT 尺寸与 `[0,1)` UV，再以 `shouldWrite` 控制 `SetRenderTargetValue`，避免旧版 `clamp` 把非法粒子堆到边缘。旧 MapGet 含两个同名 `None` 默认输入，触发 VibeUE 防崩校验，故将该 MapGet 精确重建为仅含 `Module.OccupancyRT` 与 `Particles.SSPR_ScreenUV` 的干净节点并恢复全部连线。`RT_SSPR_Occupancy` 与 RT2D DI 统一为 256×256、RTF_R16f，RT 开启 UAV、最近点过滤，DI 开启继承用户 RT 设置。Niagara 原生编译最终 5 个脚本全部 UpToDate，零错误零警告、无在途编译；System 与 RT 包均保存为非脏。VibeUE `ApplyChanges` 仍会扫描 emitter 容器里的旧孤立 scratch 副本并误报旧 GUID，但活动堆栈使用新节点，Niagara 原生编译和保存均已通过；后续应单独清理该 legacy 容器副本或收紧 VibeUE 校验范围。

### 2026-07-26 — [里程碑·效果级通过] 正式 UV Occupancy scatter 获视觉确认
用户提供的 RT 截图显示黑底上已出现大量按二维投影位置离散分布的红色像素点，不再是全黑或全部挤在 `(0,0)`；这直接证明 `SSPR_Projection.OutUV → Particles.SSPR_ScreenUV → SSPR_WriteOccupancy → RT_SSPR_Occupancy` 的正式数据链在 GPU 运行时真实生效。结合此前相机转动时投影颜色实时变化的验证，Projection 与首个 Occupancy buffer 现均达到效果级通过，可以进入 Field Operator A（各向同性 splat，把稀疏点扩成连续密度场）。

### 2026-07-26 — [M1·技术完成，视觉待验] Curl 运动 + 屏幕速度 + 二值方向胶囊已落盘
按 `WISPY-FLUID-SPEC.md` 将首个生产候选从“各向同性点模糊”收敛为“粒子速度驱动的方向性胶囊”。`ProjParticles/ParticleUpdate` 的活动顺序现为 `ParticleState → CurlNoiseForce → SolveForcesAndVelocity → SSPR_Projection → SSPR_WriteOccupancy`；Curl 验证参数为 Strength=250、Frequency=20。`SSPR_InitAttrs` 初始化 `Particles.SSPR_ScreenVelocityUV=(0,0)`；Projection 用固定 `ReferenceDt=1/60s` 投影 `Position` 与 `Position+Velocity*ReferenceDt`，输出 UV/秒；Writer 乘实时 RT 尺寸得到像素速度，以 `TrailTime=0.04s`、`MaxTrailPx=12`、`RadiusPx=1.5` 的固定上限循环写入向后拖尾的二值胶囊。重叠像素全部写相同的 1，避免把非原子 RT 写误当密度累加。独立读回确认新增 8 个 Pin、4 条连线和三段 HLSL 均正确；原生 Niagara 5 个脚本全部 UpToDate、零错误零警告，最近 LogNiagara 仅有正常编译记录；RT DI 仍绑定 `User.Render Target 2D`，系统保存成功且 Dirty=false。**尚未取得用户画面确认，因此 M1 仅技术完成，未标效果级通过。**

### 2026-07-27 — [根因] 方向轨迹最终画满 = 外部 RT2D 只有写入、没有帧清理
用户截图已确认 Curl 方向轨迹真实存在，同时连续运行后 RT 接近铺满。旧 Writer 对持久化外部 RT 只执行二值 `SetRenderTargetValue(..., 1)`，既不清屏也不衰减；因此每帧轨迹会永久并集，画满是必然结果，与粒子 Lifetime 无关。RT2D DI 的 ClearColor 只参与纹理创建/重建，不能作为逐帧清理机制。

### 2026-07-27 — [修复] 用 Grid2D 粒子稀疏写入 + Stage 前清理覆盖外部 RT
`SSPR_WriteOccupancy` 的 Custom HLSL 已从 RT2D 原地写改为 `Grid2DCollection.GetNumCells` + `SetFloatValue<Attribute=Occupancy>`；系统新增 `User.SSPR_OccupancyGrid`，实际 DI 为 256×256、`ClearBeforeNonIterationStage=true`、`SetGridFromMaxAxis=false`，其 `RenderTargetUserParameter` 绑定 `User.OccupancyRTParam`，由 Grid 的 PostSimulate 覆盖输出 `RT_SSPR_Occupancy`。活动 MapGet 直接读取 `User.SSPR_OccupancyGrid`，旧 `OccupancyRT → User.Render Target 2D` 绑定保留为未使用备用路径。Particle Update 顺序仍为 `ParticleState → CurlNoiseForce → SolveForcesAndVelocity → SSPR_Projection → SSPR_WriteOccupancy`；5 个脚本 UpToDate、零错零警、System 保存成功且 Dirty=false。执行前磁盘备份位于 `Saved/CodexBackups/NS_SSPR_ProjTest_before_grid_clear_20260727-1138.uasset`。

### 2026-07-27 — [边界] 当前是每帧清零，不是渐隐消散
本次修复只保证上一帧轨迹不会继续累积，RT 每帧只保留当前粒子胶囊。若要烟雾式逐渐变淡，必须在 M2 增加 History/Current ping-pong，在独立 Grid/Simulation Stage 或材质历史通路中执行 `History * Decay + Current`；不能在同一粒子 scatter Stage 对同一纹理安全地边读边写伪造衰减。

### 2026-07-27 — [根因修复] Grid 版全红不动 = 外部 RT 只显示重建清屏色，运行 DI/通道未同步
用户截图中的纯红不是粒子写满。UE 5.8 `NiagaraDataInterfaceGrid2DCollection.cpp::UpdateTargetTexture` 在重建外部 RT 时会把 `ClearColor` 设为 `(0.5,0,0,0)`；截图正是这层初始化色，说明 Grid 已重建 RT，但当前帧数据没有可靠复制出来。活体读回又发现两个运行实例状态分裂：关卡 NiagaraComponent 的用户变量列表缺少新增 `SSPR_OccupancyGrid`，编辑器预览实例虽有 Grid，但其克隆仍是 `NumAttributes=0`。普通 `ReinitializeSystem` 与同资产 `SetAsset` 不会补齐旧组件参数存储；官方 `SetVariable` 对 DI 也触发 `SetParameter_InternalUseOnly` 不支持错误。

### 2026-07-27 — [修复完成，视觉待验] 固定匿名通道 0，并重建两个运行组件的参数存储
为消除命名 Attribute 的运行时映射与组件克隆差异，Writer 从 `SetFloatValue<Attribute=Occupancy>` 改为 `SetValueAtIndex(x,y,0,1)`，源 Grid 明确设为 `NumAttributes=1`；256×256、`ClearBeforeNonIterationStage=true`、`RenderTargetUserParameter=User.OccupancyRTParam` 保持不变。关卡组件通过“临时卸载同资产 → 以 Reset Overrides 重新挂载 → 激活”重建参数存储，补齐 Grid DI；预览组件同步重建并把其当前克隆通道设为 1。最终两个运行 Grid 均独立读回 `256×256 / 1 channel / clear=true / User.OccupancyRTParam`；Writer 不再含命名 Attribute 或旧 RT2D 写入；5 个 Niagara 脚本 UpToDate、零错零警，资产保存成功且 Dirty=false。随后将外部 RT 中残留的红色初始化内容一次性清为黑色，System 与 RT 包仍均为非脏。修复前备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_anonymous_grid_fix_20260727.uasset`。尚需用户目视确认 RT 已恢复动态并且长期不画满。

### 2026-07-27 — [根因修复] Grid 版纯黑 = 重建 Writer MapGet 时漏接屏幕 UV 与屏幕速度
活体读回 `SSPR_WriteOccupancy` 内部图后确认：Grid2D 改造时删除了旧 MapGet 并创建 `BFD8FBC24B2DA1BEE89AF2889F618A0A`，但只重新连接了 `Module.OccupancyRT` 与 `User.SSPR_OccupancyGrid`；Custom HLSL 的 `ScreenUV` 和 `ScreenVelocityUV` 两个输入 Pin 都处于未连接状态。编译器会给 vec2 默认值，因此代码和 Grid DI 均可正常编译，却没有按粒子投影位置产生有效散点。现已在新 MapGet 上补回 `Particles.SSPR_ScreenUV`、`Particles.SSPR_ScreenVelocityUV` 两个 vec2 输出并连接至 HLSL；`ApplyChanges=true`，两条连线独立读回存在，5 个脚本全部 UpToDate、零错误零警告，System 保存成功。修复前备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_writer_uv_reconnect_20260727.uasset`。崩溃重启后原未保存关卡 Actor 未恢复，当前只打开 Niagara System 与 RT，并将唯一预览组件绑定 RT、设为 Active/Tick/ForceSolo，避免多个实例争抢同一张外部 RT；仍需用户目视确认动态画面。

### 2026-07-27 — [源码根因] VibeUE 的 DI module input 未按 Niagara 动态 Pin 正规流程注册
进一步读回活动 scratch 图与 GPU 编译产物后确认：旧 `UNiagaraScratchPadService::AddModuleInput`/通用 `AddPin` 对 `UNiagaraNodeParameterMapGet` 使用裸 `CreatePin`，绕过了 `UNiagaraNodeWithDynamicPins::RequestNewTypedPin`。可见 DI 输出虽然存在，但对应隐藏默认 Pin、模块签名和 stack input 拓扑没有完整登记；运行时因此克隆出 Grid `3×3/0 attributes` 或 RT `0×0/无 User Parameter` 的匿名 DI，造成“图和编译都正常，RT 仍黑”的假象。VibeUE 已改为动态节点统一走 `RequestNewTypedPin`，并规范 MapGet/MapSet 命名空间；离线 `Build.bat precisefluidEditor Win64 Development` 编译成功。修复已提交到插件分支 `sspr-scratchpad-fixes`：`44d9f72 Fix Niagara dynamic input registration`。

### 2026-07-27 — [技术决策] M1 最终采用 Direct RT writer，Grid2D 输出路线暂时退出关键路径
修复动态 Pin 后，Grid 与 RT module-local DI 均能在 GPU 编译产物中正确读回 256×256 和 `User.OccupancyRTParam`；但 Grid2DCollection 的外部 RT 输出在当前 Niagara 预览运行条件下仍持续黑屏，继续投入不利于验证核心视觉假设。M1 最终回到已被证明可靠的 RenderTarget2D DI 直接写入：每个存活粒子每帧按哈希分散选择 64 个像素，读取旧值并乘 `DecayMultiplier=0.90` 后写回，形成近似全屏的分布式渐隐；随后按 `ScreenUV` 与 `ScreenVelocityUV` 写入半径 1.5 px、最长 12 px 的速度方向胶囊。该做法避免旧版“只写 1 永不清除”永久画满，同时不用全屏 Simulation Stage。正式安装脚本保存在 `_black3_install_direct_rt_writer.py`，执行后 `ApplyChanges=true`、编译消息为空、系统资产保存成功。

### 2026-07-27 — [里程碑·M1 效果级通过] Curl 拉丝轨迹、动态写入与消散经用户确认
Niagara 资产编辑器 PreviewScene 产生真实 GPU 渲染帧后，`RT_SSPR_Occupancy` 显示随粒子运动变化的细小方向性轨迹；普通 EditorWorld Actor 在没有真实渲染帧时可能保持黑色，不能作为此 GPU DI 的离屏验收环境。用户最终确认“结果已经是对的了”。至此 M1 的投影、Curl 运动、屏幕速度、方向性胶囊、RT 动态更新与非永久累积全部达到效果级通过。下一阶段进入 M2：在材质/独立场处理层做多尺度卷积、密度重映射和烟雾 Resolve，而不是继续修改已通过的 M1 写入链路。

### 2026-07-27 — [回归·相机运动] 左右晃视角出现横向撕裂状残影
用户进一步做相机运动测试后发现，左右转动视角会在 RT 中留下远长于 12 px 胶囊上限的水平红线。Projection 的 `ScreenVelocityUV` 是用同一个当前 `View.WorldToClip` 投影 `Position` 与 `Position+Velocity*dt`，只包含粒子自身速度，不含相机速度；真正原因是 Direct RT 保存了上一帧的屏幕空间历史，视角改变后旧图没有重投影，新投影横向错位叠加。同时旧衰减代码从随机起点处理 64 个连续 linear address；在 row-major 的二维 RT 上正好形成水平条带，使残影呈现“撕裂”形态。

### 2026-07-27 — [修复完成，运动视觉待验] 衰减改为逐帧旋转的无方向置换
Writer 不再连续处理 64 个线性像素，改为以 `ExecIndex × 64 + decayIndex + View.FrameNumber × 7919` 生成序号，再乘奇数 `40503` 后对 RT 总像素数取模。对当前 256×256 RT，这是一种逐帧旋转、近似无重复且无水平/垂直偏置的覆盖；稳态约 1000 个粒子时每帧可触达约 64000/65536 个像素。`DecayMultiplier` 从 0.90 收紧到 0.78，使未重投影的屏幕历史约 3 帧内显著消退。修改已 `ApplyChanges=true`、compile messages 空、资产保存成功；Niagara 5 个脚本全部 UpToDate、零错误零警告。旧 RT 已清黑并重新激活唯一 PreviewScene writer。备份：`Saved/CodexBackups/NS_SSPR_ProjTest_before_isotropic_decay_20260727.uasset`。待用户左右晃动视角确认横线消失；若仍需更长尾迹且完全相机稳定，M2 必须改用 History/Current ping-pong + 相机重投影，不能继续依赖单 RT 原地历史。

### 2026-07-27 — [规格待审批] WISPY-FLUID-SPEC v0.2：M2 改为 Niagara + Material + Orchestrator 混合架构
用户复验无方向衰减后反馈相机横移伪影“好多了”，并要求先更新 Spec、审批后再执行。`WISPY-FLUID-SPEC.md` 已升为 v0.2/待审批：Niagara 只写每帧 `CurrentRT`；材质 Render Pass 用 `HistoryA/B` 做按秒衰减、代表深度相机重投影、Clamp、双尺度卷积和 Resolve；Blueprint/C++ Component 负责 Clear、GPU Pass 排序、Reset 与 A/B 交换。单 RT 粒子级 Read/Modify/Write 正式降级为 M1 调试实现。M2 拆为 A（Current+History 时序基础）、B（多尺度场处理）、C（烟雾 Resolve）；M3 再用 FrontDepth/HistoryDepth 升级逐像素重投影。当前只请求审批 M2 架构，未修改任何 M2 UE 资产。

### 2026-07-27 — [M2-A 技术完成，视觉待验] Current + History 双缓冲与显式相机重投影
M2-A 获批后新建 `/Game/SSPR_Validation/M2/RT_SSPR_Current`、`RT_SSPR_HistoryA/B`（256×256 R16F）、`M_SSPR_TemporalCombine` 和 `BP_SSPR_TemporalOrchestrator`。`SSPR_WriteOccupancy` 的正式代码已改为只写 Current 的方向胶囊，删除 `LoadRenderTargetValue`、粒子级衰减与帧号散列；修改前备份为 `Saved/CodexBackups/NS_SSPR_ProjTest_before_m2a_current_writer_20260727.uasset`。Blueprint 每帧设置 MID、只读一张 History/只写另一张、合成后清空 Current 并交换 A/B；BeginPlay 与 `ResetTemporalHistory` 会清空三张 RT、复位 History/Camera Valid 并重置 Niagara。

首版 Temporal 材质直接使用 `View.ClipToPrevClip`，静止相机的 History 保持测试却会把 A/B 全部清黑。根因不是 Ping-pong，而是 `DrawMaterialToRenderTarget` 的离屏 Canvas View 不携带游戏主相机的上一帧矩阵。现已改为 Blueprint 每帧从 PlayerCameraManager 显式传入当前/上一帧 Position、Forward、Right、Up；材质在 `RepresentativeDepth=1000` 的平面上重建世界点并投回上一帧 UV。相机平移超过 2000 uu 或 Forward 夹角余弦低于 0.5 时拒绝旧 History，避免 Cut 后旧图回流。按秒衰减使用 `exp(-DecayRate × DeltaSeconds)`，默认 `DecayRate=6`，首帧 Camera/History Valid 为 0。

验证结果：材质 22 个表达式、2 个纹理对象、10 个标量、8 个向量参数，PCD3D_SM6 诊断编译通过；Blueprint 99 个节点、154 条连线、45 个默认值，零编译错误/警告。关闭衰减并停掉 Niagara 后，History A/B 保持同图；开启显式重投影后静止相机仍保持；平移相机 100 uu 后 A/B 继续一致；恢复正式衰减并停掉 Niagara 后两张 History 都归零。调度器实例与验证场景已保存为 `/Game/SSPR_Validation/L_SSPR_M2_Validation`；从该地图重启标准 PIE 后，MID、HistoryValid、CameraDataValid、Niagara Active 与正式参数均为有效状态。M2-B/M2-C 未开始，M2-A 左右绕转和最终观感仍待用户视觉 Gate。

### 2026-07-28 — [回归修复] M2 Current-only Writer 污染 M1 独立预览，导致 RT 再次不消散
当前编辑器实际运行的是 `Untitled_1` 中单独放置的 `NS_SSPR_ProjTest`，没有 `BP_SSPR_TemporalOrchestrator`。M2-A 实现时直接把原 M1 System 的 Writer 改成了无状态 Current-only 版本；该 Writer 假定外部调度器每帧清空 Current，但独立 Niagara Actor 仍把它写入持久的 `RT_SSPR_Occupancy`。结果是所有历帧胶囊永久并集，表现为“RT 又不会 clear”。这不是 History 材质或粒子 Lifetime 失效，而是同一 Niagara 资产承担了互斥的 M1/M2 生命周期语义。

现已把系统拆开：`/Game/SSPR_Validation/NS_SSPR_ProjTest` 恢复 M1 分布式渐隐 Writer（含 `LoadRenderTargetValue`，`DecayMultiplier=0.78`）；复制并新增 `/Game/SSPR_Validation/M2/NS_SSPR_ProjTest_M2`，保留不读历史的 Current-only Writer；`BP_SSPR_TemporalOrchestrator.SSPRNiagara` 已改为引用 M2 专用系统。两套 Niagara 均 `ApplyChanges=true`、compile messages 为空、资产保存成功，Orchestrator Blueprint 为 `BS_UP_TO_DATE`。

运行回归结果：M1 清黑后启动独立 Niagara，早期与长时间导出的 `RT_SSPR_Occupancy` 都保持稀疏动态胶囊，没有随运行时间铺满；M2 临时实例中 MID、HistoryValid、CameraDataValid、DecayRate=6 和 Niagara Active 均有效，活动 History 输出正常；停掉 M2 Niagara 后再次导出，History 已归零。临时 Orchestrator Actor 随后移除，编辑器恢复到原独立 Niagara 场景并保持 PIE 运行。

### 2026-07-28 — [M2-B 技术完成，视觉待验] Core/Small/Large/Density 多尺度场接入
用户要求继续沿 Spec 推进后，新增 `RT_SSPR_Core`、`RT_SSPR_BlurSmall`、`RT_SSPR_BlurLarge`、`RT_SSPR_Density`（256×256 R16F）以及对应 `M_SSPR_CoreExtract`、`M_SSPR_BlurSmall`、`M_SSPR_BlurLarge`、`M_SSPR_DensityCombine`。第一轮让 Large 直接读取稀疏 History，导出出现明显离散采样点阵；已改为 `History → 9-tap Small → 13-tap Large`，Large 半径收敛到 7 px，消除点阵并形成平滑低频场。Density 当前权重为 Core 0.60、Small 1.00、Large 0.65，重映射阈值 0.002/0.18，边缘破碎 0.04。

Orchestrator 已扩展为每条 A/B 分支执行 `Temporal → Core → Small → Large → Density`，并在 BeginPlay/Reset 清理全部字段 RT。材质诊断全部编译通过；最终 Blueprint 构图继续扩展至 M2-C 后为 165 个节点、270 条连接、71 个默认 Pin，零失败、零编译错误/警告。

### 2026-07-28 — [M2-C 技术完成，用户视觉 Gate 待验] 指数消光烟雾 Resolve
新增 `M_SSPR_SmokeResolve`、`MI_SSPR_Smoke_Default`、`MI_SSPR_Smoke_DensityDebug` 和 `RT_SSPR_Smoke`（256×256 RGBA8）。Resolve 使用 `1-exp(-Extinction×Density)`，默认蓝灰烟色，并暴露 Extinction、DensityScale、OpacityScale、BlackPoint、SmokeColor 和 EmissiveStrength；Orchestrator 默认使用正式实例，白色实例用于纯密度检查。Smoke 材质为 Unlit Translucent；因透明材质画入持久 RT 会累积，Orchestrator 在每次 Smoke Draw 前显式清透明黑，避免重现“RT 不 clear”。

首轮 Smoke 输出仍偏软粒子团，根因是 M2 专用方向胶囊仍使用 0.04s/12px 的 M1 验证值；现只对 `M2/NS_SSPR_ProjTest_M2` 调整为 `TrailTime=0.075s`、`MaxTrailPx=20px`、`MaxTrailSteps=20`，M1 独立预览不受影响。调参后 Smoke 输出已保留更明显的方向延伸和柔软外围。运行时六个 MID（Temporal/Core/Small/Large/Density/Smoke）均有效；持续运行不铺满，停止 Niagara 后 History、Density 与 Smoke 全部归黑。当前 M2-B/C 达到技术 Gate，是否达到“拉丝烟雾而非模糊粒子”的效果 Gate 仍需用户观察动态 RT 后确认。

### 2026-07-28 — [M2-C 显示链路完成，视觉待验] Density RT 通过相机跟随面片进入场景

用户确认当前 RT “确实有感觉了”并要求跑通面片渲染。`BP_SSPR_TemporalOrchestrator` 新增 `SmokeCardPivot`（SceneComponent）和 `SmokeCard`（StaticMeshComponent）；SmokeCard 使用 `/Engine/BasicShapes/Plane`、相对旋转 Pitch=90°、缩放 2.05×1.15，BeginPlay 把 `MI_SSPR_Smoke_Default` 绑定到材质槽 0。Tick 从 PlayerCameraManager 获取位置和旋转，把 Pivot 设置到 `CameraLocation + CameraForward × SmokeCardDistance`，默认距离 100 uu，并在进入 A/B History 分支前更新。

重构后的 Blueprint 为 172 个节点、281 条连接、74 个默认 Pin，零构图失败、零编译错误/警告。标准 PIE 运行态读回确认：SmokeCard 绑定正式 Smoke Material Instance 与 Engine Plane，Visible=true、RecentlyRendered=true；Pivot 到相机距离精确为 100 uu，与 Camera Forward 的归一化点积为 1.0。当前正式场景链路为 `Density RT → M_SSPR_SmokeResolve/MI_SSPR_Smoke_Default → Camera-facing Plane`，`RT_SSPR_Smoke` 仍作为调试导出；场景深度遮挡留给 M3 FrontDepth/SceneDepth。

### 2026-07-28 — [回归修复] 面片 X/Y 轴、固定宽高比与 Mesh UV 导致错位和截断

用户在 PIE 截图中指出面片歪斜、比例不对且中间被截断。根因是 Engine Plane 在相对 Pitch=90° 后，局部 X 映射到屏幕高度、局部 Y 映射到屏幕宽度；初版却设置 X=2.05、Y=1.15，实际得到窄宽、超高载体。同时固定 16:9 与当前 PIE 视口比例不一致，TextureCoordinate 又把整张 Density RT 拉伸到这个错误矩形上。

现新增 Card 专用 `M_SSPR_SmokeCard` 与 `MI_SSPR_SmokeCard_Default`：使用 `ScreenPosition.ViewportUV` 读取 Density RT，关闭原型阶段 Depth Test；Plane 扩大为 4×4，只负责覆盖视锥，不再决定采样比例。Orchestrator 新增独立 `SmokeCardMaterial`，RT 调试 Resolve 与场景 Card 不再共用 UV 语义。Blueprint 重构为 173 个节点、281 条连接、74 个默认 Pin，零失败、零编译错误/警告；PIE 读回确认 Card 专用实例已绑定、面片近期已渲染、相机对齐点积 1.0。

截图顶部 `NS_SSPR_ProjTest` 的 “RenderTarget is read and wrote in the same stage” 来自当前 Untitled 测试关卡里仍存在的 M1 独立 Niagara Actor，而非 M2 Current-only Writer。已把该 M1 组件在当前场景设为 AutoActivate=false、Active=false、Tick=false；PIE 中只保留 `NS_SSPR_ProjTest_M2` 活跃，避免双系统重叠和旧 M1 的同阶段读写警告。

### 2026-07-28 — [边缘修复] RT Clamp、Blur 越界归零与 Card 2 px 安全边

用户观察到屏幕边缘仍有少量烟色泛出。检查确认 Small/Large Blur 直接对 `UV + Offset` 采样，且各 RT 的 Address Mode 没有在资产级显式约束；单纯在最终 Card Clamp 会让边缘像素被重复拉伸，不能解决上游卷积越界。

现把 Current、History A/B、Core、Small、Large、Density、Smoke 八张 RT 的 Address X/Y 全部显式设为 `TA_Clamp`。Small 9-tap 与 Large 13-tap 的每个采样坐标先检查半像素安全范围，越界 Tap 贡献 0，合法 Tap 才执行 Clamp 后采样，避免 Wrap 和边缘重复。Card 的 Color/Opacity 两条 Resolve 再把 ViewportUV 限制到半像素中心，并在屏幕最外侧 2 px 以 Smoothstep 衰减到透明。修改后材质重编译、资产保存与运行态回归完成；Card 正在渲染、相机对齐点积 1.0，M2 Active=true、旧 M1 Active=false。

### 2026-07-28 — [调参开放与镜头尺度修复] Writer 宽度、卷积范围与动态代表深度

用户指出 RT 方向轨迹明显粗于 Niagara 粒子，并且镜头拉远后烟雾/RT 范围约为粒子范围两倍。检查确认两层原因：M2 Writer 的 `RadiusPx=1.5` 仍是 HLSL 硬编码，Small/Large 又使用固定 `3 / 7 px` 卷积；Temporal 重投影还使用固定 `RepresentativeDepth=1000`，而实际相机到特效中心距离会随镜头移动，造成历史缩放与当前投影不一致。

现为 M2 Niagara System 增加 `User.SSPR_RadiusPx`、`User.SSPR_TrailTime`、`User.SSPR_MaxTrailPx`，Scratch Writer 的 MapGet 直接读取这三个 User 参数并连接 Custom HLSL。由于 Niagara 官方 Stack API 仍无法定位 Scratch Module 新增输入，未继续依赖 Stack 绑定；User MapGet 是资产内明确、可编译且 Blueprint 可覆盖的数据链。默认 `SplatRadiusPx` 降为 `0.75 px`，当前整数写入算法下只落中心像素；Trail 保持 `0.075s / 20px`。

`BP_SSPR_TemporalOrchestrator` 新增八个实例参数：`SplatRadiusPx`、`TrailTimeSeconds`、`MaxTrailPx`、`SmallBlurRadiusPx`、`LargeBlurRadiusPx`、`CoreWeight`、`SmallBlurWeight`、`LargeBlurWeight`。八项均移除 `DisableEditOnInstance` 并归入 Actor Details 的 `SSPR Tuning` 分类。Tick 每帧把前三项写入 Niagara、其余项写入 Small/Large/Density MID，可在 PIE 中实时调整。默认卷积收窄为 `2 / 4 px`，混合权重改为 `0.60 / 0.90 / 0.45`。

固定 `RepresentativeDepth` 节点已从运行图移除，改用 `Actor::GetDistanceTo(PlayerCameraManager)` 每帧计算相机到特效中心的代表深度，并同时写入 A/B Temporal 路径。最新 Blueprint 为 190 个节点、306 条连接、82 个默认 Pin，零失败、零编译错误/警告；Niagara Scratch 编译消息为空。重启 PIE 后读回确认三个 Niagara User Float 与 Actor 值完全一致，Small/Large/Density MID 均收到新参数；Temporal MID 的代表深度为 `220.1454468 uu`，相机到 Actor 实测为 `220.1454483 uu`，误差约 `0.0000015 uu`。Card 仍近期已渲染、相机对齐点积 1.0，M2 Active=true、旧 M1 Active=false。

### 2026-07-28 — [架构重新对齐] 高密度粒子年龄分布 + Grid2D 直连材质成为正式主线

用户说明 `/Game/SSPR_Validation/M2/NewNiagaraSystem2` 是 Leader 要求对齐的方向：拉丝连续性不应主要来自二维 History Ping-pong，而应由大量、长寿命、不同年龄的三维粒子在 Curl 场中同时占据流线不同位置，再把全部存活粒子每帧重新投影到 Grid2DCollection。Grid 通过 Niagara Grid2D Collection Renderer 直接绑定最终材质参数，正式链路不声明 Current、History、Core、Blur、Density、Smoke 等外部 RenderTarget 资产。

MCP 读回参考资产当前为单个 CPU `Fountain` Emitter：SpawnRate=5000/s、Lifetime=5s、球体半径 50、Curl Strength=5000、Frequency=10、Drag=1，稳态约 25000 个粒子；Particle Update 尾部在 `Solve Forces and Velocity` 后执行 `Particles.Velocity=(0,0,0)`。该清零会保留 Solver 已经写入的本帧位置，但禁止动量传入下一帧，使粒子更紧地跟随瞬时 Curl 场。其代价是位移近似按 `Force × DeltaTime²` 计算、有效流速具有帧率依赖，Drag 作用减弱，且下游无法读取有效 Velocity。正式实现优先评估“Curl 目标速度 + 指数响应”的帧率稳定方案；若保留 Reset，必须在清零前缓存 `Particles.FlowVelocity`。

`WISPY-FLUID-SPEC.md` 已重写为 v1.0：旧 Ping-pong Orchestrator、多 RT 材质链和代表深度重投影降为实验参考；新里程碑依次为 M0 GPU 粒子运动对齐、M1 Grid2D 单帧轨迹、M2 Grid Renderer 直连材质、M3 单材质高品质烟雾、M4 深度融合、M5 性能档位。当前只完成架构与规格重新对齐，尚未修改 `NewNiagaraSystem2`。

### 2026-07-28 — [主线切换] 旧 Ping-pong 资源归档，新粒子轨迹进入 Niagara 内部 SimRT 并绑定材质

旧 M2 Ping-pong/多 RT 原型的 20 个核心资产已从 `/Game/SSPR_Validation/M2` 移动到 `/Game/SSPR_Validation/Archive/PingPong_M2_20260728`，包括 Temporal Orchestrator、Current/History A/B、Core/Small/Large/Density/Smoke RT 与全部对应材质；只保留重定向器用于旧引用兼容。`NewNiagaraSystem`、`NewNiagaraSystem1`、`NewNiagaraSystem2` 作为 Niagara Fluids 与 Leader 运动参考未归档。

新增主线资产 `/Game/SSPR_Validation/M2/GridTrails/NS_SSPR_GridTrails_Main`、`MI_SSPR_GridTrails_Display` 与 `BP_SSPR_GridTrails_Main`。SourceParticles 为 GPU Compute Sim，已设置 `SpawnRate=5000/s`、`Lifetime=5s`、发射半径 `50 uu`、Spawn Curl Strength `130`、Frequency `0.04`、Source Density `1`，并关闭 AddVelocityInCone、Gravity、Collision、Update Curl 与 Drag；当前脚手架由 Spawn Curl 生成初始速度，再由 Solve 持续推进，稳定态目标约 25000 个存活粒子。显示 Renderer 使用项目内材质实例，并保持 `Material SimGrid <- Emitter.SimRT.RenderTarget` 的 Niagara 原生子变量绑定。连续 Curl/目标速度运动留待精简后的正式粒子运动模块实现。

引擎源码核对确认：UE 5.8 材质不能直接消费 Grid2DCollection 的原始 RDG 纹理。Niagara Fluids 的正式原生桥接是 `Grid2DCollection -> Simulation Stage -> NiagaraDataInterfaceRenderTarget2D(Emitter.SimRT) -> Emitter.SimRT.RenderTarget -> Renderer Material Parameter`。其中 `Emitter.SimRT` 在 `bInheritUserParameterSettings=false` 时由 Niagara 为系统实例自动创建，不是 Content 外部 RT 资产；因此仍满足“不声明额外 RT、不用 Blueprint Clear/DrawMaterial/Ping-pong”。

编译回读为 `UpToDate`、零错误、零警告。当前 Untitled 验证场景生成了 `SSPR_GridTrails_Main` Actor；运行时自动出现 512×512 RGBA16F `SimRT`。最终自动化验收会扫描全部同规格运行时目标并排除旧实例残留纹理；当前活动目标读回 262144 像素，RGB 最大值为 `(1.0, 1.0, 0.939453125)`，三个颜色通道均有 `261121` 个非零像素，证明粒子/Grid 数据已进入材质所绑定的内部纹理。当前系统仍以 Niagara Fluids `Grid2D_Gas_Smoke` 为脚手架，包含 Advect、Pressure、Lighting 等完整 Gas Stage；它只完成了“粒子轨迹→Grid→内部 SimRT→材质”的技术链验证。下一步必须将 Grid Emitter 精简为 `Clear -> Rasterize Trajectory Particles -> Pack/Copy to SimRT`，移除 Navier-Stokes/压力求解后再进入单材质高品质烟雾重建。

`WISPY-FLUID-SPEC.md` 已升级为 v1.1，修正“Grid2D 纹理直接绑定材质”的不准确描述，记录 Niagara 自管 SimRT 桥接的真实引擎行为，并标记当前脚手架状态和下一阶段的无压力求解精简目标。
### 2026-07-28 — [根因修复] 材质透明度恒 0：Renderer 绑定了空 TextureRenderTarget，而非 Niagara 内部 RT 子变量

正式 `NS_SSPR_ParticleTrails_Main` 原先把材质参数 `TrajectoryTexture` 绑定到 `User.SSPR_TrajectoryRT`；该对象参数默认值为 `None`，因此材质纹理采样恒为 0，Opacity 也恒为 0。现新增 Niagara 自管理 `User.SSPR_SimRT`（RenderTarget2D DI，2048×2048 RGBA16F、Bilinear、`bInheritUserParameterSettings=false`）与 Grid 迭代 Stage `SSPR Resolve Grid To Material`。Scratch 模块 `SSPR_ResolveGridToSimRT` 逐 Cell 读取自动清零的 `User.SSPR_TrajectoryGrid` 并覆盖写入 SimRT；Renderer 改绑 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget`。VibeUE 的 ScratchPadService 同步补充了 Grid2D Stage 迭代源配置与内部 RenderTarget2D User Parameter 创建接口。最终 PIE 验收：运行时生成 2048×2048 RGBA16F 纹理；256×256 材质桥读回 63 个非零像素，R 最大 118；Niagara UpToDate、0 错误、0 警告。修复前资产备份位于 `Saved/CodexBackups/NS_SSPR_ParticleTrails_Main_before_internal_simrt_20260728_2135.uasset`。

### 2026-07-28 — [里程碑·基线冻结] M2 粒子到材质链路完成视觉验收，正式进入 M3 图像处理

用户确认 `GPU 粒子 → View.WorldToClip → Grid2D → Niagara 自管 SimRT → Renderer 材质参数 → ScreenPosition.ViewportUV` 全流程已彻底跑通。关闭 TSR/TAA 的会话级 A/B 对照中链路和比例保持正确，当前离散亮点被认定为 M3 的原始密度输入，而非依靠时序抗锯齿修复的错误。自 v1.4 起冻结 Niagara 数据生产链；后续优先只改最终材质，依次建立 Raw/Core/Small/Large、多尺度混合、密度整形、边缘破碎、指数消光与烟雾着色。

### 2026-07-28 — [里程碑·M3 函数链跑通] 父材质只编排，四个材质函数完成高品质空间重建

正式函数库落在 `/Game/SSPR_Validation/M2/ParticleTrails/Functions/M3_HQBaseline`：RawDensity、MultiScaleDensity、DensityShape、SmokeResolve。MultiScale 使用连续 7×7/13×13 二项式高斯核（219 taps），DensityShape 从 `Core-Small` 与 `Small-Large` 的真实频段差恢复细丝和宽边，Resolve 使用 Beer–Lambert 指数消光；父材质只负责输入、参数、DebugRaw A/B 与最终 Color/Opacity。已知白图 Processed/Raw 均为 128² 全非零；活动 Niagara 内部 RT 的 512² 回读为 Processed 1407、Raw 1079 个非零像素，证明处理链真实扩大连续覆盖。

### 2026-07-28 — [根因与规则] 原地重建材质函数会残留 FunctionInput GUID

曾对同一函数资产反复“删除表达式并重建”，UE 5.8 仍保留旧 FunctionInput GUID，调用节点出现重名输入；自动连线命中失效 Pin 后，材质表面编译绿色但白纹理端到端输出仍全黑。正式规则改为破坏性接口变更时创建新的干净版本目录，反射检查输入名唯一，并用已知白纹理做非零 Gate；污染的原型函数只保留为未引用归档。

### 2026-07-28 — [清理] 正式验证关卡移除旧 Ping-pong Orchestrator 实例

归档 Blueprint `BP_SSPR_TemporalOrchestrator` 仍有一个 `SSPR_M2A_TemporalOrchestrator` 实例放在正式验证关卡，PIE 会执行旧 Current/History/MID 调度并产生大量 Accessed None。现只删除该关卡实例并保存，归档资产本身保留；重新进入 PIE 后没有产生新的同类运行时错误，正式链路只保留 Niagara 自管 SimRT 与函数化材质。

### 2026-07-28 — [解耦] 增加 HQ 材质实例作为独立视觉调参层

新增 `/Game/SSPR_Validation/M2/ParticleTrails/MI_SSPR_ParticleTrails_HQ_Default`，父级为函数化 `M_SSPR_ParticleTrails_Display`；Niagara Display Renderer 已改绑该实例，`TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 仍完整。函数/父材质保存算法与 HQ 默认值，实例只按需承载美术 Override。重启编辑器后 base/instance 的 Processed/Raw 四条 128² 白图 Gate 均为 16384 个非零像素。

### 2026-07-29 — [版本冻结/待审批] V1 自包含快照与 V2 各向异性高斯 Splat 工作区

当前圆形轨迹写入、Mip 多尺度重建和密度梯度光照版本冻结为 `/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729`；从该快照复制 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2`，主资产重命名为 `NS_SSPR_AnisotropicSplat_Main`、`M_SSPR_AnisotropicSplat_Display`、`MI_SSPR_AnisotropicSplat_HQ` 和 `L_SSPR_AnisotropicSplat_Validation`。UE 的目录复制不会自动重映射跨资产引用，因此又显式修正了两个目录内的材质实例 Parent、全部 Material Function Call 和 Niagara Display Renderer，使版本目录不依赖原 ParticleTrails 材质链。

新增 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` v0.1。新方案使用 Solver 前后位移缓存生成屏幕流向，每粒子写入旋转椭圆高斯，并以原子加法累积真实密度；V1 Mip 重建只保留为低频烟体层。规格当前待用户审批，尚未在 V2 工作副本安装 FlowDelta、各向异性 Splat、RasterizationGrid 或方向张量。

### 2026-07-29 — [根因修复/里程碑] V2 Raster Stage 属性裁剪修复，G0～G3 技术链通过

V2 一度表现为均匀整片、全黑或所有粒子集中到单个像素。最终确认存在两层问题：第一，Raster scratch 曾把调试 `OutMark` 写回 `Particles.SSPR_WriteMark`，导致 Stage 被编译为 `WritesParticles=True`；Partial Particle Update 下外部 UAV 写入无效，强制 Full Update 又会破坏未显式保留的粒子属性。现已把 `OutMark` 改为模块局部输出，Raster Stage 只输出到 `User.SSPR_DensityRaster`，生成元数据确认 `WritesParticles=False`。

第二，在 Raster Stage 改为纯 DI 副作用后，UE 5.8 编译器会裁掉没有被 Renderer 消费的 Position/ScreenDeltaUV。生成 HLSL 虽调用 `Context...Particles.Position`，数据集加载最初只含 Age/Lifetime/UniqueID，因此所有粒子实际读取默认零位置。正式修复是启用 Renderer 0 作为不可见的属性保活器：`RendererVisibility=1`，并将 `SpriteSizeBinding` 指向 `Particles.SSPR_ScreenDeltaUV`；Renderer 1 继续负责最终显示面片。重新编译后 Stage1 数据集明确加载 Position 与 SSPR_ScreenDeltaUV。

Stage1 正式高斯写入改为用持久化 Position 和当前 `PrimaryView.WorldToClip` 直接重投影中心，仅用缓存 ScreenDeltaUV 控制旋转椭圆长轴；密度通过 `RasterizationGrid3D(2048×2048×1)` Q10 整数原子加法累积，Stage2 Resolve 到 Niagara 自管 SimRT。当前原始 2048² 回读：41,353 个非零像素、R 最大约 4.203、R 总量约 23,532.886；Niagara 编译零错误零警告，Raster Stage 不写粒子。当前资产已恢复为正式高斯版本，不再是单点探针，下一步只需用户在视口确认形状后进入 G4 材质细丝/烟体混合。

### 2026-07-29 — [文档] 新增 Niagara Raster / MCP 独立排坑手册

用户完成 V2 G0～G3 视口验收并确认画面正常后，新增 `NIAGARA-RASTER-MCP-PITFALLS.md`。文档将本轮遇到的 Stage 粒子回写、Partial Particle Update、Custom HLSL 属性裁剪、隐藏 Renderer 保活、显式重编译、Parameter Map 主链、Raster Q10 原子累加、Clear、旧运行时 RT、原分辨率读回、MCP 分请求、Gateway 残留、PIE Python 引用泄漏、UBA 提交内存、材质 Pin 与目录复制依赖等问题整理为可复用规则，并给出固定写入→粒子单点→正式高斯→材质的最短诊断顺序。

### 2026-07-29 16:20 — [视觉诊断/调参] 中央暗块来自密度梯度光照，连续性优先使用中性光照

用户指出 V2 仍有明显粒子感且中央出现大块“阴影”。反射检查确认 Display Renderer 不投射阴影，父材质为 Unlit Translucent；暗块实际来自 `MF_SSPR_DensityGradientLighting`。旧 HQ 参数 `Ambient=0.45 / LightStrength=0.65 / GradientStrength=10` 会把高密度背光区域压到约 45% 亮度。当前 `MI_SSPR_AnisotropicSplat_HQ` 改为连续性基线：Filament/Medium/Body=`0.18/0.50/0.32`，Medium/Body 半径=`14/48 px`，DensityGain=`2`，Contrast=`0.48`，Extinction=`2.4`，OpacityScale=`0.82`，并暂用 `Ambient=1 / LightStrength=0`。该设置用于先验收密度连续性，最终体积受光仍待 G4 视觉 Gate 后单独恢复。

### 2026-07-29 16:33 — [高品质基线] SimRT 关闭自动 Mip，V2 改用确定性 LOD0 7×7/13×13 空间重建

针对整片亮度波动曾怀疑动态 SimRT Mip 链与同帧 Renderer 采样存在时序差异，因此将 V2 `User.SSPR_SimRT` 设置为 Bilinear、`MipMapGeneration=Disabled`，并在保持函数接口不变的前提下把 `MF_SSPR_MipPyramidDensity` 内部替换为 LOD0 7×7 Medium 与 13×13 Body 二项式核。材质和 Niagara 编译均通过；当前活动 2048² SimRT 一次原始回读为 32,030 个非零像素、R 最大约 6.77、R 总量约 23,390.58。修改前 System、Material 和函数已复制到 `Saved/CodexBackups/*before_stable_lod0_20260729.uasset`。

后续验证证明：LOD0 路线适合作为当前“质量优先”的确定性空间重建，但它不是整片闪烁的最终根因。函数资产名称和两个 MipBias 兼容输入已经与内部算法不一致，列为视觉 Gate 后的接口收口任务。

### 2026-07-29 16:47 — [根因修复] Fixed Tick 60 Hz 消除静止视口下整片忽明忽暗

用户发现按住右键持续调整镜头时画面稳定，松开后整张面片闪烁；开启 Niagara System Fixed Time 后立即稳定。MCP 读回确认 `fixed_tick_delta=true`、`fixed_tick_delta_time=0.01667s`。UE 5.8 `FNiagaraSystemSimulation::Tick_GameThread` 在 Fixed Tick 模式下累积引擎时间并按固定步长执行 0～N 个补步，Spawn、Solve、Lifetime 和当帧 Raster 密度不再直接使用不规则的渲染帧 DeltaTime。因此本次整片亮度脉动的主要根因是可变时间步，而非粒子数据归零或 Mip 链本身。

Fixed Tick 60 Hz 现作为 V2 高品质基线硬配置。仍需在最终封版前分别限制 30/60/120 FPS，确认低帧率补步成本和画面一致性。

### 2026-07-29 — [文档同步] V2 当前事实基线统一到主文档

`AI-BRIEF.md`、`BACKLOG.md`、`WISPY-FLUID-SPEC.md` 与 `ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md` 已统一到 V2 G4 当前状态：旧 Ping-pong 为归档；正式链路为粒子→RasterizationGrid3D 单层原子密度→Niagara 自管 SimRT→V2 材质；SimRT 无自动 Mip；材质使用 LOD0 7×7/13×13；Fixed Tick 为 60 Hz；中性光照用于当前连续性 Gate。尚未完成项明确收敛为最终视觉 Gate、冷启动回归、函数命名/接口收口、完整 V2 快照、未引用资产清理和文档 Git 提交。

### 2026-07-29 22:08 — [本地封存] UE、VibeUE、SSPR 资产与项目记录建立统一恢复点

UE NiagaraEditor 修复已保持在干净分支 `sspr-niagaraeditor-fixes`，提交 `98d86a7` 并带标签 `sspr-niagaraeditor-fixes-ue5.8.0`。VibeUE 分支 `sspr-scratchpad-fixes` 将 Simulation Stage、内部 RT2D 和 RasterizationGrid3D MCP authoring API 提交为 `af697f9`。`Content/SSPR_Validation`、两个源码分支分别生成 ZIP/Git bundle，并在 `recovery/README.md` 记录 SHA-256。本次仅做本地提交与恢复快照，没有推送远端；该快照为 G4 视觉 Gate 前检查点，不替代 Gate 通过后的最终 V2 封版。

### 2026-07-29 23:15 — [G4 候选/待人工视觉确认] 修正 7×7/13×13 未接入材质，并抑制无邻域支持的粒子核心
用户截图显示轮廓锯齿、点链与白色饱和核心仍然严重。资产只读复核发现，`MF_SSPR_MipPyramidDensity` 已包含既定 LOD0 7×7 Medium + 13×13 Body 代码，但 `M_SSPR_AnisotropicSplat_Display` 实际仍连接旧的 `MF_SSPR_MipBodyDensity -> MF_SSPR_FilamentBodyBlend` 3×3/5×5 链；此前记录的 219-tap 基线并未真正进入最终 `DensityShape`。现已在不改 Niagara 数据链和既有函数接口的前提下，把高品质函数的 `Scales` 直接接入 `MF_SSPR_DensityShape`。

`MF_SSPR_DensityShape` 保持原九输入接口，只修改内部整形：Raw Core 必须同时获得 Medium/Body 的相对与绝对邻域支持才可参与锐化，频段差值改为正值限定，避免孤立 splat 与负差分重新进入 Alpha。HQ 候选参数改为 Filament/Medium/Body=`0.06/0.58/0.36`、Medium/Body Radius=`16/52 px`、Detail=`0`、BlackPoint=`0.003`、DensityGain=`1.4`、Contrast=`1.10`、Extinction=`1.7`、OpacityScale=`0.82`；继续保持 Ambient=`1`、LightStrength=`0`、Fixed Tick=`0.01667s`、SimRT 2048² RGBA16F/Bilinear/无 Mip。

修改前函数、父材质与 MI 已备份到 `recovery/G4_density_support_20260729_230547`。修改后材质编译通过；Niagara Apply/Compile/Save 成功，系统 `UpToDate`、零错误、零警告；组件重绑后两份 Raster clone 均为 `2048×2048×1`。活动 SimRT 连续两次各推进 120 帧后的原始回读总量约 `2,403,536.68` 与 `2,405,154.29`，非零像素约 `225,574` 与 `217,915`，没有随运行单调画满。当前只完成技术 Gate，最终锯齿、粒子感、拉丝/烟体平衡及关闭 TAA/TSR 的视觉结果仍必须由用户观察确认。

### 2026-07-30 11:03 — [V2 冻结备份] G5 修改前建立完整 V2_pre_G5 恢复点

在任何 G5 资产修改前，将 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2` 整个内容目录及 `AI-BRIEF.md`、`WISPY-FLUID-SPEC.md`、`ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md`、`NIAGARA-RASTER-MCP-PITFALLS.md`、`LOG.md` 冻结到 `recovery/V2_pre_G5_20260730_110322`。共备份 29 个 UE 资产与 5 份设计文档；源/目标逐文件 SHA-256 对比为零缺失、零不一致。该目录是当前 G4 视觉候选进入 G5 前的正式回退点。

### 2026-07-30 — [G5.1/G5.2 技术 Gate] 当前帧方向张量与粒子深度场进入 Main/Aux RT

用户批准 v0.4 G5 方案后，第一实施步只落地方向/深度字段与 Debug，不接最终 Streamline 或纵深光照。`User.SSPR_DensityRaster` 扩展为 `2048×2048×1`、6 属性、Precision=`65535`：属性 0～4 为 Density Q10、双角度 TensorCos2/Sin2 Q10、DepthMoment1/2 Q16，属性 5 以原子最大值写入归一化 FrontInvDepth。新增 `User.SSPR_DepthNearUU=0`、`DepthFarUU=10000`、`FrontDepthWeightThreshold=0.1`。Raster 继续按当前相机重投影，保持纯 DI 副作用和 `WritesParticles=False`，未增加任何 History 读取或跨帧反馈。

Resolve 现在完整覆盖两张 Niagara 自管当前帧 RT：Main `User.SSPR_SimRT = (Density, TensorCos2, TensorSin2, MeanDepth)`；新增 Aux `User.SSPR_AuxRT = (DepthSigma, FrontDepth, Reserved, Coverage)`。Aux 为 `2048×2048 RGBA16F`、Bilinear、Mip Disabled。Renderer 新增 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`；独立新建 `Functions/G5/MF_SSPR_G5_FieldDebug`、`M_SSPR_G5_FieldDebug` 与 `MI_SSPR_G5_FieldDebug`，没有修改 G4 父材质接口。Debug MI 当前使用模式 6，一张视口四宫格同时显示方向/一致性、MeanDepth、DepthSigma、FrontDepth。

Apply/Compile/Save、Renderer 双绑定核对、组件 Rebind/Reinitialize 与关卡保存均完成。Niagara 状态为 `UpToDate`、零错误、零警告；Fixed Tick 仍为 `true / 0.01667s`；HQ 与 Debug 材质均零编译错误。完整 2048² 原始回读可唯一识别 Main/Aux：Main R 最大约 `143.375`，G/B 均含 `[-1,1]` 的有符号方向分量，A MeanDepth 最大约 `0.0885`；Aux R DepthSigma 最大约 `0.05487`，G FrontDepth 最大约 `0.0885`，B 恒零，A Coverage 非零像素 `234,656 / 4,194,304`（约 5.6%）。连续推进数百帧后未画满，所有通道无 NaN/Inf。下一 Gate 只需用户观察当前四宫格是否方向连续、深度随前后层次变化、空区无伪值；通过后再实施 G5.3/G5.4。

首次四宫格截图中方向场已呈连续彩色变化，但 MeanDepth、DepthSigma、FrontDepth 三格几乎全蓝。原始 RT 数值证明三场非空；进一步反射检查发现原型 `MF_SSPR_G5_FieldDebug` 被多次原地重建后残留两代 Custom 节点，父材质复制到了不含 `DepthDisplayGain` 的旧 HLSL。按既定“接口变化新建干净函数”规则，现新建 `MF_SSPR_G5_FieldDebugV2`、`M_SSPR_G5_FieldDebugV2`、`MI_SSPR_G5_FieldDebugV2`，新父材质只有 1 个 Custom 节点和 10 个表达式，代码明确包含 Depth/Sigma 显示增益；Renderer 已改绑 V2 MI。当前 Debug 参数为 `DepthDisplayGain=10`、`SigmaDisplayGain=32`，旧原型不再被引用，待字段视觉 Gate 后统一清理。

第二张用户四宫格截图确认字段视觉 Gate 通过：方向张量颜色沿弯曲主流连续变化；MeanDepth 与 FrontDepth 呈稳定暖色色阶且轮廓同帧对齐；DepthSigma 大部分薄区域保持低值蓝色，而中央厚重叠区出现连续青色带。Mean/Front 接近符合当前喷流较窄的前后跨度，并非场失效。

### 2026-07-30 — [G5.3/G5.4 首个生产候选] 无历史双向 RK2 Streamline 与粒子深度约束接入

字段 Gate 通过后，先把当前完整 G5 字段状态冻结到 `recovery/G5_fields_pre_streamline_20260730_124836`；35 个资产逐文件 SHA-256 对比零不一致。随后只新建独立资产，不修改 G4 生产父材质与 MI：`MF_SSPR_G5_StreamlineDensityV1`、`MF_SSPR_G5_DepthCueV1`、`M_SSPR_AnisotropicSplat_G5`、`MI_SSPR_AnisotropicSplat_G5_HQ`。

Streamline 为材质内当前帧双向 RK2：每侧编译上限 8 步、默认活动 6 步、3 px 步长；双角度张量解码后用前一步切线保持符号连续。3×3 邻域只扩展 Direction/Depth Guidance，不直接模糊密度；沿曲线 Gather 使用 Coherence、曲率、MeanDepth/DepthSigma 双边权重、渐细核、双侧支持和孤立 Core 衰减。Medium/Body 首候选收窄为 `12/40 px`，Filament/Medium/Body 权重为 `0.25/0.50/0.25`。`MF_SSPR_G5_DepthCueV1` 以低强度 Mean/FrontDepth 与 Sigma 厚度衰减提供纵深提示；仍不启用强密度梯度阴影、不写 PixelDepth、不使用 History。

新 G5 父材质共 52 个表达式并零错误编译；Renderer 已绑定 `MI_SSPR_AnisotropicSplat_G5_HQ`，Main/Aux 子变量绑定均保留。Niagara Apply/Compile/Save、组件 Rebind/Reinitialize、关卡保存完成，系统 `UpToDate`、零错误、零警告；Fixed Tick、2048² Raster/Main/Aux、Bilinear 和禁用 Mip 均未改变。当前进入用户最终烟雾视觉 Gate。

### 2026-07-30 — [G5 视觉失败复盘与 Visual V2 候选] 末端连通性门控和真实深度受光

用户的首张 G5 生产近景截图确认初版未通过视觉 Gate：稀疏末端仍能辨认独立粒子簇，主体在高消光下接近纯白，几乎没有纵深。初版实际已经写入并采样方向/深度字段，但 `MF_SSPR_G5_DepthCueV1` 只对 Emissive 做低强度绝对深度、Sigma 和前后分离乘法；当前覆盖区平均 `MeanDepth≈0.0576`、`FrontDepth≈0.0553`、`DepthSigma≈0.0048`，按初版默认参数平均只造成约 2～3% 亮度变化。与此同时 `G5_IsolatedCoreScale=0.12` 明确保留了孤立核心，Medium/Body 也没有用 Streamline 连通性门控，因此字段技术 Gate 通过并不等价于最终画面获得了纵深或消除了粒子感。

修改前将 39 个 V2 资产和 5 份文档冻结到 `recovery/G5_visual_v1_pre_fix_20260730_130435`，逐文件 SHA-256 为零差异。随后保持 G4 与 G5 初版不变，新建 `MF_SSPR_G5_StreamlineDensityV2`、`MF_SSPR_G5_DepthLightingV2`、`M_SSPR_AnisotropicSplat_G5_V2`、`MI_SSPR_AnisotropicSplat_G5_V2_HQ`。Streamline V2 使用每侧 8 步、4 px RK2，并在局部法线方向增加五通道窄带 Gather；孤立 Core 设为 0，Medium/Body 必须获得 Streamline 连通性后才可进入密度整形。DepthLighting V2 用 FrontDepth 四邻域梯度构造屏幕空间表面法线，并叠加 DepthSigma 与 Mean/Front 分离产生的当前帧自遮蔽；仍不读取 History、不写 PixelDepth。

Visual V2 材质为 52 个表达式，编译零错误；Renderer 已绑定 `MI_SSPR_AnisotropicSplat_G5_V2_HQ`，Main/Aux 绑定完整。Niagara Apply/Compile/Save、Rebind/Reinitialize 与关卡保存成功，系统 `UpToDate`、零错误、零警告。活动 2048² RT 回读可唯一识别 Main/Aux，所有通道无 NaN/Inf，Coverage 未画满；Raster、Main/Aux 的分辨率、RGBA16F、Bilinear、Mip Disabled 和 Fixed Tick 均保持原基线。当前仅完成技术 Gate，近景末端、标准距离、转镜和平移仍需用户观察。

### 2026-07-30 — [视觉结论/路线修正] Visual V2 仍保留粒子感，后续转入当前帧归一化场重建

用户近景截图确认 Visual V2 仍未通过最终视觉 Gate：稀疏末端和外围仍能逐个辨认离散粒子，主体虽然比旧版连续，但宽糊、偏白，FrontDepth/MeanDepth/DepthSigma 对最终画面的纵深贡献仍不明显。当前已使用的手段包括各向异性粒子 Raster、LOD0 7×7/13×13 多尺度重建、方向张量、双向 RK2 Streamline、五通道横向 Gather、孤立 Core 清零、Medium/Body 连通性门控、深度双边权重与 FrontDepth 梯度受光；这些技术 Gate 均有效，但组合仍属于对离散密度的后处理，不能从根上形成稳定连续场。

后续不再通过继续扩大 Blur、增加 History 或恢复 Ping-pong 处理。已批准的新顺序是：紧支撑当前帧粒子贡献 → Coverage/方向/深度矩正则化 → 自适应归一化场对齐卷积 → 同一连续场分频得到 Filament/Medium/Body → Front/Mean/Sigma 构造厚度、透射与可见纵深。Visual V2 保留为可回退资产，下一实现只在 V2 开发目录新增独立函数/材质。

### 2026-07-30 — [V3 冻结快照] G5 Visual V2 输出链整理为自包含版本

按用户要求，将当前最终出效果的相互引用闭包整理到 `/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730`，而不是简单复制整个开发目录。快照共 11 个资产：V3 Niagara System、V3 父材质、V3 HQ MI、V3 验证关卡，以及按 `Functions/RasterInput`、`Functions/Reconstruction`、`Functions/Shading`、`Functions/Utility` 分类的 7 个实际被父材质调用的函数。7 个 Material Function Call、MI Parent、Niagara Renderer 1 材质与验证关卡主 NiagaraComponent 均已重定向到 V3 内部；Renderer 继续保留 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 和 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`。闭包审计未发现对 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2` 的效果链引用。

V3 Apply/Compile/Save 成功；Niagara `UpToDate`、零错误、零警告；材质零编译错误；Fixed Tick 保持 `true / 0.01667 s`。活动组件 Rebind/Reinitialize 后，Raster clone 为 `2048×2048×1`、Precision `65535`、Clear=true；Main/Aux 为 `2048×2048 RGBA16F`、Bilinear、Mip Disabled。完整 2048² 原始回读唯一识别一张 Main 和一张 Aux，两者非空、互异、无 NaN/Inf 且远未画满。V3 现冻结不再修改，编辑器已切回 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2/L_SSPR_AnisotropicSplat_Validation` 继续开发。

### 2026-07-30 — [FieldRecon V1/待人工视觉确认] Coverage 归一化场对齐卷积与深度传输接入

V3 冻结后，在 V2 开发目录新增 `MF_SSPR_G5_NormalizedFieldReconstructionV1`、`MF_SSPR_G5_DepthTransportLightingV1`、`M_SSPR_AnisotropicSplat_FieldRecon_V1` 与 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ`。FieldRecon 不再调用旧 LOD0 7×7/13×13 `MipPyramidDensity`，也不调用 G5 Streamline V1/V2；查询点先以 3×3 Coverage/密度加权邻域正则化方向张量和深度，再以每侧 8 步、每步 5 横向通道做无历史场对齐采样。Filament/Medium/Body 各自积累密度分子、Coverage/一致性/深度置信度分母与支持包络；双侧支持负责连接间隙，单侧贡献只以分频受限比例保留尖端，Raw 单粒子不再作为可见兜底。

DepthTransport 从正则化的 FrontDepth、MeanDepth、DepthSigma 推导 BackDepth、厚度与透射，并输出带近远色调、厚度染色、方向受光和自透射的 RGB 因子。首个 HQ 候选 SmokeColor 为 `(0.52, 0.58, 0.68)`，Ambient/Directional=`0.62/0.50`，使深度变化不再被纯白高环境光完全吞没。

新材质 51 个表达式、零编译错误；实际函数闭包只有 FieldRecon、DepthTransport、DensityShape、SmokeResolve、ScreenEdgeMask，审计确认无旧 Mip/Streamline 调用和无 `History` token。Renderer 1 已绑定新 MI 且保留 Main/Aux 子变量映射；Niagara Apply/Compile/Save、组件 Rebind/Reinitialize 和关卡保存完成，系统 `UpToDate`、零错误、零警告，Fixed Tick 保持 `true / 0.01667 s`。完整 2048² 原始回读唯一识别 Main/Aux，当前覆盖 `82,158 / 4,194,304`，所有通道无 NaN/Inf、未画满。下一步必须由用户观察标准距离和稀疏末端，确认粒子感、模糊度、流丝连续性与纵深是否得到实质改善。

### 2026-07-30 — [FieldRecon V1 首轮视觉结论/Connected MI] 圆点减少，但刷毛排线与孔洞仍未过 Gate

用户提供标准距离和近景截图。相对 Visual V2，独立圆点/软泡已明显减少，离散贡献开始沿方向场形成短丝，证明 Coverage 归一化场对齐路线有效；但当前输出仍未通过最终 Gate：近景能看到大量方向一致的短刷毛和离散排线，主体透明度偏低，Medium/Body 支撑不足造成背景穿孔，纵深蓝灰变化虽已出现但被稀疏密度削弱。

保留初始 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_HQ` 不变，新建并绑定 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`。主要调整为 StepPx `3.25→2.25`、GuideRadius `3.5→4.5`、Medium/Body Cross `4/13→2.75/8.5`、SupportGain `0.38→0.85`、OneSidedBlend `0.32→0.46`，Filament 权重/增益下调，Medium/Body 上调，Detail/Edge 设零，BlackPoint `0.006→0.001`，并提高低密度响应、消光与不透明度。目标是先消除刷毛采样节奏和孔洞，再恢复尖细 Filament 比例。

### 2026-07-30 — [运行实例修复] 重复 Rebind 累积 DI clone 导致活动 RT 全零

Connected MI 绑定后的严格 RT Gate 首次失败：System 编译、Renderer 材质和 Main/Aux 子变量绑定均正确，但活动 Main/Aux 全零。检查关卡组件发现反复执行 `set_asset(None) → set_asset(System)` 已把运行实例从预期的 `1 Raster + 2 RT` 累积为多代 DI override，最高观察到 `3 Raster + 5 RT`；重新载入关卡仍为空，说明污染已序列化到组件，而非一次冷启动延迟。

在 V3 冻结快照可恢复的前提下，记录旧 Actor Transform，在同一 `Location=(480,110,570)` 创建干净 NiagaraActor，只绑定 V2 System 一次，配置 `1×2048²×1 RasterizationGrid3D` 与 `2×2048² RGBA16F/Bilinear/Mip Disabled RT`，激活验证后删除旧污染 Actor，并以原标签保存关卡。严格原始回读随后恢复：唯一 Main/Aux、非零覆盖 `84,757 / 4,194,304`、无 NaN/Inf、未画满。旧 Actor 已删除但可由 V3 恢复。`_g5_rebind_reinitialize.py` 已修改为同一 System 资产只原地 Reinitialize；真实 DI 接口变化今后使用一次性干净组件替换，不再积累 override。

### 2026-07-30 — [近景性能 Gate] Dense Raster 追帧螺旋修复为质量守恒 Sparse Raster

解析用户提供的 `precisefluid-0-2026.07.30-12.57.57.profViz` 后确认，“RasterGrid 100+ ms”不是单次迭代：该帧总 GPU 约 `467.993 ms`，Niagara 因 Fixed Tick 在一个渲染帧内补做了 24 次模拟；每次 Raster 为 `17.70～18.88 ms`，Resolve 约 `0.19～0.20 ms`，Grid Clear 约 `0.325 ms`，粒子 Dispatch 从 `280,839` 增至 `300,010`。单次 Raster 已超过 `16.67 ms` 固定步长，构成“帧慢→补步→GPU 更慢→继续补步”的追帧螺旋。资产读回同时确认当前真实配置为 `SpawnRate=50,000/s`、Lifetime=`5s`，约 25 万稳态粒子，而不是旧规格里的约 2.5 万。

旧 Raster 每粒子固定枚举 `49×11=539` 个高斯候选，每个有效样本最多写入 5 个加法矩和 1 个前沿深度最大值。当前在不降低 `2048²`、粒子数、材质采样数，不关闭 Fixed Tick、不改变 Main/Aux 六属性语义且不引入 History 的前提下，改为质量守恒 Sparse Raster：投影/近平面/扩展屏幕边界先剔除，候选上限改为 `25×5=125`，并以 Dense 可见核的可分离权重和对 Sparse 权重和进行单粒子质量归一化。Dense HLSL SHA-256 为 `69dc67f6e9a58fa457982b6dfee3889e11e04f838b5934b56cb3891bec20598c`，Sparse HLSL SHA-256 为 `761b87f75279b469d6cd5628dffe3a4c1df04eaa351943e602438c6b438e92b4`；V3 仍是修改前自包含恢复点。

曾先在 `Performance/NS_SSPR_AnisotropicSplat_PerfSparseV1` 上做候选，但发现当前 UE 5.8 对这套含嵌入式 Scratch Simulation Stage 的 Niagara System 执行 `duplicate_asset` 后，即使复制品 `UpToDate`、图连接与常规模块输入一致，未修改的复制对照运行时 Main/Aux 仍全零；Sparse 复制品也只在单一投影中心附近产生约 15 个非零像素。由此不能把 Niagara 资产复制成功视为可运行备份 Gate。关卡已恢复原 V2 System，Sparse HLSL 在原活动资产上原地 Apply/Compile/Save，并通过运行 RT Gate。

程序化 `ProfileGPU` 在约 `251,666～253,333` 粒子下得到 Sparse Raster 首次 `0.930 ms`、随后 `0.559/0.563 ms`，稳态约 `0.56 ms`；Resolve 为 `0.153～0.158 ms`。相对旧 Dense Raster 单次降低约 `97%`，显著低于 60 Hz 固定步长。快速原始 Gate 在三块区域共抽样 `393,216` 像素：Main R 非零 `6,970`、最大 `4.2109375`，G/B 仍含正负方向值；Aux R 非零 `4,218`，G/A 非零 `6,970`、A 最大 `1.0`；无 NaN/Inf、未画满。最终系统 `UpToDate`、零错误、零警告，`SpawnRate=50,000/s`、Fixed Tick=`true / 0.01667s`、Main/Aux 2048² RGBA16F/Bilinear/Mip Disabled 均未改变。下一步只需用户在同一近景与动态转镜条件下确认 Sparse 核没有引入可见点列、缺口或密度宽度退化。

### 2026-07-30 — [性能候选失败/紧急恢复] Sparse 短时 Gate 为假阳性，回滚原始 Dense G5

用户首次视觉检查发现烟雾完全消失。跨请求推进 60 帧后，活动组件所有 Main/Aux 均为零，证明此前“性能 Gate 已通过”的结论无效。当前组件已累积为 `2 Raster + 4 RT`；恢复 Dense HLSL、重新编译和替换为干净 V2 组件后仍全零。进一步发现 V3 复制关卡的主组件已随 V2 一起改回 V2 System，说明其外部 Actor 并未形成可靠隔离；`duplicate_asset(NiagaraSystem)` 与复制关卡都不能作为本轮运行恢复点。

原 V2 `.uasset` 因编辑器进程锁定无法在线覆盖，先备份为 `Saved/CodexBackups/NS_SSPR_AnisotropicSplat_Main_broken_sparse_blank_20260730.uasset`。随后把 `recovery/G5_visual_v1_pre_fix_20260730_130435` 中 SHA-256=`E122D5266E1C10934696797DB45D39714A8B20D00862C46AD3A05AA865363E52` 的同包名原始二进制复制到 `/Game/SSPR_Validation/Recovery/DenseG5_20260730/NS_SSPR_AnisotropicSplat_Main`。恢复 System 使用原 `49×11` Dense Raster，Renderer 绑定 `MI_SSPR_AnisotropicSplat_G5_HQ`，不是最新 FieldRecon。

恢复 Gate 改为两个独立 MCP 请求：请求 A 只生成并保留严格 `1 Raster + 2 RT` 的干净候选，让异步 Niagara GPU 编译和渲染线程实际跑帧；请求 B 再推进 300 帧、回读并替换空白 Actor。最终 Main 抽样非零 `33,517`、最大 `4.4921875`，方向 G/B 含正负值；Aux R 非零 `17,742`、Coverage 非零 `33,517`、A 最大 `1`，无 NaN/Inf。恢复 System `UpToDate`、零错误零警告，关卡已保存。此前 `0.56 ms` 只代表失效/空路径的短时数据，Sparse 性能 Gate 正式判失败；下一步先由用户确认 Dense G5 重新可见，再恢复最新 FieldRecon 与重新设计性能方案。

用户确认 Dense G5 已重新可见。随后只修改恢复 System 的 Renderer 1，将材质从旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 切回 `MI_SSPR_AnisotropicSplat_FieldRecon_V1_Connected_HQ`，Main/Aux 子变量绑定保持不变。Apply/Compile/Save 后为 `UpToDate`、零错误零警告；独立下一请求推进 60 帧后 Main/Aux 仍非零。由于 Renderer Apply 会使已存在组件热重载并累积到 `3 Raster + 6 RT`，最后再以最终已编译 System 创建一次干净候选，跨请求回读通过后替换旧组件。当前活动组件严格为 `1 RasterizationGrid3D + 2 RenderTarget2D`，另有 1 个 System 正式遗留 Grid2D；关卡已保存，不再对该恢复 System 执行 Apply/Rebind。

### 2026-07-30 — [视觉基线回退] 用户选择旧 G5 HQ，FieldRecon Connected 降为实验候选

用户对恢复后的 FieldRecon Connected 近景截图做出明确判断：旧 `MI_SSPR_AnisotropicSplat_G5_HQ` 的表现更好。FieldRecon 的 Coverage/一致性/深度置信度归一化会在稀疏支撑处削薄 Medium/Body，较强的 DepthTransport 又进一步拉开局部亮度与色调，结果是短丝、孔洞和孤立贡献更容易被辨认，主观粒子感反而强于旧 G5。该结论不是否定 Main/Aux 深度字段，而是否定当前 FieldRecon 把深度传输与支撑归一化耦合到最终显示的方式。

修改前已备份恢复 System 到 `Saved/CodexBackups/NS_SSPR_RecoveryDense_FieldRecon_before_G5_visual_restore_20260730.uasset`。Renderer 1 已切回 `/Game/SSPR_Validation/M2/AnisotropicSplat_V2/MI_SSPR_AnisotropicSplat_G5_HQ`，并保留 `TrajectoryTexture <- User.SSPR_SimRT.RenderTarget` 与 `TrajectoryAuxTexture <- User.SSPR_AuxRT.RenderTarget`。Apply/Compile/Save 后 System 为 `UpToDate`、零错误零警告。材质热重载把旧活动组件累积为 `2 Raster + 4 RT`，因此再次用最终已编译 System 生成一次干净 Actor，并在下一独立请求推进 300 帧、回读 Main/Aux 后替换旧 Actor。

最终活动组件严格为 `1 RasterizationGrid3D + 2 RenderTarget2D`，另有 1 个正式遗留 `Grid2DCollection`。跨请求三块区域共抽样 `393,216` 像素：活动 Main R 非零 `41,201`、最大 `38.625`，G/B 含正负方向值；活动 Aux R 非零 `28,886`、Coverage 非零 `41,201`、A 最大 `1.0`；全部通道无 NaN/Inf、未画满。关卡已保存，当前人工视觉基线正式恢复为旧 G5 HQ；FieldRecon 资产保留但不再绑定。下一步近景性能优化必须以该基线做对照，且不得再次原地 Apply/Rebind 当前恢复 System。
