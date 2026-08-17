# UE 5.8 NPR Rendering Research

> 调研日期：2026-08-12
> 范围：UE 常见风格化渲染路径、《鸣潮》《原神》《明日方舟：终末地》的公开做法、
> UE 5.8 原生 Substrate Toon Shading、贴图与资产规范。
> 说明：本文中的“原生 Toon”指 **Shading Model / BSDF**，不是 Shader Model 5/6。

## 结论

当前最小且可持续的技术路线是：

1. 以 **UE 5.8 原生实验性 Substrate Toon BSDF + Toon Profile** 承担直接光、局部光、
   天光、Lumen GI、漫反射/高光 Ramp 和阴影排线。
2. 只增加一个独立的描边方案；先用后处理深度/法线/Stencil，只有质量或性能不通过时
   才比较反向外壳或自定义渲染 Pass。
3. 脸部先跑原生 Toon；只有固定测试证明侧光、顶光或表演光无法稳定通过，才增加
   Face SDF/专用脸部阴影。不要把它预设为全角色必需品。
4. **现在不要 fork UE 渲染器，也不要新增自定义 Shading Model。** 只有原生 Toon 在目标
   RHI、角色专用光照、GBuffer 数据或脸/发高光上出现可复现的硬阻塞，才升级到插件 Pass
   或源码分支。

三款参考作品不能直接当成 UE5 实现模板：《鸣潮》的公开基线是深度定制的 UE 4.26；
《原神》和《终末地》都基于深度定制 Unity。它们真正可复用的是美术—光照—资产—平台
一体化的方法，而不是某段引擎代码。

## 证据边界

- **公开事实**：Epic 官方文档、开发团队访谈、开发者演讲。
- **工程推断**：由公开事实映射到 UE 5.8 的实现建议，均明确写为“建议”或“推断”。
- **不可确认**：三款商业游戏的实际 Shader 源码、完整 GBuffer 布局、逐通道贴图定义、
  压缩格式和当前线上版本参数没有完整公开。网上的“拆包通道表”不能当制作规范。
- 本次是离线研究，没有读取或修改任何目标 UE Editor 的实时状态。

## 三款参考风格

| 作品 | 已公开技术事实 | 可见风格支柱 | 对本项目的可复用原则 |
| --- | --- | --- | --- |
| 《原神》 | Unity；PC/主机与移动端是两套定制管线；整体为 PBR-based stylized rendering；材质光照模型按美术需要调整，不完全守恒 | 清新、明亮、干净；角色与场景处理分离；人工控制脸部与阴影；大世界动态 TOD/天气 | 从 PBR 一致性出发再做风格化；角色特例集中管理；先满足移动/低端预算；调色属于渲染系统 |
| 《鸣潮》 | UE 4.26，回移部分 UE5 能力；Deferred；独立角色光照管线；Base Color 与 Mask 使用渐变；后处理材质和自定义 LUT；专用脸部阴影贴图 | 高对比、互补色、强滤镜感；比平涂更重渐变、体积和电影光；场景有稳定基础光 | Toon Ramp 只是底座；角色光照、TOD、渐变资产和表演光需要同一套验收 |
| 《终末地》 | Unity 被大幅改造，底层渲染框架和上层管线基本自研；自研多平台动态光影、虚拟纹理；角色笔触随光照和视角变化 | “写实主义二次元”；冷色、真实材质与实用设计；角色有绘画感，场景细节经过再设计而非照搬照片 | 环境继续使用可信 PBR，角色只做受控偏离；材质细节与笔触应响应光照，避免简单二值卡通化 |

### 《原神》：干净的 PBR 风格化

