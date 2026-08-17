# UE 5.8 Native Toon Prototype · SPEC

> 状态：Draft v0.2
> 日期：2026-08-13
> 实现状态：G0 进行中；Abyss `/Game/Neow/NPRRendering` 已通过 UEAgent 创建并验证为空
> 研究依据：[RESEARCH.md](RESEARCH.md)

## 1. 决策

当前只实现一条路径：

`UE 5.8 Substrate Toon BSDF + 静态 Toon Profile`

环境继续使用目标项目已有 PBR 材质。角色使用一个 Toon 母材和各部位 Material Instance；
三种风格通过编辑器内切换 Toon Profile 做离散 A/B，不实现运行时 Profile 管理。

描边、Face SDF、SceneViewExtension/RDG、自定义 Shading Model 和 Renderer fork 不进入本版。

## 2. 目标与范围

### 目标

在同一角色、环境、灯光、相机和输出设置下，验证 UE 5.8 原生 Toon 能否覆盖：

- 干净的二段动画风；
- 以渐变和受控高光为主的电影化风格；
- 保留 Roughness、Metallic、Anisotropy 的 NPR/PBR 混合风格；
- 目标平台上可接受的 GPU、Shader/PSO 和纹理预算。

### 不做

- 复刻《原神》《鸣潮》《终末地》的专有 Shader 或拆包贴图语义；
- 全场景颜色量化、运行时换 Profile、多套 Renderer 或通用 NPR 框架；
- 任何描边方案、Face SDF、眼睛/头发专用 Shading Model；
- 修改生产资产、保存生产关卡或修改 UE Engine 源码；
- 在没有目标平台数据时宣称可量产、可移动端运行或性能通过。

## 3. G0 必需输入

进入实时实现前必须一次性记录以下输入；任一缺失，G0 不通过：

| 输入 | 必须记录的值 |
| --- | --- |
| 目标项目 | `.uproject` 绝对路径与 UEAgent route receipt |
| 引擎 | UE 5.8 精确版本、源码/安装版、提交或 Build ID |
| 渲染路径 | Deferred、Substrate Blendable GBuffer (legacy) 是否启用 |
| 目标平台 | 平台、RHI、GPU、显存、Device Profile |
| 输出 | 分辨率、Screen Percentage、AA/上采样方式、HDR/SDR |
| 预算 | 目标帧率及 Toon 允许的增量 GPU 预算 |
| 视觉合同 | 三类风格各一组参考图，由用户签字 |
| 内容边界 | Prototype Content Root、测试关卡、可引用角色/环境资产 |

Prototype Content Root 固定为 `/Game/Neow/NPRRendering`。测试证据写入
`tmp/NPR_rendering/<date>-native-toon/`，不写入生产目录。

## 4. 资产合同

### 必建资产

| 资产 | 职责 |
| --- | --- |
| `L_NPR_Validation` | 隔离的匹配测试关卡 |
| `M_NPR_CharacterToon` | 唯一角色 Toon 母材；包含 Substrate Toon BSDF |
| `MI_NPR_<Hero>_<Part>` | 复用角色现有贴图并提供部位参数 |
| `TP_NPR_Clean2Band` | 干净二段风格 Profile |
| `TP_NPR_GradientSoft` | 软渐变风格 Profile |
| `TP_NPR_HybridPBR` | NPR/PBR 混合 Profile |

若目标项目已有等价母材或测试关卡，G0 必须优先复用并从本表删除重复资产。

### 当前禁止创建

- 第二个角色 Toon 母材；只有 Blend Mode 或渲染域确实不同才允许拆分；
- `T_*_Style`、`T_*_SpecularOffset`、`T_*_FaceSDF`；
- 任何 Outline/Post Process Material；
- 自定义 C++ Module、Global Shader、Scene View Extension 或 Engine Patch；
- 为“以后可能使用”创建的 Material Function、Data Asset、Manager 或配置层。

### 用户资源交付

首轮只需要一个 Hero，不要求完整量产包：

| 类别 | 最小要求 |
| --- | --- |
| 模型 | FBX；厘米单位；变换已应用；脚底接近原点；稳定三角化；保留作者法线/切线 |
| 骨骼 | 一个 Skeleton、一个根骨、蒙皮完整；若只做静态 LookDev，可先给绑定 Pose |
| 材质区 | 至少能区分 Face/Skin/Hair/Cloth/Metal；使用 Material Slot，不为每区拆独立模型 |
| UV | UV0 与贴图对应；脸部最好不镜像；无意外重叠、越界或不同部位密度突变 |
| Base Color | `T_<Hero>_<Part>_BC`；PNG/TGA；2 的幂；身体 2K、脸/发/附件 1K 起；不烘焙方向固定阴影 |
| Normal | `T_<Hero>_<Part>_N`；DirectX 切线空间；sRGB 关；1K–2K；提供自定义法线时不要让 UE 重算 |
| ORM | 可选；`T_<Hero>_<Part>_ORM`，R=AO/G=Roughness/B=Metallic，sRGB 关；没有逐像素变化就不提供 |
| Opacity | 仅 Masked 发片需要；单独灰度图或明确写明 Base Color Alpha 语义 |
| 参考 | 正面、3/4、侧面各一张目标图；注明最接近 Clean、Gradient 或 Hybrid 哪一类 |

