# UE Neural Render Lab · LOG

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
