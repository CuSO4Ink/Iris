# 项目经历与面试技术挖掘

> 2026-09-07 起作为 review 主入口。目标：过一遍全部项目过程，确认技术点没有因改名、归档、失败或被压缩为关键词而遗漏。
> 本轮是目录与主要 Brief 首轮盘点。以下为已有材料支撑的挖掘提纲，不是全部源码复核或个人掌握结论。

## 怎么过一个项目

1. 原始需求：效果/使用者要什么，原方法哪里不够，有什么约束。
2. 完整过程：最早方案、关键转折、被否决路线、最后停在哪里。
3. 实现链：输入 → CPU/GPU/工具处理 → 中间数据 → 最终消费者。
4. 技术拆解：算法、坐标系、格式、资源生命周期、采样、同步、稳定性和接口。
5. 选择与排查：为什么这样选；出现什么现象，如何缩小原因，修正解决什么、增加什么代价。
6. 面试展开：两分钟概述、五分钟实现链、逐技术点继续追问；未做过的扩展作为设计讨论。

“已列技术点”“过程已梳理”“已做问答”分别记录。当前下列主题只完成首轮提纲，未进行本轮口述测验。
项目执行状态解释历史停点，不能表示复习完成。性能方法保留，具体数字按需查，不要求背诵小数。

## 核心项目覆盖与过程提纲

