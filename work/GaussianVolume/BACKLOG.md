# GaussianVolume · BACKLOG

> 只列 `SPEC.md` 当前 Gate。当前唯一主线为 7DRGS；Gabor、Q3、Epanechnikov 与 pool-free 只保留历史记录。

## P0 — 可复现端到端链路

- [x] 固定官方 `gabor_fields` 提交与 Gaussian-only 补丁。
- [x] 跑通 `smoke2.vdb` → dense grid → Gaussian fit → PLY → UE JSON。
- [x] UE 导入 64/1K/4K 资产并通过插件自动化测试。
- [x] 固定训练外 Halton 视角 32–39，输出 τ/T/轮廓指标与 checkpoint hash。
- [x] 生成并导入同源 UE SVT U8/F16，验证分辨率、格式、frame transform 与材质参数。
- [x] Q2 10K 导出 9,944 primitives，完成未见视角评估并导入 UE。
- [x] Q3 24K@120 用同一 8-view/64-spp 协议评估并否决：full/foreground-T 与 τ PSNR 相对 Q2 下降 `14.00/14.52/22.41 dB`；停止训练，保留 Q2。

## P1 — 表示质量 Gate

- [x] 对 Q1/Q2 统一报告 T/τ PSNR、silhouette IoU 与负密度；Q2 full/foreground-T=`48.60/36.93 dB`、τ=`28.07 dB`、IoU=`0.629`、negative-τ=`0`。
- [ ] 旧 heuristic block/adaptive 4K/10K/30K 只保留失败基线；若需要作品集画面对照，由用户在 live viewport 手动完成。
- [x] 建立独立 Empty/U8/F16 对照关卡；SVT 与 Gaussian 对齐到相同 1000 cm padded-volume 坐标。
- [ ] 在 live viewport 对齐 transfer function，并由用户签字中远景质量。
- [x] Q3 24K 未达到质量 Gate，停止增加 Gaussian primitives；Q3 继续冻结。
- [x] Q2 9,944 Gaussian＋4,096 Gabor residual 已训练到 step 1200 并导出；用户人工画质验收失败，路线归档。
- [x] 引入结构不同的 CC0 Hero Congestus cloud；拒绝底部偏平的 WDAS 展示源，并完成 density-only 清洗、六面 padding 与边界检查。

## P2 — 可信产品基线

- [x] UE SVT U8=`PF_R8`、F16=`PF_R16F` 同源资产。
- [x] 固定 1920×1080、Gaussian-only 和 warm-frame CSV 的数值测量口径；不再维护固定相机或自动截图流程。
- [x] 用 UE 5.8 `RDG_EVENT_SCOPE_STAT` 将总消耗注册为 `GaussianVolume`，并以 GPU trace 验证 scope 生效。
- [x] 锁定冷进程 EmptyBaseline 差分＋RHI resource dump＋SVT 原生 memory stat 的总 working-set 取证方法。
- [x] 固化 `capture_memory_baselines.ps1`：独立冷进程运行 Empty / Gaussian Q2 / SVT U8 / SVT F16 / NanoVDB Fp8 / FpN；检测到 Python/GPU 工作时默认拒绝启动。
- [ ] 为跨基线对照锁定相同曝光、密度尺度与背景；用户可调的展示密度不进入拟合质量指标。
- [x] 构建官方 NanoVDB converter，生成同源 Fp8/FpN，接入 PNanoVDB HLSL accessor、HDDA、独立 Actor/GPU tag 和两个对齐关卡；Editor/NullRHI 验证通过。
- [x] 逆向落地 7DRGS UE runtime，并将真实 `smoke2.vdb` 解析转换为 block-4、`388,890` 点、6 方向叶片的可重光照 PLY；TechLab 已保存项目相对路径 Actor。
- [x] 同源/同机位隔离 `ProfileGPU`：7DRGS 整帧/自身=`9.19/1.799 ms`，SVT U8 整帧/HeterogeneousVolumes=`8.43/1.070 ms`；当前解析 7DRGS 未胜过 SVT。
- [x] 将 CGHEVEN Hero Congestus 50 转为同源 UE SVT U8 与 B2 Ultra 7DRGS：`1,112,674` 空间样本、`6,676,044` 六方向 points；TechLab 部署和 point-count readback 通过。
- [x] 7DRGS 接入 DirectionalLight editor live refresh 与显式 SkyLight ambient fill；`AbyssEditor` 构建成功。
- [ ] 在 D3D12 live viewport 由用户签字 Gaussian、NanoVDB Fp8/FpN 与 SVT 的画面和 transfer function；未完成前不宣称 matched-quality 优于 VDB。
- [x] 用真实 `-game` 冷进程执行显存采集；SVT U8 runtime GPU memory=`12.402 MiB`，NanoVDB FpN raw grid=`4.598 MiB`，修复后的 Gaussian Compute=`2.344 MiB`，0.5× pool-free=`1.50 MiB`。
- [ ] 同硬件记录 UE SVT、NanoVDB、Gaussian 的 volume pass、完整 frame、稳态/峰值 GPU working set 与带宽；Gaussian 1/4/16 平移实例曲线已完成。

