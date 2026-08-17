# TA Cross-Domain Collision Lab

> [!ARCHIVED] **2026-08-12**
> This was a speculative candidate pool, not an active implementation project. It moved to archive
> without promoting any candidate; future ideas enter the owner's chosen concept workflow and need
> a fresh problem, baseline, minimum test, and decision before `/project-init`.
>
> 状态：2026-07-23，技术碰撞候选池，尚未进入实现  
> 工作目录暂沿用 `TAProductionTools`。  
> 定位：从计算机图形学与技术美术的真实生产问题出发，引入尚未成为常规工作流的跨领域方法；普通审计和批处理只能作为基线，不能单独构成作品集命题。

## 项目命题

制作一组可以被真实美术或 VFX 团队直接使用的 UE 编辑器工具。每个模块必须同时具备：

1. 明确的生产触发问题；
2. 可运行的编辑器工作流；
3. Before / After 场景；
4. 时间、性能或维护成本数据；
5. 不依赖“AI”或“新算法”标签也能成立的使用价值。

当前记录九条技术碰撞候选路线。它们首先是待检索、待证伪的假设，不默认承诺全部实现。

## 核心主旨

交互雪、体积云等常见效果已经拥有大量成熟教程。这个项目不以复现热门效果为目标，而是提前寻找计算机图形学和技术美术中尚未被广泛产品化的**技术碰撞**：

> 人类知识库中已经存在大量分别成熟的技术 A、B、C。它们可能来自渲染、几何处理、计算机视觉、信号处理、压缩、控制理论、编译器、数据库、材料与物理模拟等不同领域。过去受个人知识边界和实验成本限制，许多有价值的组合长期无人连接；AI 可以利用知识广度充当跨领域检索器和组合搜索器，提出候选连接，再由可复现实验验证它们是否真的形成生产价值。

这里的目标不是随机拼接技术名词，也不是声称“网上没人做过”，而是系统寻找：

```text
真实且高频的生产摩擦
→ 现有方案长期被迫取舍
→ 另一个领域已经解决过结构相似的问题
→ 将其表示、目标函数或求解方法迁移过来
→ 建立画质、性能、内存或制作时间优势
```

理想候选位于以下交叉区域：

- **需求平民**：组长、美术、VFX 或引擎团队可以自然提出；
- **解法非显然**：不是常规教程、参数调优或已有 UE 功能包装；
- **结果可落地**：最终进入可编辑、可调试、可度量的 UE 工作流；
- **创新可证伪**：允许实验得出“组合没有收益”，不为保住概念继续堆技术；
- **声明克制**：公开检索未发现成熟同构实现，只代表创新假设，不能代替完整先例检索。

AI 在本项目中的职责是扩大搜索半径、发现结构相似性和快速淘汰错误组合；最终创新性由先例检索决定，采用价值由实验和生产工作流决定。

## 硬性筛选条件

每个候选必须同时成立：

1. **生产根基**：问题可以被真实美术、VFX 或引擎组直接提出；
2. **技术碰撞**：解法不是 UE 已有功能的重新包装，而是从其他领域迁移一种非显然方法；
3. **采用优势**：相对人工流程或原生功能，至少在质量、性能、制作时间或维护成本上建立一个可测优势；
4. **公开空缺**：经过检索后，未发现已经广泛采用的同构 UE 工作流；只能写“公开检索未发现成熟实现”，不能声称绝对首创。

---

## 模块 A：Niagara Bounds + Scalability Compiler

### 生产问题

> Niagara 特效在转动镜头或离开屏幕边缘时突然消失；手工放大 Fixed Bounds 后虽然不再消失，却导致系统长期无法被正确剔除。与此同时，Epic / High / Medium / Low 多套特效通常靠复制和手调，母版修改后各档位容易漂移。

### 当前人工做法

- 特效师播放若干次后凭经验填写 Fixed Bounds；
- 对随机速度、风场、碰撞和用户参数取保守极值；
- 复制 Niagara System，分别制作不同画质版本；
- 出现穿帮或性能问题后由 TA 逐个排查。

### 原生基线为什么不够成为项目

UE 已提供 Fixed / Dynamic Bounds、Effect Type、按预算裁剪、Spawn Count Scaling，以及在 System、Emitter、Renderer 层设置 Scalability Override。单纯自动填写 Bounds 或批量修改这些参数，只能作为普通生产工具。

### 技术碰撞 A1：可达域分析 + 统计校准的 Bounds

将编译器与控制系统中的**区间传播 / 可达域分析**迁移到 Niagara：

1. 从初始位置、速度、生命周期和用户参数范围开始；
2. 对重力、Drag、线性力、随机初速度等受支持模块传播位置与速度区间；
3. 对 Noise、碰撞和自定义 Data Interface 等无法解析的模块进行有限次仿真；
4. 使用 held-out 随机种子校准经验尾部 Margin；
5. 输出“解析可达域 + 统计残差”的混合 Bounds，并标明置信范围和不受支持的模块。

研究问题：

> 相比人工保守盒和纯多种子仿真，混合可达域能否在保持 held-out 零误裁或目标误裁概率时，得到显著更紧的 Bounds？

这不是发明新的粒子系统，而是把程序分析中“程序可能到达哪些状态”的方法，迁移到特效空间包围盒。

### 技术碰撞 A2：Rate-Distortion + 黑盒搜索的 Scalability

将视频压缩中的**率失真优化**迁移到 Niagara 画质档位生成：

- Rate：实测 GPU / CPU 时间、透明覆盖、粒子峰值和内存；
- Distortion：相对母版视频的轮廓、亮度、运动和时间稳定性误差；
- Controls：Spawn Rate、Renderer / Emitter 开关、Ribbon 分段、灯光、碰撞、材质版本和更新频率；
- Search：在离散开关和连续参数上搜索满足帧预算的 Pareto 解。

研究问题：

> 相比统一 Spawn Count Scaling 和人工档位，能否在相同 GPU 预算下保留更接近母版的时空外观？

UE 原生提供“有哪些旋钮”，本项目研究“如何根据最终画面自动选择旋钮组合”。

### 最小验证

第一阶段只解决 Bounds，避免一开始做成庞大的 VFX 管理平台：

1. 在编辑器中对指定 Niagara System 运行多个随机种子；
2. 在给定的用户参数范围内采样粒子位置；
3. 计算推荐 Fixed Bounds；
4. 标记导致 Bounds 异常膨胀的离群粒子；
5. 提供相机环绕测试，验证特效不会错误消失；
6. 将推荐值写回资产前展示差异并要求确认。

Bounds 技术碰撞成立后，再验证 Scalability：

- 从一份母版派生 Spawn Rate、最大粒子数、灯光、碰撞、Ribbon、材质和距离裁剪档位；
- 保留主轮廓、主光和关键事件，优先删除低贡献粒子；
- 母版更新后能够重新生成档位，而不是维护多份失联副本。

### 交付画面

- Bounds 过小导致的相机边缘消失；
- Bounds 过大导致的剔除浪费；
- 自动采样后的紧致 Bounds；
- 离群粒子轨迹和问题定位；
- 同一效果多个画质档位的同步对比；
- Niagara GPU / CPU 时间、峰值粒子数和屏幕覆盖对比。

### 成功指标

- 测试相机和参数范围内无错误裁剪；
- 推荐 Bounds 明显小于人工保守 Bounds；
- 能指出 Bounds 膨胀的具体发射器或粒子；
- 派生档位相对母版保持主要视觉结构；
- 母版修改后无需逐份手工同步。

### 停止条件

- 区间传播面对常见 Niagara 模块时总是退化成极松的 Bounds；
- 统计校准相对纯仿真没有更好的紧致度或可靠性；
- Rate-Distortion 搜索只能学到统一降低 Spawn Rate；
- UE 已能直接、稳定地完成相同的多种子 Bounds 分析和问题定位；
- 只能得到比人工 Bounds 更大的保守盒；
- Scalability 只能做统一数值缩放，无法保持效果结构；
- 为支持少数特效而要求侵入式修改所有 Niagara 模块。

---

## 模块 B：Material Instance + Shader Permutation Cleaner

### 生产问题

> 项目的 Master Material 持续增加 Static Switch。修改一次材质会触发大量 Shader 编译，但团队无法快速回答：哪些开关组合真的被使用、哪些实例完全重复、哪些功能已经没有资产依赖。

### 当前人工做法

- 依靠命名规范区分材质实例；
- 在 Content Browser 中逐个检查 Static Switch；
- 遇到编译或 Cook 压力后临时拆分 Master Material；
- 保留“不确定是否有人使用”的历史功能和实例。

### 普通审计为什么不够成为项目

UE 已提供 Reference Viewer、Material Statistics 和项目级 Shader Permutation Reduction；工作室也可能拥有内部 Material Permuter。只输出 Static Switch 表格、重复实例和引用关系，属于有用但常规的管线工具。

### 技术碰撞：频繁项集 + 超图划分的 Material Family Compiler

将数据库与芯片设计中的方法迁移到 Master Material 拆分：

1. 把每个实际 Material Instance 表示为一组已启用 Feature；
2. 用**频繁项集挖掘**找出项目中经常共同出现的功能组合；
3. 将 Feature 视为节点、Material Instance 视为连接这些 Feature 的超边；
4. 使用**加权超图划分 / 集合覆盖**提出少量 Material Family；
5. 优化目标同时考虑：
   - 实际编译 Shader 数量；
   - Cook / DDC 数据；
   - 重复材质逻辑；
   - 需要迁移的实例数量；
   - 一次功能修改触发的重编译范围；
6. 输出可解释的拆分方案，例如“Foliage / Wet Surface / Generic Prop”，并展示每次划分减少了哪些组合。

研究问题：

> 相比一个持续膨胀的 Master Material、人工拆分和只删除未使用开关，数据驱动的 Family 划分能否以很少的图逻辑重复，显著降低真实 Shader / Cook 成本和修改影响范围？

创新点不在“统计排列”，而在于把 VLSI 超图划分中减少跨分区连接的思想，用于自动寻找材质功能家族。

### 最小验证

第一版只做可信审计，不自动重写材质图：

1. 扫描选定目录下的 Material 与 Material Instance；
2. 解析父子关系和实际覆盖的 Static Switch；
3. 按最终开关组合聚类；
4. 找出参数与父级完全一致的无效覆盖；
5. 找出配置完全相同的重复实例；
6. 统计各组合被多少资产、关卡或组件引用；
7. 输出可点击报告，跳转到材质、实例和引用资产；
8. 对删除、合并和拆分只给出建议，不自动执行破坏性修改。

审计数据可信后才运行划分求解：

- 结合实际 Shader / Cook 数据标记高成本组合；
- 识别从未被使用的 Static Switch 分支；
- 根据真实使用组合建议拆分父材质；
- 为确认安全的重复实例提供引用替换预览。

### 交付画面

- Master Material 的实例继承图；
- Static Switch 组合矩阵；
- 重复实例与无效覆盖列表；
- 每种组合的引用数量；
- 清理前后的实例数量、组合数量、Shader 编译或 Cook 数据。

### 成功指标

- 报告中的父子关系、开关值和引用关系可以人工抽样复核；
- 能发现真实重复项或无效覆盖，而不是只列资产数量；
- 清理建议不会把动态参数差异误判成完全重复；
- 至少在一个测试内容集上降低维护项或实测编译 / Cook 成本。

### 停止条件

- 超图划分给出的结果只是美术已经显然知道的资产分类；
- 估算目标下降，但真实 Shader / Cook 数据没有改善；
- 为减少排列而复制了过多材质图逻辑，维护成本反而上升；
- 只能得到 UE 原生 Reference Viewer 和 Material Statistics 已直接提供的信息；
- 无法可靠解析继承后的最终参数；
- 只能估算 Shader 数量，无法用真实编译或 Cook 数据验证；
- 自动修改引用的风险高于工具节省的人工成本。

---

## 模块 C：Robust Field Compiler

### 生产问题

> 扫描、Kitbash、布尔运算和 Nanite 高模在画面里可以正常使用，但网格可能不封闭、自交、法线混乱、包含薄片和非流形结构。为了生成可供 Niagara、材质、碰撞或空间查询使用的 SDF，TA 仍然需要清理拓扑、封洞和制作额外代理。

### 当前人工做法

- 手工修复开口、反面和自交；
- 制作封闭低模作为 Distance Field Proxy；
- 提高体素分辨率掩盖薄结构问题；
- 为粒子碰撞、材质效果和玩法查询分别制作代理；
- 对无法修复的资产使用隐藏碰撞体或局部作弊。

### 普通方案为什么不够

传统 SDF 管线通常隐含“输入网格封闭、定向一致”的前提。单纯增加体素分辨率只能减小离散误差，不能可靠解决内外符号错误；普通自动封洞又可能改变扫描资产的大孔洞、薄壳和真实拓扑。

### 技术碰撞：鲁棒几何符号 + 置信度场 + 多分辨率查询

将几何处理中的鲁棒符号判断、概率/置信度表达和实时稀疏场结合：

1. 用 BVH 或体素距离变换得到 unsigned distance；
2. 使用广义绕数、Signed Heat Method 或相近的鲁棒方法估计非封闭网格的内外符号；
3. 不强迫所有位置得到虚假的确定答案，同时输出 sign confidence / ambiguity；
4. 在高置信区域生成普通 SDF；
5. 在低置信区域选择保守外壳、局部修复或 unsigned fallback；
6. 将结果编译为多分辨率稀疏场，供 Niagara Collision、材质采样和其他查询共享。

研究问题：

> 相比 UE 常规 Mesh Distance Field 和人工封闭代理，能否在不清理原始脏模型的情况下显著减少符号错误与粒子穿漏，同时保持可接受的烘焙时间和内存？

创新假设不在于发明新的 SDF 算法，而在于把已有鲁棒几何方法、显式不确定性和 UE 多消费者工作流编译成一个可用产品。

### 最小验证

测试集必须主动包含：

- 开口扫描模型；
- 单面薄片；
- 自交和重叠组件；
- 法线方向混乱；
- 非流形边；
- 一个干净封闭网格作为正常基线。

输出并比较：

- sign error；
- 表面距离误差；
- 薄结构保留率；
- Niagara 粒子穿漏率；
- 烘焙时间和 GPU 内存；
- 相比手工制作代理节省的步骤。

### 停止条件

- 在常见脏资产上仍需要大量手工标注内外区域；
- 低置信区域占比过大，只能退化为无用的保守外壳；
- 相比简单 voxel close / flood fill 没有可靠性优势；
- 共享一个 Field 迫使各消费者接受不合适的精度与成本。

---

## 模块 D：Inverse Niagara

### 生产问题

> VFX Lead 给出一段参考视频，希望在 UE 中获得相似的火花、烟尘、魔法轨迹或能量效果。特效师必须从空白 Niagara System 开始猜测发射、速度、阻力、噪声、生命周期、材质和灯光参数；生成式视频可以复现二维画面，却不能输出可编辑、可交互、可换镜头和可优化的实时特效。

### 当前人工做法

- 逐帧观察参考并凭经验拆解；
- 搜索相似教程或 Marketplace 模板；
- 手工调整大量互相耦合的参数；
- 用 Flipbook 直接贴近参考，但失去三维运动和交互；
- 用视频生成模型制作结果图，却不能进入 Niagara 生产管线。

### 技术碰撞：逆向图形学 + 系统辨识 + 受约束特效模板

不从视频生成另一段视频，而是反求一个可编辑的 Niagara 程序：

1. 从参考视频提取前景遮罩、轮廓、亮度分布、光流、粒子轨迹、生命周期和时间频率；
2. 限定一个 Niagara 效果家族和一组具有语义的可调参数；
3. 用同机位渲染候选 Niagara 结果；
4. 通过系统辨识、贝叶斯优化、CMA-ES 或其他黑盒搜索，使候选的时空特征接近参考；
5. 输出普通 Niagara System、Emitter、Material 和公开参数；
6. 用新机位、不同灯光和交互条件验证它不是只对单段视频过拟合。

研究问题：

> 对一个受限效果家族，能否从单段或少量参考视频中恢复一个比人工从零搭建更快、相似度可测、并且仍可编辑和跨视角成立的 Niagara 起点？

创新点不是 Video-to-Video，也不是让大模型直接写节点，而是把二维参考拟合成受 UE 运行时约束的三维程序化系统。

### 最小验证

第一版只允许选择一个可辨识的效果家族，例如：

- 弹道火花与余烬；
- 具有主方向的魔法粒子流；
- 简单冲击烟尘；
- 一种参数已知的合成 Niagara 数据集。

验证分为两部分：

1. **合成反演**：用已知 Niagara 参数生成视频，检查系统能否恢复参数或等价外观；
2. **真实参考**：拟合公开视频，并比较人工从零搭建时间、视频特征误差和新视角表现。

输出必须仍可由特效师编辑，不能只交付缓存、视频或不可解释的神经表示。

### 停止条件

- 单视角歧义导致结果换视角立即失效；
- 优化只会拟合颜色和轮廓，无法恢复可信运动结构；
- 搜索成本高于有经验特效师手工搭建；
- 为覆盖不同效果不断增加模板，最终退化成庞大且不可维护的特效库；
- 输出无法被正常 Niagara 工具继续编辑和优化。

---

## 模块 E：Semantic Engine Feature Capsule

### 生产问题

> 大型项目通常需要修改 UE 源码实现项目专用 Feature。UE 升级时，团队必须在放弃官方新功能、迁移整块定制代码和长期解决 Fork 冲突之间反复付费；即使 Engine Diff 很小，大量 Private Header 与渲染阶段假设也会形成隐藏的升级成本。

### 核心抽象

不追求任意 Feature 零侵入，而是把不可迁移的源码差异重新编码为：

```text
项目 Feature 逻辑 → Project Plugin
UE 版本差异       → 薄 Version Adapter
必要的引擎改动     → 少量通用 Hook
升级动作           → 可验证、可重放的 Patch / Hook Manifest
```

Engine 中只允许保留数据暴露、阶段回调、结果覆盖或 Provider 注册入口，不允许出现项目 Shader、资产引用和业务规则。真正需要最小化的不只是修改行数，而是：

```text
维护成本 = Engine Diff + Private API 依赖 + 语义时序假设
```

### 技术碰撞

- 微内核与 Ports-and-Adapters：把项目功能隔离成 Feature Capsule；
- Aspect-Oriented Programming：把少量控制流注入描述为 Hook；
- Semantic Patch / Clang AST：按函数、调用关系和资源作用域迁移 Hook，而不是依赖行号；
- 契约测试：验证 Hook 次数、线程、阶段、资源生命周期与最终画面；
- 最小覆盖优化：在满足 Feature 数据和控制需求的前提下，选择维护成本最低的 Hook 集。

### 最小工具与流程

第一版不制作通用 AST 编译器，只使用现有能力：

1. 一个承载绝大部分实现的 Project Plugin；
2. 按 UE 版本保存、每个 Hook 一个提交的极小 Git Patch Series；
3. 一份限制可修改文件、最大行数、禁止项目逻辑和 Private Header 的配置；
4. 一个执行 `apply / audit / verify / port` 的 PowerShell 脚本；
5. `git am --3way`、`git rerere`、UBT 与 UE Automation Test；
6. 只有当 Hook 数量和跨版本冲突被证明足够多时，才升级到 Clang AST Semantic Hook Manifest。

研究问题：

> 对一个真实的深层 UE Feature，能否将原始 Fork 修改蒸馏为少量通用 Hook 与版本适配层，并在跨版本升级时显著减少冲突数、人工迁移时间和 Private API 依赖，同时保持画面与性能一致？

### 交付与指标

- 一个必须深入 Renderer、Lumen、Nanite 或其他核心系统的具体视觉 Feature；
- 原始直接修改 UE 的基线版本；
- Capsule 化后的 Plugin、Version Adapter 和 Engine Hook Patch；
- 至少两个 UE 版本之间的真实迁移；
- Engine 修改文件数与 LOC；
- Private Symbol Dependency 数量；
- 自动应用成功率、人工冲突数和迁移耗时；
- Hook Contract、截图一致性和性能测试结果。

### 停止条件

- 具体 Feature 已能完全通过 UE 官方 Plugin、Subsystem、Scene View Extension 或 Renderer Delegate 实现；
- Capsule 只减少了 Engine Diff 行数，却继续依赖大量 Private API 和内部生命周期；
- Hook 数量接近原始修改点数量，未形成稳定边界；
- 为少量稳定 Patch 过早制作复杂 AST 工具；
- 没有具体 Feature 载荷，只剩普通插件规范和 Git 流程；
- 核心算法本身必须被替换，无法通过有限 Hook 隔离。

---

## 模块 F：Compressed GPU Event Bridge

### 生产问题

> 大量雨滴、火星、碎屑和碰撞粒子适合使用 GPU Simulation，但撞击后又需要驱动声音、Decal、Gameplay Callback 或 CPU Secondary FX。逐事件 Readback 会产生同步与带宽压力，切回 CPU Simulation 又失去粒子规模优势；UE 当前 Niagara Event Handler 也不支持 GPU Simulation。

### 技术碰撞：流式 Heavy Hitters + 时空事件聚类 + 稀疏异步 Readback

不把每个 GPU 粒子事件传回 CPU，而是在 GPU 上先把候选事件压缩成少量可消费代表：

```text
大量 GPU 碰撞候选
→ 空间 Hash / 时间窗口
→ 聚类、Heavy Hitters 或 Reservoir
→ 保留峰值并累计总能量、数量与覆盖范围
→ 只 Readback K 个代表事件
→ CPU 声音、Decal、Gameplay 或 Secondary FX
```

代表事件至少包含位置、法线、最大与累计冲量、事件数量、覆盖半径、时间范围和事件类型。不同消费者可以使用不同压缩目标：声音保留能量峰值，Decal 保留空间覆盖，Gameplay 只允许显式白名单事件进入。

研究问题：

> 相比 CPU 粒子事件和全量 GPU Readback，能否以固定的小型 Readback 预算保留主要事件时序、空间分布和累计能量，使大规模 GPU 粒子可靠驱动少量 CPU 世界反馈？

### 最小验证

1. 制作高密度雨滴或火花碰撞场景；
2. 生成 GPU 事件候选 Buffer；
3. 第一版只实现规则网格聚类与每格最大冲量事件；
4. 异步 Readback 固定上限的代表事件；
5. 分别驱动声音或 Decal 中的一种消费者；
6. 与 CPU Event 基线和全量事件记录离线 Ground Truth 对比；
7. 简单方案成立后，再验证 Reservoir、Heavy Hitters 和多消费者压缩目标。

### 成功指标

- Readback 字节数与等待时间；
- CPU 和 GPU 时间；
- 同帧及跨帧事件数量上限；
- 高能事件召回率；
- 空间覆盖和累计冲量误差；
- 声音、Decal 或 Secondary FX 的时间稳定性；
- 相比 CPU Simulation 可支持的候选粒子规模。

### 停止条件

- 少量 GPU 事件已经能通过现有异步 Readback 稳定满足生产预算；
- 聚类延迟使撞击反馈不可接受；
- 代表事件产生明显位置漂移、节奏丢失或能量闪烁；
- GPU 聚类成本接近节省的 CPU 与 Readback 成本；
- 为兼容不同消费者不断堆叠互相矛盾的压缩规则；
- 项目退化成通用 Gameplay Event Bus，而不是解决 GPU VFX 到 CPU 世界反馈的边界问题。

---

## 当前候选状态

1. **Niagara Perceptual Scalability Compiler**：Rate-Distortion × Niagara 质量旋钮。
2. **Reachability-Calibrated Bounds**：程序可达域 × 粒子包围盒。
3. **Material Family Compiler**：频繁项集 / 超图划分 × Shader Feature 管理。
4. **Robust Field Compiler**：鲁棒几何符号 / 置信度场 × UE 查询代理。
5. **Inverse Niagara**：逆向图形学 / 系统辨识 × 可编辑实时特效。
6. **Semantic Engine Feature Capsule**：微内核 / 语义补丁 / 契约测试 × UE Fork 蒸馏与跨版本迁移。
7. **Compressed GPU Event Bridge**：流式事件压缩 / 稀疏 Readback × GPU 粒子驱动 CPU 世界反馈。
8. **Topology-Aware Surface Propagation**：测地距离 / Heat Method × 材质传播前沿 × Niagara 边界反馈，用于沿真实网格拓扑蔓延的腐蚀、冰冻、能量与裂纹效果。
9. **Shader Genome**：语义类型约束的 Material Function 图文法 × Interactive Evolution / Quality-Diversity Search × UE 编译、性能与可编辑性 Gate，用于在真实项目预算内搜索可继续人工打磨的效果组合。仅当项目需要反复生产皮肤、技能主题、阵营视觉或赛季特效等视觉家族时成立；单个一次性 Shader 不足以支撑该项目。
10. 普通 Bounds Analyzer 和 Material Instance Auditor 只作为输入、基线与调试界面，不单独视为创新候选。

当前列表不代表实现优先级。每项必须先完成先例检索、最小技术探针和生产收益 Gate，再决定是否进入作品集排期。

## 作品集定位

这些模块不声称发明各自的底层算法：

- Niagara 模块的价值是把可达域分析或率失真优化迁移到 VFX 生产；
- Material 模块的价值是把频繁项集与超图划分迁移到 Shader Feature 管理；
- Robust Field Compiler 的价值是把鲁棒符号、不确定性与 UE 查询代理编译连接起来；
- Inverse Niagara 的价值是把参考匹配从二维结果生成改写为可编辑程序反演；
- Semantic Engine Feature Capsule 的价值是把不可迁移的文本差异改写为最小、可验证、可重放的语义注入协议；
- Compressed GPU Event Bridge 的价值是把不可全量跨越 GPU/CPU 边界的粒子事件压缩成保留峰值、覆盖与能量的稀疏世界反馈；
- UE 编辑器工具、审计界面和批处理只是让研究结果可以落地。

最终只有在真实场景、可操作工具和量化收益全部成立后，才进入作品集收录候选。