| 项目/来源 | 需要串起的过程 | 技术点与追问方向 | 下一层挖掘缺口 |
| --- | --- | --- | --- |
| [GaussianVolume](../../archive/GaussianVolume/AI-BRIEF.md) | 解析体积 → Structured Gaussian Field → VDB/candidate renderer → 固定点预算/去网格 → 标准 3DGS → 六轴 transport/DGSM → UE 合成 | 稀疏体素、射线积分、密度/opacity、协方差/投影椭圆、teacher、densify/prune、排序/quad raster、候选池、scan/scatter、联合双边、overdraw | 逐读[复盘](../../archive/GaussianVolume/summary/PROJECT-RETROSPECTIVE.md)和[账本](../../archive/GaussianVolume/IMPLEMENTATION-AND-OPTIMIZATION-LEDGER.md)，解释各路线淘汰原因；历史解析路线与最终 splat 路线分开 |
| [slime](../slime/AI-BRIEF.md) | GPU PBF → 标量场 RT → Marching Cubes → 法线/材质；水材质撤回，平滑核与中央差分修正 | 约束投影、邻域、核半径/步长/迭代、密度场与真正 SDF 的区别、等值面、梯度、分辨率、粗糙度 | 读 Log/HLSL/缓存，恢复求解和交互顺序；解释面皮感与明暗块如何区分几何和着色原因 |
| [SSPR](../SSPR/AI-BRIEF.md) / [ScreenSpaceParticleReconstruction](../ScreenSpaceParticleReconstruction/AI-BRIEF.md) | 两处历史中的 Raster/sparse splat、Raw Moments、Streamline、NeighborQuery、Gather-only 重启 | 世界→视图→RT、2.5D、各向异性核、原子归约/gather、erf 积分、原始矩、深度/方向、质量归一化、K 上限、固定步长追帧 | 两份 Brief 主线不一致，暂并列，不判哪个更新；按 Log/资产路径对齐时间线。失败的刷毛、印章和滤波堆叠也要复盘 |
| [DyeSplashBaker](../../archive/DyeSplashBaker/AI-BRIEF.md) | 扩散/SWE 尝试 → FloodStep v2 到达时间场烘焙 → 阈值动画 → 地面/墙面贴花 | Grid2D、各向异性测地距离、R16F/R32F、Progress、DBuffer、法线/粗糙度、遮挡射线、GravityUV、接缝锚定、噪声团块 | 读求解规格和 Log，解释为何不需要完整动力学；区分已用方法与 Domain Warp 等候选 |
| [NiagaraGridBounds](../../archive/NiagaraGridBounds/README.md) | 固定/软边界/Spline bounds → 按需两阶段 GPU reduction | AABB、网格变换、分组归约、Stage 顺序、CPU/GPU 数据来源、静态分支 | 读两份 HLSL 与规格，解释范围变化对 cell 尺寸、邻域覆盖、延迟的影响 |
| [lightning](../lightning/AI-BRIEF.md) | 种子化 RMD → 分叉树/节奏 → Controller/Bolt → User 参数改 Module 输入 | 可复现随机、递归中点位移、层级分支、Ribbon、切线/宽度、Particle Reader、SimTarget、命名空间、Scratch 所有权 | 读 DESIGN、四级分叉规格和 HLSL，串起形态参数与算法；恢复参数未消费/重编译再生排查 |
| [历史 UE5.5 渲染](../../archive/AIEffectFoundry/AIEffectFoundry_CapabilityMap.md) | 自定义 Shading Model/光参数/Outline/半透明排序/编辑工具 → 迁移取舍 | GBuffer、Toon 分阶、Ramp/Curve、SDF 脸影、Kajiya、MatCap/ILM、边缘光、ToneMap/ACES/LUT、Pixel Inspector | 能力图是经历线索；恢复各功能如何接渲染链，不能把 5.8 原生功能当旧 patch；缺源码不阻塞设计复盘 |
| [NPR_rendering](../NPR_rendering/AI-BRIEF.md) | 旧枚举迁移 → Toon/PBR 分层 → 语义贴图 → Micro 变黑排查 → SSS Probe | Substrate、材质继承、切线/UV、Meso/Micro、通道打包、线性纹理/压缩、PartID/MaterialID、网格与纹理分工 | 读新 Log；保留未接 Front Material、关闭 Micro 恢复、BSDF 新建编译失败等排查，不能只写三风格 A/B 未完 |
| [Bifrost](../../archive/Bifrost/AI-BRIEF.md)：PCG/环境材质 | Landscape 语义 → 五类散布 → 过滤/贴地/选网格 → 实例和材质 | 高度/坡度/层权重、Surface/Volume Sampler、Raycast、朝向、Weighted Selector、ISM/HISM、剔除、Biplanar、湿润/风化/覆盖层 | 逐图追参数到效果，补环境材质链；早期不用 PCG 不覆盖后期 Landscape2 |
| Bifrost：海洋/岸线 | VDM 迁移 → 无限平面/分级网格 → 岸线/泡沫 → 水体排序 | XYZ 位移、WPO、SDF/Height、相机跟随、近远景采样、法线、SingleLayerWater、Height Capture | 读历史 Brief/水缓存，恢复几何、遮罩、着色、排序四条链；FluidFlux 为内部沿用代号 |
| Bifrost：云/天气 | 密度结构 → 侵蚀/跳步 → 云光雾风统一控制设计 | 天气图/语义图集/3D 噪声、Domain Warp、Beer-Lambert、相函数、多重散射、Conservative Density、MPC、插值 | 云材质与未完成 W0 设计分别复盘；不因未交付漏掉设计，也不写成运行成果 |
| [UE-NeuralRender-Lab](../UE-NeuralRender-Lab/AI-BRIEF.md) | R1/R2 神经材质 → R4 神经云 → world-box 部署 → Z 向锚定排查 | latent texture/triplane、tiny MLP、BRDF 输入、teacher/student、组合留出、HDR loss、FP16、ray/AABB、坐标变换、Scene Depth、Global Shader | 材质和云各做过程线；分别解释表达能力、泛化、部署成本，不能只记 R4c 待复测 |
| [AirWall](../../archive/AirWall/AI-BRIEF.md) | 编辑/反馈问题 → Spline → 碰撞代理/视觉 → 接触波纹 | 弧长 UV、切线朝向、Spline Mesh/Shape、接触坐标、传参、overdraw、事件预算 | 从 overview/Log 找真实问题；区分归档方案与实际参与实现，未确认部分留作经历回忆 |
| EffectPipeline / 实习生产 | 特效/缓存导入 → Sequencer/关卡 → 跨版本迁移 → 崩溃排查 | VDB/Zibra、SimCache/PointCache、VAT/RBD VAT、引用、World Partition、写盘、缓存生命周期 | 当前目录删除，旧索引指 Git `45e55bb`，待读历史树确认；不恢复公司工程，不凭缺文件抹掉经历 |
| Houdini / Boids / PBD 实习线索 | DCC 生成 → 烘焙/导出 → GPU 粒子/材质消费 | SOP/VEX、法线处理、VAT/VDM、邻域网格、分离/对齐/聚合、位置约束、边界/碰撞 | 回到原技术拆解确认实际算法与负责部分，不能把通用 L-system 等示例直接算成经历 |
| [RenderDocMCP](../../archive/RenderDocMCP/AI-BRIEF.md) | 人工拆帧 → qrenderdoc/Replay API → 文件 IPC/MCP → 报告纠正 | Pass/Draw、资源反查、Shader/CBuffer、深度/混合状态、读回、查询成本、注入兼容 | 使用归档 Brief；旧游戏身份、Dual CSM、A2C 推断已纠偏，讲如何区分观察与推断 |
| [UEAgent](../UEAgent/AI-BRIEF.md) / ReflectCache | 工具调用 → 类型化执行/缓存 → 编译保存/读回 → Protocol 3.0 简化 | Native MCP/Gateway/VibeUE、反射/序列化、队列、会话绑定、Scratch 归属、编译失效、保存/恢复 | 读可靠执行和真实案例；OCC/hash/save token 是旧版取舍，不是当前架构；覆盖嵌套 ReflectCache |
| [test](../test/AI-BRIEF.md)：两题 | Q1 材质工具；Q2 单图→observation/review→SceneSpec→资产/Blender→UE→交付 | 图像歧义、尺度/透视、中间表示、可编辑性、确定性生成、资产匹配、材质/灯光、反馈、可移植性 | Q1 独立读 material-forge；Q2 沿版本/交付读过程，分清接受后重放与原图自动重建 |
| [BlendderMcp](../BlendderMcp/AI-BRIEF.md) | Gateway → 交互/后台 Blender → 几何读回/预览/导出 → 消费项目 | Python、进程/会话、结构化场景、坐标/单位、mesh 指标、导出/清理、CLI/HTTP | 读 worker/导出与失败记录，明确与 UEAgent、消费项目的分工 |
| [Kinesis](../Kinesis/AI-BRIEF.md) | 动作状态与 Root/Capsule 问题 → 动画系统设计/研究 | in-place/root motion、BlendSpace、Montage/Notify、GAS/Tags、Motion Warping、IK/重定向、中断 | 当前只读目标与部分约束；继续分清已做、研究、未来计划，不宣称完整系统已交付 |

