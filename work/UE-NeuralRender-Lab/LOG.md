# UE Neural Render Lab · LOG

> 决策流水。追加式，新条目加在**文件末尾**。

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

### 2026-07-07 16:53 — [决策] 初始化 UE 神经渲染实验室
项目目标定为探索 UE 小模型部署、神经后处理材质、神经渲染管线接入当前生成管线的可行性；首轮不直接写实现，先做路线盘点与可行性矩阵。

### 2026-07-07 16:58 — [发现] 全网侦察：四条路线可行性差异很大

**路线一｜NNE 实时推理（引擎内跑真 ONNX 模型）**
- 官方插件自 UE5.2 起随引擎带，标注 Experimental。核心资产 `UNNEModelData`，两条运行时接口：`INNERuntimeCPU`（CPU同步）/ `INNERuntimeRDG`（GPU、走渲染图，不经CPU回读，适合后处理/降噪/超采样）。
- 可跑通的参考仓库：
  - `microsoft/OnnxRuntime-UnrealEngine`（官方 FPStyleTransfer 示例，风格迁移）—— 原始版本 CPU staging 导致低帧率
  - `DeadMorose777/OnnxRuntime-UnrealEngine`（UE5.5 移植，去掉CPU staging，端到端GPU-only：编码用compute shader → `INNERuntimeRDG::EnqueueRDG` 推理 → 解码合成为post-tonemap pass）
  - NVIDIA 官方博客：NNERuntimeTRT(TensorRT for RTX) 跑同一 style transfer sample，RTX 5090/1080p，DirectML 5.7ms → TensorRT 3.8ms（1.5x）
- 硬约束：ONNX Zoo模型多为定长 1x3x224x224，覆盖全屏需 Tiling（多次inference/frame，CUDA↔图形上下文切换开销大）或改模型尺寸到720x720之类避免切块。
- 平台现实：三方QA评测（techbyteblog）指出主机/移动端支持仍是"实验性或不存在"，NPU目前基本只有Intel通过DirectML跑通。

**路线二｜Neural Post Processing（材质编辑器零代码接入）**
- UE官方文档明确标 Experimental，"谨慎用于上线项目"。流程：ONNX→NNE Model Data→Neural Profile资产→后处理材质挂 `Neural Input`/`Neural Output` 节点。
- 两个后端：`NNERuntimeORTDml`（DirectML）、`NNERuntimeRDGHlsl`（卷积按32对齐优化）。
- 局限同路线一（分辨率受模型尺寸限制），且一个材质只能调用一次Neural Input（Neural Output可多次）。

**路线三｜ML Deformer —— 唯一确认已生产落地**
- Neural Morph Model / Nearest Neighbor Model 已用于 Epic 自家 MetaHuman 管线的布料/肌肉形变。三方深度测评（dredyson, UE5.6）确认《巫师4》Demo 用的正是"多ML Deformer叠加（长度激活+曲线驱动）"方案。
- 解决的是蒙皮形变问题，不是通用后处理/生成管线，但证明"神经网络技术在UE生产管线里能落地"这件事本身是成立的。

**路线四｜离线神经渲染管线导入（3DGS/NeRF类）——最稳的路线**
- 不走UE内runtime推理，本质是外部训练+UE内渲染展示。插件生态成熟：`NanoGS`(简单，PLY直接拖入)、`MLSLabs`(支持4DGS序列/动画splat，需装PyTorch依赖)、`XScene/XVerse`(基于Niagara实现实时splat渲染)。
- 不依赖实验性API，工程风险最低。

**行业信号**：Arm × Sumo Digital《光影新生/Neural Dawn》（UE5.6.1，17人18个月，2026Q4上线）是目前唯一"神经图形+UE生产管线"完整商业案例，集成MegaLights+光追+神经超采样(NSS)/神经帧率提升(NFRU)。但依赖Arm下一代Mali GPU专用神经加速器，硬件门槛是硬约束，不是纯软件可复现方案。

**结论**：路线三、四工程风险最低，可优先做POC；路线一、二技术新颍但仍是Experimental标签，适合小范围验证不适合直接排产。

### 2026-07-07 17:10 — [发现] RDG推理管线技术栈拆解 + 找到可编译运行的完整源码

**技术栈四层**：
1. **RDG (Render Dependency Graph)**：UE4.22起的渲染子系统，DAG调度，核心类`FRDGBuilder`，通过`AddPass()`加节点声明读写的`FRDGTexture`/`FRDGBuffer`，UE自动处理依赖顺序和内存屏障。
2. **SceneViewExtension**：接入渲染管线的钩子，继承`FSceneViewExtensionBase`，在`SubscribeToPostProcessingPass()`注册回调挂到指定后处理阶段（如Tonemap之后），每帧拿到`FRDGBuilder`引用。
3. **Compute Shader (.usf)**：手写HLSL做"翻译"——SceneColor纹理编码成tensor buffer（NCHW布局），推理完解码回纹理。这是材质编辑器覆盖不到的自由度。
4. **NNE的RDG接口**：`INNERuntimeRDG`/`IModelInstanceRDG::EnqueueRDG()`，直接吃`FRDGBufferRef`，让模型推理作为图里一个Pass，和渲染Pass共享同一条GPU时间线，全程不落地CPU。

