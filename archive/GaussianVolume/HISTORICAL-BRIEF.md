<!-- iris-project-kind: ue -->
# GaussianVolume AI Brief

> [!WARNING] **历史执行 Brief。** 本文件来自 2026-08-12 收尾前维护备份，保留完整
> G1–G38 合同与证据引用；当前权威归档状态见同目录 `AI-BRIEF.md`，不得恢复旧 Gate。

> **UEAgent first（UE live/MCP 强制前置）**：先导航到 [UEAgent 入口](../../work/UEAgent/AGENTS.md) 和 [HOTPATH](../../work/UEAgent/skills/ue-mcp-workflows/HOTPATH.md)，再处理本项目 brief。先读取目标项目 `Saved/UEAgent/route.json` 并运行 `compact_context.ps1`；只有 `CACHE_READ` 才停止 MCP，否则首次 live call 前运行 `doctor.ps1`。确认路由状态后才读取项目任务文档。纯离线源码/cache/config/log/文档分析可跳过 MCP，但不得声称 live editor 状态。

> 最终实现流程、固定预算训练规则与逐版本优化历史统一追加到 `IMPLEMENTATION-AND-OPTIMIZATION-LEDGER.md`；后续 AI 必须先读该账本，不得另建互相冲突的路线文档。

## 2026-07-31 最终收尾合同：G35 视觉 + G37 性能 + G38 显存

- 当前正式资产已从 G28 boundary-morph 回滚并冻结为原始标准 3DGS 15K geometry/opacity +
  VDB direct `J^0.4` 六轴 transport：
  `S3_Original15KGeometry_CurrentGamma04J_AngularSigma05.ply`，`311,993` 点、
  `64 B/point`、payload=`19.043 MiB`、SHA256=
  `AE7177BF3753E9905C34208A9D46A2647018F55A49FF13581A717BA1040EA0FB`。
  G24～G28 继续作为历史轮廓候选，不是当前部署资产。
- G31/G32 以原始 15K 边缘几何和双侧结构 coverage 桥接解决蓝底贯穿空槽；G33 保留
  轮廓切线引导；G35 用 `5×5 / 25 taps` coverage/depth joint bilateral 只过滤内部直射光
  latent，用户已确认效果并冻结。G34 稀疏大步长方向模糊因梳状笔刷失败并回滚。
- G37 只按 PS 已有 `AlphaCutoff=1/255` 保守收缩 HW quad support，不改 PLY、DGSM、
  composite 或保留像素。GS total `1.343→1.093 ms`（`-18.6%`），HW Raster
  `0.819→0.5665 ms`（`-30.8%`）；同帧 SVT feature=`3.241 ms`，GS=`1.093 ms`，
  比值=`2.97×`。用户确认效果冻结，G37 从性能候选晋升为当前运行时基线。
- G38 已完成 D3D12、1920×1080、每方案 3 次独立 `-game` 冷进程显存闭环。单个体积功能的
  净新增 RHI working set：SVT=`305.566 MiB`、GS=`66.476 MiB`，GS 少
  `239.090 MiB / 78.245%`，约为 SVT 的 `1/4.597`。GS 可拆为常驻
  `19.063 MiB` + 瞬态净增 `47.414 MiB`。
- `2343.980 MiB` 是包含 UE 场景、Lumen、TSR、VSM 与公共池的完整 GS 测试进程，绝不是
  单个 GS 资源。完整进程中位数为 SVT=`2664.178 MiB`、GS=`2343.980 MiB`，实际节省
  `320.198 MiB / 12.019%`。后续文档必须把“资源自身/RHI 增量”和“整个 UE 进程”分栏。
- 当前结论只对已签字的中远景静态云、当前 UE SVT U8、当前机位/灯光成立；不扩展为近景 Hero、
  动画、多光源、通用 VDB 替代或已胜过 NanoVDB。Development editor feature-time 与
  Development `-game` working set 已闭环；若发布 Shipping headline，再补 Shipping GPU 采样。
- 正式入口：`SOP-VDB-TO-GS-G35.md`；性能报告：
  `PERFORMANCE-VDB-VS-G35-G37-20260731.md`；显存报告：
  `VRAM-COLD-G37-VS-SVT-20260731.md`。

## 2026-07-30 历史收口合同：S3 312K 标准 3DGS 几何重光照云

- 当前主线已从规则 B8/G2 几何切换为 **标准 3DGS 自适应几何 + 单记录 shared-opacity 六轴静态 transport + DGSM**。当前 editor 日志实际加载
  `WDAS_S3_StandardGeometry312K_SharedOpacity_DirectJ_NoBakedDC.ply`：
  `311,993` points、`64 B/point`、primitive payload=`19,967,552 B`
  (`19.043 MiB`)；SHA256=`2CC4C78200369389E42A208A6BA2F3EEA6CB042362209B643D7F3A884B8A6607`。
- 几何来自标准 3DGS 训练。选用 `iteration_15000`，test
  L1=`0.00240468`、PSNR=`43.5372 dB`；`iteration_30000` test
  PSNR 回落到 `42.9078 dB`，因此不以更长训练冒充提升。
- 当前版本已经消除 G2 的规则点阵，并保留方向光、SkyAtmosphere 色温、
  DGSM 明暗关系和中远景重光照能力。用户确认项目可以进入收口阶段，但尚未
  完成最终 visual Gate。
