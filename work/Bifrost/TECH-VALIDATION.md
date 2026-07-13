# Bifrost Technical Validation Plan

> 当前阶段的唯一执行计划。所有技术先在独立 TechLab 验收；不做 S3 构图、地编、资产摆放或最终场景整合。

## 0. 统一验收规则

每项技术只有同时满足以下四项才能叫“落地”：

1. **正确性**：在 UE5.8 独立测试关卡中稳定运行，包含近远镜头或边界条件。
2. **可控性**：至少提供高层参数或 Blueprint/Actor 接口，不依赖改 shader 常量或手填底层数组。
3. **性能**：记录 RTX 5060 上的分辨率、GPU 时间、显存或 primitive/采样规模，并给出失效阈值。
4. **证据**：固定镜头截图/视频、参数开关、节点或 C++/shader 架构图、已知限制。

未满足四项的内容只能称为原型，不进入场景集成。

## 1. TechLab 公共底座 T0

创建无美术依赖的 `L_Bifrost_TechLab`，包含固定相机组、纯色背景、标准 Directional Light / Sky / Fog、GPU 采样与截图机位。每个模块可被单独开关，并在同一相机、分辨率、曝光下输出对比与 profile。

## 2. 逐项验收卡

| ID | 技术 | 最低验收标准 | 不通过条件 |
|---|---|---|---|
| T1 | 恒星 Layer 1 + 标准光照链 | 近中远机位中恒星表面、曝光、Directional Light、Sky/Fog 关系稳定；主参数可调 | 仅编译通过，或靠后期掩盖曝光问题 |
| T2 | GaussianVolume renderer | UE5.8 中正确显示；相机移动不漂移；解析 tau、single scattering、composite 可开关验证 | 只在 UE5.7/静态截图有效，或合成覆盖场景 |
| T3 | Gaussian Field Authoring | `Spline -> 32/64/128` primitive；flow/thickness/density/breakup/emission/LOD 可编辑；half-res 与 depth composite 正确 | 只能手填 primitive，或无性能曲线 |
| T4 | Neural Gaussian Decoder | 自训练 ONNX 经 UE NNE 真实推理，输出 primitive 残差；与程序/静态 field 对比 | 离线烘焙冒充运行时、泛用滤镜、无模型/帧耗数据 |
| T5 | 自定义 Raymarch Core | 可复用 ray-box、密度、步进、早出、depth composite 和参数接口；先完成一个局部介质 demo | 云和极光各写不可复用 shader，或无步数/分辨率曲线 |
| T6 | HPVolumeCloud UE 适配 | 在 UE 中重实现并验证云形态、侵蚀、定向散射；复用 T5 | 只拿参考图/复制 Unity 代码，或重复造 renderer |
| T7 | 恒星 Layer 2 Marching Cubes | 明确 `density/noise -> SDF -> NS_Slime` 链；局部轮廓/日珥；两种距离稳定 | 普通噪声直接喂 SDF，或整球 overdraw 失控 |
| T8 | FluidFlux 海面 | 材质、Niagara 无限网格、Height RT 分别验证；近中远海面与岸线 mask 正确 | 仍引用 demo、RT 坐标错位或仅预览可见 |
| T9 | 环境 LookDev 基础 | `M_Env_Uber` 与 Lordenfel 材质在标准测试 Mesh 上通过曝光、粗糙度、色彩、尺度检查 | 沿用资产包 LookDev 或随机实例参数 |

## 3. 依赖与顺序

`T0 -> T1 / T2 / T5 / T8 / T9`；`T2 -> T3 -> T4`；`T5 -> T6`；`T1 -> T7`。T4、T6、T7 不阻塞其他模块。所有验收结束后，才决定哪些模块进入最终固定镜头；能做不等于必须进入同一画面。

## 4. 当前最小下一步

先完成 T0 测试关卡与记录模板，然后以 T2（现有 GaussianVolume renderer）作为第一个事实验收对象，优先暴露 UE5.8 兼容性、RDG 合成和性能问题。