## 外围目录与漏项检查

目录存在不等于值得独立讲一个项目；仍登记，避免只沿旧简历漏掉新经历。

| 来源 | 归属与后续动作 |
| --- | --- |
| `archive/TAProductionTools/PROJECT.md` | 待读取，检查独立生产工具经历或重复索引 |
| `work/rimworld/` | 已见 MOD 兼容和本地 Bridge/TextureBudget/SimulationBudget；读修改，提取依赖、资源/模拟性能经验 |
| `work/neoma/` | 已见长期 Agent 调度、持久化、真实 Provider 验证；补失败恢复、证据提交、可观察性 |
| `work/QQTechDigest/` | Python 事件接入、签名校验、SQLite 时间窗口、匿名化，作为工具工程补充 |
| `work/codexup/` | session 数据统计与空轮询，作为测量驱动优化案例候选 |
| `work/Omni/` | 系统职责/路由设计，关联具体实现，不重复计算经历 |
| `work/zhihu/` | 主要为 CLI 安装认证；有独立实现或排查才展开 |
| `work/unity/` | Brief 空模板，不据此宣称 Unity 项目经验；其余内容待扫 |
| `work/violina/` | 创作项目，本轮不读小说正文；存在可迁移软件实现时再纳入工具工程 |
| `work/review/` | 复习组织本身，不算新增技术经历 |
| `work/RenderDocMCP/` | 现存 README，合并到归档项目导航，不算第二个项目 |
| Git 删除/改名项目、外部技术拆解 | 继续查旧索引与 Git；EffectPipeline 已登记，其余找到来源才补写 |

## 跨项目反查

| 主干 | 回连项目 | 应解释的问题 |
| --- | --- | --- |
| 数学/坐标 | SSPR、NPR、AirWall、神经云、Scene Compiler | 投影/逆投影、切线空间、AABB、协方差、插值/梯度实际用在哪里 |
| GPU 数据/并行 | NiagaraGridBounds、slime、SSPR、GaussianVolume | scatter/gather、原子竞争、归约/scan/sort、格式、带宽、采样成本 |
| 连续场/数值 | PBF、Dye、SSPR、体积云 | 模拟与重建、密度/距离/到达时间、核支持域、积分、稳定性/误差 |
| 光照/材质/颜色 | Toon、NPR、Bifrost、GaussianVolume、神经材质 | BRDF/散射、阴影/GI、线性空间、HDR/色调映射、法线与几何分工 |
| UE/C++ | GaussianVolume、神经云、UEAgent、Kinesis | 模块、对象/代理、线程、生命周期、RDG/Global Shader、反射 |
| DCC/生产 | Houdini、VAT/VDM、NPR、BlendderMcp、test | 制作到运行如何保持语义、单位、索引、通道、引用一致 |
| 调试/取舍 | 全部，重点 RenderDocMCP/SSPR/NPR | 现象→假设→隔离变量→真实数据→验证修正；为何撤销路线 |

用 [TA 图谱](TA-KNOWLEDGE-GRAPH.md) 检查未连接领域，用 [复习卡](TECH-STACK-REVIEW-CARDS.md) 辅助讲解。知识不足与资料不足分别处理，不臆测用户薄弱项。

## 本轮纠正

- 旧评审“85%”没有逐项目覆盖依据，撤销，不换成另一个估算值。
- “十分之一”和旧 7 项补证据退出复习主线；历史测量继续留存供查阅。
- 归档、失败、等待验收都能贡献技术素材，只需讲准确尝试与结果。
- SSPR 双目录待对齐；RenderDocMCP 使用归档入口；UEAgent 当前已到 Protocol 3.0。
- 旧卡“上一轮失分”“必须背所有数字”等不作为掌握记录，问答前不判会不会。
- 本轮完成复习组织重构与首轮漏项盘点；全项目深挖按 BACKLOG 继续，尚不能宣称所有技术点已挖完。
