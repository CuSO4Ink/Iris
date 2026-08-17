# UE 5.8 卡通渲染管线 SOP

> 只记录当前采用的技术选型与执行流程；不记录历史、日志和被替代方案。当前不含描边 Pass。

## 1. 技术选型

| 域 | 选型 |
| --- | --- |
| 环境 | 原生 PBR、Lumen/Sky Light、Reflection、VSM |
| 角色主干 | UE 5.8 Deferred + Substrate Toon BSDF + 静态 `UToonProfile` |
| 服装/皮革/金属 | Stylized PBR；保留 Normal、Roughness、Metallic、直接高光和 IBL |
| 皮肤 | 独立 Skin Profile；Metallic=0；先用 Toon + 低能量 SSS/Transmission，出现双重明暗、发灰或不稳定时改为纯 Skin Ramp |
| 脸 | Face SDF 控制主光漫反射；几何法线保留高光、真实投影和辅助光响应 |
| 头发 | Toon 漫反射 + Tangent/Anisotropy 高光；必要时使用简化阴影代理 |
| 眼睛 | 独立 Opaque/Masked Eye 材质、稳定法线与独立 Catchlight/MatCap |
| 阴影 | Cast Shadow、Diffuse Ramp、AO、Contact Shadow、GI 分开管理；阴影只削弱直接光 |
| 后处理 | 固定曝光 → Tonemap → LUT → Bloom → TSR/TAA |
| 引擎改动 | 原生 Toon 先验证；只有 Face SDF 或光照数据出现可复现硬阻塞后，才在 `Aether/` 分支做最小扩展 |

## 2. 资产与贴图合同

### 模型输入

- `.vrm`、`.glb` 或 `.fbx`，保留 Skeleton、蒙皮、作者法线、UV0 和材质槽。
- 材质域至少区分 Face、Skin、Hair、Eye、Cloth、Leather/Rubber、Metal。
- UV0 保留原 Base Color。只有重叠 UV 需要不同材质遮罩时，新增非重叠 Mask UV，不重排 UV0。

### 运行时贴图

| 贴图 | 合同 |
| --- | --- |
| `T_<Part>_BC` | sRGB 开；保留设计色，不含固定方向阴影、高光或 AO |
| `T_<Part>_N_Meso` | 切线空间结构 Normal；Normalmap/BC5；sRGB 关；启用 Normal Mip 归一化；只承载压槽、浅倒角、接缝、折痕和不改变轮廓的中频结构 |
| `T_<Part>_N_Micro` | 切线空间材质微法线；Normalmap/BC5；sRGB 关；按 MaterialID、真实尺度和方向生成；不承载零件边界或装配厚度 |
| `T_<Part>_P` | R=AO，G=Specular，B=Metallic，A=Roughness；BC7；sRGB 关；没有网格 AO 时 R=1；Cavity 独立保留，不冒充 AO |
| `T_<Part>_Mask` | 按需打包 Fuzz、Coating、Leather、AO 等行为遮罩；通道语义固定 |
| `T_<Surface>_Detail_N` | 同质材质槽可用的无缝平铺微法线；Normalmap；sRGB 关；按真实尺度采样；异质材质槽必须先按 Mask 分层 |
| `T_<Part>_AO` | 仅在需要独立分辨率时使用；否则写入 `P.R`；只作用于间接光 |
| `T_<Hero>_Skin_Thickness` | 从隔离皮肤几何计算，用于 SSS/Transmission；不能从 Base Color 推断 |
| `T_<Hero>_FaceSDF` | 线性距离场；sRGB 关；脸部 UV 不镜像 |
| `T_<Hero>_HairDirection` | 头发高光方向；缺失时使用稳定 mesh tangent |
| `T_<Hero>_EyeMask` | Iris、Sclera、Pupil、Catchlight/Shadow 分区 |

规则：Metallic 由材质身份决定；Roughness 由材质参考与分级决定；Macro Normal 来自几何/烘焙；
Meso Normal 来自语义结构 Primitive；Micro Normal 来自可信材质微表面。不得把 Base Color 灰度直接转换成最终 Metallic 或整张 Normal；禁止用一张随机微法线覆盖同槽内所有非金属类别。Meso 与 Micro 分别缩放解码后的 XY 并重建 Z，再以 `normalize(float3(Nmeso.xy + Nmicro.xy, Nmeso.z * Nmicro.z))` 合成；禁止 `Lerp` 法线。没有独立 Micro 的实例保持 `MicroNormalStrength=0`。任一强度需要远高于 1 才可见时，退回检查生成尺度、导入压缩和采样路径。结构法线必须包含压槽、缝线、折痕和浅倒角等内部中频造型，不能只沿 Base Color/MaterialID 边界生成一圈斜率。