**可编译运行的案例**：`DeadMorose777/OnnxRuntime-UnrealEngine`（微软官方FPStyleTransfer的UE5.5移植版，端到端GPU-only）。已抓取核心源码（`RealtimeStyleTransferViewExtension.cpp` + `MyNeuralNetwork.cpp`），完整链路：
- 构造函数检测RHI（仅D3D12/D3D11激活）→ `SubscribeToPostProcessingPass`注册到`EPostProcessingPass::Tonemap`
- `FEncodeCS`：SceneColor纹理 → `GraphBuilder.CreateBuffer`创建InputTensor buffer → compute shader编码
- 推理核心一行：`ModelInstance->EnqueueRDG(GraphBuilder, InputBindings, OutputBindings)`，Binding直接绑`FRDGBufferRef`
- `FDecodeCS`+`FUpscaleCS`：OutputTensor解码成低分辨率纹理 → 放大到ViewRect尺寸
- `AddCopyTexturePass`拷回目标纹理，全程零CPU回读
- 模型初始化走`UE::NNE::GetRuntime<INNERuntimeRDG>("NNERuntimeORTDml")` → `CreateModelRDG` → `CreateModelInstanceRDG` → `SetInputTensorShapes`

**与材质路线的关系**：材质编辑器里`Neural Input`/`Neural Output`节点在幕后做的正是这套Encode→EnqueueRDG→Decode流程；自己写C++等于拿到这套流程的完全控制权——分辨率不再受224²限制（模型分辨率单独跑，手动Upscale合成任意屏幕分辨率），编解码算法可自定义。可作材质POC出效果后的进阶延伸起点，直接fork改造。

### 2026-07-07 17:34 — [发现] 两条路线的应用场景清单 + RDG路线找到官方生产级案例(NNEDenoiser)

**材质路线的应用场景（官方文档直接点名，不是猜的）**：
- 风格转换：AnimeGAN / CartoonGAN / Pix2Pix / CycleGAN
- 素描风格：ShadeSketch
- 神经色调映射
- 图像分割与分类
这几类输出本质是"整屏颜色重映射"，天然适配材质图的运作方式。个人作品集角度，AnimeGAN类卡通风格化最值得做——视觉冲击力强，还能跟Part2(美术审美)呼应，做成"神经网络风格化 vs 手写材质风格化"对比。

**RDG路线的意外发现：NNEDenoiser——不是demo，是官方默认开启的生产功能**
- UE路径追踪器(Path Tracer)默认启用的降噪插件，支持通过NNE运行时导入和运行**自定义**神经降噪器网络。模型以`UNNEModelData`资产形式导入，推理可在CPU/GPU/RDG上跑（取决于选定运行时）。
- 自带Intel Open Image Denoiser三档预设(fast/balanced/high quality)，但接口开放，可换成自研或第三方降噪模型。
- 论坛证据（UE5.4.4/5.5.1开发者反馈）：已有人用同一套RDG HLSL runtime做超分辨率任务（ConvTranspose算子），证明这套接口已扩展到风格迁移之外的实用场景。
- 行业佐证：AMD FSR Redstone套件（Neural Radiance Caching / ML Super Resolution / ML Frame Generation）走的是同一条"RDG里跑轻量神经网络"思路，不是UE孤例，是行业方向。

**结论/建议**：RDG进阶篇章不必局限于复刻风格迁移demo，更有说服力的叙事是"接入NNEDenoiser接口，跑一个自定义降噪/超分模型，讲清楚它和路径追踪管线(Movie Render Queue)的耦合方式"——这样故事是"理解并扩展了UE官方生产管线里已经在用的架构"，比"搬了个开源风格迁移demo"分量更重，也更贴近TA工作里"性能预算+管线集成"的核心价值主张。

### 2026-07-07 20:09 — [发现] 材质路线完整操作细节 + Neural Profile 参数全表 + 两种索引模式

抓取UE5.7官方文档完整正文（此前只拿到摘要），补全材质路线的实操细节：

**五步流程**：①启用Neural Rendering插件 ②导入ONNX→NNE Model Data资产 ③创建Neural Profile资产（Material→Profiles菜单），把NNE Model Data塞进模型插槽 ④新建材质：Material Domain=Post Process + 勾选Used with Neural Networks + 赋值Neural Profile，图表挂Neural Input(仅能调用1次)/Neural Output(可多次)节点接到Emissive Color ⑤点Apply生效。