文件与文件夹名称只用英文。不要先制作 Outline、Face SDF、Style Mask、Ramp LUT 或 Hatching；
这些都必须由首轮材质结果证明需要。资源放在一个外部目录并提供绝对路径，导入位置由本规格
统一决定，不要先手工复制进 Content。

## 5. 角色 Toon 与 Cloth PBR 材质

`M_NPR_CharacterToon` 使用 Substrate Toon BSDF；`M_NPR_CharacterClothPBR` 使用 Default Lit，复用
相同的 Base Color、Opacity Mask 与 Emissive 主链。v0.1 只覆盖 Opaque/Masked 角色部位。

| 输入 | v0.1 合同 |
| --- | --- |
| Base Color | 复用现有 `T_*_BC`；sRGB 开；允许大尺度手绘渐变，不烘焙方向固定阴影 |
| Normal | Toon 复用现有 `T_*_N`；Cloth 从 PackedNMR 的 R/G 重建 Z，再用 UV0 叠加共享切线空间细节法线；sRGB 关并保留 Mip |
| AO/Roughness/Metallic | Cloth PackedNMR 使用 B=Metallic、A=Roughness；AO 暂不提供 |
| Specular | Material Instance Scalar；不新增 Specular 贴图 |
| Anisotropy/Tangent | 仅头发和 Hybrid Profile 使用；其他部位为零/默认切线 |
| Emissive | 默认零；只复用角色已有发光遮罩 |
| PatternUVs | 独立可调 UV Scale；只供 Hatching 使用 |
| Toon Profile | 直接绑定一个 `UToonProfile`；只在编辑器 A/B 时切换，不在运行时修改 |

角色脸、皮肤和头发使用 Toon 母材；布料与服装金属使用 Cloth PBR 母材。Profile 是 Toon 母材的
静态绑定，因此一次 A/B 中所有 Toon 部位必须使用同一个 Profile；本版不为同时展示三种风格复制
三套材质，也不通过共享中间材质实例切换叶子实例的渲染路径。

### Profile 初始合同

| Profile | Diffuse | Specular | GI | Pattern/Offset |
| --- | --- | --- | --- | --- |
| `Clean2Band` | 两个稳定色阶、窄过渡、不追求物理守恒 | 窄而干净，皮肤弱、头发/金属强 | Diffuse/Specular Indirect Scale 从 `1.0` 开始 | Hatching 关；无 Offset Texture |
| `GradientSoft` | 三个可读层次、宽过渡，保留 Base Color 渐变 | 中等宽度，避免纯白硬斑 | 从 `1.0` 开始，过亮时只调 Profile | Hatching 关；无 Offset Texture |
| `HybridPBR` | 单调连续、软肩部，不做二值化 | 保留 Roughness/Metallic/Anisotropy 差异 | 从 `1.0` 开始 | 可使用一张共享 Hatching Texture；无 Offset Texture |

三套 Profile 的 `Diffuse Ramp Includes Shadow` 首轮均关闭。只有真实阴影与 Ramp 无法满足
参考图时，才将它作为单一变量开启一次。间接高光量化实验性 CVar 在 v0.1 中关闭。

### 贴图规则

- Cloth 回退贴图命名为 `T_<Hero>_Cloth_<Id>_NMR`：R/G=切线空间 Normal XY（0–1 编码）、
  B=Metallic、A=Roughness，使用 BC7、关闭 sRGB；因为 B/A 仍有数据，不使用会丢弃它们的 BC5。
  由 Base Color 推导的数据仅作 LookDev 初值，不视为物理测量或最终量产资产。
- 共享微法线命名为 `T_<Hero>_ClothDetail_<Surface>_N`：DirectX 切线空间、Normalmap 压缩、关闭
  sRGB、UV0 Wrap；材质实例暴露 UV Scale 与 Strength，并以 `1 - Metallic` 遮罩，避免织纹进入金属区。
- 首轮不创建 Offset、Style 或 Face SDF 贴图；先证明 Profile 曲线不够用。
- Hybrid 需要排线时，只创建一张 `T_NPR_HatchingHybrid`：256 或 512、2 的幂、可平铺、
  sRGB 关、RGBA 由浅到重。
- 若 Profile 曲线通过、但不同表面确需局部改变 Diffuse 阈值，允许一次条件 Probe：创建
  `T_<Hero>_DiffuseOffset`，灰度距离场、sRGB 关、512 起。该 Probe 不自动进入交付基线。