## P3 — Candidate working-set Gate

- [x] 用 count→scan→scatter 紧凑全局 pool 替换固定 `tiles × maxCandidates` 数组。
- [x] pool 使用固定预算且无 CPU readback resize；修复自由镜头 view basis 后默认索引容量为 `524,288 IDs`=`2 MiB`。
- [x] telemetry 明确输出 requested/granted/capacity/overflow 与 primitive/candidate/auxiliary/total bytes。
- [x] 512K 与 1M pool 做同代码 300-frame A/B：GPU median `7.35` vs `7.34 ms`，缩容无可测性能代价。
- [ ] tight PBF 的旧 `41.2%` 收益来自错误 camera basis，已降级为历史诊断；须按正确 `GetViewRight()/GetViewUp()` 重采后才能引用。
- [x] 强制 64K pool 验证空间公平 overflow：requested/granted=`107,633/65,536`、truncated tiles=`167`，不会清空后半屏。
- [x] 正确 basis、Q2 默认 512K pool 的 1080p runtime requested/granted=`142,979/142,979`、overflow=`0`、truncated tiles=`0`。
- [x] 用户近景移动相机暴露 128K 固定池会产生 tile 截断；恢复 512K Compute。无 candidate pool 的解析 raster 已完成并因 close-up 画质/性能 Gate 失败而降级为负实验。
- [x] 512K Compute 贴脸边界取证：requested/granted=`1,362,172/524,288`、overflow=`837,884`、`1,110/1,110` tiles 截断；无截断最低逻辑 working set=`5.517 MiB`，不扩池追求近景。
- [x] quality reference 默认 `CandidatePoolCapacity=0`，分配 exact tile matrix，不允许候选截断。
- [ ] quality reference 与后续紧凑路径做像素/候选正确性 A/B。

Q2 compact-pool 历史实测 requested/granted=`142,979/142,979`、capacity=`524,288`、overflow=`0`。candidate=`2,097,152 B`、primitive=`318,208 B`、uniform auxiliary=`32,668 B`，逻辑合计 `2,448,028 B`（`2.335 MiB`）；1080p RHI 命名资源约 `2.344 MiB`。当前 48 B／exact-pool／完整 LightT quality reference 不沿用这些 working-set 与性能数字。

## P4 — Runtime storage / architecture