**Neural Profile资产参数全表**：
- 模型组：Runtime Type(NNERuntimeORTDml/NNERuntimeRDGHlsl)、NNE Model Data、Input/Output Dimension(只读)
- 重载组：Batch Size Override(模型batch维为动态-1时手动指定)
- 图块组：Tile Size(可设Auto，UE自动铺满图块，官方例子：模型输入1x3x200x200，缓冲区1000x1000→自动切5x5=25图块打包成(5x5)x3x200x200一次批量跑完再合并)、Border Overlaps(图块边界重叠幅度)、Overlap Resolve Type(Ignored忽略 / Feathered线性羽化混合——官方风格转换范例用2x2图块+Feathered隐藏接缝)

**调试命令**：`r.Neuralpostprocess.TileOverlap.Visualize 1`可视化图块重叠区域（可作breakdown截图素材）；`r.Neuralpostprocess.Apply`开关神经网络（关闭时Output直接原样返回Input值，方便A/B对比）。

**两种索引模式（此前完全没挖到的信息）**：
- 纹理索引模式(默认)：只原生支持[1x3xHxW]标准布局，纹理会缩放到目标尺寸(Tile=Auto时不缩放，纹理外图块被镜像)
- 缓冲区索引模式(Buffer Indexing Mode)：支持任意[BxCxHxW]模型(B≠1)，不做自动过滤，需材质图/自定义shader手写读写逻辑。官方例子：屏幕切成B=2x2=4批次，用Neural Input/Neural Output(Buffer)节点分别处理；需配合Batch Size Override=4(支持动态批次)或Tile Size=2x2(不支持动态批次)，两者可叠加

**运行时差异**：NNERuntimeORTDml走DirectML后端；NNERuntimeRDGHlsl卷积按输出宽度优化，结果对32取模(意味着输出宽度理想应为32倍数)。

**三个踩坑点**：①一个材质仅1次Neural Input但Neural Output可多次调用，决定材质图结构；②最终分辨率被模型输出尺寸卡死(先查Neural Profile的Output Dimension)，提升清晰度只能换高分辨率模型或用Tile/Buffer索引拆分，图块边界可能有肉眼可见不连贯(可作"取舍"素材)；③纹理索引模式原生只吃BCHW，TensorFlow默认导出BHWC需显式转换否则读错通道。

**对作品集breakdown的价值**：多数人只会用默认纹理索引模式，能讲清楚Buffer Indexing Mode怎么手动控制批次拆分 + Tile重叠可视化截图，比单纯"套了个风格迁移模型"更能体现工程理解深度。

### 2026-07-22 — [裁决] 从当前作品集排期归档

本裁决只影响个人作品集，不删除独立 Lab：现有四路线均是侦察建议，没有本人选定的真实应用问题、POC、成熟基线或实测。旧“Portfolio 用”措辞不再构成排期；未来必须由本人先选一个问题、一个非神经基线和一个研究赌注，完成最终效果与 A/B 后再申请收录。

### 2026-07-23 — [决策] 重开并收缩为一个实时神经风格化案例

本人明确需要一个神经渲染作品。项目只保留“离线 Teacher 风格蒸馏为轻量 Student，并通过 UE 5.8 Neural Post Processing 在 Bifrost 测试场景实时运行”这一条路线；传统 Post Process Material 为非神经基线。当前不做自定义 RDG/SceneViewExtension、降噪、超分、ML Deformer、3DGS 或多风格模型。

### 2026-07-23 — [发现] MCP 在线端点未启动，静态前置条件成立

`http://127.0.0.1:8000/mcp` 当前无法连接，系统中未发现 UnrealEditor 进程，因此本轮不能把 Neural Profile/材质节点自动化写成已验证能力。静态检查确认 `Abyss.uproject` 已启用 `NeuralRendering`、`ModelContextProtocol`、`EditorToolset` 与 `VibeUE`，UE 5.8 Neural Rendering 源码和 Win64 二进制存在；下一步在编辑器启动后只做 live tool discovery 与隔离 Probe。

### 2026-07-26 19:25 — [发现] MCP 神经材质结构链路通过在线 Probe

在 `/Game/NeuralRenderLab/_MCPProbe` 验证了 `NeuralProfileFactory`、Profile 设置 schema、Post Process/Used with Neural Networks/Profile 绑定、`PPI_PostProcessInput0.Color → Neural Input.Input0` 与 `Neural Output.RGBA → Emissive`。所有资产类型、属性和连线均已用独立工具回读；未保存或修改 Bifrost 关卡。项目与工作区没有现成 ONNX，因此 NNE Model Data 导入、模型绑定、材质编译、运行画面和 GPU 数据仍属于 G2，不能写成已通过。

### 2026-07-26 19:26 — [发现] UE 5.8 批量删除被引用 Neural Profile 会触发渲染线程断言

对同时包含神经材质与其 Profile 的 Probe 目录调用批量删除时，编辑器在 `FNeuralProfileModelTextureManager::RemoveProfile()` 的 `FindAndRemoveChecked()` 断言退出。日志显示删除顺序先处理了仍被材质引用的 Profile。后续硬性采用“解除 Profile 引用并回读 → 删除材质 → 删除 Profile → 删除目录”的粒度化清理，不再对神经资产目录做批量删除。崩溃后的 Probe 内容与 autosave 已移出 Content/Autosaves，暂存到 `Saved/CodexTrash/NeuralRenderProbe-20260726-1926`，可恢复。

