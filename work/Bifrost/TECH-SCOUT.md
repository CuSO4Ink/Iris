# Bifrost · TECH-SCOUT（技术候选池 / 宝藏池）

> [!IMPORTANT] **定位**：四条标准找的**全部**候选牌都在这里——Part A（北欧海岸对口）· Part B（脱开场景的通用宝藏）· Part C（新场景概念草稿）· Part D/E（近两年前沿 + 研究向）· 备选总表 · 文末岔路。供技术选型与**重设方向**用。
> **已锁的只是「当前北欧海岸线」内部的选择**：D1=等离子恒星驱动天气、D2=冷神性、⑤前景剪影机位（见 `CONCEPT.md` / `LOG.md`）。
> **但「深耕北欧海岸 vs 跳新场景（Part C）vs 围前沿重设一个场景 vs 开研究向支线」仍是未拍板的开放岔路**——见文末「抛回给人的岔路」。这几条用户从未拍板，AI 不替选。
>
> **2026-07-06 候选池状态更新**（约束松绑后的去留裁定）：
> - **已毙**：~~B1 黏菌~~（用户审美硬否决：阴湿活物恶心感）、~~D1 Radiance Cascades~~（Lumen 珠玉在前）。
> - **铁磁流体 B2 复活**：用户澄清铁磁流体≠黏菌（金属矿物质感，非阴湿活物），解除气质警报；**降级为点缀**（不当主海面，用户已复刻 FluidFlux），融视觉不融物理挂 FluidFlux，见 `PIPELINE.md` §4。
> - **分色三选一未拍板**：B8/A7/A5 同类效果最多留 1 个，防彩虹过载。
> - **B4 放电**仍存疑（躁动 vs 肃穆情绪对冲）；**B6 反应扩散**仍存疑（观众难辨，值不值问题）。
> - **E1 Work Graphs** 质疑（成片零视觉加成）；**E2-E5 / D5-D6** 研究向/复选框化牌暂搁。

---

## Part A · 已探索宝藏（前几轮，对口"北欧巨构海岸"场景）

这批是围着 Bifrost 原场景（巨构海岸 + 近距恒星 + 极地天象）找的，出处都硬、能自实现。

| # | 技术 | 出处 | 能造 | 独占 | 惊艳 | R&D | 备注 |
|---|---|---|---|---|---|---|---|
| A1 | 恒星表面：翻涌等离子 + 日珥弧 + 日冕 | 开源 `stellar-renderer-3d` + 太阳物理 | ★★★ | ★★★ | ★★★ | ★ | 把"发光球"升级成情绪主角；已进 CONCEPT §2 |
| A2 | 极光真·体积渲染 | Lawlor & Genetti《Interactive Volume Rendering Aurora on the GPU》(2010) | ★★ | ★★★ | ★★★ | ★★★ | 沿磁力线电子沉降 + 大气密度解析积分 + 发射光谱分层；论文偏老需现代化移植 |
| A3 | 体素体积云 / 贝母云 | Nubis（地平线）+ 宾大 Meteoros + Maxime Heckel | ★★★ | ★★ | ★★ | ★ | 最稳的底；贝母云=极地限定结构色 |
| A4 | 相对论引力透镜（若天体设为致密星） | Bruneton《Real-time High-Quality Black Hole》(arXiv 2010.08735) | ★★ | ★★★ | ★★★ | ★★★ | 王炸但改叙事基调（神性→吞噬） |
| A5 | 冰晶大气光学：光柱 / 幻日 / 22°晕 | atoptics 冰晶光学 | ★★ | ★★★ | ★★ | ★★ | 极地夜真实存在，实时里几乎空白 |
| A6 | 水下光谱 + 体积焦散 | 2024《Real-Time Underwater Spectral Rendering》(CGF) | ★★ | ★★ | ★★ | ★★ | 按波长衰减的焦散网 |
| A7 | 色散折射（冰棱 / 盐晶分光） | 实时 iridescence / thin-film | ★★ | ★★ | ★★ | ★ | 小而精点缀 |

**两条自研管线（收敛叙事骨架）：**

- **管线 A —「天空是一个体积场」**：一套 raymarching 框架喂多种发射/散射介质（极光 · 体积云 · 恒星日冕日珥 · 体积光柱 · 星云）。breakdown 一句话：*"一套自研体积管线，点亮了整片天空的每一种光。"*
- **管线 B —「光是有波长的」**：一套光谱光传输串起所有分色奇观（贝母云/冰晶结构色 · 冰棱色散 · 水下光谱焦散 · 引力红移）。breakdown 一句话：*"从冰到水到天体，光在这片海岸上一路被分解成光谱。"*

