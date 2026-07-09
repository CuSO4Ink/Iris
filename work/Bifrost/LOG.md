# Bifrost · LOG

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

### 2026-07-02 11:34 — [决策] 立项 Bifrost，作为 AIEffectFoundry 方向3 首个 diorama 实例
北欧神话 + 宏大奇幻 + 巨构瑰丽基调的海岸 diorama。独立成项目方便专注推进技术拆分，但定位为"方向3的落地样本"，不作作品集主场景，避免海岸题材绑架整体作品集叙事。

### 2026-07-02 11:34 — [决策] 风格化 > 写实
选风格化巨构而非照片级真实海岸：写实海岸是红海且 AI 生成材质泛滥，难证明人的审美价值；风格化高度依赖 Art Direction 决策，正好凸显 Human-in-the-loop 里"人不可替代"的一环。

### 2026-07-02 11:34 — [决策] 三层职责分工 L1/L2/L3
L1 量产层交 AI/MCP（常规材质/资产/脚手架），L2 审美层由人主导（色彩/比例/光影/构图/调色），L3 前沿内核由人做且只做 1 个奇观焦点，避免摊大做不深。内核视为可复用能力，服务视觉表达而非被单场景绑定。

### 2026-07-02 14:38 — [回滚] 撤销 AI 擅自具象化的效果/色彩候选
之前文档里 AI 自作主张把奇观焦点、色彩基调、内核技术都写成了具体候选清单（瀑布/巨浪/涡旋、青金石海水/极光冷调等），过早落地、越俎代庖。这些是 L2/L3 的 Art Direction 决策，属"人不可替代"的核心，AI 替选就砸了项目命题。

### 2026-07-02 14:38 — [决策] 立项前先完整落地设计理念与执行路径
正式开工前把文档体系化重构：三项 Art Direction 决策（奇观焦点/色彩基调/内核技术）全部收敛为「决策框架」——只列拍板时该权衡的维度，不预设候选、不替人选，灵感靠人自己沉淀 moodboard。执行路径拆成 L1/L2/L3 可执行任务清单，含依赖顺序与验收标准。就地重构三件套，保持轻量协作风格。

### 2026-07-02 17:10 — [决策] D2 色彩基调定为「冷神性」
经 CONCEPT.md 提示词矩阵多版出图对比（冷/暖/撞色），本人确认冷色调（冷白蓝巨星、肃穆神性光）比暖瑰丽、撞色张力更对味。D2 收口：冷神性。守住"瑰丽≠俗艳"红线，冷调下仍需控高光曝光避免生硬。D1（奇观焦点）尚未拍板，仍开放。

### 2026-07-02 19:45 — [决策] D1 奇观焦点定为「合成态：等离子恒星驱动天气」× 冷神性
在本人自己的生图工具上多轮验证后确认：一颗巨大冷白等离子恒星（翻涌熔融表面）同时是天气/风暴/god-rays 的驱动光源，二者不是二选一而是因果链合成态。内核 = 等离子恒星（复用 NS_Slime marching cubes），天气退化为其光学衍生效果，满足"内核只做1个"硬约束。D1/D2 两项 Art Direction 决策均已收口，锁定提示词见 CONCEPT.md §6。

### 2026-07-02 19:45 — [发现] AI 自建生图模型的诊断不可靠，不能据此判断提示词优劣
此前 AI 未经要求自行调用内部低质量生图模型，误诊断"恒星必须显式补强 metaball/isosurface 措辞才能读出融合质感"。本人在自己实际工具上验证：未经补强的原始简单措辞效果反而最好，最终定案版本用的就是原始写法。教训：不能用低质量代理模型的渲染结果反推提示词好坏，AI 后续只负责提示词文本，不再自行生图验证。

### 2026-07-02 21:20 — [否决] Bifröst 彩虹桥/能量桥作为场景视觉元素
D3 讨论中曾提出"恒星表面伸出触须并汇聚成 Bifröst 能量桥"作为更省成本的 dynamic mesh 应用点（细长弧形比巨星实体更适配 marching cubes 的成本模型）。本人否决：桥这个元素在当前巨构海岸环境下显得突兀。D1（等离子恒星驱动天气）不变；Bifröst 之名仅作项目命名寓意保留，场景内不出现具体桥体几何。D3（恒星本体的 dynamic mesh 实现路径）仍开放，回到"局部轮廓化 / 纯 shader 假体积 / 转真体积渲染"三个技术选项。

### 2026-07-06 19:32 — [决策] T-L2.2 主机位定为「⑤前景剪影环境镜」
CONCEPT.md §4 五机位提示词跑图对比后，确认前景人物剪影 + 背景恒星发光的构图最服务"渺小人视角的压迫性宏大感"。T-L2.2 完成。

### 2026-07-06 21:04 — [决策] Bifrost 升格为跨 P1+P3 垂直代表作
用户拍板：Bifrost 的搭建过程本身即"我调教的 UE5.8 MCP 提效工作流"要展示的作品，故上调身份——由"方向3落地样本、不作主场景"提升为跨 Part1(前沿内核)+Part3(MCP 量产流程)的垂直代表作，作 Portfolio Part3 的收录载体。守一条边界：内核仍是可复用能力、海岸题材不绑架整体作品集审美；升格的是收录地位，不是让它垄断叙事。已同步 AI-BRIEF 与 Portfolio 枢纽映射。

### 2026-07-06 21:04 — [发现] 版本基线三处打架，已统一到 UE5.8
巡检发现 AIEffectFoundry 三份文档仍写"UE5.5 主线出图、UE5.8 仅 preview"，与本项目 AI-BRIEF 的 UE5.8 基线及用户"调教的 UE5.8 MCP"实践冲突。经用户拍板，全部统一到 UE5.8 主线（早期 5.5 主线决策作废，切换点为 2026-07-02 本项目立项）。

### 2026-07-06 21:19 — [决策] 文档极致压缩 + TECH-SCOUT 全量归档
按当前主线（等离子恒星内核 + 冷神性 + ⑤前景剪影机位 + D3 展开中）压缩全套文档，删弱相关、归档过时，主线进度与决策记录零丢失：TECH-SCOUT 从 ~200 行精简为只留服务主线的加料牌（恒星质感/天象加料/冷神性 GI/高斯体积），Part B~E 五池 + 新场景概念 C1–C3 + 前沿研究向 + 备选总表全量归档至 `archive/TECH-SCOUT-full.md`（不删，供重设方向/开研究向支线时翻）；BACKLOG 的 D1/D2 已决策条目删划线权衡维度只留结论、D3 收敛为纯指针；CONCEPT §4 删掉重复机位代码块与工具操作长段，压成机位短语表（主机位⑤已定）。

### 2026-07-06 21:29 — [回滚] TECH-SCOUT 归档判断有误，已恢复为全量候选池
上一条把 Part B~E / 新场景 C1–C3 / 前沿研究向 / 备选总表 / 文末岔路问题当"过时"归档移出，属误判：D1/D2 只锁定了**当前北欧海岸线内部**的焦点与色彩，而"深耕北欧海岸 vs 跳新场景 vs 围前沿重设 vs 开研究向支线"（岔路第 2/3 问）用户**从未拍板**，归档等于替用户拍死"北欧海岸=终局"，违反 canary「AI 不替选」。已将全量恢复回 `TECH-SCOUT.md`（顶部说明改为"已锁只在北欧海岸线内部、重设方向仍开放"）并删除误建的 `archive/TECH-SCOUT-full.md`。BACKLOG（已决策条目去权衡维度、D3 收指针）与 CONCEPT §4（重复机位块清理、主机位⑤已定）的压缩为真压缩，保留不回滚。

### 2026-07-06 21:54 — [否决] D1 Radiance Cascades 作为前沿内核候选
本人拍板毙掉。理由：UE5.8 自带 Lumen（成熟的追踪+缓存+降噪 GI 方案）就在旁边，自实现 Radiance Cascades 画面上赢不过 Epic 团队打磨的 Lumen，flex 只能落在"算法深度理解"而非"画面吊打" —— 说服力弱、性价比低，作品集意义不大。注：已澄清 Lumen 用的是 Radiance Cache（辐射缓存），非 Radiance Cascades（Sannikov 2024 级联算法），二者不同技术；但即便独占性成立，在 Lumen 珠玉前叙事站不住，故毙。TECH-SCOUT 梯队①的 D1 划除，甜点区首选收窄到 E1 / B1 / B3。

### 2026-07-06 22:28 — [否决] B1 黏菌作为候选（用户审美硬否决）
本人审美硬否决。黏菌的雷是"阴湿活物感"——潮湿、蠕动、生物腐败的恶心。只调得出恶心效果，不论技术多独占都不做。

### 2026-07-06 23:35 — [回滚] B2 铁磁流体复活 + 降级为点缀
用户澄清铁磁流体≠黏菌：黏菌的雷是"阴湿活物感"（潮湿、蠕动、生物腐败），铁磁流体是"金属/矿物质感"的动态——冷硬的物理之美，非湿软的生物之丑。同样是动态自组织，材质气质天差地别。铁磁流体解除气质警报，复活进候选。同时降级：用户已复刻 FluidFlux 当主海面，铁磁流体不再当主海面（不当 C2 概念里整片黑液海），改为"融视觉不融物理"挂在 FluidFlux 上——材质层加磁尖刺 displacement/法线（弱）+ 恒星正下方局部 Niagara 强尖刺焦点。保住"恒星磁场牵引海面长刺"因果链，绕开 R&D ★★★ 磁-流耦合。成本从 10-15 天赌一把降到 3-5 天可控。见 `PIPELINE.md` §4。

### 2026-07-06 23:35 — [决策] "内核只做 1 个、做深不摊大"约束松绑
本人拍板松绑。改为"基底层（必做）+ 点缀层（独立模块增量挂载）"分层架构：基底完成即一张完整成片，点缀每个独立可插拔，挂几个算几个，失败不拖累主线。恒星仍是核心 hero，但不再是唯一允许的奇观。铁磁流体/极光/分色/沙雪/鸟群等全归点缀层。见 `PIPELINE.md` §1。

### 2026-07-06 23:35 — [决策] 恒星因果链定案 + 技术方案落地
恒星是整个场景的唯一因果源：恒星光→云散射（A3）、恒星磁场→极光（A2）、恒星磁场→海面尖刺（B2 融合）。天象与海面全是恒星的衍生，叙事自洽。技术方案：恒星=材质三层堆（本体+可选isosurface轮廓+光源）；天象=一套 raymarching 体积框架喂云+极光；铁磁流体=材质①+局部Niagara②挂 FluidFlux。场景布置=围主机位⑤优化+构图blockout先行+kitbash巨构。全套方案+MCP量产管线+人/AI边界+一个月周计划落 `PIPELINE.md`，原文存档 `PIPELINE-RAW.md`。同步更新 CONCEPT（§5 因果链）、BACKLOG（P0-P5+点缀层任务）、TECH-SCOUT（B1毙/B2复活降级）、AI-BRIEF。

### 2026-07-07 — [决策] D3 拍板 = A 方案·轮廓局部化，D3-KERNEL.md 从"待填骨架"改为落地记录
07-06 PIPELINE.md 早已按 A 方案（材质三层堆+边缘 isosurface）写恒星实现，但 D3-KERNEL.md 仍留骨架 + BACKLOG 显示"🚧 展开中/待选 A/B/C"，事实决策与文档记账脱节。本次审阅承认 D3 = A 方案：主体走假体积（B 方案共享底），边缘轮廓叠 marching cubes（A 方案独占身份）。B/C 否决理由：B 丢 marching cubes flex，C 换栈+砸 D1 定案。§0 硬约束"内核只做 1 个"同步作废（07-06 已松绑）。

### 2026-07-07 — [决策] 体积云从点缀升到基底
审阅发现宣传因果链 4 支（光→大气/云散射、磁场→极光/尖刺）但 W3 保底成片实交付只 1 支（光→大气散射），另 3 支全在点缀层，"叙事自洽"塌房。修正：体积云上移到基底层（W3 交付），保底成片保 2 支因果链闭合；磁场→极光、磁场→尖刺仍归点缀（W4 目标成片交付）。CONCEPT §4 明确交付分档标注。

### 2026-07-07 — [决策] 分色/铁磁流体优先级二义性收口
分色三选一定为"是否要做未拍板"（不再暗含"决定要做"）；铁磁流体的 ⭐ 明确为"因果链完整性"标记（缺则叙事支柱缺失），非主线优先级——既守"点缀可失败"原则，又诚实标注它对目标成片的分量。

### 2026-07-07 — [决策] 新增 ROADMAP.md 作为唯一执行主图
原周计划散在 PIPELINE §7-§9、依赖散在 BACKLOG 依赖速览、验收散在各任务描述里。合并为单一 ROADMAP.md（§1 三档交付基线 · §2 周计划带信心区间 · §3 依赖图 · §4 关键任务量化验收 · §5 待拍板项 · §6 breakdown）。W2/W3 标 🟡 中信心（MCP 首轮量产易吃 2 周）+ 缓冲机制。T-P0.1 补 5 项量化验收（FOV/恒星屏占比/人物屏占比/景深比例/背景光比）避免下游返工。

### 2026-07-07 — [决策] 文档大手术：归档 + 精简 + 修全部审阅问题
`archive/` 新建，`TECH-SCOUT.md`（30k，讨论完的候选池）+ `PIPELINE-RAW.md`（对话原文）迁入。工作目录只留 7 份指导落地必需文档：AI-BRIEF · ROADMAP · CONCEPT · PIPELINE · D3-KERNEL · LOG · BACKLOG。全套修 P0-P3 共 12 项审阅问题：D3 记账、§1 输入闭环（默认答案已在 PIPELINE 隐式回答）、分色/铁磁流体优先级、因果链交付分档、W2/W3 信心区间、T-P0.1 验收颗粒度、PIPELINE-RAW 归档、D3 §0 松绑、TECH-SCOUT 措辞、LOG 标题占位符 `# {项目名}` 修正为 `# Bifrost · LOG`、BACKLOG 依赖速览与"独立挂载"表述打架收口（迁入 ROADMAP 后不再重复）、AI-BRIEF 100 行超限（撤回，实际未超）。

### 2026-07-07 — [决策] 定位重构：单机位 diorama → 第三人称跑图 diorama
用户拍板："不想做单纯单机位展示，希望第三人称跑图展示且效果不错"。规模定为"海滩上跑一跑"——400m 单向沙滩走廊 + 两侧悬崖/海面作视觉边界，45-90s 走完，3-4 段可跑区。核心质量哲学升级："扛得住别人跑图游览"——每个可达角落都要经得起看，主图 T-L2.2 从"设计驱动因子"降级为"场景内的最优机位截图"。作品集叙事从"1 张 hero shot + breakdown"改为"完整场景 + walkthrough 视频 + AI 工作流 breakdown"，Part1/Part3 双叙事更硬核。

### 2026-07-07 — [决策] 地编工具选型：不用 Landscape、不用 PCG、Foliage 局部可选
排除理由：(1) Landscape 是大世界地形系统，400m 海滩用 Nanite Static Mesh + 局部 sculpted terrain 更可控；(2) PCG Graph 编辑必须人在 Slate 里连节点，AI 断层，撒完仍需人调分布/朝向；(3) diorama 单场景 PCG breakdown 因果链弱于"AI 生 mesh + AI 摆位"。替代方案：程序化前移到 Python 层——AI 通过 `execute_python_script` 批量 `AddInstance` / `SpawnActor` / `SetTransform` 撒点，比 PCG 更 AI 友好、更可控、breakdown 因果链更清晰。Foliage Tool 作为前景植被的可选局部工具（石缝苔藓量少可控）。此决策专为跑图 diorama 规模作出，若未来场景扩大到 1km² 需重新评估。

### 2026-07-07 — [决策] 跑图 diorama 规模化生产策略：分段 + kitbash + AI 批量 + 分级 LookDev
400m 海滩分 4 段（远端 / 中景 / 主锚点区 / 回望端），每段独立 kitbash + 材质 palette。AI 负责段内批量摆位、材质挂载、参数化生成；人负责段间过渡带、主锚点区精修 LookDev、走位测试验收。资产复用矩阵：3-5 个 kitbash 包（岩石 / 遗迹 / 漂流物 / 贝壳藻类 / 远景巨构），每包 AI 生 20-50 个 Instance 变体。材质规范化：3 张母材质（沙 / 岩石 / 遗迹金属）+ N 张 MI 全部 AI 批量生成。分级 LookDev：主锚点区 60% 精力、其余三段各 15% 左右，避免每段都追求完美导致爆时间。这个策略下 AI 从"提效"升级为"可行性前提"——没有 AI 无法在 5 周内做完 400m 场景，对 Part3 叙事是极大加分。

### 2026-07-07 — [决策] 周期定 5 周（原 6-8 周压缩），无独立缓冲周
用户拍板 5 周。压缩策略：取消原 W7-W8 缓冲周，改为每周内嵌 0.5 天缓冲（周五半天不排硬任务，用作回滚 / 找补）；原 W4-W5 分级 LookDev 合并到 W4 一周做完（主锚点 60% 精力 / 其余段 40%）。风险：跑图 diorama 保守估计 6-8 周，5 周属于激进档，若 W3 末保底成片跑砸，需砍 W4 点缀层（铁磁流体尖刺 + 极光）保 W5 走位测试。W3 末保底成片仍是硬线。玩家角色资产用户自处理，本项目不排任务。

### 2026-07-07 — [决策] 路线 C：保底线砍到最小可跑通，体积云/铁磁流体/极光上移一档
工时对齐核对发现 5 周装不下全范围（人力不可压部分 P0+P2内核+P4 LookDev+P6 已逼近 22.5 天上限，AI 提效只省得动 L1 量产体力活）。用户在 A(守5周狠砍)/B(扩6-7周)/C(5周分层交付) 三路线中拍板 C。W3 末保底成片砍到最小版：4 段跑通+恒星 hero+FluidFlux+kitbash+god-rays+大气散射+基础调色+1 条因果链（光→大气散射）；体积云降回 W4 第一优先补（覆盖 07-07「体积云升基底」的排期定位，技术方案不变仅交付档位变），铁磁流体/极光归 W4 目标线，够到几条算几条。**注：本次仅落地 ROADMAP §2 交付基线；§3 周表/§4 依赖/§5 验收的路线 C 收敛延后，暂以 HANDBOOK 为准。**

### 2026-07-07 — [决策] 按真实能力画像出 HANDBOOK 分步执行手册，旧文档跑顺再收敛
澄清用户真实画像：TA 基础（能连材质节点图/用 Sequencer/装插件改设置/导入摆放 Actor）+ MCP 已跑通可用 AI Agent 直控 UE + 重度依赖 AI + 不碰 C++。原 ROADMAP/PIPELINE 按"独立懂技术 TA"写，与此画像有差距。新增 `HANDBOOK.md`：不是 UE 保姆教程，而是三方协作编排手册——🤖对话AI出脚本/指令/诊断、🎮UE-Agent 执行、🧑人拍板+精修+验收，核心循环"你提需求→我出脚本→Agent执行→你验收→不过回改"。含 MCP 铁律下达模板、W1-W5 逐步谁做/用什么工具、§7 对 Agent 话术库（建材质/批量摆位/截图/清批/报错回传可复制模板）、§8 AI 帮不上必须人亲自上的红线清单。用户选"先出新手册跑顺、再回头收敛旧文档"，故 HANDBOOK 与 ROADMAP 周排布冲突处暂以 HANDBOOK 为准。

### 2026-07-07 — [决策] 工程宿主选方案 A：寄生 study 工程 + /Game/Bifrost 命名空间隔离
MCP 实测当前打开的是个人 UE study 工程（活动关卡 `/Game/ThirdPerson/Maps/ThirdPersonMap`，含大量学习性杂物：Slime/NiagaraFluid/Mediterranean_Coast/SoStylized/StarterContent 等）。用户拍板方案 A：不新起干净工程，就寄生在 study 工程里，靠 `/Game/Bifrost/` 命名空间 + batch/tag/folder/cleanup 铁律做隔离，好处是直接复用 NS_Slime/VolumeCloud。已 MCP 建好 `/Game/Bifrost/` 资产目录骨架 18 个子目录（Maps/Materials{/Instances}/Meshes{/Kitbash}/Blueprints/Star/Sky/Ocean/Segments{S1-S4}/Accents/Breakdown/_Sandbox），全部新建成功。Bifrost 专属关卡待建（用户手建/另存到 Maps/，MCP 不能新建空白关卡）。

### 2026-07-07 — [发现] study 工程可复用资产实测清单 + FluidFlux/GodRay 按原名未搜到
MCP find_assets 实测：✅ NS_Slime 有 4 个变体（`/Game/Effects/Slime/NS_Slime{World,BackUp,Local}` + `/Game/Effects/Niagara/MyNiagara/NS_Slime`）+ 完整 Slime 材质/BP 生态；✅ 体积云在 `/Game/Effects/VolumeCloud/` 与 `/Game/SlimeGame/Materials/Environment/VolumeCloud/`；✅ Niagara 流体框架 `/Game/NiagaraFluid/`；✅ 风格化水 `/Game/Environment/SoStylized/Environment/Water/`（候选海面）。❌ FluidFlux / PreComputedGodRay 按名字未搜到——用户暂缓确认（不阻塞 T-P0.0），后续用到再厘清真实名字/位置。

### 2026-07-07 14:58 — [决策] 场景等比×2，200m→400m
方式②整场景等比翻倍：路径 200m→400m，4 段界同步翻倍（S1 0-100 / S2 100-240 / S3 240-320 / S4 320-400m）。**走廊宽度不变**（保持 20-40m，只拉长不拉宽，画面密度更高）；**段/锚点数量保持 4**（等比是拉长非增段，4段4锚点是设计骨架）；walkthrough 跑位游览时长 30-60s→45-90s（1.5× 而非 2×，避免单向海岸跑图超 90s 拖沓），walkthrough 成片仍 1 分钟压缩版不变。此变更推翻了「200m 单向」硬约束。场景侧 v1 21 个已按 tag 清除、v2 21 个已重撒完成；本次同步 7 份文档共 41 处，残留检查 0。

### 2026-07-07 18:55 — [发现] T-P0.1 blockout v2 落地 + MCP 实测同步文档
用户已在 UE 出 blockout v2，AI 经 MCP 网关（get_actors_in_folder + get_actor_transform/bounds，只读非破坏）实读关卡 `L_Bifrost` 全部数值。P0_Blockout 20 个 actor（batch `W1_P0_blockout_v2`，Outliner `Bifrost/P0_Blockout/{S1-S4,_Markers}`）：400m 4 段、段边界 X=100/240/320m 与 ROADMAP §1 完全吻合、出生点 X=4m、主机位⑤ HeroCam @ S3 中心 (280,0,1.8)。另有独立尺度参照关 P0_ScaleTest_L（5 个，batch `W1_P0_scaletest_L_20260707`：人1.8m/悬崖300m/巨构180m/巨星Ø3000m）。数值落 `breakdown/P0-blockout/blockout-v2-measured.md` + `blockout-v2-raw.json`，ROADMAP 新增 §1.1 实测表。**偏差修正**：实测走廊宽度 S1/S4=60m·S2=48m·S3=40m，与 07-07 14:58 LOG「走廊宽度不变保持 20-40m」不符——实际 blockout 更宽（40-60m），以实测为准，宽度上限从 40m 修正为 60m（S3 最窄 40m 仍守"最窄=画面密度最高"意图）。T-P0.1 灰模达成，通行验收待 T-P0.2。

### 2026-07-07 20:20 — [决策] T-P0.2 第三人称接入完成，T-P0.1 通行验收随之达成，P0 三件闭环
用户用自备角色蓝图 + GameMode（非默认 ThirdPersonCharacter）接入 `L_Bifrost`，在 PIE 里从 S1 出生点实跑到 S4 尾端，确认不掉海、不穿墙、不卡 Gate、帧率不塌，本人口头验收通过。据此回填 `BACKLOG.md` T-P0.2 完成，及 `T-P0.1`"玩家路径可通行"验收项（HANDBOOK §2 表格 + blockout-v2-measured.md §3 checklist）。W1 三件套（T-P0.0 路径设计 / T-P0.1 blockout / T-P0.2 第三人称通行）全部闭环，可进入 W1 收尾（MCP 环境验证/最小母材质 demo）或直接为 W2 量产做准备。

### 2026-07-07 20:39 — [发现] MCP `set_actor_transform` 单位坑：文档记米，接口吃 UU，且未传字段会被清零
移动 `ST_Cliff_300m` 时踩了两个坑，均已修复，记录避免复现：(1) **单位换算**——`blockout-v2-measured.md` 的 loc/size 数值单位是"米"，但 `ActorTools.set_actor_transform`/`get_actor_transform` 的 `location` 参数吃的是原始 UU（1m=100UU）；这个悬崖用的 base mesh 恰好是 100UU(=1m) 的默认 cube，所以 `scale` 数值凑巧等于目标"米数"本身（scale=160 → 160m，而非常见认知里 scale=1.6）。两次都误把"米数"当"UU数"直传，结果 location 少了两位数（280m 传成 280UU=2.8m）、scale 也少了两位数（1.6 而非 160，做出 100×100×100UU 的迷你方块）。用户反馈"方向反了"实际是这个单位 bug 导致的视觉假象，逻辑方向本身没错。(2) **隐藏清零**——工具文档说"未设置字段=不改变"，实测是"未设置=重置为 0/(1,1,1)"，只传 `scale` 那次把 `location`/`rotation` 一并清零。修复方案：`location`/`rotation`/`scale` 三个字段每次都显式全传，且 location 数值 = 文档米数 × 100。修复后校验通过：悬崖 (450,-90,150)m / 160×140×300m，位于 S4 走廊终点(400m)再往右 50m。**后续任何 MCP transform 调用都要记住这两条**：数值先 ×100 再传，三个字段一次性显式带全。

### 2026-07-07 21:10 — [发现] MCP 实测确认可建 MaterialFunction + Static Switch Parameter，环境 uber 材质架构可落地
为 T-L1.1 环境 uber 母材质定架构（Static Switch Parameter 分通道开关 + 可复用模块封装成 MaterialFunction）前，先验证 `MaterialTools` 是否支持 MF 资产（`AIEffectFoundry_MCPStrategy.md` 第一版最小动作集未明列，属未知风险）。`_Sandbox` 下实测：`create_function` 建空 MF → `list_expression_classes` 能查到 `MaterialExpressionFunctionInput`/`FunctionOutput`/`StaticSwitchParameter` 三个类 → `add_expression` 三个节点全部成功 → `connect_expressions` 连线成功（踩了一个小坑：`FunctionOutput` 的输入引脚名不是常见的 "A"，需先 `get_expression_input_names` 查真实引脚名再连）→ `recompile` 编译通过。测试资产已清理。结论：**Uber Material + 独立材质函数（MF）+ Static Switch Parameter 的架构技术上可行**，`add_expression`/`connect_expressions` 等接口对 Material 和 MaterialFunction 通用（参数名统一叫 `material_or_function`）。T-L1.1 可以正式按此架构开工写 `CreateMaterial`/`create_function` 脚本。

### 2026-07-07 22:xx — [决策] T-L1.1 架构收口为单张环境 Uber 材质 `M_Env_Uber`，撤销"3 张母材质分工"
落地过程中 AI 先按 `PIPELINE.md`/`BACKLOG.md` 里"3 张母材质（沙/岩石/遗迹金属）"的旧措辞建了 `M_Rock`，与 07-07 21:10 条目本来定的"环境 uber 材质"架构方向不一致——用户发现后拍板纠正："一整个全局环境的材质，名字就叫 `M_Env_Uber`，所有 feature 都写进去，要什么效果用材质实例调"。据此撤销 3 张母材质分工，收口为单一 uber 架构：
- 把 `M_Rock` 的参数从 `Rock_*` 前缀改为通用命名 `Base_*`/`Wetness_*`/`Weathering_*`/`Overlay_*`（不绑定材质类型），新增 `Base_Metallic` 参数（原先硬编码常量 0，无法支撑遗迹金属的高 Metallic 需求），重命名/重建为 `M_Env_Uber`，7 个 MF（`MF_OrientationMask`/`MF_MacroVariation`/`MF_DetailNormalBlend`/`MF_WetnessBlend`/`MF_WeatheringOverlay`/`MF_OverlayBlend`/`MF_ProceduralOrTexture`）原样复用，编译保存通过（31 个节点）。
- 用 `MaterialInstanceTools.create`+`set_scalar_parameter`/`set_vector_parameter`/`set_static_switch_parameter` 批量生成 6 张 MI：`MI_Sand_Dry_01`/`MI_Sand_Wet_01`/`MI_Rock_Base_01`/`MI_Rock_Weathered_01`/`MI_RuinMetal_Fresh_01`/`MI_RuinMetal_Oxidized_01`，一次性全部成功无报错（沙用低 Metallic+细颗粒频率、岩石开风化+叠加层做苔藓、遗迹金属高 Metallic+风化+叠加层做锈斑，三种材质外观全靠参数取值区分，同一张母材质）。
- 已删除被取代的 `M_Rock`。同步回填 `BACKLOG.md`/`PIPELINE.md`/`ROADMAP.md`/`AI-BRIEF.md`/`HANDBOOK.md` 五处"3 张母材质"措辞为 uber 架构描述。当前色值/参数取值为占位估算，节点图与 LookDev 微调仍需用户验收（HANDBOOK §3 已标验收动作）。

### 2026-07-08 — [发现] AI-BRIEF「当前状态」滞后于 ROADMAP/BACKLOG/HANDBOOK，已回填
巡检发现 `AI-BRIEF.md`"当前状态"段落停留在 07-07 早期措辞（"下一步…继续 T-P0.1+T-P0.2"），而 T-P0.0/T-P0.1/T-P0.2/T-L1.1 当时已在 BACKLOG/ROADMAP/HANDBOOK 记为完成，四份文档口径不一致。已回填 AI-BRIEF：状态改为"W1 已闭环，进入 W2"，补 T-L1.1 完成摘要，下一步指向 W2（T-L1.2 kitbash · T-L1.3 FluidFlux · T-L3.1 恒星层1+3）。用户本轮切换协作 AI，此条兼作交接前的状态对齐检查点，后续接手 AI 可直接信 AI-BRIEF 当前状态，不必逐份 diff 校验。

### 2026-07-08 12:09 — [发现] T-L3.1 层1恒星本体材质骨架已用 MCP 一次性落地，未走 demo 阶段
用户拍板"遗迹 kitbash 自行淘包、AI 转推 T-L3.1"后，按 HANDBOOK §3 分工（AI 建骨架+参数建议，节点审美/梯度/光源用户定）直接建了正式资产（沿用 `M_Env_Uber` 先例）：`MF_Star_DomainWarpNoise`（双层 3D 噪声+domain warp 湍流场，7 个 ScalarParameter，输出 0-1 Turbulence）、`MF_Star_ColdGradient`（Fresnel 边缘因子+噪声扰动混合冷白核心→icy cyan 边缘 HDR emissive，2 VectorParam+4 ScalarParam，输出 EmissiveColor/EdgeFactor）、`M_Star_PlasmaCore`（Unlit/Opaque 主材质，调用上述两函数接入 MP_EmissiveColor，另接一路默认强度 0 的可选 WPO 翻涌位移）、`MI_Star_PlasmaCore_01`（14 个参数占位赋值，冷神性色域）。均已 `recompile` 通过。另在 `L_Bifrost` 放测试球 `SM_Star_PlasmaCore_LookDev`（folder `Bifrost/Star_Test`）供肉眼验收。技术实现上发现 `abyss-ue` MCP 的 `ProgrammaticToolset.execute_tool_script` 可把整段节点图搭建脚本化为单次调用（内部循环 `add_expression`/`connect_expressions`/`set_properties`），比逐条工具调用大幅省 round-trip，后续批量材质/摆位任务应优先用此工具。占位参数均为 AI 估算值，节点审美/色彩梯度/层3光源仍需用户在 UE 里验收微调（对齐 HANDBOOK §3 边界）。

### 2026-07-08 13:49 — [发现] FluidFlux 澄清：真实资产为用户魔改的 `/Game/Materials/DemoPublic/Wave`
补全 07-07 遗留的"FluidFlux/PreComputedGodRay 按原名未搜到"缺口之一：FluidFlux 并非市场同名插件，是用户基于 `/Game/Materials/DemoPublic/Wave`（内容自带 Demo 材质）魔改而成，内部代号沿用"FluidFlux"。T-L1.3 接入时以此路径为准。PreComputedGodRay 仍待厘清（未涉及本轮）。

### 2026-07-08 14:xx — [决策+踩坑] FluidFlux 资产复制到 `/Game/Bifrost/Ocean/Wave`，发现并修复"浅拷贝"陷阱
用户拍板资产复制（不跨文件夹引用）。`AssetTools.duplicate` 整文件夹复制后直接验证发现踩坑：UE 的 duplicate 是**浅拷贝**，新资产之间互相的引用不会自动重定向，新 `M_Wave_Base_Inst`/`M_Wave_Base` 复制完仍在内部连线里指向旧 `/Game/Materials/DemoPublic/Wave/*`，等于新文件夹是空壳。用 `ProgrammaticToolset.execute_tool_script` 批量扫描两个材质图的全部节点，把 7 处贴图引用 + 3 处 `MF_CoastlineWave` 函数调用 + Inst 的 Parent 全部重定向到 `/Game/Bifrost/Ocean/Wave/*` 同名资产，recompile+save 后用 `get_properties` 逐一读回确认生效（注意：`get_dependencies`/`get_referencers` 这两个查询接口在资产刚改完后返回陈旧缓存，不能拿来验证，得用 `get_properties` 读对象真值）。结论：**材质层（`M_Wave_Base`/`M_Wave_Base_Inst`/`MF_CoastlineWave`）现已是真正独立自洽的拷贝**，可放心继续做冷神性调色/加遮罩。**未修复**：`NS_InfiniteMesh`（Niagara）内部渲染器绑定极可能仍挂旧资产——当前 MCP 无 Niagara 专用工具集，通用属性工具够不到这层嵌套结构，需要用户在 UE Niagara 编辑器里手动重新指向新网格/材质，接入 L_Bifrost 前必做。详细清单见 `breakdown/T-L1.3-fluidflux/fluidflux-material-audit.md` 第7节。

### 2026-07-08 14:xx — [发现] MCP 只读核查 FluidFlux 材质结构，确认未接入 + 发现潜在遮罩接口
恢复 MCP 只读查询（引擎重启后 session 失效，需重新 `list_toolsets` 才能重建连接，之后正常）。核查结论：①`Wave/Model/NS_InfiniteMesh`（Niagara，驱动 9 级 `SM_FluxPlane*` 分级平面+`SM_Distant`远景低模，无限海面 clipmap 手法）目前只被 demo 关卡 `Mediterranean_Coasts` 引用，**尚未接入 `L_Bifrost`**，T-L1.3 确认是真实待办非误记；②生产材质是 `M_Wave_Base`（SingleLayerWater 着色模型）+ `M_Wave_Base_Inst`（43 参数暴露，含波形/法线/水体光学/海岸泡沫/朝向五大类）；③`M_WaveTest`/`M_WaveTest_Inst` 是未被引用的遗留原型，接入时忽略；④**关键发现**——暴露参数里有个 `LandScapePosition&Size`（Vector，位置+尺寸形式），结构上很可能可以直接复用为 07-06 决策要预留的"S3 磁场影响区局部遮罩"，不用新增参数，但具体连线未逐节点追踪，需人工在材质图里确认（列入 HANDBOOK §8 人工确认项）。详细参数分类表与接入建议顺序落 `breakdown/T-L1.3-fluidflux/fluidflux-material-audit.md`。