- 所有贴图保留合适 Mip 并在近景、远景、运动和目标 Device Profile 下验收。

## 6. 验证场景

`L_NPR_Validation` 只引用、不修改目标项目已有角色和环境资产，至少包含：

- 一个 Hero：脸、皮肤、头发、布料、金属五类区域；
- 一个中性环境硬表面资产；
- Close 与 Medium 两个固定相机；
- 固定曝光、白平衡、色彩管理、Screen Percentage 和 AA；
- 四种互斥灯光状态：Neutral Day、Side/Back Light、Top Face Stress、Local Light + Sky/GI；
- 一段 5–10 秒角色/相机运动，用于材质、阴影、高光和 Hatching 稳定性检查。

环境全程保持原 PBR 基线；不增加全场景 Toon 后处理、天气或动态 TOD。

## 7. Gate 流程

| Gate | 工作 | 通过证据 |
| --- | --- | --- |
| G0 Preflight | 完成 UEAgent route/compact context；创建并验证 Content Root；冻结第 3 节输入 | receipt、`/Game/Neow/NPRRendering`、目标配置与预算 |
| G1 Asset Intake | 检查用户模型、贴图、命名、UV、法线和材质区，不修改源文件 | 导入清单、问题清单、用户参考图 |
| G2 Baseline | 在隔离关卡记录原角色/环境 Default Lit 画面与性能 | 两机位、四灯光状态、GPU/纹理/Shader 基线 |
| G3 Native Toon | 创建一个母材与三套 Profile；逐套静态绑定、编译、回读 | 无编译错误；12 组固定画面；Profile 绑定证据 |
| G4 Matched A/B | 固定所有非候选变量，比较 Default Lit 与三套 Profile | 同机位同灯光 A/B、用户视觉 Gate、性能数据 |
| G5 Decision | 选择一个 Profile 基线或拒绝原生路径 | Brief/Log 决策、回滚点、明确失败原因 |

每个 Gate 失败回到上一个已验证状态；不并行维护第二条实现路径。

## 8. 验收标准

### 功能

- Toon 材质无编译错误、默认材质回退或无意的 Engine 源码修改；
- Directional、Local、Sky Light 和 Lumen GI 均产生可解释响应；
- 三套风格只通过 Profile 静态绑定和 Material Instance 参数完成；
- 生产资产和生产关卡保持未修改、未保存。

### 视觉

- 用户至少签字一套 Profile 为可继续生产的候选；
- 脸部在正/侧/顶/背/局部光下没有不可接受的阴影翻转；
- 头发高光和 Hatching 在正常播放速度下无明显闪烁或拖影；
- Close 与 Medium 机位都能保持角色和环境融合，不靠全屏 LUT 掩盖问题。

视觉项只有用户可以通过；静帧结构正确不能替代运动画面 Gate。

### 性能与资产

- Shader/PSO 预热后，固定设置下记录至少 300 个稳定帧；报告 median 与 p95；
- 用 Unreal Insights 记录帧序列，用 ProfileGPU 或 RenderDoc 归因 Pass；不以单帧 `stat gpu`
  当最终结论；
- Toon 增量 GPU 时间不超过 G0 签字预算；预算未填写则项目不能标记通过；
- 记录材质 Shader/PSO、纹理驻留与 Streaming Pool；无未使用贴图和重复母材；
- 数据贴图 sRGB 关、尺寸为 2 的幂、Mip/Compression/Texture Group 与用途匹配。

## 9. 失败升级与回滚

### 仅在以下证据出现后更新 SPEC

- 脸部单独失败：先记录 G4 失败，再评估一个 Face SDF Probe；
- 原生 Toon 缺少必须的逐灯数据、GBuffer Payload 或目标 RHI 支持：才评估
  `Aether/` 自定义 Shading Model/Renderer 分支。

每次只允许一次最小 Probe；通过后替换当前路径，失败则删除 Probe，不留兼容层。

### 回滚

1. 测试 Actor 恢复原 Material；
2. 回读引用后，只删除 Prototype Content Root 下由本规格创建的资产；
3. 不删除、不迁移、不覆盖角色、环境或生产关卡；
4. 保存失败原因和匹配证据，项目回到 G2 Baseline。

## 10. 交付物

- 目标项目中的隔离测试关卡、一个 Toon 母材和三套 Profile；
- Default Lit/三套 Profile 的匹配画面、5–10 秒运动片段和可信 GPU 数据；
- 贴图、材质、Shader/PSO、Streaming 审计结果；
- 用户视觉 Gate 与最终采用/拒绝决策；
- 更新后的 `AI-BRIEF.md`、`BACKLOG.md`，通过或拒绝后再写 `LOG.md`。

## 11. 规范依据

- [UE 5.8 NPR research](RESEARCH.md)
- [Epic `UToonProfile` API](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/UToonProfile?lang=en-US)
- [Epic Substrate Toon BSDF API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialExpressionSubstrateToonBSDF)
