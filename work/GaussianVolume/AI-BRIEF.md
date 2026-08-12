# GaussianVolume AI Brief

## 2026-07-28 当前交接状态

- 当前只保留两个 Hero 候选：H12=`1,112,674` 点的 7DRGS 质量参考，H13=`50,000` kernels、`48 B/kernel` 的 Gaussian Volume 紧凑候选；同源 SVT 必须保持可见用于 A/B。
- H13 的 `LightTransmittance` debug view 已显示稳定的黑白方向梯度，证明六轴 τ 数据、上传与 shader 消费链路均已接通；`Final` 也能看到方向明暗。尚未完成的只有用户对阴影强度的视觉签字，不再重复训练或重接 transport。
- H12 首次没有自阴影的现场根因是 Actor 实例 `Dual SH=false`，因此走了不重建 light-conditioned `J` 的旧 composite；现已恢复 `Dual SH=true`，ambient scale=`0`。恢复后的最终视觉复核曾被中断，仍待用户签字。
- 最后一次可靠现场读回：H13 Density=`1.32799995`、Gamma=`1.245066`、Directional Shadow Density Scale=`0.304266`；H12、H13、SVT 均 visible，H0 不在当前关卡。UE 地图、导入 PLY/JSON 和 Actor 实例覆盖值不在本仓库，不能从 Git 状态推断关卡是否已保存。
- 下一步只做 H12 Final 复核与 H13 阴影强度签字；两项通过后再做 matched-quality SVT/NanoVDB GPU time 与 working-set A/B。不得默认启动 H14、正式 16×24 数据或新训练。
- 两套运行时源码均已版本化：`ue-plugin/GaussianVolume/` 与 `ue-plugin/GaussianSplattingForUnrealEngine/`。后者是本项目的 clean-room `0.1-reconstruction`，提交源码／shader，不提交 Content 下的大体积资产。

最后更新：2026-07-28

## 2026-07-27 Degree-2 历史 Gate

- 当前用户已接受 degree-1 预览作为继续训练基线；训练仍只更新 light-conditioned `J`，位置、density/opacity、空间 covariance、TView、temporal 与 cross-covariance 全部冻结。
- degree-2 从已接受的 1K PLY 初始化：旧 4 个 SH 系数逐值复制，新增 5 个系数为零。全量 `1,112,674` 点 parity 检查为旧字段 max error=`0`、新增系数 max abs=`0`。
- 3K 训练的 held-out/train J PSNR 在 1K/2K/3K 分别为 `22.03/26.22`、`21.89/26.85`、`21.75/27.26 dB`；确认 2K 后开始过拟合，因此选用 1K checkpoint。
- 选中 PLY 为 `271,494,101 B`、61 fields、SHA256=`0071EAAEAF2A4540333A0EE9FD54AEC8C4A5E7B25104DFEEC8408673148A5ADC`；静态参数相对已接受 degree-1 PLY 的 max error=`0`。
- TechLab 当前未保存加载 `7DRGS CGHEVEN Hero Congestus 50 Degree 2 1K 1.112M PREVIEW`，保留 dual-HG `0.65/-0.2/0.1`、phase intensity=`0.35`。下一步只等待用户 live viewport 视觉确认；确认前不扩正式 16×24 数据、不裁剪。

## 2026-07-27 历史 Gate

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
7. 7DRGS 仍是唯一高质量参考；H11 已证明继续 image-space `J` loss 不会产生可辨认自阴影。当前只复核 H12 的 Dual SH 修复并签字 H13 阴影强度；两项未完成前不扩正式数据、不裁剪、不启动新版本。

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