- [x] primitive 从 64 B 压到精确 32 B，shader 直接解码，不保留常驻解包副本。
- [x] 32 B/local-space 相对 64 B reference 将 `GPU/GaussianVolume` median 从 `1.8834 ms` 降到 `1.5344 ms`。
- [x] 原位 scene-color 合成删除额外全屏输出；保留 `r.GaussianVolume.InPlaceComposite=0` 安全回退。
- [x] 原位主线 500 帧：完整 GPU median/P95=`6.9685/7.0853 ms`，volume tag median/P95=`1.5357/1.5977 ms`。
- [x] 用户确认 full-res pool-free 真实覆盖云，近景无 tile 格；candidate count/scan/scatter 已从该分支删除。
- [x] pool-free 改为 0.5× R16F optical-depth accumulation＋全分辨率一次 resolve；正式 runtime 原位合成，不重新分配全屏输出。
- [x] 1080p runtime 命名资源=`1.50 MiB`；full-res→0.5× 的 pass P50/P95=`1.9661/2.1377`→`0.5996/0.6007 ms`。
- [x] pool-free close-up Gate 失败：full-res 细节可接受但 `50+ ms`；0.5× 仍约 `25 ms` 且细节不通过；0.25× 不再测试，分支仅保留负实验记录。
- [x] uniform fast path 把未使用的 per-primitive LightTau 从 9,944 floats 缩成 1 float；单实例不创建独立 instance buffer。
- [x] `AdditionalInstanceOffsets` 以 32 B/instance 共享同一 primitive buffer；最终 1/4/16 份逻辑 working set=`857,244/857,372/857,756 B`。
- [x] 真实 D3D12 分配口径记录 instance buffer 的 `64 KiB` 最小粒度；4→16 不再增加 allocation，1→4 仍需约 `64 KiB`。
- [x] 4/16 同屏过载明确报告 candidate overflow=`66,726/569,953`；不自动扩池隐藏固定预算边界。
- [ ] 只有项目未来需要旋转/缩放实例时才升级为完整 local-space transform table；当前不做独立 Actor 内容哈希去重。
- [x] quality reference 扩展为 48 B primitive：FP32 `omega`、signed `sigma_t`、有限段 Faddeeva Gabor 解析积分。
- [x] 方向光＋天光由显式 Actor 引用驱动；高数量 `LightT` 不再旁路，只在数据/光方向变化时重建并缓存。

## P5 — 7DRGS 主线