### 2026-07-26 19:30 — [发现] 共享 Abyss 工程的另一插件 Shader 改动阻塞编辑器重启

重启 Abyss 时，全局 Shader 编译在 `GaussianSplattingComposite.usf(36)` 失败：`GSRelightAmbientColor` 无法绑定到 `FGSCompositePS::FParameters`。编辑器停在 Error 窗口，MCP 端口未恢复。本项目不修改该插件；G2 继续前必须由其所有者恢复可启动的共享工程状态。

### 2026-07-26 22:14 — [发现] G2 最小 ONNX 接入链通过，实际推理画面与性能仍待验收

临时生成的 Identity ONNX 已通过 `onnx.checker`：opset 17、IR 9、BCHW Float32、输入输出 `[1,3,64,64]`、151 B，SHA256 `b8e9127ecd6e432cbab50aea89b118c42876d57de7236c30c0b59695f248f170`。在 `/Game/NeuralRenderLab/_MCPProbeG2` 完成 NNE Model Data 导入、`NNERuntimeORTDml` Neural Profile 绑定、维度回读、神经 Post Process Material 编译和临时 Unbound Post Process Volume 挂接；所有关键属性、材质连线和 Blendable 引用均独立回读通过，日志未出现相关编译错误。

编辑器当前为四视图且非实时，`ViewportService.set_realtime(true)` 返回成功但 `is_realtime` 仍为 false，因此本轮不把实际推理帧、画面或 GPU 数据写成已通过。回滚严格按“解除 Volume Blendable → 删除 Volume → 清空材质 Profile 引用 → 删除材质 → 删除 Profile → 删除 NNE → 删除空目录”执行；每一步均回读，编辑器与 MCP 保持在线，Bifrost 未保存。Postflight 回读显示关卡包仍为 dirty；由于操作前没有记录其 dirty 状态，未擅自清除或重载，以免覆盖既有未保存改动。3 个 G2 autosave 已移到 `Saved/CodexTrash/NeuralRenderProbe-G2-Autosaves-20260726`，可恢复。

### 2026-07-27 21:26 — [决策] 签字目标风格为冷色北欧概念插画与轻度丝网印刷质感

唯一视觉方向确定为图形化概念插画：6–8 个主色、冷青阴影与暖橙高光、阴影压缩成大色块；保留建筑和主体轮廓，内部材质适度简化；笔触限制在大表面且不跨越物体边界；天空、发光体和粒子保留较完整亮度层次。传统 Post Process 负责色板、明暗压缩和轮廓基线，神经模型必须证明额外的稳定笔触、材质抽象或局部色彩重组价值。G0 尚需锁定主参考图、5 个固定镜头和 1 条未见相机路径。

### 2026-07-27 21:43 — [决策] 建立可渐进调效的最小成对蒸馏框架

本人选择先搭框架、再逐步调整目标效果，不把主参考图作为当前阻塞。新增单文件 PyTorch Student 训练/续训/ONNX 导出流程，数据契约为同名 `input`/`target` 成对图；训练目标暴露 Teacher、色块、结构、纹理、色板和平面简化六项权重，整体强度留给 UE 材质 Blend。默认模型 750,051 参数、FP32 权重约 2.86 MiB；RTX 5060 上完成 256²、batch 4 的真实反向传播自检，峰值分配约 384.4 MiB。512² 静态 BCHW ONNX 为 2.87 MiB，通过 opset 17 导出与 `onnx.checker`。未加入 Teacher 生成器、时序损失、多架构和超参平台；只在真实画面暴露对应问题后扩展。

### 2026-08-01 — [执行] 完成 v00 单帧神经风格化冒烟与 UE 接入

使用一张 Bifrost 编辑器帧作为唯一内容源；裁掉左侧 80 px 的编辑器 XYZ gizmo 后得到 `1886×1071` 输入。生成的 `data/reference/style_v00_imagegen.png` 只作为冷色北欧概念插画 + 轻度丝网印刷的风格尺，因其会重画地形，未直接作为像素对齐 target。另用一次性离线脚本从原图生成严格同构 `data/train/target/fog_v00.png`，并将这一对图 hardlink 为 64 个训练键，让随机 crop 覆盖画面；这不是内容扩充。

按 `config.v00.json` 训练：`channels=32`、`blocks=3`、`crop_size=128`、80 epochs、batch 8、学习率 `0.0002`、workers 0、AMP 开启；最佳验证损失 `0.05604`（epoch 68）。最佳权重为 `runs/v00_single_r2/best.pt`，对比图为 `runs/v00_single_r2/comparison_source_teacher_student.jpg`。Student 已学到冷青抬升和地形保留，但暖橙高光偏弱、色块偏硬；这是单帧过拟合的链路证明，不是可泛化的作品集模型。