## 3. 表面表现规范

以下数值是 UE 中性灯光下的起始窗口，不是材料常数；最终值以同类实物或扫描材质在固定灯光中的高光形状为准。
非金属统一 `Metallic=0`，Substrate `F0=0.02–0.06`；Legacy 材质无测量依据时保持默认 `Specular=0.5`。

### 表现层级

| 层级 | 内容 | 制作方式 |
| --- | --- | --- |
| 轮廓/厚度 | 鞋底厚度、包边、叠片、翻边、突出扣件 | 几何；法线贴图不得代替会改变轮廓或遮挡关系的结构 |
| 结构起伏 | 压线、接缝、浅面板倒角、浅鞋底沟槽、折痕 | Height/烘焙 Meso Normal，并配套 Cavity；先于微法线制作 |
| 微表面 | 皮革粒面、织物经纬、毛孔、细纤维、细小橘皮、细磨痕 | 按 MaterialID 分区的低幅 Micro Normal + Roughness；按真实尺度和方向采样 |
| 光学层 | 漆膜、油蜡层、绒毛、各向异性、回归反射 | Coat/Second Roughness、Fuzz、Tangent/Anisotropy 或专用响应 |

`PartID`、`MaterialID`、`Meso Height/Normal` 和 `Micro Normal` 是四种独立数据：零件边界不等于材质边界，材质遮罩不产生高度，随机微法线不产生装配厚度。

### 服装面料

| Profile | 必须读出的现象 | 制作与 UE 选型 | Roughness 起始窗口 |
| --- | --- | --- | --- |
| `Textile_CottonLinen` 棉/麻/府绸 | 哑光、细弱经纬、柔和掠射纤维光；纹理不能抢过衣褶 | 衣褶用几何；真实尺度定向微法线 + 低 Fuzz；Base Color 不烘焙经纬阴影 | `0.65–0.90` |
| `Textile_Jersey` T 恤/弹力针织 | 表面较平、细密针织方向、柔软连续小褶 | 很弱针织法线 + 低 Fuzz；拉伸区不允许纹理尺度漂移 | `0.60–0.85` |
| `Textile_Canvas` 帆布/厚棉 | 粗经纬可见、布身硬、折线较硬 | 织纹 Structural Normal + Cavity；大褶仍用几何 | `0.70–0.95` |
| `Textile_DenimTwill` 牛仔/斜纹 | 稳定斜向纹、缝边与摩擦区褪色；不是随机蓝噪声 | 定向 Twill Normal；磨损同时影响颜色与 Roughness，并服从膝、肘、边缘 | `0.65–0.90` |
| `Textile_WoolKnit` 毛线/粗针织 | 可辨认线圈、线圈间自遮挡、明显绒毛 | Hero 线圈用几何/Height；中景 Structural Normal + Cavity；Fuzz | `0.75–0.95` |
| `Textile_SatinSilk` 丝绸/缎 | 光滑底面、窄而沿织向拉长的高光、随视角滑动 | 极弱法线 + 稳定 Tangent/Anisotropy；禁止皮革颗粒和宽哑光高光 | `0.18–0.45` |
| `Textile_Velvet` 天鹅绒/丝绒 | 正视偏暗、掠射出现有色绒光，刷向改变明暗 | Fuzz + 稳定 Tangent；绒向属于数据，不从 Base Color 猜 | `0.70–0.95` |
| `Textile_NylonPoly` 尼龙/涤纶运动面料 | 比棉布更平整，织纹细，介电高光略窄 | 低幅定向法线；低 Fuzz，可加轻微 Anisotropy | `0.35–0.70` |
| `Textile_Coated` 雨衣/涂层布 | 布料褶皱仍存在，表面另有更平滑的第二高光 | 布料基底 + Simple Coat/Second Lobe；Coat Mask 独立 | 基底 `0.55–0.80`；涂层 `0.15–0.45` |
| `Textile_FleeceFur` 抓绒/毛绒/仿毛 | 明显毛层、柔软轮廓和掠射绒光 | 中远景 Fuzz；Hero 轮廓用毛卡/Groom/几何，不能只靠法线 | `0.80–0.98` |
| `Textile_LaceMesh` 蕾丝/网布/网眼 | 真正孔洞、丝线交叉和边缘厚度 | 小孔用 Masked + Coverage，Hero 大孔用几何；孔洞不能画成黑色 Base Color | `0.55–0.85` |
| `Textile_Sheer` 雪纺/薄纱/欧根纱 | 透光、叠层加深、边缘与褶皱处密度更高 | Coverage 与 Transmittance 分离；优先 Masked/dither，Hero 必要时用 Thin Translucent | `0.30–0.70` |