- 唯一画质主线固定为三项：
  1. 合并外轮廓上的小鼓包和小凹口，只保留较大的云形起伏；
  2. 内部可以保留丰富团块，但不能让每个中小团块都穿透到外轮廓；
  3. 拉宽最外圈密度衰减，使云自然消散，而不是把整张颜色和内部光照一起变糊。
- 现有 2.25 px edge-only RGBA filter 与 4 px composite AABB padding 在 live
  viewport 中没有产生可辨识改善。根因是目标属于约十几到几十像素尺度的
  silhouette/coverage 结构，不是 1–2 px 锯齿。不得继续靠增加普通全图模糊半径
  追效果。
- 连续 RGBA alpha、多尺度轮廓训练与低频 coverage 重建均已执行。训练侧
  `w=0.05/500` 的 8-view alpha L1=`0.003763`（15K 基线=`0.004697`），但
  转入 UE 后中景轮廓更碎；更强权重与 opacity-only 均未胜过原 15K，因此主
  资产不替换。
- 当前自测冻结候选为原 15K 资产 + shared-opacity 标准 `3σ` 栅格 + 边界专用
  5×5 latent coverage 重建（4 px tap step，8 px 半径，9 px AABB pad）。
  内部像素只做 4-tap 边界探测后跳过，边界才执行 25-tap 核；没有新增 RT/pass，
  也不做全图 RGB blur。
- 五帧平均外轮廓指标虽为中景 GS/SVT roughness=`5.917/4.008`、远景
  `4.354/4.012`，但用户复核指出主体差异仍很大：GS 内部是独立小团块、深缝
  和高频明暗，SVT 则有连续低频体积包络。外轮廓指标不能再代替整体 visual
  Gate；当前候选判定失败。
- 用户调过的 Component、灯光、DGSM 与关卡参数属于冻结项；轮廓实验不得顺手
  改色温、对比度、opacity、power 或 relight 参数。
- 画质 Gate 通过前不发布性能胜出结论。`19.043 MiB` 只是 primitive/PLY
  payload，不等于 1080p 总 GPU working set；最终必须包含 visible/sort、
  GSColor、DGSM、RDG transient、完整 frame 和 volume pass。性能优化只在同机位
  profile 后按实测最大项推进，不以降画质、删关键 pass 或只报资产大小换结论。

## 2026-07-28 当前执行合同：WDAS 404K 单记录静态重光照 GS

- 当前交付对象固定为右侧同源 UE SVT 的中远景静态云 A/B，不再以旧 Hero 50K／NanoVDB 小资产阈值约束这条 WDAS 展示线。最终表示是 exact `404,524` 个空间 Gaussian，每核只存一次几何／opacity 和六轴静态光学传输；禁止恢复 `×6` 叶片展开。
- 固定预算候选来自 half grid 的 `8³` block moments，spatial sigma=`0.4`。相对旧 404K 宽核基线，held-out foreground-T PSNR `32.0247→35.6296 dB`、τ PSNR `38.6174→42.1720 dB`、edge L1 `0.08248→0.05874`；40-step extinction probe 未同时通过 foreground/edge Gate，已否决，不得部署或包装成训练提升。
- 发布 PLY 为 `WDAS_Cloud_Half_B8_Balanced_CompactTransportGS_404K.ply`：`404,524` records、`64 B/record`、payload=`25,889,536 B`、SHA256=`482b53c72728efc2fb78528dc951000bb8536ee4905500198f59090aba4f2e39`。画质改进不得增加 point count、leaf count、DGSM 分辨率或 per-point layout；`600–800K` 只允许在当前 visual Gate 明确失败且用户再次批准后进入。
- UE 的 Lumen indirect 曾硬编码 intensity=`1`，导致组件 `AmbientLightIntensityScale=0.025` 和 tint 对蓝色填充无效；共享合成入口现消费现有 intensity/tint uniform。该修复不增加 per-point／texture 数据。TechLab 已保存 Actor `Compact Transport GS + DGSM | WDAS Balanced / 404K`，自动加载、shader 编译和 D3D12 offscreen runtime 均通过；最终颜色、对比度、局部细节和方向光响应只等待用户 live viewport 签字。
- 2026-07-29 G2 live viewport 暴露正面受光偏黑。compact 六轴 `j_0..j_5` 与 runtime Y/Z angular weights 的顺序错配已修正。曾尝试令 compact 跳过疑似重复的 DGSM，但用户现场确认该版对比度拉不开、背面压不暗，已立即回滚；compact 继续严格使用 G2 原 `bEnableRNGDGSM=true` 配置。G2 PLY、关卡与其他 Actor 参数未修改；回滚后的 AbyssEditor 构建、链接和 `GaussianSplatting.CompactTransport` NullRHI 自动化测试均通过，用户复验后确认光照不再是阻断项。当前唯一视觉问题是 B8 规则点阵，下一步只推进 G13 exact-G2-preserving multi-scale split。
- 后续日落 A/B 又暴露独立光色缺口：VDB 已随 SkyAtmosphere 明显变红，Gaussian 仍近白。关卡只存在一盏已绑定的 `Light Source`，且 `Atmosphere Sun Light=true/index=0/per-pixel=false`，排除绑定与 G2 配置错误。runtime 已删除自行推导的 `Ground/Outer` 光槽 heuristic，scene-light 模式直接复用 UE `ResolvedView.DirectionalLightColor`，仅叠加原 `relight=0.7` 与 tint；manual-light 路径保持原语义。AbyssEditor 链接、NullRHI 与 DX12 offscreen 的 `GaussianSplatting.CompactTransport` 均通过并加载 exact `404,524` 点；仍待用户 live viewport 做日落光色复验，通过前不得再次写“仅余点阵”。
- 用户确认当前画面“效果好很多”，该状态已冻结为可恢复 Gate `WDAS404K-BALANCED-G1`：`artifacts/gates/2026-07-28_wdas_404k_balanced/`。后续试验不得原位覆盖 Gate 文件；没有同时通过数值和用户视觉验收时直接退回 G1。
- 后续固定预算扫描得到待验 G2 `sigma=0.38 + anisotropy boost=1.15`。在同一 1,000 held-out rays 上，相对 G1：foreground-T `+0.483 dB`、τ PSNR `+0.002 dB`、τ MAE `-1.62%`、edge `-2.79%`、Gabor energy/phase `-15.28%/-11.28%`，仍为 exact `404,524 × 64 B`。G2 已保存到 TechLab 并由独立 D3D12 重开 readback 确认；原视觉参数 `opacity=0.6`、power=`0.9`、relight=`0.7`、ambient=`0.01` 保持不变。必须经用户 live viewport 通过才可晋升。
- “同细节性能最优”只允许在同机位 visual Gate 通过后，再用同分辨率、等价灯光实测 complete GPU frame、Gaussian/SVT pass、steady/peak working set 才能落为最终结论；在此之前只声明结构预算不增和离线 screen-space 指标改善。