导出 `exports/NRL_Student_v00_512.onnx`：1,046,201 bytes、opset 17、静态输入 `[1,3,512,512]`，`onnx.checker` 通过；SHA256 `F223FB49A13D37B028B56DC9402BAC333E6DAE1D7C169DC66417B43C3376E70`。

UE MCP 接入已完成并独立回读：

- Model Data：`/Game/NeuralRenderLab/v00/NRL_Student_v00_512.NRL_Student_v00_512`。
- Neural Profile：`/Game/NeuralRenderLab/v00/NP_NRL_v00.NP_NRL_v00`，Runtime 为 `NNERuntimeORTDml`，输入/输出均为 `1×3×512×512`，Batch Override=1，Tile=Auto、无 overlap。
- Post Process Material：`/Game/NeuralRenderLab/v00/M_NRL_v00_PP.M_NRL_v00_PP`；SceneColor → Neural Input → Neural Output，与原 SceneColor 用 `Strength` 参数 Lerp，再接 Emissive；材质域为 Post Process，编译成功。
- 当前 Bifrost 关卡新增临时 unbound Volume：`/Game/Bifrost/Maps/L_Bifrost.L_Bifrost:PersistentLevel.PostProcessVolume_0`，priority 100、blend weight 1、仅挂该材质；输入节点、输出节点、Profile 和 Blendable 引用回读一致，相关 NNE 错误查询为空。

尚未做 CaptureViewport 或 GPU/显存基线：当前只能确认资产、图结构和编译链，不把实时画面写成已验收。Volume 使 Bifrost 关卡包保持 dirty，已刻意不保存关卡；Model Data/Profile/Material 当前为 clean。下一步是用户手动查看实时视口并记录画面，再制作多镜头成对 Teacher、传统材质基线和未见路径测试。

### 2026-08-05 — [执行] v01 材质感知局部重光 pilot 完成离线训练与导出

本人否决 v00 的高饱和、硬色块与丝网栅格方向；新目标收缩为“克制电影概念图 + 材质感知局部重光”：球体使用象牙白/淡金高光并只对邻近云产生暖色响应，远处同色云保持冷灰蓝，禁止可由全屏 LUT/纹理直接复现的风格覆盖。

使用当前 `1699×1145` 场景截图，裁掉左右 19/11 px 查看器边框。ImageGen B 方向稿只作低频光照参考；`make_teacher.py` 将宽尺度光色残差迁移回源图并保留源高频，使用 `strength=0.85`、`base_strength=0.15`、`radius=36` 与单个软焦点椭圆，生成严格保留云形、球体纹路和遮挡的 `1669×1145` Teacher。训练器新增 `data.repeats` 以替代单帧 hardlink，并新增差异区域候选裁剪，避免随机 crop 被大面积不变区域主导。

首个 4-block/256-crop Student 在完整画幅把远处白云一起染暖，暴露出感受野和训练采样不足。最终候选 `config.v01-pilot-context.json` 改为两级降采样、6 个扩张残差块、512 crop，并保留 25% 普通区域裁剪；最佳为 epoch 39。中央 512 crop 的 Teacher L1 相对原图降低 `84.7%`；完整画幅降低 `72.5%`，相对简单全局 RGB 仿射基线降低 `16.2%`。上方远云仍有轻微暖色泄漏；这些均为同帧过拟合检查，不是 held-out 泛化证据。导出 `exports/NRL_Student_v01_pilot_context_512.onnx`：4,669,270 bytes、opset 17、静态 `[1,3,512,512]`，SHA256 `950B620ADCFEF8E45475EB858B4A5A871884028266F36A4472F8436E56BFBC93`。

UEAgent doctor 为 HEALTHY，当前关卡 `/Game/Bifrost/Maps/L_Bifrost`，`/Game/NeuralRenderLab/v01` 不存在；但关卡 dirty。NNE 导入所需 `execute_python_code` 在当前插件版本会先保存所有 dirty 包，因此未越过保存边界，也未创建任何 v01 UE 资产。必须由本人先处理 dirty 内容或明确授权保存全部 dirty 包后再继续。

### 2026-08-06 11:55 — [执行] v01 完成 UE 结构接入并进入实时目视验收

导入并精确保存 `/Game/NeuralRenderLab/v01/NRL_Student_v01_Context_512`、`NP_NRL_v01_Context` 与 `M_NRL_v01_Context_PP`。Profile 为 `NNERuntimeORTDml`、输入输出 `1×3×512×512`、Tile Auto；材质复用 v00 已审计图，只替换 v01 Profile，SceneColor → Neural Input → Neural Output → Strength Lerp → Emissive 回读一致，相关错误日志为空。

现有 `PostProcessVolume_0` 已在内存中改为 v01 材质、priority 100、blend weight 1、unbound，并标记到 `Codex/NeuralRenderLab/v01`；`L_Bifrost` 因预览保持 dirty，未保存。结构通过不等于画面通过，下一步由本人在实时视口用 Blend Weight 0/1 做 A/B，再决定是否继续多帧数据与性能 Gate。

### 2026-08-06 13:30 — [发现] 重载后临时 Volume 回到 v00，已复用原 Actor 重挂 v01