### 皮革与聚合物

| Profile | 必须读出的现象 | 制作与 UE 选型 | Roughness 起始窗口 |
| --- | --- | --- | --- |
| `Leather_Natural` 天然粒面皮革 | 不重复粒面；宽而破碎高光；褶皱只在弯折、受压、缝制区 | 厚度/包边用几何，粒面用低幅 Height；涂饰/油蜡皮加弱 Second Lobe/Coat；禁用全表面等幅虫状皱纹 | 未涂饰 `0.45–0.70`；涂饰 `0.25–0.50` |
| `Leather_Suede` 绒面革/Nubuck | 柔软掠射绒光、刷向变化；无亮塑料膜和卵石鼓包 | 很弱定向微法线 + Fuzz；禁用 Clear Coat | `0.75–0.95` |
| `Leather_Synthetic` PU/合成革 | 较规则压花、均匀表面膜、天然孔隙变化少 | 压花 Height + 低幅 Micro Normal；按 finish 加弱 Coat | `0.30–0.60` |
| `Polymer_Hard` ABS/TPU 护甲壳 | 干净连续高光、倒角清楚、表面基本平整 | 厚度与倒角用几何/Structural Normal；仅允许极弱橘皮；有漆时加 Coat | `0.25–0.60` |
| `Polymer_VinylLatex` 漆皮/乙烯基/乳胶 | 连续锐利高光、张力褶皱、表面膜感强 | 平滑 Normal + Coat/Second Lobe；褶皱来自几何，禁止粒面噪声 | `0.08–0.30` |
| `Polymer_Rubber` 橡胶/硅胶 | 宽弱高光，掠射仍反光；接触区磨亮；沟槽有深度 | 鞋底纹/防滑纹用几何或 Height；细孔低幅；黑色不等于无高光 | `0.65–0.90` |
| `Polymer_Foam` EVA/泡棉 | 微孔哑光、软边、受压形变感；不应像硬塑料 | 低幅多尺度孔隙 + 高 Roughness；厚度和压痕用几何/Height | `0.75–0.95` |
| `Polymer_Clear` 透明塑料/树脂 | 清晰表面反射、厚度造成吸收或色偏、内部可见 | 有厚度的透明几何 + Transmittance/IOR；划痕主要进 Roughness | `0.02–0.25` |

### 五金与饰品表面

| Profile | 必须读出的现象 | 制作与 UE 选型 | Roughness 起始窗口 |
| --- | --- | --- | --- |
| `Metal_Polished` 抛光钢/金银铜 | 反射带金属颜色、几乎无介电漫反射、倒角高光清晰 | `Metallic=1`；Hero 倒角必须有几何；指纹/细划痕主要改 Roughness | `0.05–0.25` |
| `Metal_Brushed` 拉丝/磨砂金属 | 高光沿加工方向拉长，方向跨零件保持连续 | `Metallic=1` + Tangent/Anisotropy；划痕必须服从加工方向 | `0.20–0.55` |
| `Metal_PaintedEnamel` 喷漆/珐琅五金 | 完整表层为介电漆膜；掉漆处才露金属 | 完整处 `Metallic=0`，露底处切 `1`；漆面用 Coat/Second Lobe | `0.10–0.50` |
| `Gem_GlassCrystal` 玻璃/水晶/透明宝石 | 切面产生锐利反射与折射，颜色随厚度变化 | 切面和厚度用几何；Transmittance/IOR，必要时有色吸收；不能用平面高光贴图冒充 | `0.02–0.15` |
| `Gem_Pearl` 珍珠/珠光 | 柔和宽高光、浅层乳白散射和轻微视角色偏 | 介电底层 + 弱 Coat/浅层散射；`Metallic=0` | `0.15–0.35` |
| `Trim_Sequin` 亮片/金葱 | 离散小片各自闪烁，闪点随视角变化 | Hero 用薄片几何/Atlas Normal；当前 Blendable GBuffer 不依赖 Substrate Glints；禁止白噪声 Emissive | 片面 `0.08–0.35` |
| `Trim_Reflective` 回归反射条 | 仅当视线接近入射光反向时显著变亮 | 独立 Mask + 专用回归反射响应；不能用低 Roughness 或 Emissive 冒充 | 不适用 |
| `Trim_Emissive` LED/发光饰件 | 无灯时不自发光，点亮时保留结构边缘且只有限量 Bloom | 独立 Emissive Mask/强度；Base Color、发光与 Bloom 分开 | 不适用 |

### 服装结构与工艺