miHoYo 的 GDC 2021 演讲公开了 Model & Texture、Face Dynamic Lightmap、角色/场景采用
不同渲染管线和人工控制阴影等制作主题；另一份由 Unity Technologies Japan 上传的开发者
演讲明确说明：PC/主机和移动端采用两套定制管线，整体基于 PBR，但会按材质和美术目标
修改光照模型，并将风格目标概括为 fresh、bright、clean、anime-like。
([GDC Vault](https://www.gdcvault.com/play/1027539)、
[GDC 2021 slides](https://media.gdcvault.com/GDC%2B2021/2021GDC%2B_%2BHaoyu%2BCai%2B_%2Bpresentation%2Bfile.pdf)、
[Unity Technologies Japan 上传的开发者演讲](https://www.slideshare.net/slideshow/210617-unity-dojo20211mihoyozhenzhongyi/249437133))

同一演讲还公开了最多八级级联阴影、HBAO/AO Volume/Capsule AO、Clustered Deferred
Lighting、动态局部光阴影、反射/环境探针，以及为了符合风格而没有直接采用 ACES
RRT+ODT 的 HDR 输出方案。这说明其“动画感”不是舍弃现代实时光照，而是系统性地约束
光照、阴影、AO、色彩和材质响应。

**UE 5.8 映射建议**：用原生 Toon Profile 做干净的 2–3 段漫反射和窄高光；脸部先测试
原生 Ramp Offset，失败才引入双向 Face SDF；环境保持较克制的 Default Lit/Substrate
PBR，不要给整个世界统一套二值化后处理。

### 《鸣潮》：渐变、角色专用光照和强调色

库洛在 Epic 的开发者访谈中明确说明项目选用 UE 4.26，并回移必要的 UE5 功能；角色与
世界融合的关键是 TOD 和后处理光照，团队建立了独立角色光照管线。其风格化重点是渐变，
渐变被制作进角色 Base Color 和 Mask；场景使用 UE 光照、假体积雾、后处理材质、自定义
LUT 和稳定的基础光照，脸部表演还会使用专门阴影贴图。
([Epic / Kuro Games 开发者访谈](https://www.unrealengine.com/developer-interviews/exploring-the-post-apocalyptic-charm-of-asg-open-worlds-in-wuthering-waves))

访谈同时说明它选择 Deferred 是为了 SSR/GTAO、材质与天气管理和跨平台一致性，并公开了
移动 One-pass Deferred 的平台限制。这比“它用了某个 Toon Shader”更重要：生产质量来自
稳定的场景光基线、角色专用控制、渐变资产、表演工作流和平台降级策略。

**UE 5.8 映射建议**：使用更软、更连续的 Toon Profile；把大尺度颜色渐变留在 Base Color，
把局部光照偏移留给官方推荐的 Ramp Offset 距离场；用角色 Lighting Channel 或项目已有
角色光照能力做最小分离。不要一开始复制独立整套渲染器。

### 《终末地》：NPR/PBR 混合的“写实主义二次元”

开发团队公开称，对 Unity 做了大幅改造，底层渲染框架和上层渲染管线基本自研，并使用
自研 ECS、图形 API 层、虚拟纹理和多平台全动态光影。美术上，混凝土等现实材料会经过
信息重组，角色笔触会随光照和观察方向变化；团队称其为“写实主义二次元”。
([机核对鹰角主创的直接访谈](https://www.gcores.com/articles/192321)、
[Apple Developer 对开发团队的访谈](https://developer.apple.com/news/?id=cpt08xv8))

这是一套混合管线，而不是“更复杂的卡通 Ramp”。写实材质、动态阴影、冷色关系、笔触、
模型与服装设计共同建立风格。

**UE 5.8 映射建议**：场景继续走完整 PBR；角色 Toon Ramp 使用较软过渡，保留
Roughness/Metallic/Anisotropy，笔触先用 Toon Profile 的 RGBA Hatching 验证。若其只能作用
于阴影而无法覆盖所需视角响应，再增加一个局部材质函数，不要直接改 Deferred Lighting。

## UE 常见 NPR 技术路径

| 路径 | 优点 | 主要代价/失败模式 | 适合阶段 |
| --- | --- | --- | --- |
| 后处理量化 + 深度/法线/Stencil 描边 | 无源码 fork；全场景快速统一；容易做原型 | 只能看到屏幕空间结果；透明、遮挡、远景、TAA/TSR 与材质特例难处理；全屏成本 | 风格探索、描边、局部统一效果 |
| Unlit/Emissive 材质内自算光照 | 单材质控制强；不碰 Renderer | 需要自己补光源、阴影、GI、雾、反射；材质逻辑重复；多光源和跨平台迅速变重 | 固定镜头、小场景、特效材质 |
| Default Lit/Substrate PBR + 局部风格后处理 | 复用成熟光照、Lumen、阴影与平台路径 | 无法精确控制每盏灯的 Toon Ramp；后处理会误伤场景 | 环境风格化、弱卡通效果 |
| SceneViewExtension/RDG 自定义 Pass | 不 fork 引擎也能插入渲染 Pass；比材质后处理更可控 | 依赖 Renderer 内部资源与版本；仍需维护 C++/Shader | 原生能力有明确缺口之后 |
| 自定义 Shading Model / Renderer 源码 fork | 能控制 GBuffer、逐灯光照、阴影和材质数据 | 合并 UE 升级、Shader permutation、PSO、每平台验证成本最高 | 只有硬阻塞且产品收益已证明时 |
| **UE 5.8 原生 Substrate Toon BSDF** | 官方逐灯集成；Ramp、GI、局部光、排线、各向异性；无需 fork | Experimental；依赖 Blendable GBuffer legacy；描边/脸部特例仍需组合；平台矩阵需实测 | **当前首选基线** |

Epic 官方后处理文档确认 Deferred GBuffer 可提供深度、法线和材质属性，Custom Depth/Stencil
可做对象筛选和描边；Before Tonemapping 对深度/法线与 TAA 更稳定，After Tonemapping 的
LDR 成本更低。官方同时建议谨慎使用后处理 Pass，并要求在目标平台测量。
([Post Process Materials](https://dev.epicgames.com/documentation/en-us/unreal-engine/post-process-materials-in-unreal-engine))

社区插件证明“不 fork 引擎也能组合多种 Cel/Outline 方法”是可行的，但它只能作为实现参考，
不能替代 Epic 的平台支持承诺。
([UE5 Toon Shader Plugin 源码](https://github.com/miltoncandelero/ue5-toon-shader-plugin))

### “修改渲染管线”通常实际改什么

网上方案常把不同层级都称为“改管线”，应先分清改动边界：

1. **材质/后处理层**：读取 Scene Color、Depth、Normal、Custom Depth/Stencil，做颜色量化、
   描边或对象分区。没有新的逐灯材质语义，也没有真正新增 Shading Model。
2. **插件渲染 Pass**：通过 Scene View Extension/RDG 在既有渲染图插入 Global Shader Pass，
   读写允许的 Scene Texture。可以避免 Engine fork，但仍要随 UE Renderer 资源接口升级。
   Epic 公开的扩展入口见
   [FWorldSceneViewExtension](https://dev.epicgames.com/documentation/en-us/unreal-engine/API/Runtime/Engine/FWorldSceneViewExtension)。
3. **自定义 Shading Model/BSDF**：通常要同时处理材质枚举与编译、Material Editor 暴露、
   Base Pass/GBuffer 编解码、Deferred/Forward 光照分支、阴影/间接光、调试视图、Shader
   permutation、Cook/PSO 和每个目标 RHI。只加一个光照函数并不等于完成产品管线。
4. **完整 Renderer fork**：角色专用 GBuffer、独立光源列表、特殊阴影或调色可能继续扩大到
   Lumen、VSM、Ray Tracing、Translucency 和平台 Renderer；这是版本合并成本最高的层级。

因此“自定义 SM 比后处理更正确”不是充分理由。只有产品需要逐灯数据、额外 GBuffer Payload
或官方 BSDF 无法表达的光照次序时，它才是最小的正确层级；UE 5.8 已经原生覆盖大部分常见
Toon 漫反射/高光需求。

## UE 5.8 原生 Toon Shading 的能力与边界

Epic 在 UE 5.8 将 **Substrate NPR Shading / Substrate Toon Shading** 标为 Experimental。
它建立在 **Substrate Blendable GBuffer (legacy)** 模式上，官方列出的能力包括：

- 所有光源类型，包括局部光、Sky Light 和 Lumen GI；
- Toon BSDF 与按材质指定的 Toon Profile 资产；
- 漫反射/高光 Ramp 与 Dithering；
- 自阴影 Extinction 与 Hatching；
- Anisotropic Specular；
- 漫反射和高光间接光缩放。

来源：
[UE 5.8 Release Notes](https://dev.epicgames.com/documentation/unreal-engine/unreal-engine-5-8-release-notes?lang=en-US)、
[FToonProfileStruct](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/FToonProfileStruct?lang=en-US)、
[ToonProfileStruct Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ToonProfileStruct)、
[Toon BSDF Python API](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/MaterialExpressionSubstrateToonBSDF)、
[UToonProfile](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/UToonProfile?lang=en-US)。

### 原生 Toon 相比传统方案

| 比较项 | 后处理 Toon | Unlit 自算 | 源码自定义 SM | UE 5.8 原生 Toon |
| --- | --- | --- | --- | --- |
| 逐灯响应 | 弱/间接 | 需自行传入 | 强 | 强 |
| 引擎阴影与局部光 | 结果级处理 | 需重建 | 可完整接入 | 官方接入 |
| Sky Light / Lumen GI | 只能量化最终结果 | 需重建/近似 | 可接入但开发重 | 官方列为支持 |
| 漫反射/高光 Ramp | 屏幕空间 | 材质内 | Renderer 内 | Toon Profile 原生 |
| 各向异性高光 | 难 | 可写但昂贵 | 可写 | 原生列出 |
| 阴影排线 | 后处理叠加 | 材质实现 | 可写 | 原生 RGBA Hatching |
| 描边 | 常用强项 | 另做 | 另做 | 官方功能列表未给出，另做 |
| 维护 UE 升级 | 低 | 低至中 | 高 | 低，但 Experimental 行为会变 |
| 平台确定性 | 取决于 SceneTexture | 取决于材质路径 | 全部自担 | 官方未给完整 Toon 平台矩阵，必须实测 |

### 不能从“原生”推导出的结论

- **不能推导为可直接量产**：Toon 本身是 Experimental；
  [Substrate Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-substrate-materials-in-unreal-engine)
  也要求谨慎用于 Shipping。升级小版本前要重新做画面、性能与 Shader 编译回归。
- **不能推导为内置描边**：5.8 Release Notes 和 Toon API 没有把 Outline 列为能力。
- **不能推导为移动/Forward 全功能等价**：公开文档没有完整 Toon 平台/RHI/Forward 矩阵。
- **不能运行时随意改 Toon Profile**：`UToonProfile` 官方备注为 per-material，并写明
  “Don't change at runtime”。运行时变化应先验证 Material Instance/参数或准备离散 Profile。
- **不能替代角色专项管线**：脸部阴影、头发分层、眼睛、半透明、角色专用光、TOD 和调色
  仍然是独立问题。

### 原生 Toon 已公开的贴图语义

- `DiffuseRampOffsetTexture`、`SpecularRampOffsetTexture`：官方建议灰度 `[0,1]`，内部映射到
  `[-1,1]`；推荐距离场。不要在没验证 Shader 采样通道前盲目把它们塞进综合 Mask。
- `ShadowHatchingPatternTexture`：RGBA 从浅到重排列；阴影变暗时依次混合 R、G、B、A。
- `PatternUVs`：Toon BSDF 提供独立图案 UV 输入，适合控制排线尺度和空间。
- 间接高光量化还需要实验性 CVar
  `r.Substrate.Experimental.ToonReflectionQuantizationEnabled=1`；不能默认计入 Shipping 基线。

## 项目贴图与资产规范

以下是 **NPR_rendering 项目建议**，不是三款商业游戏的泄露规格。先以最小资产集验证，再由
实测数据修改分辨率和通道，不为未来可能的效果预留贴图。

### 命名

遵循 Epic 的 `[AssetTypePrefix]_[AssetName]_[Descriptor]_[OptionalVariant]`：

- Material：`M_CharacterToon`、`M_EnvironmentHybrid`
- Material Instance：`MI_<Character>_<Part>`
- Post Process Material：`PPM_ToonOutline`
- Texture：`T_<Character>_<Part>_<Type>`
- Toon Profile：项目内使用 `TP_<Style>_<Variant>`；`TP_` 是本项目约定，不是 Epic 官方前缀

来源：
[Epic Recommended Asset Naming Conventions](https://dev.epicgames.com/documentation/en-us/unreal-engine/recommended-asset-naming-conventions-in-unreal-engine-projects)。

### 最小贴图集合

| 资产 | 色彩空间/压缩意图 | 初始尺寸建议 | 用途与约束 |
| --- | --- | --- | --- |
| `T_*_BC` | sRGB 开；Color/Default | Hero 身体 2K，脸/发/附件 1K 起 | 固有色与大尺度手绘渐变；不烘焙方向固定的实时阴影 |
| `T_*_N` | sRGB 关；Normal Map/BC5 类 | 1K–2K | 切线空间法线；角色皮肤保持克制，衣料/硬表面按可见收益添加 |
| `T_*_ORM` | sRGB 关；Masks | 1K 起 | R=AO、G=Roughness、B=Metallic；供环境与终末地式混合材质使用；语义固定 |
| `T_*_Style` | sRGB 关；Masks | 512–1K | 仅在原型证明需要时创建。建议 R=Specular Weight、G=Outline Weight、B=Shadow Bias、A=Material Region；不直接替代 Toon Profile Offset |
| `T_*_DiffuseOffset` | sRGB 关；Grayscale/Masks | 512–1K | 原生 Toon 漫反射 Ramp Offset；灰度距离场，保留阈值的 Mip 稳定性 |
| `T_*_SpecularOffset` | sRGB 关；Grayscale/Masks | 512–1K | 只有高光确需逐像素偏移时创建；否则删除并用 Profile 曲线 |
| `T_Hatching_*` | sRGB 关；Masks RGBA | 256–512 可平铺 | R/G/B/A 由浅到重；固定 PatternUVs 尺度，测试运动与 TSR |
| `T_*_FaceSDF` | sRGB 关；BC5/Linear | 512–1K | **可选外挂**；RG 可存左右方向场；不能宣称为原生 Toon Profile 输入 |
| Color Grading LUT | 官方布局与设置 | 256×16 | Lookdev 可用 NoMipMaps + ColorLookupTable；最终 HDR/多显示器优先场景参考调色 |

尺寸是起点而非硬性标准。用目标画面占屏、Texel Density、Streaming Pool、目标 RHI 和
Mip 驻留数据决定是否升降；禁止“Hero 一律 4K”。

### 导入与运行规范

1. Base Color 使用 sRGB；Normal、ORM、Mask、SDF、Offset、Hatching 等数据贴图关闭 sRGB。
2. 尽可能使用 2 的幂。Epic 文档明确指出非 2 的幂贴图不会生成 Mip，也不会 Streaming。
3. Color、Normal 和大部分数据贴图保留 Mip；Normal 开启适当的 Mip 归一化。SDF/细线排线
   必须在远景 Mip 下验收，不能只看原始分辨率。
4. 通道打包只用于生命周期、UV、分辨率、Mip 和压缩需求相同的数据。为省一次采样而把
   Offset、Face SDF、Outline 等不同数据硬塞在一起，通常会制造压缩与维护问题。
5. 使用 Texture Group 和 Device Profile 约束 LOD。若 Group 最终只允许 1K，就不要提交
   无收益的 2K 源资产到 cooked 包。
6. Character 贴图默认走普通 Streaming；Virtual Texture 只给超大世界、地形或经测量证明
   受益的大型纹理集，不把它当角色贴图默认值。
7. 不在每个角色复制 Master Material。优先一个角色母材、一个环境基线、少量 Toon
   Profile 和 Material Instance；只有不同渲染域/Blend Mode 才拆母材。

官方依据：
[Textures](https://dev.epicgames.com/documentation/en-us/unreal-engine/textures-in-unreal-engine)、
[Texture Asset Editor](https://dev.epicgames.com/documentation/en-us/unreal-engine/texture-asset-editor-in-unreal-engine)、
[Texture Streaming Configuration](https://dev.epicgames.com/documentation/en-us/unreal-engine/texture-streaming-configuration-in-unreal-engine)、
[Texture Format and Groups](https://dev.epicgames.com/documentation/en-us/unreal-engine/texture-format-support-and-settings-in-unreal-engine)、
[Virtual Texturing](https://dev.epicgames.com/documentation/en-us/unreal-engine/virtual-texturing-in-unreal-engine)、
[Color Grading LUT](https://dev.epicgames.com/documentation/en-us/unreal-engine/using-lookup-tables-for-color-grading-in-unreal-engine)。

### 风格 Profile 不使用商业游戏名

建议只建三个中性原型 Profile，避免把“复刻作品名”固化为产品资产：

- `TP_Clean_2Band`：硬边、低噪点、窄高光，对应干净动画风验证。
- `TP_Gradient_Soft`：软 Ramp、Base Color 渐变、较强调色，对应电影化渐变验证。
- `TP_Hybrid_PBR`：更连续的漫反射、保留 Roughness/Metallic/Anisotropy，对应写实混合验证。

## 最小验证切片

不要先做完整管线。一个能推翻错误路线的匹配测试就够：

### 内容

- 一个 Hero 角色：脸、皮肤、头发、布料、金属至少五种区域；
- 一个环境资产：混凝土/岩石或工业硬表面；
- 三个 Toon Profile；
- 一个描边 Pass；
- Face SDF 先不接，保留为第二轮对照项。

### 固定变量

- 固定相机、曝光、色彩管理和 TOD；
- 室外日光、背光、室内局部光三组场景；
- 同一 Mesh、贴图、灯光分别跑 Default Lit 与原生 Toon；
- 测试静帧和运动，覆盖 TAA/TSR、近景/远景、遮挡与半透明交界；
- 在真实目标 RHI 和 Device Profile 上测试，不用 Editor 桌面预览代替平台结论。

### 通过条件

1. 三种风格都能只通过 Profile/实例参数切换，不复制 Renderer 或角色母材。
2. 脸部在正光、侧光、顶光、背光和表演局部光中没有不可接受的阴影翻转。
3. 头发高光、阴影排线和描边在运动中无明显闪烁、拖影和一像素跳动。
4. Local Light、Sky Light、Lumen GI、雾、透明/VFX 交界行为有明确结果。
5. 记录 GPU Pass、材质 Shader 数、PSO/编译量、纹理驻留和目标帧预算；不能只凭截图选型。

### 升级到源码修改的硬门槛

只有下列至少一项有可复现证据时，才评估 `Aether/` UE 源码分支：

- 原生 Toon 在目标平台/RHI 不支持或存在无法规避的错误；
- 产品必须获得原生接口没有暴露的逐灯数据或新增 GBuffer Payload；
- 角色专用光照无法通过 Lighting Channel、材质参数或独立 Pass 实现；
- 脸、发、局部光与阴影的视觉门槛在原生路径上稳定失败；
- 插件 Pass 的成本或画质实测显著差于源码方案，且升级维护预算已获确认。

在此之前，修改 Renderer 只会把一个尚未定义清楚的美术问题变成长期引擎维护问题。

## 当前风险清单

- UE 5.8 Toon 是 Experimental，且依赖 Blendable GBuffer legacy；正式量产版本可能变化。
- 官方尚未给出完整 Toon 平台矩阵，移动端、Forward、各 RHI 和降级路径都是未验证项。
- 官方能力列表不含描边；后处理描边在 TSR、透明、发丝和远景上可能失败。
- Hatching 与细 Ramp 在 Mip、动态分辨率和时间抗锯齿下可能闪烁。
- `UToonProfile` 不应在运行时修改，天气/TOD 变化需要提前设计参数责任边界。
- 三款游戏的逐通道贴图与线上 Shader 细节没有公开，任何“完全复刻”目标都缺少可靠验收基准。

## 决策

**采用 UE 5.8 原生 Toon 作为候选基线；暂不 fork Renderer。** 下一步不是继续搜更多拆包
教程，而是确定目标平台和帧预算，然后完成上述一个匹配验证切片。只有实测失败项才允许扩大
实现范围。