用户未找到 v01 标签的原因是此前预览未保存；重载后同一 `PostProcessVolume_0` 回到了保存的 v00 标签/材质。已不新建重复 Actor，直接切回 v01 材质、标签与 `Codex/NeuralRenderLab/v01` 文件夹；当前关卡再次 dirty，仍不保存。

### 2026-08-06 21:55 — [发现] v01 实时成本过高，已关闭预览

用户确认 v01 对编辑器性能影响严重。按网络结构估算，48 通道、6 个宽上下文块与 512 tile 在 1920×1080 下约覆盖 12 个 tile，总计约 `383.2 GMAC/frame`；这是算量估算，不替代 ProfileGPU。已把临时 Volume 的 Blend Weight 设为 0 并回读，未保存 `L_Bifrost`。

不通过缩小 tile 到 256 解决：它会把 1080p tile 数增至约 40。下一候选只改现有配置为 24 通道、4 个宽上下文块、384 tile，估算约 `57.3 GMAC/frame`（v01 的 15%）与约 0.80 MiB FP32 权重；尚未训练，先由本人决定是否接受这次质量换性能实验。

### 2026-08-12 — [维护] 训练运行态迁出项目目录

将 `data/`、`runs/`、`exports/` 迁到 `tmp/UE-NeuralRender-Lab/`，四份配置同步改为从配置文件目录解析该位置；删除可由 `uv.lock` 重建的项目内 `.venv`。今后 `work/UE-NeuralRender-Lab/` 只保留代码、配置、锁文件和正式文档，训练素材、checkpoint、Preview、指标、ONNX 与 Python 环境都属于可清理过程态。完成项已从 `BACKLOG.md` 移除，历史仍由本日志保留。

### 2026-08-14 — [决策] 封存全屏后处理，切换为 tiny neural material 研究

作品集目标已结束；本人授权把范围扩为探索与科研。此前玩家扩散场因可由深度/材质算法直接表达而否决，v00/v01 全屏 Neural Post Process 因神经必要性弱及运行成本高而封存。当前唯一合同改为单材质离线验证：程序化分层湿石材 Teacher、标准 PBR 基线和 learned latent texture + tiny MLP Student。R1 只验证未见 light/view 组合上的表达优势与表示大小；未通过不进入 UE，通过后才以 Custom HLSL 做匹配 GPU A/B。

### 2026-08-14 — [执行] R1 tiny neural material 数值 Gate 通过

新增单文件 `train_neural_material.py`，没有增加依赖。Teacher 为运行时合成的粗糙石材、薄水 clearcoat、灰尘/sheeen、薄膜色偏和方向性微高光；PBR 基线共享 base color、normal、roughness 空间场，但只使用 diffuse + 单 GGX。Student 为 `64×64×8` learned latent grid 与两个宽度 64 的 ReLU 隐层；输入切线空间 light/view/normal/half vector 与四个角度项，输出 log-HDR 响应。

36 个光照方向和 24 个观察方向形成 864 个组合，其中 691 个用于训练、173 个完整组合 held out；每个单独方向仍出现在训练集，避免按像素拆分造成泄漏。RTX 5060 上训练 1800 steps、batch 32768，用时 `30.32 s`，峰值显存 `115.11 MiB`。held-out PBR/Student log-RMSE 分别为 `0.02633/0.01023`，比值 `0.388`；tone-mapped PSNR 为 `27.68/39.06 dB`。模型共 38,723 参数，FP16 表示 `77,446 B`（`0.074 MiB`），checkpoint SHA256 为 `F20D047CF794D2AC32638EECE03A8004D9CA2BD41A09397938C5E978768AD1B9`。

`tmp/UE-NeuralRender-Lab/neural-material/r1/` 已保存 `best.pt`、`metrics.json`、`comparison.png` 与 `angular_sweep.gif`。数值条件通过；机器初检显示 Student 能跟随 Teacher 的方向性亮斑且误差显著低于 PBR，但视觉 Gate 仍保留给本人签字，因此尚未启动 R2，也未修改 UE/Bifrost。

### 2026-08-14 — [裁决] R1 视觉通过，R2 Custom HLSL 性能 Gate 失败

本人允许在 R1 对比与连续角度结果后继续进入 R2，因此按既定合同将视觉 Gate 记为通过。修正 latent 采样与 UE 导出后，最终 R1 指标为 PBR/Student log-RMSE `0.02633/0.01021`、比值 `0.3876`，Student PSNR `39.13 dB`；训练 `17.58 s`，峰值显存 `115.11 MiB`。导出的 8-bit latent 版本比值为 `0.3720`，Student PSNR `39.45 dB`。

新增最小导出器 `export_neural_material_ue.py`，生成五张输入纹理与 `83,584 B` 的 `NRL_R2.ush`（SHA256 `d243b14ff6d8c011be2aa41b671d172c4ad18456000400d5a4e821ae9315525c`）。UE 中 `/Game/NeuralRenderLab/R2/` 的 PBR、Student、Teacher 三个 Unlit Custom HLSL 材质和五张纹理均已编译、保存并回读为 clean；临时 `M_NRL_R2_Probe`、sidecar 与 probe shader 已删除。

最终 GPU A/B 使用同一 `50000×50000 cm` 平面、固定相机 `(250000,250000,20000) / (-90,0,0)`、Simulate、Game View、关闭 Cinematic Control；RTX 5060 / D3D12 SM6 / `1962×1078` 下，每个采用 30 帧 warmup + 120 帧稳态样本。PBR 的 GPU mean/p50/p95 为 `1.96/1.91/2.34 ms`，Student 为 `1.98/1.89/2.14 ms`，Teacher 为 `1.90/1.88/2.12 ms`；三份回执均为 comparable 且设置未变化。Student/Teacher mean 比值 `1.042`，未达到 `<= 0.60`；相对 PBR 的差值低于本次总 GPU 测量噪声，不能声称 Student 更便宜，因此 R2 失败并停止 R3。

镜头被接管、PBR 截止时间不足、Student 首用瞬态和 Teacher 相机被移动的样本均未纳入裁决。收尾按标签与文件夹双重查询后只删除测试 Actor；`L_Demo` 世界哈希恢复为 `c4f22e75f7665a453940ae689103623fa62be47d39c94830f5627937a5dcce2d`，视口哈希恢复为 `369e77aa4a821b5a733464113633eb2260eaeeee7deba480478c8b11c48f6cdf`，PIE 与 performance freeze 均关闭，只剩原有 dirty `L_Demo`，未保存关卡。原始回执与裁决摘要位于 `tmp/UE-NeuralRender-Lab/neural-material/r2-benchmark/`。

### 2026-08-14 18:01 — [执行] R4a 神经体积代理通过数值 Gate，等待视觉签字

新增单文件 `train_neural_volume.py`，复用既有 PyTorch/CUDA/Pillow 环境且不增加依赖。Teacher 对固定程序化云执行 64 次视线步进及每样点 8 次太阳透射步进；Student 用解析代理球的入射点／厚度、三个 `64×64×8` learned triplane 和三层宽度 64 MLP，每条命中视线只求值一次。训练与测试按完整 camera/sun 组合 held out，并以不含 learned spatial field 的全局二次 ridge 代理作为普通解析基线。

RTX 5060 正式候选训练 1200 steps；held-out PSNR `31.87 dB`，Student/analytic log-RGB RMSE 比值 `0.2786`，alpha RMSE `0.0239`，108,100 参数，FP16 表示 `0.206 MiB`。`512×288`、78,684 条命中视线的 PyTorch eager CUDA median 为 Student `0.929 ms`、Teacher `390.556 ms`，比值 `0.00238`；全部固定数值门槛通过。机器检查的连续重光照没有跳变，但 Student 比 Teacher 有更强高频颗粒和轻微轮廓膨胀，因此视觉 Gate 未代签，UE RHI 未启动。证据位于 `tmp/UE-NeuralRender-Lab/neural-volume/r4a/`；checkpoint SHA256 为 `0AAFBBC6347CCFF73F3AC60AAEFC37154A6FB84662F28870627622E018E0FD23`。

### 2026-08-14 18:08 — [执行] R4a 4× 空间采样修正改善静态误差，残留侧／逆光亮环

按冻结合同允许的唯一一次最小修正，只把每个 camera/sun 组合的训练射线从 96 增至 384；网络、损失、held-out 规则和 Gate 均未改变。held-out PSNR 提升到 `33.49 dB`，Student/analytic log-RGB RMSE 比值降到 `0.1835`，alpha RMSE 降到 `0.00925`。Student/Teacher PyTorch eager CUDA median 为 `1.197/400.835 ms`，比值 `0.00299`，数值 Gate 继续通过。

静态对比中的颗粒和轮廓误差明显缓解，证明主要根因是空间监督稀疏；但连续太阳 sweep 的侧／逆光帧仍可见 Teacher 没有的局部亮环，因此视觉 Gate 继续等待本人裁决，未进入 UE。当前候选已提升到 `tmp/UE-NeuralRender-Lab/neural-volume/r4a/`，初版保存在 `r4a-initial/`；当前 checkpoint SHA256 为 `339962C3DDB04C6F610A872E87D7E66CA2C148E73812EC4F2A0792A2B85698F7`。

### 2026-08-14 18:18 — [执行] 连续太阳监督与更小 triplane 消除亮环并改善全部指标

离散太阳训练每 `45°` 一个方位，而 16 帧 sweep 包含中间 `22.5°`，亮环集中出现在未监督方向。训练集因此加入太阳方位 `±22.5°` 连续抖动，held-out 测试仍使用精确离散 camera/sun 组合。该修正把相邻帧变化 RMSE 从 `0.00353` 降至 `0.00282`，逆光亮环消失；随后按最小容量原则把 triplane 从 `64²` 收缩到 `32²`，没有增加损失项或网络层。

最终候选 held-out PSNR `34.36 dB`，Student/analytic log-RGB RMSE 比值 `0.1737`，alpha RMSE `0.00839`；连续 sweep 平均／最差帧 RMSE `0.00388/0.00463`，相邻帧变化 RMSE `0.00227`。模型降为 34,372 参数、FP16 `0.0656 MiB`，Student CUDA median `0.913 ms`。机器检查未见明显亮环、跳变、轮廓漂移或闪烁；视觉 Gate 等待本人签字，UE RHI 未启动。当前 checkpoint SHA256 为 `F4DCF12A8A22E711B9D450DFBDC5A0D29E5DE66B78269161A6765D9CFD0CAA92`。

### 2026-08-14 18:22 — [修正] 训练与 held-out 随机生成器解耦后结论保持

连续方位增强会推进原先共享的随机生成器，使版本间 held-out 射线位置不完全一致；这不造成训练泄漏，但削弱横向比较。现已把训练和 held-out 固定为独立种子并复跑当前 `32²` 候选。结果为 PSNR `34.44 dB`、Student/analytic log-RGB RMSE 比值 `0.1772`、alpha RMSE `0.00964`、相邻帧变化 RMSE `0.00223`，全部结论保持；当前 checkpoint SHA256 为 `1B6850F1FB1E1CEFDFCE16A7647025BEAFAAC3DA8B919D0EFC088FA03CE052BB`。

### 2026-08-14 18:24 — [裁决] R4a 视觉 Gate 通过

本人确认当前静态对比与连续重光照 sweep 可接受，R4a 数值、机器检查与视觉 Gate 至此全部通过。R4b UE RHI／Tensor 路径获得进入许可，但尚未启动；本次签字不构成 UE 实时性能结论，也未执行任何 UE live 操作。

### 2026-08-14 20:57 — [执行] R4c 切换为 world-box 并接入 UE Runtime 插件

早期相机相对／代理球预览在转动视角时像贴在屏幕上，不能表达关卡内固定体积，因此不保留为 fallback。训练域、held-out 射线与导出检查统一切换为归一化 AABB；`train_neural_volume.py` 默认结果改到 `tmp/UE-NeuralRender-Lab/neural-volume/r4c-box/`。新候选 held-out PSNR `33.983 dB`、Student/analytic log-RGB RMSE 比值 `0.14754`、alpha RMSE `0.007446`，连续重光照平均／最差／相邻帧变化 RMSE 为 `0.005707/0.007283/0.002684`。模型仍为 34,372 参数，FP16 `68,744 B`；PyTorch eager CUDA Student/Teacher median 为 `1.817/1164.178 ms`，只作离线余量证据。

`export_neural_volume_rhi.py` 导出 `NRL_R4c_Box.fp16.bin/json`；SHA256 为 `F416D6EF390A69D44EAC8EB5A5317740D961580EFEF968E2A3842C5F09B59225`，量化输出 RMSE `2.92e-5`、最大绝对误差 `0.001143`。Abyss 新增 `NeuralVolumeProxy` 0.2.0 Runtime 插件：`ANeuralVolumeProxyActor` 以 `UBoxComponent` 提供世界范围，SceneViewExtension 在 SM6 Compute Shader 中完成 ray/AABB 求交、Student 推理、Scene Depth 遮挡与合成。运行时暴露 Enabled、Strength、SunDirection、Use Scene Depth 和 Debug View；权重从插件 Resources 直接加载，不依赖 NNE 或 `/Game/NeuralRenderLab`。

插件首次启动日志确认 68,744 B 权重加载和 `FNeuralVolumeProxyCS` 编译成功。本人手动把 Actor 放入当前 dirty 的 `L_Demo`，确认左右移动的世界锚定正常；关卡未保存。`/Game/NeuralRenderLab/v00`、`v01`、`R2` 均已被当前路径废弃，但尚未执行资产删除。

### 2026-08-16 19:10 — [修正] 透视射线改用真实相机起点，完整 DLL 链接成功

本人报告固定相机下修改 Actor `Location.Z` 时 Debug View 3 表现为缩放而不是移动。Debug 3 在网络求值前直接输出 Box 命中遮罩，因此无需重训，问题限定在投影／射线层。组件回读确认 Box 世界位置与缩放会更新；实现随后把透视视图的 ray origin 从逐像素近裁剪面点改为 `ViewMatrices.GetViewOrigin()`，正交视图仍保留近面起点，射线方向继续由两个反投影点确定。

编辑器尚加载旧 DLL 时，新 USF 的 `ViewOriginAndPerspective` 暂时落入 `$Globals`，与旧 `FParameters` 产生一次 Global Shader 绑定错误；这不是模型或 HLSL 算法错误。关闭编辑器后，`AbyssEditor Win64 Development` 完整链接成功并生成新 `AbyssEditor-NeuralVolumeProxy.dll`。当前验证停在“重启 UE、确认 Shader 编译与 Z 向 Debug 3 行为”，尚未将修正记为视觉通过，也未做 GPU A/B 或关卡保存。