| 结构 | 表现规则 |
| --- | --- |
| 接缝、包边、滚边、下摆 | 影响轮廓或产生遮挡时用几何；其余用 Height/Structural Normal + Cavity，不能只画深色线 |
| 缝线 | 有线径、走向和针距；Hero 用几何/Height，中景用 Normal；颜色、粗糙度继承线材而非布料 |
| 刺绣 | 线束高于底布，方向随针法变化；需要 Height、定向 Normal、Cavity，必要时轻微 Anisotropy |
| 染色/普通印花 | 不增加厚度，继承底布 Normal；只改 Base Color，可有很小 Roughness 差 |
| 胶印/丝网厚印 | 有薄层高度和更平滑表面；Height + 独立 Roughness/Coat Mask |
| 贴布/徽章 | 独立厚度、边缘、缝线和材质；至少需要 PartID，Hero 用几何 |
| 拉链 | 齿、布带、滑块分别归类；Hero 齿与滑块用几何，不能把整条拉链烘成一根亮线 |
| 纽扣、按扣、铆钉、扣具 | 有厚度和倒角；先按塑料、金属、木/角等材质分类，再套对应 Profile |
| 链条、圆环 | 每节有独立轮廓、遮挡和高光；Hero 必须几何，中远景才允许代理 |
| 绳、鞋带、织带 | 有截面、编织/捻向和压扁区；几何承担轮廓，定向微法线承担纤维 |
| 褶裥、抽褶、绗缝、填充 | 属于布片结构与体积，必须由几何/模拟决定；贴图只补压线和细皱 |
| 磨损、污渍 | 只能出现在摩擦、接触、积尘和受力位置；可改颜色、Roughness、Normal，不能当作材质身份 |

先匹配真实材质，再做风格化压缩：允许降低微纹理对比和压缩高光动态范围，不允许改变材质身份或用噪声补结构。

### 参考与验收

1. 每种材质先锁定 `类别 + finish（干/油蜡/涂层/磨损）+ 真实尺寸 + 磨损区`，并准备正视、45° 和掠射参考；无法确定时输出候选，不直接写死。
2. 固定中灰背景、曝光和相机；灯光至少包含 45° 大面积主光、掠射条形光和 IBL。回归反射另用与相机近轴的点/聚光灯检查。
3. 依次验收 `PartID`、统一灰色/统一 Roughness 的 `Clay Structure`、灰色 Base Color 的 `Surface Response`、最终 Beauty；不得跳过前两项。
4. Clay 中必须读出零件边界、倒角、厚度和压线；Surface Response 中必须不靠颜色读出皮革、橡胶、塑料、布和金属。
5. Close-up、Gameplay Medium、Full Body 三个距离均检查；微纹理在中远景必须自然收敛，不闪烁、不形成脏噪声。

## 4. 多视角语义重建与贴图生成

当前自动路径只支持 VRM/GLB。使用现有 `vrm_material_probe.py` 的 CPU 光栅器直接取得可见
Triangle ID、深度、重心 UV 和面朝向；FBX 先转换为 GLB，不维护第二套捕获实现。

### A. 多视角输入

1. 审计材质槽、UV0、透明覆盖和镜像/重叠 UV；材质槽只作为物件范围，不等于真实材质分类。
2. 每个目标材质槽生成 8 个环绕正交视角；只有覆盖报告存在缺口时才增加第二高度带或隔离视图。
3. 每个视角保存 Unlit Base Color，并保留 Triangle ID、深度、UV 与面朝向供回投使用。
4. UV 展开图不作为语义识别主输入；所有识别首先发生在模型实际视图中。

### B. 语义层

语义必须分层保存，不能压成一张互斥 ID：

- `PartInstance`：具体零件。
- `StructureRole`：Panel、Strap、Seam、Fold、Hardware、Trim、Unknown。
- `MaterialFamily`：Textile、Leather、Polymer、Metal、Gem、Special、Unknown。
- `SurfaceMark`：Print、PaintedShadow、Wear；默认不产生结构高度。
- `RepresentationClass`：GeometryRequired、MesoHeight、SurfaceOnly；决定结构进入几何、法线或仅表面通道。
- `Confidence`：逐像素浮点置信度。

当前做法由视觉判断在多视角上生成软区域提示，再用可见三角形回投。Base Color 只允许在已提出的
语义区域内辅助区分类别，例如从扣件候选中收紧金属区域；禁止把亮度、Sobel 或颜色边缘直接输入 Height。
`StructureRole=Hardware` 只表示独立扣件/护件，不能据此写入 Metallic；金属必须由独立
`MaterialFamily=Metal` 证据确认。

### C. 表面融合

