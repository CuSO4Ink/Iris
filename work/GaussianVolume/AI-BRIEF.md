# GaussianVolume
![[Don’t Splat your Gaussians_ Volumetric Ray-Traced Primitives for Modeling and Rendering Scattering and Emissive Media.pdf]]
> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

预研 Gaussian volume primitives 作为实时体积密度场与结构化 VFX 内核的可行性，优先验证解析传输、UE runtime 和可复用空间查询；VDB LOD / proxy 作为次级落地方向，不承诺替代成熟 VDB 播放方案。

## 当前状态

UE 5.8 上已完成 G0-G3 渲染技术主体：premultiplied 合成、场景深度遮挡、per-ray `t_star` 排序、输入保护、Actor local-space 上传、Spline authoring（支持多 spline 追加）、Debug View、跨 Actor 共享渲染器、HDR/bloom 前合成和 `LightTauCS` 跨 primitive 光照。ProbeActor 已收缩为 BeginPlay 单次密度采样，避免 UE 5.8 GPUScene stale-light ensure。128 primitive PIE smoke test 通过，无 ensure、shader error 或崩溃。主 pass 保留有界 64-hit 工作集，满载时优先保留最近命中；同时删除了重复全屏 SceneColor copy 和无效 CPU 深度排序。当前进入 **G4 固定机位性能基准**；Ribbon 并排对照已取消，差异由 Gaussian 自身镜头与口头说明承担。仍未证明相较 VDB、raymarch 或 Niagara 的通用生产优势。

## 当前焦点

保持 **Structured Gaussian Field FX** 范围：以 spline/field 驱动的磁拱、极光、能量丝带验证连续三维密度、解析透射、single scattering、场景遮挡和共享空间查询；随后仅按 GPU profile 决定是否实现 half-res 或候选加速，不扩展为通用云 renderer。

## 方向决策（2026-07-10）

- 不把项目包装为 ZibraVDB、普通 VDB 或 3DGS 的替代品；Gaussian volume / analytic ray integration 已有公开研究，当前项目的价值应来自 UE runtime、可编辑生成、LOD 和跨系统 field query 的组合。
- 当前项目定位为底层研究型渲染内核：连续 Gaussian 密度、解析 optical depth / transmittance、single scattering、GPU buffer 和 UE Compute Shader 链路。
- 产品化候选收缩为 **structured Gaussian Field FX**：针对稀疏、方向性、需要艺术控制的体积带/极光/能量特效，验证同一 Gaussian field 是否能同时服务体积渲染、光束衰减和 Niagara/材质查询。
- 若该方向不能在同画质或同预算下相较 Niagara Ribbon、普通 raymarch 或 3D texture 体现可测量收益，则保留为图形学研究原型，不继续堆通用功能。

## 技术栈与硬约束

- 应用边界：结构化 Gaussian Field FX 是当前主验证方向；VDB 中远景 LOD / 压缩代理 / 光照代理保留为次级路径，不承诺直接替代 hero VDB 云。
- 第一阶段暂时抛开最终精度，先验证 runtime 结构、性能曲线和工程可落地点。
- 不走普通 3DGS screen splatting 主线；云方向优先看 ray-traced volumetric primitives / analytic transmittance。
- MVP 光照保持克制：single scattering + fake ambient / powder term；多次散射、复杂 phase、VDB 高精度拟合后置。
- 先用手工/程序化 Gaussian cloud 验证 renderer，再接 VDB → Gaussian primitive 转换。

## 术语表

- **Gaussian volume primitive**：用于表示体积密度的连续椭球 primitive，属性包括 center、scale/covariance、rotation、density/extinction 等。
- **Analytic transmittance**：沿 ray 穿过 Gaussian 密度场时，通过解析积分估计 optical depth / transmittance，避免固定步长 raymarch。
- **Free-flight sampling**：体积路径追踪中的自由程采样，第一阶段仅作为论文结构参考，不作为 MVP 必做项。
- **VDB proxy / LOD**：从高质量 VDB 生成更轻量的运行时代理表示，用于中远景或光照缓存。
- **Candidate traversal**：每条 ray 查找可能相交/有贡献 Gaussian primitive 的过程，是 runtime 成本关键。

## 文档地图

- `AI-BRIEF.md`：项目身份、范围和硬约束
- `LOG.md`：追加式决策/发现记录
- `BACKLOG.md`：当前待办
- `notes/product_direction.md`：应用方向、验证假设与停止标准

## 协作约定

- LOG 只记 `[决策]` `[否决]` `[发现]` `[回滚]`，不记流水账。
- 讨论论文时优先抽取可落地模块：数据结构、积分公式、遍历结构、加速方式、UE 集成风险。
- 遇到“要不要先追精度”的分歧时，当前阶段默认先验证结构可行性。
- 多模态 token 成本受限：需要画面或编辑器运行结论时，助手只明确列出待验证的可观察项、机位和数值；由用户在 UE 中观察并文字反馈。除非用户明确要求，助手不得自行截图、读取截图或通过桌面自动化采集画面。

---

## 维护

- 阶段切换 / 术语变更 / 技术栈升级 → 更新本文件
- ≤ 100 行，超了拆到 notes/ 或新文件
- 项目归档时本文件随迁，保留