## 2026-07-28 WDAS Full 400K 对齐预览（大体积 VDB 窗口）

- 该分支只回答“大体积 VDB 能否用更高 Gaussian 预算做 screen-space 对齐”，不替换下方 50K compact 主线，也不得把 `400K` 对小型 Hero NanoVDB 的旧阈值混为一谈。源 WDAS VDB 为 `2.729 GiB`、`1,487,654,107` active voxels；UE U8 SVT 资产为 `594.8 MiB`，但磁盘/资产大小不是 GPU headline，完整 SVT 在当前 8 GiB 编辑器会话中只记录为超显存压力样本。
- screen-space 训练源固定为 full grid 的 quarter band-limit `498×338×613`；`4³` moment blocks 得到 `404,524` 个 occupied kernels，再把最低优先级的致密内核合并到相邻保留核，精确得到 `400,000`，总质量相对误差=`0`。这不是逐体素复刻 full VDB。
- 正式恢复训练为 `200` steps、8 views（6 train / 2 held-out）、5×5 patches。held-out full-T PSNR `31.927→32.145 dB`、foreground-T `31.531→31.757 dB`、Gabor energy L1 `0.002868→0.002798`、phase-energy L1 `0.005271→0.005202`；τ PSNR `39.834→39.814 dB`、edge L1 `0.075420→0.075498`，因此严格 numeric gate=`false`，不得伪造为全面数值提升，最终取舍由 UE live visual Gate 决定。
- 方向光 transport 已为全部 `400,000` kernels 烘焙六轴 τ，额外 `12 B/kernel`，与基础 packed primitive 合计仍为 `48 B/kernel`；当前预览显式固定 `r.GaussianVolume.CandidatePoolCapacity=1048576`，primitive+pool 下限约 `22.31 MiB`，auxiliary/transient/实际 allocation 仍须单独测量后才能形成显存结论。
- UE 当前只启用 `GaussianVolume | WDAS Full Screen-Matched 400K Directional`，transform=`location(1440,-400,350), rotation(0,0,0), scale(1,1,1)`；transfer 固定 `DensityMultiplier=1, DensityGamma=1, DirectionalShadowDensityScale=0.1`，方向光/天光 scale=`0.516019/0.3`。JSON：`artifacts/wdas_full_screen400k_trained_directional/GaussianVolume_WDAS_FullScreen400K_Directional.json`。

## 2026-07-28 固定 50K 质量主线（后续 AI 不得改回旧路线）

- 当前正向候选是 `organic moment contraction → progressive frequency supervision → extinction calibration`，最终仍为 exact `50,000` 个普通 volumetric Gaussian，导出 `omega=0`；Gabor 只作为离线频率损失，不增加运行时 kernel 字段、MLP、采样或显存。
- 有机收缩只在 PCA 方向不明确的近各向同性节点扰动切面和质量二分相位；强各向异性结构仍沿数据主轴，每个 leaf 继续做质量守恒的一、二阶矩合并。禁止恢复固定网格／严格 50:50 的规则 kd-tree 作为当前质量起点。
- V3 的 UE visual Gate 已失败：黑团主要来自过强的 directional-τ 映射，点阵和细节丢失来自 UE `DensityGamma>1` 对低密度尾部的压制；同时 V3 的 center/covariance 与 V2 完全相同，不能把它描述为几何或各向异性训练成功。
- 当前候选改为 V6：训练实际更新 center/covariance，并以体积守恒的 log-eigenvalue boost 将各向异性 ratio 的 P50/P90 从 V3 的 `1.60/1.97` 提到 `2.01/2.83`；held-out τ PSNR=`19.893 dB`、foreground-T PSNR=`18.100 dB`、Gabor-energy L1=`0.02103`。UE visual Gate 必须固定线性 transfer `DensityMultiplier=1, DensityGamma=1` 和 `DirectionalShadowDensityScale=0.1`；当前 Actor 已导入 V6 directional JSON，最终画质仍等待用户 live viewport 签字。

## 不可漂移项目合同（后续 AI 先读）

本项目只交付一个**正向作品集命题**：在限定的 1080p 中远景静态云窗口内，Gaussian volumetric primitives 在 **screen-space matched quality** 下，能以比 VDB/SVT 更低的总运行时成本完成显示。这里的“总成本”同时包括 GPU working set、峰值/transient、volume pass 与完整帧 GPU 时间；不得把项目改写成逐体素压缩、通用 VDB 替代或负结果研究案例。若正向窗口尚未闭环，只能标记为内部未完成，未经用户明确同意不得把失败本身包装成最终案例。

### 冻结比较口径

- 目标平台固定为 UE 5.8、RTX 5060、1920×1080；资产固定为同源静态单 density Hero cloud；场景固定为一盏方向光＋SkyLight；近景贴脸、动画、多光源与通用资产不进入承诺。
- 离线拟合、训练与 transport bake 的耗时不计入运行时胜负；但最终导出的全部 density/transport 数据都必须计入 GPU payload。
- “同质量”只按最终屏幕 T/tau、轮廓、高频细节和用户 live viewport 签字判断，不要求逐体素复刻 VDB。所有性能 A/B 必须先过同一 screen-space quality gate。
- VDB 基线同时保留 UE U8 SVT 与更强的 NanoVDB Fp8/FpN＋HDDA；不得只选较弱基线。灯光必须等价：不能拿有静态自阴影的 Gaussian 对无自阴影 VDB 直接宣称同功能 GPU 时间。
- 内存统计必须包含 primitive、candidate、tile/instance/light/LOD buffers、page table/cache 与 owned transient；磁盘文件、raw primitive buffer 或关闭关键 pass 不能作为 headline。

### 已建立的底层正向窗口

- 真实 Hero grid 的最强本地 resident baseline 是 NanoVDB Fp8 `9.586 MiB`。采用 `48 B/kernel`、固定 `512K` candidate pool 和 1080p auxiliary 后，Gaussian 50K 为 `4.320 MiB`，小 `2.22×`；最多 `165,032` kernels 才能保持任意内存优势，最多 `60,330` kernels 才能保持 `2×` 优势。
- 8 个中远景机位的理论工作量：Gaussian 平均 `115.44` tile tests/pixel、`24.85` 个解析 support hits/pixel；dense/SVT 为 `140.87` samples/ray；NanoVDB 为 `43.87–54.12` 个昂贵三线性 samples/ray、`63.91–65.96` 次总循环/ray。
- 因此运行时结论分两层：相对 dense/SVT 存在宽正窗口；相对 NanoVDB 的正窗口要求单次 Gaussian 解析积分成本低于约 `1.77–2.18×` NanoVDB 三线性采样，并继续降低当前 tile 粗化带来的 `4.65×` 理想 footprint 放大。理论工作量不是毫秒，最终必须由 RTX 5060 同质量实测闭环。
- Gaussian 的结构优势是连续核用一次解析积分替代长距离采样、O(N) 紧凑 payload、统一外观下 optical depth 可交换且无需排序、静态单方向光可用每核六向 tau 做 O(1) transport。VDB 的结构优势是 HDDA 空区跳跃、前向 early termination、原生 mip/filter/order，以及近景/高频/稀疏拓扑下不会发生屏幕 overlap 爆炸。

### 不可跳过的运行时因子

任何后续“更省”结论都必须逐项覆盖：resident/peak/transient memory、上传与实例共享、cull/project、candidate count/prefix/scatter 与 atomics、每像素 reject/解析积分或 HDDA/三线性采样、early termination、LOD/filter、scene-depth occlusion、灯光与合成、带宽/cache、SFU/ALU、register occupancy、warp divergence、分辨率与 close-up overlap。实现细节必须和表示层优势分开标注。

### 硬性防漂移 Gate

- Compact/published 路径必须显式固定 `r.GaussianVolume.CandidatePoolCapacity=524288`，并证明全部发布机位 overflow=`0`。当前插件默认 `0` 是 exact worst-case quality reference；它会破坏 bounded-memory 结论，不能进入内存 headline。
- 最终表示必须 `≤60,330` kernels 才能宣称相对最强本地 baseline 的 `2×` resident 优势；`60,331–165,032` 只能宣称小于 `2×` 的优势；超过 `165,032` 不得宣称胜过 NanoVDB Fp8。
- GPU 时间只有在 matched quality、等价灯光、相同分辨率/机位、无 candidate 截断下，Gaussian volume pass 与完整 frame 都优于对应基线时才能写“运行更省”。理论模型只用于设门槛，不替代实测。
- 任何 AI 想改变上述目标、基线、质量口径、场景窗口或把负结果升级为作品集叙事，必须先停下并向用户申请范围变更。

底层模拟与完整因子表的可执行来源：`mvp/simulate_gaussian_vs_vdb.py`；当前报告：`artifacts/storage_simulation/gaussian_vs_vdb.md`。本合同优先于下方历史 Gate 记录；历史负分支只作证据，不得重新定义项目身份。

## 2026-07-27 Degree-2 视觉 Gate