1. 逐像素通过可见 Triangle ID 和 UV 回投，按面朝向与提示置信度加权。
2. BaseColor 参与语义分类前必须变换到与 UV 光栅完全相同的坐标约定；用几何覆盖区与 BaseColor Alpha 的重叠率检查方向、Wrap 和 Transform，未通过不得继续分类。
3. 保留浮点 Coverage；只在 Panel/Strap 的无采样洞内使用三角形多数票补洞，Hardware、Print 不允许整面扩张。
4. 先在表面语义中解决冲突，再写入 UV；不跨 UV 岛模糊。
5. 重叠 UV 只有在实例语义一致时允许共享。标签冲突时新增非重叠 Mask UV，不修改 Base Color UV0。
6. 输出 StructureID、MaterialID、各语义 Coverage、SurfaceMark 和 Confidence，供人工检查和后续重算。PartID 与 MaterialID 独立生成；禁止把 `ToeCap=TPU`、`Strap=Leather` 等零件名称直接当成材质身份。
7. Confidence 只用于诊断和标签决策；生成 Primitive 前必须去除小连通噪声并转换成稳定 Coverage，
   禁止将原始置信度乘进 Height 振幅。

### D. Primitive 与贴图

| 语义 | 当前结构规则 |
| --- | --- |
| Panel | 独立护板先标为 GeometryRequired，细分贴合源表面后生成带侧壁的 skinned shell 并转移权重；只有不影响轮廓/遮挡的低浮雕才用冠面、倒角和压槽 Height |
| Strap | 有独立截面、压叠关系或轮廓时生成 skinned shell；仅嵌入式压带使用圆钝 Height |
| Hardware | 较硬凸面 + 窄倒角；影响轮廓时升级为几何 |
| Seam | 中心线、宽度、深度和针距生成 Groove/Ridge |
| Fold | 只输出候选中心线、方向、宽度和振幅；没有证据不生成 |
| Print/PaintedShadow | 对 Height 的增量固定为零 |
| Unknown | 保持平坦，不猜结构和材质 |

1. Primitive 合成 16-bit Meso Height，再确定性转换为 DirectX 切线空间 Meso Normal；结构边缘超采样并生成 Gutter。
2. Macro Normal 来自网格或高低模烘焙；Meso 负责浅面板、压槽、缝线和折痕；结构 Gate 通过后，按 MaterialID 分别生成 PU、TPU、Rubber、Textile、Metal 等 Micro Normal。
3. GeometryRequired 必须使用实例级轮廓；不得按原始低模三角形直接选面挤出。先细分/重拓扑、贴合源表面，再 Solidify/Bevel，并从源网格转移 Armature 与 Skin Weights。
4. Meso Cavity 从 Height 独立生成。没有网格 AO 时 `P.R` 保持 1，禁止把 Cavity 或 Base Color 阴影冒充 AO。
5. Metallic 由 MaterialFamily 决定；Roughness 由 MaterialFamily、Finish 和 Wear 决定，不按 Base Color 明度映射。
6. 鞋类当前语义合同为 `Vamp / ToeCap / Rand / Outsole / Collar / Guard / Strap / Hardware / Print`，依次生成 `PartID → MaterialID → Meso → Micro → PBR`；Hardware 只有获得明确金属材质证据时才允许写入 Metallic。
7. UE 固定输入 `BaseColorTexture + PartNormal + MicroNormal + PackedPBR + PartNormalStrength + MicroNormalStrength + RoughnessStrength + MetallicStrength`。两张法线独立解码、缩放和重建 Z 后再做白化式合成；默认制作强度均为 1。
8. 首次创建纹理与同名纹理更新是两条不同操作：更新必须使用支持覆盖现有 Texture2D 的 typed importer，并以目标 Texture Source/快照哈希变化为成功条件；普通 create-only import 的 no-op 不算重导入成功。重导入后重新检查 Normalmap/BC7、sRGB、LODGroup、Mip 与 Normal 归一化设置。

### E. 自动检查与视觉 Gate

- 检查 UV 共享比例、跨视角多标签冲突、未分配结构比例和每类 Coverage。
- 检查 Normal 单位长度、结构区平均斜率、P95 斜率、N/P 尺寸和通道合同。
- 技术检查通过后，由用户在固定灯光下检查 Clay Structure、Surface Response 和 Beauty；不以自动测试代替画面验收。

## 5. 执行 Gate

