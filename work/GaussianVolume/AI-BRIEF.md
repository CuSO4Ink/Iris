# GaussianVolume
![[Don’t Splat your Gaussians_ Volumetric Ray-Traced Primitives for Modeling and Rendering Scattering and Emissive Media.pdf]]
> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

预研 Gaussian volume primitives 作为 VDB 体积云降耗方案的可行性，重点验证论文结构的 runtime 价值，而不是一开始追求 hero 级云精度。

## 当前状态

重新激活 / 预研继续

## 当前焦点

基于 **Don't Splat your Gaussians** 的结构做最小验证：Gaussian volume primitive 数据结构、ray-Gaussian 解析透射率、primitive 遍历/加速、single scattering 管线，以及后续 UE 落地优化点。

## 技术栈与硬约束

- 目标定位：优先作为 VDB 中远景 LOD / 压缩代理 / 光照代理，不承诺直接替代 hero VDB 云。
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

## 协作约定

- LOG 只记 `[决策]` `[否决]` `[发现]` `[回滚]`，不记流水账。
- 讨论论文时优先抽取可落地模块：数据结构、积分公式、遍历结构、加速方式、UE 集成风险。
- 遇到“要不要先追精度”的分歧时，当前阶段默认先验证结构可行性。

---

## 维护

- 阶段切换 / 术语变更 / 技术栈升级 → 更新本文件
- ≤ 100 行，超了拆到 notes/ 或新文件
- 项目归档时本文件随迁，保留