- 当前用户已接受 degree-1 预览作为继续训练基线；训练仍只更新 light-conditioned `J`，位置、density/opacity、空间 covariance、TView、temporal 与 cross-covariance 全部冻结。
- degree-2 从已接受的 1K PLY 初始化：旧 4 个 SH 系数逐值复制，新增 5 个系数为零。全量 `1,112,674` 点 parity 检查为旧字段 max error=`0`、新增系数 max abs=`0`。
- 3K 训练的 held-out/train J PSNR 在 1K/2K/3K 分别为 `22.03/26.22`、`21.89/26.85`、`21.75/27.26 dB`；确认 2K 后开始过拟合，因此选用 1K checkpoint。
- 选中 PLY 为 `271,494,101 B`、61 fields、SHA256=`0071EAAEAF2A4540333A0EE9FD54AEC8C4A5E7B25104DFEEC8408673148A5ADC`；静态参数相对已接受 degree-1 PLY 的 max error=`0`。
- TechLab 当前未保存加载 `7DRGS CGHEVEN Hero Congestus 50 Degree 2 1K 1.112M PREVIEW`，保留 dual-HG `0.65/-0.2/0.1`、phase intensity=`0.35`。下一步只等待用户 live viewport 视觉确认；确认前不扩正式 16×24 数据、不裁剪。

该历史 Gate 最后更新：2026-07-27

## 2026-07-27 当前 Gate

- 唯一主线仍为 7DRGS。WDAS cloud 因源资产本身底部偏平、轮廓不适合最终展示而退出当前 Gate；边界检查证明不是转换器裁掉了半边。
- 当前 quality reference 改用公开 CC0 的 CGHEVEN `Hero Congestus Cloud VDB - 50`。原始 density grid 有效分辨率为 `238×264×403`，转换前六面各加 `8 voxels` 空白，最终 dense grid=`254×280×419`，所有外边界 density=`0`。
- 最高细节解析版使用 block=`2`、`1,112,674` 个独立空间 Gaussian、6 个轴向光叶片，共 `6,676,044` 个 7D points。PLY=`2,136,336,393 B`，SHA256=`FD1E5F2B1895742611E1CD20452A76ABCB06B3BB42E8D231168BA6A3C7792A73`。
- 该版本仍是 VDB 的解析抬升代理，不是论文训练器输出。当前目的是先确认能否达到可接受的 Hero cloud 细节和方向重光照上限，不在签字前宣称性能或表示优势。
- UE runtime 已接入 DirectionalLight 的 editor live refresh 与 SkyLight ambient fill；`AbyssEditor` 构建成功。TechLab 已保存可见的 `7DRGS CGHEVEN Hero Congestus 50 B2 Ultra 6.68M`，以及默认隐藏的同源 UE SVT U8 A/B。
- B2 Ultra 首次 D3D12 加载暴露 Slice 的单维 dispatch 超过 `65,535` 组；Slice 与 Preprocess 已统一改用 UE 原生 wrapped dispatch，冷编译和重启验证无 ensure、shader error 或 GPU crash。
- B2 Ultra 解析版仍是已签字的质量 teacher。`1,112,674` 点训练版完成 `500→15,000` 后虽 finite、Mask IoU=`0.951`、inverse-depth L1=`0.00319`，但 held-out foreground J/TView=`16.54/14.83 dB`、τ L1=`3.81`；用户在 live viewport 看到严重颗粒噪声与细节模糊，画质 Gate 明确失败。
- 根因不是单纯“灯光方向太少”：旧 B2 init 只从六叶片取第一叶并只复制空间属性，opacity 以 `0.1` 冷启动后被冻结；SH/covariance 正则未进入主 loss，light condition 还能改变有效空间 covariance。15K 只保留负证据，禁止续跑或裁剪。
- B2 teacher distillation 的初始化链已修正：六叶片按空间点聚合，B2 opacity/TView 保留，六个轴向响应拟合为 light-conditioned `J` degree-1 SH；静态 temporal/cross-covariance 固定，SH、teacher-anchor 与能量有界项已进入主 loss。全量初始化为 `1,112,674` 点、`235,888,349 B`，SHA256=`B65F489AC60A2E426C970F5C093A58D57B18CE43666F37E79D97EEBC34DDCC62`。
- 全量 `1K` smoke 已完成。首轮证明 opacity 可训练会再次漂到 `0.998`，因此最终口径冻结 opacity／几何／TView，只训练 `J`，并采用 teacher-anchor=`10`、energy=`1`。最终 1K 用时约 `78 s`；所有静态参数最大误差=`0`，held-out J PSNR=`21.93 dB`、train=`24.98 dB`，gap=`3.06 dB`，六轴 anchor drift RMSE=`0.01282`。
- UE runtime patch 已应用，`FGS7DSlicingCS` 冷重编译成功；1K PLY 已加载为 `7DRGS CGHEVEN Hero Congestus 50 Teacher 1K 1.112M PREVIEW`，point readback=`1,112,674`。当前下一 Gate 只剩用户 live viewport 画质验收；通过后才扩为正式 teacher 数据并训练 matched-quality student，再依次尝试 `900K→800K`。

> 作品集裁决：按 `SPEC.md` 已确认的新方向继续。先完成静态 VDB→官方 Gaussian 拟合→UE 的可信链路和表示上限，再做总 working-set 优化；不得恢复 Spline/Structured Gaussian Field FX。

## 项目身份

GaussianVolume 是一个 UE 5.8 静态高细节体积代理案例。目标不是从零发明完整体积算法，而是把已有 volumetric primitives、官方拟合方法与 UE 实时调度组合起来，回答一个可测量的生产问题：

> 在匹配 optical-depth/transmittance 质量时，能否用更小的稳态 GPU working set 实时显示中远景单密度 VDB？

近景 Hero、动画与通用 VDB 替代不在当前承诺内。最终只保留一个主要研究赌注；原创上探失败时，官方 Gaussian 拟合＋UE 解析渲染的保底案例仍必须成立。

## 当前技术路线

- **表示保底**：Don't Splat Your Gaussians / Gabor Fields 的 Gaussian volumetric primitives 与解析主射线积分。
- **当前主线**：7DRGS。先把真实 VDB 转成能够匹配 SVT 细节并响应方向光的 7D Gaussian 表示，再优化点数、方向叶片、排序与光栅成本。
- **已归档精度层**：Q2＋4K signed Gabor residual 已训练到 step 1200，但用户人工画质验收失败，不再进入调参、运行时优化或同预算 A/B。
- **产品比较**：同源 UE 8-bit SVT/Heterogeneous Volume 与 NanoVDB Fp8/FpN＋HDDA；不拿磁盘大小、primitive buffer 或关闭关键 Pass 冒充总显存优势。

## 当前 Gate 与执行顺序

1. 已跑通 `smoke2.vdb` 的官方 Gaussian-only 端到端链路，并以 Q2 10K 建立当前高保真上限；
2. Q3 24K@120 已按同一 held-out 协议否决，Q2 10K 继续作为高保真上限；
3. 同源 UE SVT 与 NanoVDB 已进入 D3D12 实跑；tight PBF、512K pool、32 B packing、overflow telemetry、原位合成与 1/4/16 平移实例共享已经落地；
4. 助手不再维护固定机位、自动截图或截图微调；用户负责 live viewport 画面、transfer function 和截图，助手只推进云表示、shader、显存、性能与数值验证；
5. pool-free 已确认真实覆盖云且解决 candidate tile 格，但 close-up Gate 已失败：full-res 细节可接受但贴脸 `50+ ms`；0.5× 仍约 `25 ms` 且细节不通过；0.25× 只会继续牺牲画质；该分支仅保留为负实验；
6. Q2＋4K Gabor 已完成 step 1200 和最终导出，但用户确认画质太差，路线正式归档；不再做灯光调参、性能 A/B 或 residual 优化。Q3、Epanechnikov、pool-free 主线与固定机位截图仍冻结。
7. 7DRGS 是历史高质量参考：B2 Ultra 解析质量 reference 已通过，15K 训练版因颗粒和模糊判负；H11 又证明继续 image-space `J` loss 不会产生可辨认自阴影。H12 改用逐点 light-space T，并修复现场 `Dual SH=false` 覆盖；H13 的六轴 tau 数据、上传和 shader 消费已由 `LightTransmittance` 方向梯度验证。两项当时仍待视觉签字，后续已被上方 S3/G35/G37/G38 主线取代，不再作为当前待办。

当前不继续堆启发式 VDB 聚合器、Spline FX、通用资产化或第二个研究问题。

## 已验证事实