| Gate | 工作 | 通过条件 |
| --- | --- | --- |
| G0 合同 | 锁定 UE 版本、平台/RHI、参考图、固定灯光/相机、曝光、AA 和预算 | 输入与预算唯一 |
| G1 资产 | 审计模型、UV、法线、材质槽和贴图通道 | 所有槽位和缺失数据可解释 |
| G2 资产重建 | 多视角标注 → Part/Structure/Material/SurfaceMark → RepresentationClass → Geometry shell 或 Meso → MaterialID Micro → PBR | 回投无错位，Geometry 有轮廓/侧壁/权重，Meso 与 Micro 可独立检查，材质身份可信 |
| G3 场景 | 建立固定 Close Face、Close Hand、Medium、Full Body 与六种灯光状态 | Default Lit 基线可复现 |
| G4 Surface | 依次通过 Clay Structure、Surface Response、Beauty | 结构不靠颜色、材质不靠噪声，Normal/Roughness/Metallic 可解释 |
| G5 Skin | 接入 Skin Profile、Thickness 与低能量 SSS | 脸手暗部干净，无双重光照；失败则切纯 Ramp |
| G6 Face | 接入 Face SDF、Face Area 和真实 Cast Shadow | 正侧顶背光稳定 |
| G7 Hair/Eye | 接入 Hair Direction、稳定高光、Eye Mask/Catchlight | 运动无闪烁、发片阴影无颗粒 |
| G8 集成 | 固定后处理，检查 LOD、运动、纹理、Shader/PSO 和 GPU | 达到预算且跨距离稳定 |
| G9 冻结 | 编译、回读、Cook、目标平台和用户视觉验收 | 技术与画面同时通过 |

## 6. 备选技术池（非当前选型）

本节只登记竞品抓帧、Shader 逆向和复刻文章中值得保留的候选技术，不表示项目已经采用。候选项只有在
G0–G8 中出现明确画面目标、可复现缺陷或量化性能瓶颈，并完成最小 A/B 验证后，才能进入第 1 节的
当前选型；不得因此预建第二套 Renderer。