- [x] 逆向实现 7DRGS UE 数据、切片、排序、光栅与合成链。
- [x] 将真实 `smoke2.vdb` 转换为 388,890 点、6 方向叶片代理并验证方向响应。
- [x] 同源 `ProfileGPU` 证明当前解析版本自身=`1.799 ms`，慢于 SVT U8 的约 `1.070 ms`；不宣称性能领先。
- [x] 用完整轮廓 CC0 Hero Congestus 50 建立 B2 Ultra 质量上限；六面 padding 后外边界 density=`0`，同源 SVT resolution=`238×264×403`。
- [x] 构建并部署 `6,676,044` points、2.04 GiB 的最高细节 PLY；默认显示 7DRGS、隐藏同源 SVT，保留 Outliner 手动 A/B。
- [x] 修复 B2 Ultra 超过 D3D12 单维 dispatch 上限：Slice／Preprocess 改为 UE wrapped dispatch，6.68M 资产冷启动无 dispatch ensure。
- [x] 真实 VDB 的 B2 Ultra 7DRGS 已通过用户细节与方向重光照验收；轻微全局色差暂不阻塞。当前解析六叶片版本仍不视为论文训练结果。
- [x] 修正训练器基础设施：明确 stage、完整 resume、checkpoint/validation 解耦、确定性 prune 与最小恢复测试。
- [x] 生成线性 `J/TView/depth/mask` 数据并完成 500 iterations 全量可恢复试跑：`172 s`、held-out J PSNR=`21.13 dB`、PLY `1,112,674` 点且 finite。
- [x] step 15,000 训练版完成并判负：held-out foreground J/TView=`16.54/14.83 dB`，用户确认颗粒噪声严重、细节模糊；checkpoint/PLY 只保留负证据，禁止续跑或裁剪。
- [x] 完成训练失败审计：旧 init 只取六叶片第一叶且丢失 opacity/J/TView/directional fields；opacity 冷启动 `0.1` 后被冻结；SH/covariance 正则未接入 main loop；light condition 可改变有效空间 covariance。
- [x] 完成公开方法横向审计并冻结边界：采用 BiGS 的 fixed-geometry/appearance-conditioning 与 LightGaussian/PUP 的 teacher-first prune/recover 原则；不整体转向 BiGS、RNG/GS³、Gabor 或新 renderer。
- [x] 修复六叶片聚合与 B2 density/appearance 初始化；6 项最小测试覆盖六叶片一致性、UE slicing 指数、正则 loss/gradient 与恢复链。
- [x] 将 `lambda_sh_reg`、`lambda_sigma_reg`、B2 anchor 与 `J` 能量/非负约束接入 main loop；静态 covariance 已冻结，因此不再为它增加 condition-number optimizer 路径。
- [x] 静态训练中冻结 opacity、TView、temporal block 与 spatial-condition cross covariance；light direction 只驱动 `J`，不允许改变 density、空间 mean/covariance。
- [x] 将 `patches/7drgs-j-sh-light-direction.patch` 落到 UE runtime；`J` 使用 light direction，`TView` 保留 camera direction；D3D12 shader 冷重编译通过。
- [ ] 建立 B2 teacher＋VDB anchor 数据：正式目标约 `16 cameras×24 lights×512`，首轮 `sh_degree=1`，相机与灯光方向各自完整留出。
- [x] 运行当前 8-view×6-light 数据的全量 `1K` 数值 smoke：静态参数零漂移、held-out/train J PSNR=`21.93/24.98 dB`、gap=`3.06 dB`、anchor drift RMSE=`0.01282`、六轴越界率=`8.54%`。
- [x] degree-2 从已接受的 degree-1 PLY 零增量升级；全量 parity 为旧字段 max error=`0`、新增 5 系数 max abs=`0`，teacher anchor 只约束 PLY 中已有的系数前缀。
- [x] 完成 3K degree-2 对照并按 held-out 选择 1K：held-out PSNR=`22.03→21.89→21.75 dB`，拒绝部署过拟合的 2K/3K。
- [ ] degree-2 1K preview 已在 TechLab 加载且未保存；等待用户验收 live viewport。正式 16×24 数据再报告 foreground LPIPS、高频 residual 与跨光向稳定性，签字前不跑完整训练。
- [ ] smoke 通过后训练 matched-quality `1.112M` student，再按 `1.112M→900K→800K` 确定性裁剪与恢复；600K 只在 800K 通过后进入。
- [ ] 正式性能 A/B 前为静态资产接入 Slice cache：仅资产／Component transform／时间／灯光方向／切片参数变化时失效；缓存与强制重算输出必须一致。
- [ ] 对通过画质的点预算分别记录 Slice、Preprocess、Sort、HW Raster、Composite 与完整 frame。
- [ ] 在 matched quality 下重做 SVT/7DRGS GPU time、working set 与资产转换耗时对照。

## 已归档 — Gabor residual

- [x] step 1200、最终 clean PSNR=`31.1498 dB`、14,040 primitives 已保存。
- [x] 用户人工画质验收失败；停止灯光调参、性能 A/B 和 runtime residual 优化。

## 作品集通过线

- matched quality、同源资产和同等运行条件下，稳态 GPU working set 低于 UE SVT 与 NanoVDB 中更优者；
- RTX 5060、1080p：完整 frame `≤16.67 ms`；volume pass 只要求完整报告；
- 强目标为稳态 GPU working set 至少降低 `2×`，冲刺目标为降低 `4×`；
- peak transient 不抵消收益，1/4/16 实例不线性复制共享资产；
- 没有隐藏 candidate 截断、关闭关键 Pass 或只挑 Hero 帧。

若只达到实时但没有 matched-quality memory 优势，删除 VDB proxy 优势主张，只保留 UE volumetric primitive renderer 工程案例。

## 冻结

- 表示 Gate 前不实现紧凑池之外的运行时扩展；
- 不恢复 Spline/Structured Gaussian Field FX、旧连续 cross-fade 主线或 Epanechnikov 支路；
- 不把动画、通用资产、多光源动态 GI 或 Bifrost 集成带回当前范围；当前只做一盏方向光＋天光的静态重光照。
