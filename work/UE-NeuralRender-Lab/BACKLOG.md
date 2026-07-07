# UE Neural Render Lab · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 从路线三(ML Deformer)或路线四(离线3DGS导入)里选一个先落地最小POC，验证工程可行性。

## 待办（按优先级，风险低→高）

- [ ] POC-A：用 NanoGS 把一个 .ply 高斯泼溅资产拖进现有 UE 项目，验证渲染质量和与 Nanite/光照的共存成本。
- [ ] POC-B：如果项目已有骨骼网格体/布料相关需求，试装一个最小 ML Deformer（Neural Morph Model）流程，对照官方 MetaHuman 训练数据量级（5000~50000帧）评估训练成本。
- [ ] 中风险验证：NNE 实时推理最小 demo —— 用官方 FPStyleTransfer 或 DeadMorose777 的 UE5.5 GPU-only 移植版，本机跑通一次，记录真实帧时间（对照NVIDIA博客 DirectML 5.7ms / TensorRT 3.8ms 的参考基线）。
- [ ] 中风险验证：Neural Post Processing 材质路线 —— 走一次官方文档的零代码流程（ONNX→NNE Model Data→Neural Profile→材质挂Neural Input/Output），确认224x224定长限制和Tiling开销是否能接受。
- [ ] 建性能预算表：1080p/4K，模型尺寸，Tile策略，GPU ms，显存，对比CPU同步 vs RDG异步两种接入方式。
- [ ] 平台落地评估：目标平台是PC还是移动/主机？如果非PC，NNE的Experimental平台支持可能直接排除路线一/二。
- [ ] 决策点：路线一/二是否值得投入 C++/SceneViewExtension 工程量，还是蓝图/材质层面就能满足当前项目诉求。
- [ ] 追踪行业信号：Arm×Sumo Digital《光影新生》2026Q4上线后补充实测数据（依赖Arm专用神经加速器，非纯软件方案，仅作参考不可直接复现）。
- [ ] 进阶延伸（Portfolio用）：fork `DeadMorose777/OnnxRuntime-UnrealEngine` 跑通一次GPU-only风格迁移，作为材质POC出效果后的RDG手写管线进阶篇章素材，换成自己的模型/编解码算法。
- [ ] 新方向（更有分量的RDG进阶叙事）：研究 NNEDenoiser 插件接口，尝试接入一个自定义降噪或超分模型替换默认Intel OIDN预设，讲清楚它和路径追踪管线(Movie Render Queue)的耦合方式——比复刻风格迁移demo更贴近官方生产架构。

## 已完成（近期，便于回忆）

- [x] 初始化项目三件套：AI-BRIEF.md / LOG.md / BACKLOG.md。
- [x] 全网侦察四条路线（NNE实时推理 / 神经后处理材质 / ML Deformer / 离线3DGS导入）及代表案例，写入 LOG.md。
- [x] RDG推理管线技术栈拆解 + 抓取 `DeadMorose777/OnnxRuntime-UnrealEngine` 核心源码，写入 LOG.md。
- [x] 梳理材质路线/RDG路线各自应用场景清单，发现RDG路线的官方生产案例NNEDenoiser，写入 LOG.md。

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。