| 来源 | 候选技术 | 主要优势 | 启用条件 | 优先级 |
| --- | --- | --- | --- | --- |
| 共通 | 角色辅助数据：Normal、Material/Outline ID、Stencil、Velocity | 把描边、角色阴影、局部调色和时间稳定性从 Base Color/主 GBuffer 中解耦 | 原生 Toon 无法稳定完成描边或角色分类；先验证最小 MRT/Stencil 成本 | A |
| 《终末地》/《白银之城》 | 角色写入场景深度/GBuffer 后，以独立 Forward/Overlay HDR 层重绘 | 角色仍参与 AO、反射和遮挡，同时允许独立脸、发、眼和补光模型 | Substrate Toon 在分光源响应、透明额发、角色调色或雾水集成上出现硬阻塞 | B |
| 《绝区零》/《白银之城》 | 平滑法线 inverse-hull 描边 + 分材质颜色 + Motion Vector | 外轮廓稳定、颜色服从材质身份，并可在 TSR/TAA 下正确重投影 | 项目确定需要描边；先与轻量屏幕空间内部线 A/B | A |
| 《终末地》/《白银之城》 | 角色专用 Shadow Proxy/高精度阴影，与场景 VSM 分层复合 | 提高脸、发片和落地轮廓的稳定性，允许独立 Bias、软硬和艺术控制 | VSM-only 出现可复现漏影、颗粒、双面发片或轮廓不稳定 | A |
| 《终末地》 | 从 Face SDF 重建光照法线，并按 Face Area 与几何法线混合 | 抑制鼻梁、眼窝碎影；同一数据可驱动漫反射、边缘光和侧光 | 现有 Face SDF 只切明暗仍无法通过正侧顶背光 Gate | A |
| 《终末地》 | SDF 阴影过渡宽度随灯光水平角动态变化 | 正/背光保持清楚块面，侧光变软，减少阴阳脸 | 固定阈值/Softness 无法同时覆盖正面与侧面灯光 | A |
| 《终末地》 | 角色朝向、真实灯光与视线共同构造艺术化 Half Vector；可选 Specular-only/第二侧光 | 高光停留在可读区域，不必用 Emissive 烘死；局部补光不污染漫反射 | 真实 GGX 在规定镜头中持续丢失关键高光，且 Mask/Roughness 调整不足 | B |
| 《终末地》 | 晴/雨双粗糙度、动态雨痕法线、水位湿度与 MatCap 水光 | 湿润同时改变法线、粗糙度和高光，避免全角色统一“刷油” | 项目存在可玩雨天、涉水或湿身状态，并有明确切换与性能预算 | B |
| 《终末地》 | 发根到发梢 Tangent/Flow 数据 + 主次双层方向性高光 | 用较低成本获得稳定、可染色的发丝光带和次级高光 | 单层 Anisotropy 无法覆盖长发、前后发或彩色次高光 | B |
| 《终末地》 | SH 环境光进入 HSV 后限制冷色/暗部饱和度 | 保留环境融合，同时防止角色暗部被彩色环境光染脏 | 中性材质与固定曝光正确后，角色仍在多场景中系统性偏灰或偏色 | B |
| 《绝区零》 | 区域 Mask 阈值选择多组描边颜色，并在 Substance Painter 提供运行时近似预览 | 美术所见即所得，描边颜色可随皮肤、头发、衣物变化 | 描边进入当前选型；先复用 MaterialID，不新增重复 Mask | A |
| 《绝区零》 | Instancing-only 变体与实例参数数组 | 减少重复 Shader 变体和状态切换，统一批量绘制路径 | Shader permutation/PSO 或 CPU Draw 成为量化瓶颈，且资产适合实例化 | B |
| 《绝区零》 | CSM 分层分帧更新 | 将远级阴影更新摊到多帧，降低阴影峰值成本 | 仅用于非 VSM 平台路径；快速光照和镜头运动下必须验证时间差 | C |
| 《绝区零》 | 语义复用 GBuffer：场景与角色在同一 RT 使用不同通道解释 | 减少 RT 数量和带宽 | 原生 Blendable GBuffer 经测量成为硬瓶颈；需要引擎改动并证明维护收益 | C |
| 《绝区零》 | 双摄 Deferred Planar Reflection | 平面反射比 SSR 更完整、稳定 | 只用于关键平面且反射不可被 Lumen/SSR/探针满足；必须有独立 GPU 预算 | C |
| 《绝区零》 | Bloom 多级结果打入 Atlas，以 Instancing 合并降/升采样 | 减少 RT 切换和部分 Draw；多级 Bloom 时可能提速 | Render Target 切换是实测瓶颈；必须同时测带宽、ALU、Padding 和串色 | C |
| 《白银之城》 | VSM 与角色常规阴影分通道打包到共享载体 | 保留场景 VSM，同时为角色提供稳定可控的补充阴影 | 独立 Shadow Proxy 已通过画面验证，且通道打包能实际节省带宽/RT | B |
| 《白银之城》 | 按 Shading Model/Material ID 分支解释 CustomData | 同一辅助纹理支持皮肤、头发、Coat、边缘光等不同数据 | 辅助数据种类超过独立 Mask 预算；必须建立固定解码表和 Debug View | B |
| 《白银之城》 | 透明层使用剩余透射率；双通道差值编码畸变向量 | 分离层颜色、背景透射和折射偏移，适合玻璃、热扰动和魔法材质 | 项目需要可排序的角色透明/折射层，原生 Translucency 无法满足 | B |
| 《白银之城》 | FFT 卷积 Bloom | 对超大半径和指定 PSF/星芒核的成本更稳定、形状更可控 | 美术明确要求普通 Bloom 无法生成的核形状，并完成分辨率/GPU A/B | C |
| 近期实战 / UE 5.8 | Texture Graph 作为离线遮罩清洗与通道打包器 | 把去灰底、阈值、形态学处理和变体生成移出运行时材质，降低重复采样与 ALU | 只把导出的普通纹理带入 Cook；运行时不依赖仍为 Experimental 的 Texture Graph | A |
| 近期实战 | `SceneTexelSize` 驱动的深度 + 法线 + ID 后期描边 | 线宽随分辨率稳定；深度负责外轮廓，法线/ID 补内部结构，可选择性套用 Stencil | 场景物件或 VFX 也需要描边，且 inverse-hull 无法覆盖；必须测采样数和动态分辨率 | A |
| 近期实战 | 多采样 SceneColor 径向折射模糊，叠加 Interleaved Gradient Noise 与 RGB 权重 | 低样本下获得冲击波、传送门和爆炸透镜的模糊、扰动与色散 | 关键特效明确需要屏幕扭曲；限制覆盖率/采样数，并验证半透明排序、TSR 和动态分辨率 | B |
| 半透明时装复现（非官方） | 资产阶段拆分不透明内衬、半透明外层和独立装饰，并固定层级顺序 | 把难解的逐三角透明排序问题改成可控的 Mesh/Pass 顺序，近景裙纱更稳定 | 服装存在大包围或多层透明；先用资产拆分解决，仍不足时才考虑 OIT/定制透明管线 | A |
| UE 5.8 | Stateless/Lightweight Emitter + Niagara Effect Type 预算曲线 | 消除大量 Tick/编译/粒子状态成本，并按距离、重要度、实例数和全局预算自动降级 | 环境尘埃、火花、落叶等效果不依赖自定义模块或逐粒子持久状态 | A |
| UE 5.6+（Experimental） | Texture Collections + Bindless 索引采样 | 在同一材质中动态选择大批纹理，适合换装、贴花库和 VFX Flipbook 家族 | 平台 Bindless 路径稳定，且实测能减少排列/绑定成本；否则继续用数组或普通参数 | C |