- 官方 `gabor_fields` 基线固定在提交 `009816f8dac566f343c292caddb231cab6a6099a`，Gaussian-only 等上下界问题已有可复现补丁。
- `smoke2.vdb` 已跑通 VDB→密集网格→官方 Gaussian 拟合→PLY→GaussianVolume JSON→UE；64、1K、4K、Q2 10K 资产均已导入验证。
- Q3 以 `24,576` 个 Gaussian、明确关闭 Gabor 优化运行到 120 checkpoint。相同 8 个 held-out 视角、512×512、64 spp 下，Q3 相对 Q2 的 full-T/foreground-T/τ PSNR 分别低 `14.00/14.52/22.41 dB`，只有 silhouette IoU 从 `0.629` 升至 `0.686`；Gate 否决并停止训练，Q3 不进入 UE 主线。
- Q2 导出 `9,944` primitives。稳定顺序积分器改用显式非负垂距，避免 `C-B²/A` 的灾难性消减；8 个未见视角、512×512、64 spp 的结果为 full-T `48.60 dB`、foreground-T `36.93 dB`、τ `28.07 dB`、silhouette IoU `0.629`、negative-τ fraction `0`。Q1 4K 的 full/foreground-T `36.11/24.22 dB` 只作为下限。
- 同源 UE SVT 已生成并导入：U8=`PF_R8`、F16=`PF_R16F`，均为 `191×610×178`、1 帧、7 mip；材质参数用 getter 写后读回验证。
- 已从 TechLab 生成独立 `EmptyBaseline`、`SVT_U8`、`SVT_F16` 三个测量关卡；SVT actor 依据原始 frame transform 对齐到与 Gaussian 相同的 1000 cm padded-volume 坐标，最长轴 extent=`500 cm`，各关卡不混放 Gaussian。
- 已直接用 UE 5.8 随附的 OpenVDB/NanoVDB 源与库构建官方 converter；同源 Fp8/FpN（absolute error=`0.001`）的 raw GPU grid 分别为 `7,048,192` / `4,820,928` bytes。插件已增加 `NanoVDB Volume Baseline` Actor、PNanoVDB HLSL accessor、HDDA 空节点跳跃、独立 `NanoVDBBaseline` GPU tag，以及对齐的 Fp8/FpN 关卡；Editor 冷编译和 NullRHI 文件解析/关卡保存通过。
- 显存采集已改为真实 `-game` 冷进程；Windows `GPU Process Memory` 记录进程 dedicated/shared memory，延迟到 warm frame 的 `rhi.DumpMemory` / `rhi.DumpResourceMemory Transient=all` 负责归因，SVT 同时读取 UE 原生 `SparseVolumeTexture Memory`。
- TechLab 保留同 transform 的 Q2、最终 step-1200 Gabor、同源 SVT U8 与 `7DRGS Smoke2 VDB B4 389K Sharp 6-Light` Actor 作为历史对照；当前只启用并显示 7DRGS，Gabor/Q2/SVT 均关闭。
- GPU candidate 已改为 `count → prefix scan → scatter` 紧凑全局池。自由转镜头发现旧 tile culling 用错 `ViewToWorld` 列向量，现已改为 UE 官方 `GetViewRight()/GetViewUp()`，与主射线的 `ClipToWorld` 坐标一致。默认容量回到 `524,288 IDs`、索引池 `2 MiB`；最终 1080p runtime requested/granted=`142,979/142,979`、overflow=`0`、truncated tiles=`0`。旧 128K 固定机位 tight-PBF 收益数字须重采后才能作为最终证据。
- 512K Compute 在用户贴脸视角 requested/granted=`1,362,172/524,288`、overflow=`837,884`、truncated tiles=`1,110/1,110`；整屏 tile 格来自丢弃 `61.5%` candidates，不是 Gaussian/Gabor 表示细节。该视角无截断的最低逻辑 working set=`5.517 MiB`，已高于 NanoVDB FpN raw grid `4.598 MiB`，因此不扩池挽救近景；近景继续使用原 VDB，Gaussian Gate 限定中远景。
- primitive 已从 64 B 压到精确 32 B；uniform Q2 的未使用 per-primitive LightTau 又从 9,944 floats 缩到 1 float。最终 1080p primitive=`318,208 B`、candidate=`2,097,152 B`、auxiliary=`32,668 B`，逻辑合计 `2,448,028 B`（`2.335 MiB`）。shader 直接在 Gaussian local space 做解析积分，不常驻解包副本。
- 同一统一外观 Q2 云可用 `AdditionalInstanceOffsets` 添加共享平移副本。512K pool 下 1/4/16 份的 1280×720 逻辑 working set=`2,430,108/2,430,236/2,430,620 B`；D3D12 的外置 instance buffer 有 `64 KiB` 最小分配，所以真实 allocation 是 1→4 增约 `64 KiB`、4→16 不再增加。旧 128K 的 4/16 overflow 数字只保留为历史压力测试，当前默认值仍需重采连续相机与多实例峰值。
- 正式 `-game` 中，原位 scene-color 合成删除两个跨帧保留的全屏输出纹理。512K pool 下最终 1080p RHI 命名 Gaussian 资源为 `2.344 MiB`；输入 SceneColor 没有 UAV flag 时会自动 copy 回退，编辑器显存不进入 headline。对照同源 NanoVDB FpN raw grid `4.598 MiB` 与 UE SVT U8 原生 runtime GPU memory `12.402 MiB`，当前 runtime 自定义资源口径分别约小 `1.96×` 与 `5.29×`；在用户完成 matched-quality/transfer-function 签字前，这不是最终同画质结论。
- 旧 128K／错误 camera-basis 版本的 500 帧 GPU 数据不再作为最终性能结论。修复后已完成 D3D12、1920×1080、overflow=`0` 的运行验证；正式 GPU P50/P95 在用户确认自由镜头画面后重采。
- `r.GaussianVolume.PoolFreeRaster=1` 已由用户确认真实覆盖云，近景无 candidate tile 格。为处理贴脸 `50+ ms` fill-rate，分支改为 0.5× R16F `sum(tau)`＋全分辨率一次 resolve；powder 由总 tau 计算。1920×1080 正式 runtime 只有 tau=`1.1875 MiB`＋primitive=`0.3125 MiB`，合计 `1.50 MiB`，没有 candidate pool 或额外全屏输出。
- 同一非贴脸 runtime 视角 500 帧中，full-res→0.5× 的 pool-free pass P50/P95=`1.9661/2.1377`→`0.5996/0.6007 ms`，完整 GPU P50/P95=`6.8625/7.5071`→`5.4609/5.5104 ms`。用户随后在真实贴脸视角确认：full-res 可保细节但 `50+ ms`，0.5× 仍约 `25 ms` 且细节不通过；因此该分支 Gate 失败，不能用非贴脸采样冒充实时结论。
- UE 5.8 已用 `RDG_EVENT_SCOPE_STAT` 注册顶层 `GaussianVolume` GPU stat；Editor/Game/Shipping 编译链接通过，重启后的 GPU trace 已实际记录该 scope。`stat gpu` 显示总项，现有 RDG event 继续为 `ProfileGPU` 提供 Count/Prefix/Scatter/LightTau/RayTrace 细分。
- UE 展示密度可由用户直接调节；上述 PSNR 只对应原始 `DensityMultiplier=1.0` 拟合输出。Actor/根组件的 editor、runtime 可见性现会统一驱动渲染注册，关闭 Visible 或 Outliner 眼睛不会再残留云体；冷编译和现有自动化测试通过。
- 新增的解析 VDB→7DRGS 转换把 `smoke2_vdb.npy` 以 block=4 聚合为 `64,815` 个空间样本，并用 6 个轴向光照叶片展开为 `388,890` 个 7D Gaussian；角向 sigma=`0.5`、空间 sigma=`0.55`。相同机位隔离显示确认整体轮廓和密度层级已接近同源 SVT，方向从 `+X` 切到 `-X` 时画面响应明确，但细边界仍更颗粒化。
- UE 7DRGS runtime 增加显式 `RefreshRenderingParameters()`，脚本修改方向/颜色后不再停留在旧 render-thread 参数；PLY 路径保持项目相对路径。`AbyssEditor` 冷构建成功，TechLab 已保存真实 VDB 代理 Actor。
- 同一 TechLab、同机位、同分辨率的隔离 `ProfileGPU` 单帧取证：7DRGS 整帧=`9.19 ms`、自身=`1.799 ms`（Slice=`0.356`、Preprocess=`0.103`、Sort=`0.249`、HW Raster=`1.039 ms`）；SVT U8 整帧=`8.43 ms`、HeterogeneousVolumes=`1.070 ms`。当前高细节解析 7DRGS 比 SVT U8 慢约 `0.73 ms` 的体积范围，尚未形成性能优势。
- 横向方法审计结论：公开 7DGS 的角维是 view direction 而非 light；BiGS 证明静态 relighting 应固定几何并约束 light/view appearance，但完整 `1089 params/primitive` 不适合直接套用；LightGaussian/PUP 一类压缩方法都先建立高质量 teacher，再 prune/recover。当前采用这些原则，不转向完整 BiGS、neural shader 或第二套 renderer。
- 15K checkpoint 审计：xyz/scale/rotation/opacity 不变且 opacity 始终 `0.1`；`J` DC std=`0.169→1.146`、最大系数=`10.236`，directional/full Cholesky diagonal p99 约 `2.081→106.747`、抽样最大=`4269.5`，训练 J PSNR=`48.10 dB` 却未见前景仅 `16.54 dB`。这是错误初始化与无约束过拟合，不是 UE AA 或硬件问题。
- Gabor 已从 Adam step `720` 完成到 `1200`，恢复优化耗时 `5 h 38 min`，最终 32 视角 clean PSNR=`31.1498 dB`，导出 `9,944 Gaussian + 4,096 Gabor = 14,040` primitives，其中 `3,544` 个 Gabor 为负权重 residual。用户在 UE 人工验收后判定画质太差，路线归档。