> [!NOTE] Part A 的现状：CONCEPT.md 里 D1/D2 已锁「等离子恒星 + 冷神性」。A1 已落地为内核。A2–A7 属"若要加料"的候选池，尚未进内核名额。

---

## Part B · 本轮新捞（脱开场景基调，自由撒网）

这批**完全不管北欧/海岸**，纯按四条标准找的通用宝藏。全部有开源实时实现或论文，验证过"能亲手造"。

| # | 技术 | 出处（可落地） | 能造 | 独占 | 惊艳 | R&D | 一句话为什么是牌 |
|---|---|---|---|---|---|---|---|
| **B1** | ~~**Physarum 黏菌自组织网络**~~ | Jeff Jones 2010 + SebLague/Slime-Simulation + 一堆 WebGPU 10M-agent 实现 | ★★★ | ★★★ | ★★★ | ★★ | ❌ **已否决（2026-07-06）**：用户审美硬否决——阴湿活物恶心感，只调得出恶心效果。 |
| **B2** | **铁磁流体 ferrofluid（磁场尖刺）** | SIGGRAPH 2019 Huang + 2024 IoB 磁静解算器 + UE5 原型 | ★★ | ★★★ | ★★★ | ★★★ | ✅ **复活为点缀（2026-07-06）**：用户澄清铁磁流体≠黏菌（金属矿物质感非阴湿活物）。降级为点缀——用户已复刻 FluidFlux 当主海面，铁磁流体融视觉不融物理挂 FluidFlux（材质①+局部Niagara②），见 `PIPELINE.md` §4。保留恒星磁场→海面尖刺因果链。 |
| **B3** | **分形 SDF 建筑（Kleinian/Mandelbox/Menger）** | 一堆 raymarching 实现 + GMT/GMT-fractals 实时探索器 | ★★★ | ★★ | ★★★ | ★★ | 无限自相似的异星巨构，可穿行、可无限缩放。分形本身是红海，但**"当成可探索的建筑空间 + 现代 PBR 光照 + 体积雾"少见**，天生自带"渺小人 vs 宏大"压迫感。 |
| **B4** | **Lichtenberg / 介电击穿分支放电** | DBM 模型 + 迭代解拉普拉斯方程（epa058 / iris.joshua-becker 开源） | ★★★ | ★★★ | ★★ | ★★ | 分支放电结构**真按物理生长**（∇φ^η 概率选点），不是贴图/噪声糊的闪电。能量沿网络脉冲流动，独占度高。 |
| **B5** | **大规模 murmuration / boids** | Reynolds 1986 + Rama Karl GPU flock + WebGPU 百万个体 | ★★★ | ★★ | ★★★ | ★ | GPU compute 十万~百万个体涌现，成群飞鸟/鱼/孢子在空中拧成流动的形状。**动态生命层**，最省事的一张（风险最低）。 |
| **B6** | **反应扩散 / 图灵斑纹（Gray-Scott）** | Turing 1952 + 一堆 WebGPU ping-pong 实现 | ★★★ | ★★ | ★★ | ★ | 材质表面**实时生长**有机纹路/腐蚀/结晶。适合当"活的材质层"，让墙面/皮肤/珊瑚在镜头里缓慢演化。 |
| **B7** | **Chladni / cymatics 声波驻波** | 阻尼板 PDE + 沙粒沉积到节点线（cymatics-labs 等） | ★★ | ★★★ | ★★ | ★★ | 声音把沙/盐塑成几何图案。独占且冷门，但偏装置/抽象，当场景主体难，当"可交互奇观"强。 |
| **B8** | **色散 / 双折射宝石（光谱 path tracing）** | Ray Tracing Gems II + piellardj diamond-webgl | ★★ | ★★ | ★★ | ★★ | 宝石内部真·光谱色散 + 双折射双像。偏离线 path tracing，实时较重，适合近景 hero 单体。 |
| **B9** | **Granular 沙/雪（MPM / PBD）** | GPUMPM (kuiwuchn) + PBD snow globe + taichi_elements | ★★ | ★★ | ★★ | ★★ | 沙/雪真堆积、真形变、留脚印。可信度层，独占度中，模拟偏重。 |

> [!NOTE] 落选说明：程序化苔藓/风化那类搜下来全是 UE 插件商品，掉回"底座"档（开开关就有、不独占），不进池。

**本轮的判断（一句话）：** B 池里**天花板最高的是 B1 黏菌 + B2 铁磁流体 + B3 分形建筑**——三个都是"活着的 / 自组织的 / 无限的"这一路，独占度顶格；B5 boids 是最低风险的"哇"点；B4 Lichtenberg 是最好的"连接/脉冲"胶水。它们能咬合成同一个母题：**一座活着的、自组织的非人造建筑**。

---

## Part C · 顺手草拟的新场景概念（候选，未拍板）

用户放开了"可以直接按新技术重设场景"。下面是**两个和北欧海岸毫无关系**的方向草稿，纯脑暴，供挑或推翻。都遵守老约束：**风格化 > 写实、渺小人视角的压迫性宏大、内核尽量收敛成 1 套自研管线**。

### 概念 C1 —「活体神殿 / The Living Cathedral」

一座**不是被建造、而是被生长出来**的巨型异星神殿内部。

- **骨架（B3 分形 SDF）**：Kleinian/Mandelbox 无限回廊，镜头穿行时空间自相似地向内塌陷，渺小的人站在其中。
- **灵魂（B1 黏菌）**：墙体表面 / 空腔里爬满黏菌自组织网络，像活着的血管/神经，实时生长、连接建筑的节点、找最短路——**它是这座建筑的"神经系统"**。
- **脉冲（B4 Lichtenberg）**：能量沿黏菌网络以分支放电的形式**脉冲流动**，网络亮起的瞬间就是神殿"苏醒"的心跳。
- **活材质（B6 反应扩散）**：墙面纹路在镜头前缓慢结晶/生长，暗示整座建筑还在长。
- **一句话 breakdown**：*"这座建筑没有一块是建模摆放的——它由一套 GPU compute 自组织管线长出来，并且还在长。"*
- **收敛**：B1/B4/B6 全跑在 GPU compute + ping-pong 上，B3 是 raymarching 骨架，**一套 compute/raymarch 混合管线驱动全场**。独占度顶格，同行复刻不了。R&D：中偏高（黏菌 3D 化 + 与 SDF 空间耦合是真活儿）。

### 概念 C2 —「磁之潮汐 / Ferrofluid Tide」

一片悬浮在磁场里的**黑色液态金属海**，被一个不可见的磁源牵引。

- **主角（B2 铁磁流体）**：整片海面是铁磁流体，随磁场起伏成尖刺阵列、拉出液桥、攀爬悬浮的金属环——**hero 就是这团会自组织成尖刺的黑液**。
- **生命（B5 murmuration）**：磁场里成群的发光粒子/金属屑像鸟群一样涌动，勾勒出磁力线的形状。
- **分色（B8 色散）**：黑液表面薄膜干涉出油膜彩虹，尖刺尖端像宝石一样分光。
- **一句话 breakdown**：*"整片海是一次实时铁磁流体模拟，磁场一动，海就长出刺。"*
- **收敛**：B2 是重头（模拟核心），B5/B8 是氛围与质感搭头。独占度顶格（实时 demo 几乎无人做铁磁流体），**但 R&D 最厚**——这是"最惊艳也最冒险"的一张。

### 概念 C3（最省事保底）—「涌动之空 / Murmuration Sky」

如果不想吃 R&D：纯押 **B5 murmuration** 做主角，百万个体在巨构剪影间涌成流动雕塑，配 B4 分支放电当高潮脉冲。惊艳、低风险、能造，但独占度不如 C1/C2。

---

## Part D · 真·近两年前沿（2023–2025，回应"论文太老"的批评）

> 上一轮 Part A/B 里不少是**老算法（图灵1952 / Reynolds1986 / 极光2010 / DBM）套近两年开源实现**——内核旧，独占靠"没人在实时里做"。这轮专挖 **2023–2025 的真前沿**。
> **但先点破一个分野**：近两年前沿大半在往两个方向跑——① 被引擎收编成复选框（神经材质、ReSTIR 正在变成 NVIDIA/UE 的开关，掉回"底座"档，TA-flex 价值反而低）；② 需要 ML 训练管线（不是纯手艺）。**能同时"够新 + 能亲手造 + 还没变成复选框"的甜点区很窄**，下面按这个甜点区排。

| #      | 技术                                                        | 年份/出处                                                                                        | 能造  | 独占  | 惊艳  | R&D | 甜点区判断                                                                                                   |
| ------ | --------------------------------------------------------- | -------------------------------------------------------------------------------------------- | --- | --- | --- | --- | ------------------------------------------------------------------------------------------------------- |
| ~~**D1**~~ | ~~**Radiance Cascades（无噪实时 GI）**~~ | 2024, Sannikov《流放之路2》 | — | — | — | — | ❌ **已否决（2026-07-06，本人拍板）**：UE5.8 自带 Lumen（追踪+缓存+降噪 GI）在旁，自实现 RC 画面赢不过 Epic 打磨的 Lumen，flex 只剩"算法深度理解"、在 Lumen 珠玉前叙事站不住，性价比低。注：Lumen 用的是 Radiance **Cache**（辐射缓存）非 Radiance **Cascades**，二者不同技术；独占性虽成立仍毙。见 `LOG.md`。 |
| **D2** | **Flow Map 实时涡旋流体（Leapfrog / Vortex Particle Flow Maps）** | SIGGRAPH 2025, yuchen-sun-cg/lfm（开源）、Cirrus、vpfm.sinanw.com                                  | ★★  | ★★★ | ★★★ | ★★★ | **真·2025 前沿**，替掉 Part A 里那些老流体。实时保住丰富涡旋的烟/火/水，独占度顶格；代价是 GPU 重、移植吃力。                                     |
| **D3** | **风格化高斯溅射当 VFX 媒介**                                       | 2024–2025, G-Style 风格化 splatting (CGF)；keijiro/SplatVFX；NanoGS / GSX Shadows (UE5)           | ★★  | ★★★ | ★★  | ★★  | 把 GS **从"扫描现实"扭成"艺术媒介"**——风格化体积点云做特效，几乎没人在艺术向这么用。新美学，独占靠"没人往这想"。                                        |
| D4     | 混合 ReSTIR 次表面散射（实时 SSS）                                   | SIGGRAPH 2025 talk（path trace + diffusion profile 混合）                                        | ★★  | ★★  | ★★  | ★★★ | 玉石/蜡/皮肤的电影级实时透光。窄但精，适合近景 hero 单体。                                                                       |
| D5     | 神经外观模型 / RTX 神经材质                                         | 2024, NVIDIA（arXiv 2305.02678）；SIGGRAPH 2025 Neural Shading 课 (Slang)                        | ★   | ★   | ★★  | ★★★ | ⚠️**正在变引擎复选框 + 要 ML 管线**。列出来是让你知道它存在，但按你的标准（手艺 flex）性价比低，**归"半底座"**。                                    |
| D6     | ReSTIR GI / PT Enhanced / ReSTIR-PG                       | 2024–2025, NVIDIA RTR                                                                        | ★   | ★   | ★★  | ★★★ | ⚠️同上，重基建、在被 RTXDI 收编。"我集成了"而非"我造了"，flex 价值低。                                                            |

**Part D 的一句话判断：** ~~真前沿里真正踩中你甜点区的只有 D1 Radiance Cascades（首推）+ D2 Flow Map 流体 + D3 风格化 GS 这三张~~ → **D1 已否决（2026-07-06，Lumen 珠玉在前，见上表）**。Part D 内剩 **D2 Flow Map 流体 + D3 风格化 GS**；D4 是精致窄口；D5/D6 已滑向"底座/基建"，不建议押。**甜点区首选转向 E1 GPU Work Graphs / B1 黏菌 / B3 分形建筑（见备选总表梯队①）。**

---

## Part E · 最后一轮补搜（神经渲染 + 3DGS「研究向」层）

> 用户放话：**神经渲染 / 3DGS 可以当"超级前沿研究向"来试——做出来是顶格加分，做不出也完全没关系。** 所以这一档单列为 **R&D 高、独占极高、成不成两可** 的"冲高选项"，不占主线保底名额。
> 判断口径同前四条，但**额外标注「研究向 vs 可落地」**：可落地=有开源引擎实现能直接改；研究向=多在 arXiv/训练管线，实时化/艺术化要你自己趟。

| # | 技术 | 年份/出处 | 能造 | 独占 | 惊艳 | R&D | 定位 |
|---|---|---|---|---|---|---|---|
| **E1** | **GPU Work Graphs · 全 GPU 驱动程序化世界** | 2024, DX12 新特性；CGF《Real-Time Procedural Generation with GPU Work Graphs》(Kuth 2024)；AMD GPUOpen WorkGraphPlayground / Mesh Nodes 示例（开源可跑） | ★★★ | ★★★ | ★★ | ★★ | ✅**可落地·真·新硬件特性（2024.3 才发布）。** shader 自己动态调度 shader，整个世界每帧全在 GPU 上程序化生成+渲染。**几乎没人拿它做艺术向 demo**，"我用 Work Graphs 让整个场景在 GPU 里自己长出来"是极硬的 TA flex。甜点区新成员，强烈建议纳入正式候选。 |
| **E2** | **Neural Radiance Cache（实时神经辐照缓存）** | NVIDIA NRC；SIGGRAPH Asia 2025《NRC on Mobile GPU》；NL-NRC（SIGGRAPH 2025，紧凑网络存辐射场） | ★★ | ★★ | ★★ | ★★★ | ⚠️研究向。小 MLP 在线训练缓存 GI，无噪且省。够新但**要 ML 在线训练管线 + 正被 NVIDIA 收编**，flex 偏"我集成"。当"研究向冲高"可，当主线不划算。 |
| **E3** | **虚拟化 3DGS · Nanite 式 LOD（Virtualized Gaussians）** | SIGGRAPH 2025《Virtualized 3D Gaussians: cluster-based LOD》 | ★★ | ★★★ | ★★ | ★★★ | 🔬研究向。给高斯点云做 Nanite 式集群 LOD，超大场景实时。**顶格独占**（能自己撸出"高斯版 Nanite"是炸裂 flex），但工程量巨大，纯冲高。 |
| **E4** | **可重光照 / PBR 高斯溅射** | LumiGauss (WACV 2025)、GaussianMaterial PBR (2025)、MatSpray、GTAvatar | ★★ | ★★ | ★★ | ★★★ | 🔬研究向。给高斯点云加 PBR 材质 + 可重光照，解决 GS"死在原光照里"的老毛病。让 GS 能进你自己的光照系统（呼应管线 A/D1）。研究热但实时艺术管线未成熟。 |
| **E5** | **4D / 生成式高斯（DreamGaussian 系）** | 4DGaussians (2024)、DreamGaussian / DreamGaussian4D、Text-to-3D GS (CVPR 2024) | ★★ | ★★ | ★★★ | ★★★ | 🔬研究向·最"魔法"。文字/单图→动态 4D 高斯资产，会动会变形。**当"生成式媒介"用极惊艳**，但生成质量不可控、实时化难，是纯 R&D 赌注。 |

**Part E 的一句话判断：** 这一档里**唯一同时"够新+能亲手造+可落地+还没变复选框"的是 E1 GPU Work Graphs**——它其实该和 D1 一起进甜点区第一梯队。E2–E5（神经渲染 + 3DGS 研究向）按用户定调是**"冲高彩蛋"**：做出来独占顶格、breakdown 直接封神；做不出来也不伤主线，因为主线自有 D1/E1/B 池保底。**建议策略：主线押可落地的（D1/E1/B），另留一条研究向支线试 E3/E4/E5 之一，成了是惊喜，不成不亏。**

---

## 备选总表（全表汇总 · 按"可落地度 × 独占度"分梯队）

> 把 Part A~E 所有牌拉通排一次，方便一次看全。**梯队 = 落地把握**；★数沿用前表。此表只汇总，不替你拍板。

### 梯队 ① · 甜点区首选（够新 + 能亲手造 + 独占 + 风险可控）——**主线优先从这里挑**
| 牌 | 技术 | 一句话 | R&D |
|---|---|---|---|
| ~~**D1**~~ | ~~Radiance Cascades 无噪实时 GI~~ | ❌ **已否决**（2026-07-06）：UE5.8 自带 Lumen 在旁，自实现 RC 画面赢不过、flex 只剩"算法理解"，在 Lumen 珠玉前叙事站不住。见 LOG | — |
| **E1** | GPU Work Graphs 全 GPU 程序化世界 | 2024 真新硬件特性，几乎没人做艺术向，硬 flex | ★★ |
| **B1** | Physarum 黏菌自组织网络 | 百万 agent 长成"活运输网"，没人做成 3D 场景灵魂 | ★★ |
| **B3** | 分形 SDF 建筑 | 无限自相似异星巨构，天生"渺小 vs 宏大" | ★★ |

### 梯队 ② · 高独占但吃 R&D（冲最高天花板）
| 牌 | 技术 | 一句话 | R&D |
|---|---|---|---|
| **B2** | 铁磁流体磁场尖刺 | 实时几乎无人做，最惊艳也最冒险 | ★★★ |
| **D2** | Flow Map 涡旋流体 | 真 2025 前沿，实时保住丰富涡旋，GPU 重 | ★★★ |
| **A4** | 相对论引力透镜 | 王炸，但改叙事基调（神性→吞噬） | ★★★ |
| **A2** | 极光真·体积渲染 | 独占强，老论文需现代化移植 | ★★★ |

### 梯队 ③ · 稳出片保底（能造、惊艳、低风险）
| 牌 | 技术 | 一句话 | R&D |
|---|---|---|---|
| **B5** | 大规模 murmuration/boids | 最省事的"哇"点，动态生命层 | ★ |
| **B4** | Lichtenberg 分支放电 | 最好的"连接/脉冲"胶水 | ★★ |
| **B6** | 反应扩散图灵斑纹 | 活的材质层，缓慢演化 | ★ |
| **A1** | 等离子恒星表面 | 已进 CONCEPT，情绪主角 | ★ |
| **A3** | 体素体积云/贝母云 | 最稳的底 | ★ |

### 梯队 ④ · 精致窄口 / 点缀（近景 hero 或小料）
| 牌 | 技术 | 一句话 | R&D |
|---|---|---|---|
| **D3** | 风格化高斯当 VFX 媒介 | 把 GS 扭成艺术媒介，新美学 | ★★ |
| **D4** | 混合 ReSTIR 次表面散射 | 玉石/蜡/皮肤电影级透光 | ★★★ |
| **B8** | 色散/双折射宝石 | 近景 hero 单体分光 | ★★ |
| **A5–A7** | 冰晶光学 / 水下光谱 / 色散折射 | 极地限定的小而精点缀 | ★★ |
| **B7** | Chladni 声波驻波 | 冷门，当可交互装置强 | ★★ |
| **B9** | Granular 沙/雪 | 可信度层，模拟偏重 | ★★ |

### 梯队 ⑤ · 研究向"冲高彩蛋"（做出来封神，做不出不亏）
| 牌 | 技术 | 一句话 | R&D |
|---|---|---|---|
| **E3** | 虚拟化 3DGS（高斯版 Nanite） | 顶格独占，工程量巨大 | ★★★ |
| **E4** | 可重光照/PBR 高斯 | 让 GS 进自己的光照系统 | ★★★ |
| **E5** | 4D/生成式高斯 | 最"魔法"，质量不可控 | ★★★ |
| **E2** | Neural Radiance Cache | 够新但要 ML 管线、在被收编 | ★★★ |

### 梯队 ⑥ · 已滑向"底座/基建"（不建议当手艺亮点押）
| 牌 | 技术 | 为何降级 |
|---|---|---|
| **D5** | 神经材质/RTX 神经外观 | 正变引擎复选框 + 要 ML 管线 |
| **D6** | ReSTIR GI/PT | 被 RTXDI 收编，"我集成"非"我造" |

> [!NOTE] 全表可组合的三条母题（供参考，非拍板）：
> - **「一座活着的非人造建筑」**：E1/B3 骨架 + B1 神经 + B4 脉冲 + B6 活材质（= 概念 C1 活体神殿，独占顶格）。
> - **「一套自研体积/光管线点亮整片天空」**：D1 + A1/A2/A3 + 管线 A（北欧海岸主线，恒星已锁）。
> - **「研究向支线」**：主线之外单开一条，赌 E3/E4/E5 之一，成了是 breakdown 封神彩蛋。

---

## 抛回给人的岔路（AI 不替选）

1. **主线从哪个梯队挑**：甜点区首选（梯队①：D1 / E1 / B1 / B3）优先，还是要冲最高天花板吃厚 R&D（梯队②），还是稳出片保底（梯队③）？
2. **方向**：继续深耕北欧海岸（Part A，等离子恒星已锁），还是跳到 Part C 新场景（C1 活体神殿 / C2 磁之潮汐 / C3 涌动之空），还是**围着 D1/E1 这类前沿重设一个场景**？
3. **要不要开研究向支线**：主线之外单赌一条 E3/E4/E5（神经渲染/3DGS 研究向）——成了 breakdown 封神，不成不伤主线？（用户已定调"做不出也没关系"）
4. **要不要**我把选中的方向展开成正式 CONCEPT，并配提示词矩阵跑图？

> [!NOTE] 非拍板倾向（仅供参考）：
> - ~~单张最优解仍是 D1 Radiance Cascades~~ → **D1 已否决（2026-07-06，Lumen 珠玉在前）**。单张"既新+能亲手造+独占+风险可控"的最优解转为 **E1 GPU Work Graphs**（2024 真·新硬件特性、艺术向几乎空白）。
> - 研究向若要赌一张，**E4 可重光照高斯**最能和主线咬合（让 GS 进你自己的光照系统），比纯生成式的 E5 可控。

---

## 参考文章 / 链接（References）

> 按牌号列出每项技术的**可查出处**（论文原文 / 开源实现 / 走查博客）。链接都已联网核对可访问；少数无单一权威源的，给检索关键词而非编造 URL。

### Part A · 北欧海岸对口

- **A1 · 恒星表面（等离子/日珥/日冕）** — 无单一权威开源库；实时做法多为 FBM+域扭曲的"太阳表面"shader。检索：ShaderToy `"sun surface" / "solar corona"`；参考真实太阳物理影像 NASA SDO（<https://sdo.gsfc.nasa.gov/>）。
- **A2 · 极光真·体积渲染** — Lawlor & Genetti《Interactive Volume Rendering Aurora on the GPU》(2010)，论文 PDF：<https://www.cs.uaf.edu/~olawlor/papers/2010/aurora/lawlor_aurora_2010.pdf>
- **A3 · 体积云 / 贝母云** — Guerrilla《The Real-Time Volumetric Cloudscapes of Horizon Zero Dawn》(SIGGRAPH 2015，Nubis)；走查博客 Maxime Heckel：<https://blog.maximeheckel.com/posts/real-time-cloudscapes-with-volumetric-raymarching/>
- **A4 · 相对论引力透镜 / 黑洞** — Bruneton《Real-time High-Quality Rendering of Non-Rotating Black Holes》(arXiv 2010.08735)：<https://arxiv.org/abs/2010.08735>；开源实现 `ebruneton/black_hole_shader`：<https://github.com/ebruneton/black_hole_shader>
- **A5 · 冰晶大气光学（光柱/幻日/22°晕）** — Atmospheric Optics（Les Cowley）：<https://www.atoptics.co.uk/>
- **A6 · 水下光谱 + 体积焦散** — 《Real-Time Underwater Spectral Rendering》(Computer Graphics Forum, 2024)。检索标题即可命中 CGF/Wiley 与作者主页。
- **A7 · 色散折射 / 薄膜虹彩（iridescence）** — Belcour & Barla《A Practical Extension to Microfacet Theory for the Modeling of Varying Iridescence》(SIGGRAPH 2017)：<https://belcour.github.io/blog/research/publication/2017/05/01/brdf-thin-film.html>

### Part B · 通用宝藏

- **B1 · Physarum 黏菌网络** — Jeff Jones (2010) 原论文《Characteristics of Pattern Formation and Evolution in Approximations of Physarum Transport Networks》；Sage Jenson 走查：<https://cargocollective.com/sagejenson/physarum>；开源实现 `fogleman/physarum`：<https://github.com/fogleman/physarum>（另 Sebastian Lague《Slime Simulation》视频+源码）
- **B2 · 铁磁流体（磁场尖刺）** — Huang et al.《On the Accurate Large-scale Simulation of Ferrofluids》(SIGGRAPH 2019)：<https://computationalsciences.org/publications/huang-2019-ferrofluids.html>；后续《Surface-Only Ferrofluids》(SIGGRAPH Asia 2020)：<https://dl.acm.org/doi/10.1145/3414685.3417799>
- **B3 · 分形 SDF 建筑（Kleinian/Mandelbox/Menger）** — Mikael Hvidtfeldt Christensen《Distance Estimated 3D Fractals》系列（Syntopia）：<http://hvidtfeldts.net/>；实时探索器 GMT：<https://www.gmt-fractals.com/>
- **B4 · Lichtenberg / 介电击穿分支放电（DBM）** — 开源实现 `epa058/Lichtenberg-Figures`：<https://github.com/epa058/Lichtenberg-Figures>；交互 demo（Joshua Becker）：<https://iris.joshua-becker.com/lab/dielectric-breakdown-fractal/>
- **B5 · 大规模 murmuration / boids** — Craig Reynolds《Boids》原始页（含 1987 论文）：<https://www.red3d.com/cwr/boids/>
- **B6 · 反应扩散 / 图灵斑纹（Gray-Scott）** — Karl Sims《Reaction-Diffusion Tutorial》：<https://www.karlsims.com/rd.html>
- **B7 · Chladni / cymatics 声波驻波** — 阻尼板本征模 + 沙粒沉积到节点线。检索：`Chladni plate eigenmode simulation` / `cymatics WebGL`。
- **B8 · 色散 / 双折射宝石（光谱）** — 开源实时宝石渲染器 `piellardj/diamond-webgl`：<https://github.com/piellardj/diamond-webgl>（在线 demo：<https://piellardj.github.io/diamond-webgl/>）；理论见《Ray Tracing Gems II》(NVIDIA 免费开放)
- **B9 · Granular 沙/雪（MPM / PBD）** — `taichi-dev/taichi_elements`（MPM）：<https://github.com/taichi-dev/taichi_elements>；`kuiwuchn/GPUMPM`：<https://github.com/kuiwuchn/GPUMPM>

### Part D · 近两年前沿（2023–2025）

- **D1 · Radiance Cascades（无噪实时 GI）** — Alexander Sannikov 原始论文（预印本）：<https://radiance.wiki/papers/sannikov-original>；知识站 radiance.wiki：<https://radiance.wiki/>；走查 jason.today：<https://jason.today/rc>；tmpvar 交互解释：<https://tmpvar.com/poc/radiance-cascades/>
  > [!NOTE] 表内标注的 **arXiv 2408.14425** 实为**天体物理同名论文**（Osborne 等《…Non-LTE Radiative Transfer》），与游戏 GI 的 Radiance Cascades **同名不同物**，勿混引。GI 侧另有 arXiv 2505.02041《Holographic Radiance Cascades》可参。
- **D2 · Flow Map 实时涡旋流体** — 《Fluid Simulation on Vortex Particle Flow Maps》(VPFM, TOG/SIGGRAPH 2025)：<https://arxiv.org/abs/2505.21946>；开源 `pfm-gatech/VPFM`：<https://github.com/pfm-gatech/VPFM>；项目页：<https://vpfm.sinanw.com/>；另《Leapfrog Flow Maps for Real-Time Fluid Simulation》(SIGGRAPH 2025) 同组。
- **D3 · 风格化高斯溅射当 VFX 媒介** — `keijiro/SplatVFX`（Unity VFX Graph 实验实现）：<https://github.com/keijiro/SplatVFX>；美学向另见 G-Style stylized splatting (CGF 2024/25)。
- **D4 · 混合 ReSTIR 次表面散射（实时 SSS）** — SIGGRAPH 2025 talk（path trace + diffusion profile 混合）。基础见 ReSTIR 系列（Bitterli et al. 2020）。
- **D5 · 神经外观模型 / RTX 神经材质** — NVIDIA《Real-Time Neural Appearance Models》(arXiv 2305.02678)：<https://arxiv.org/abs/2305.02678>；项目页：<https://research.nvidia.com/labs/rtr/neural_appearance_models/>
- **D6 · ReSTIR GI / PT** — NVIDIA ReSTIR GI（Ouyang et al. 2021）及后续 RTXDI 收编，检索 `ReSTIR GI NVIDIA`。

### Part E · 神经渲染 + 3DGS 研究向

- **E1 · GPU Work Graphs · 全 GPU 程序化世界** — 论文《Real-Time Procedural Generation with GPU Work Graphs》(Kuth et al., HPG 2024)：<https://dl.acm.org/doi/10.1145/3675376>（项目页：<https://coburggraphicslab.github.io/publication/Kuth24RPG.html>）；AMD GPUOpen `WorkGraphPlayground`（开源可跑）：<https://github.com/GPUOpen-LibrariesAndSDKs/WorkGraphPlayground>
- **E2 · Neural Radiance Cache** — NVIDIA《Real-time Neural Radiance Caching for Path Tracing》(SIGGRAPH 2021, arXiv 2106.12372)：<https://research.nvidia.com/publication/2021-06_real-time-neural-radiance-caching-path-tracing>
- **E3 · 虚拟化 3DGS · Nanite 式 LOD** — 《Virtualized 3D Gaussians (V3DG)》(SIGGRAPH 2025, arXiv 2505.06523)：<https://arxiv.org/abs/2505.06523>；项目页：<https://xijie-yang.github.io/V3DG/>；开源 `city-super/V3DG`：<https://github.com/city-super/V3DG>
- **E4 · 可重光照 / PBR 高斯溅射** — 《LumiGauss: Relightable Gaussian Splatting in the Wild》(WACV 2025)：<https://lumigauss.github.io/>；开源 `joaxkal/lumigauss`：<https://github.com/joaxkal/lumigauss>
- **E5 · 4D / 生成式高斯（DreamGaussian 系）** — DreamGaussian 项目页：<https://dreamgaussian.github.io/>；开源 `dreamgaussian/dreamgaussian`：<https://github.com/dreamgaussian/dreamgaussian>

> [!NOTE] 说明：以上为**出处/学习入口**，非"照抄即用"清单。多数是论文/走查，实时化与艺术化仍需自行趟（尤其 Part E 研究向）。链接失效时按标题+作者检索通常仍可命中。