优先级含义：A 为当前主线成熟后应安排的最小研究；B 只在对应画面需求或硬阻塞出现时验证；C 为高维护或
平台相关方案，默认不做。A 也不是实施承诺，仍需遵守“原生能力先验证、一个当前生产路径”的约束。

### 制作规范与工程技巧（非技术候选）

这些内容不作为 trick 或新技术，只在现有材质和 Niagara 工作流中按需复用：

- `NormalizedAge` + `DynamicParameter` 四通道只是 VFX 参数与母材质复用规范，不是新技术；三个以上同类效果共享生命周期语义时再统一。
- RenderDoc + `Saved/ShaderSymbols` 适合缩短 Shader 原型迭代；最终修改仍回写源码并走正常编译、Cook 和目标平台验证。

### 备选项依据

- [终末地—渲染学习](https://zhuanlan.zhihu.com/p/2013370672647268314)
- [《终末地》阴影构造复刻](https://zhuanlan.zhihu.com/p/2008887309844640748)
- [《终末地》风格化 PBR 管线复刻](https://zhuanlan.zhihu.com/p/2012135042818778255)
- [《终末地》Custom Marschner 头发高光复刻](https://zhuanlan.zhihu.com/p/2065173774345955215)
- [米哈游 ZZZ 绝区零渲染细节新发现](https://zhuanlan.zhihu.com/p/672289040)
- [绝区零角色渲染逆向](https://zhuanlan.zhihu.com/p/620637822)
- [复刻绝区零/原神的 Bloom 效果](https://zhuanlan.zhihu.com/p/675125241)
- [白银之城—渲染概览](https://zhuanlan.zhihu.com/p/2063768280813265644)
- [UE5 Niagara 特效纹理：材质节点与 Texture Graph 清理非纯黑背景](https://zhuanlan.zhihu.com/p/1995832328275133732)
- [UE5 Niagara 屏幕空间径向模糊与折射材质函数](https://zhuanlan.zhihu.com/p/1982810651450701394)
- [UE5 后期描边 Shader 的原理与实现](https://zhuanlan.zhihu.com/p/2012914677433259718)
- [从零玩转 UE5 Niagara 爆炸特效：九种分层变体](https://zhuanlan.zhihu.com/p/1992516570396787716)
- [Niagara 轻量发射器及粒子系统轻量化优化](https://zhuanlan.zhihu.com/p/1920944533576857554)
- [高级半透明时装渲染流程复现](https://zhuanlan.zhihu.com/p/29093087845)
- [Unreal Engine Shader 开发技巧](https://zhuanlan.zhihu.com/p/650248246)

## 7. 永久约束

- 不用一个 Toon Profile 控制整个角色。
- 不用 `BaseColor × 常量 → Emissive` 抬暗部。
- 不把 AO、Contact、Ramp 和 Cast Shadow 一起乘最终颜色。
- 不用 Unlit 重写整套假光照。
- 不用 LUT、Bloom 或 Sharpen 掩盖材质、阴影和 Mip 问题。
- 不用同一张随机 Detail Normal 表示所有非金属，也不用法线贴图代替厚度、叠片和轮廓结构。
- 不在原生 Toon 未出现硬阻塞前复制 Renderer 或维护第二条生产路径。

## 8. 依据

- [UE 5.8 Toon Profile](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/ToonProfileStruct)
- [UE 5.8 Substrate Toon BSDF](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/UMaterialExpressionSubstrateToon-?lang=en-US)
- [UE 5.8 Substrate Materials Overview](https://dev.epicgames.com/documentation/en-us/unreal-engine/overview-of-substrate-materials-in-unreal-engine)
- [Physically Based Shading at Disney](https://disneyanimation.com/publications/physically-based-shading-at-disney/)
- [MERL Measured BRDF Database](https://www.merl.com/research/downloads/BRDF)
- [NVIDIA vMaterials](https://developer.nvidia.com/vmaterials)
- [Leather Surface Morphology Study](https://pmc.ncbi.nlm.nih.gov/articles/PMC8541137/)
- [Leather Coating Roughness and Gloss Study](https://www.mdpi.com/2079-6412/10/5/494)
- [FHWA Retroreflectivity Definition](https://www.fhwa.dot.gov/publications/research/safety/07042/chapter1.cfm)
- [MaterialSeg3D](https://materialseg3d.github.io/)
- [SAM 3](https://github.com/facebookresearch/sam3)
- [SAMesh](https://github.com/gtangg12/samesh)
- [Material Anything](https://github.com/3DTopia/MaterialAnything)
- [Substance Sampler Image to Material](https://experienceleague.adobe.com/en/docs/substance-3d-sampler/using/filters/tools/image-to-material)