## 仍未成立

- NanoVDB CPU 解析、GPU buffer 上传和 HDDA shader 已在 D3D12 `-game` 执行并完成内存归因，但画面与 transfer function 尚未由用户签字；
- 512K compact-pool Compute 的贴脸边界已确认会全屏 overflow，当前只闭环产品承诺内的中远景 matched-quality 与最坏 GPU；pool-free 不再承担该 Gate；
- 当前资源口径、60 FPS 与 Gaussian 1/4/16 表示共享已出现明显优势，但尚未得到用户的 matched-quality/transfer-function 签字、峰值/稳态与带宽数据，因此作品集 headline 仍未成立；
- `GaussianVolume` GPU stat 已给出完整成本；不设独立 pass-time 成功阈值；
- support/PBF 的 candidate telemetry、overflow 与 GPU tag 已收口；最终 UE 画面由用户手动签字；
- 用户调整的 `DensityMultiplier` 是展示调色，不得作为 Q2 拟合精度证据；
- quality reference 对所有数量启用 Gaussian-base `LightTauCS`，只在数据或方向光变化时重建并跨帧缓存；当前只声明静态方向光＋天光可重光照，不声明已实时优化。
- 当前 7DRGS 是从真实 VDB 解析抬升出的可运行代理，不是原论文完整训练结果；它已证明数据/重光照/渲染链可用，但本次同源 GPU A/B 未胜过 UE SVT，不能写成“7DRGS 更快”。
- 训练压缩尚未成立：15K 是失败 student，不能代表 B2 已被 1.112M matched-quality 重建；在新 `1–2K` smoke 通过前不启动正式训练、裁剪或性能宣传。
- Gabor 的最终训练、JSON、UE Actor 和代码只作为负实验保留；不再占用当前 Gate、自动任务或 GPU。

## 文档边界

- `SPEC.md`：唯一当前研究协议；
- `BACKLOG.md`：只列按 Gate 排序的可执行动作；
- `LOG.md`：追加式事实、决定和回滚；
- `notes/archive/`：失败分支，不得覆盖主线。

可以写“复现并工程扩展”“工程组合”“预算调度研究”。在完整检索、实验和消融前，不写“首次”“原创算法”或“通用 VDB 替代”。

## 2026-07-31 G28 S3 closeout（历史节点，已被 G31～G38 取代）

当前项目已完成 S3 的中景/远景视觉验收 Gate，并冻结一条可回归主线：VDB teacher → 标准
3DGS 15K 几何 → 12.5% view-boundary、150-step 轮廓候选 → 六列 `J^0.4` compact
transport → UE GPU sort/HW Quad/shared-opacity composite/DGSM/phase。冻结 PLY 为
`Plugins/GaussianSplattingForUnrealEngine/Content/Data/S3BoundaryMorphMask125_20260731/S3_ViewBoundaryMorph_Mask125_150_MassNormalized_FJ.ply`
（`311,993` 点，`64 B/point`，约 `19.043 MiB`，SHA256=
`5F0F3F2D4D72523026382966073B04CAE464780DF1DF21EF1E9C9483AF4421B`）。

验收通过的是中远景轮廓/体积层次/方向光与天光重光照的可用性；近景 Hero、严格 SVT
matched-quality 和性能领先不在承诺内。opacity=`0.4`、power=`1.0`、relight=`0.3`、
ambient=`0.01`、DGSM density=`0.45` 及 phase/Actor transform 保持原配置。AlphaCutoff、
内部 alpha、统一 footprint、全图 blur 等支路均已回滚；它们只保留在日志中作为负结果。

该段只记录 G28 当时的阶段结论。当前资产、视觉、性能和显存事实以上方 G35/G37/G38
最终收尾合同为准；`19.043 MiB` 仍只表示 PLY payload，单个 GS 完整 RHI working set
实测为 `66.476 MiB`。
