# GaussianVolume Product Direction

最后更新：2026-07-22

## 当前定位

GaussianVolume 是 UE 解析 volumetric primitives 的研究型工程案例。它只在证据成立时定位为原 VDB/SVT 的中远景代理、编辑器预览或多实例降级；近景 Hero 保留原 VDB，不宣称通用替代。

当前产品状态是**假设未成立**。运行时内核和优化已有实测，但 block/adaptive 画质仍模糊、稀疏，尚无 matched-error 的 VDB/SVT 优势。高数量路径关闭 `LightTauCS`，因此“实时可重光照”也未成立。

## 工程组合

- A：已有各向异性 volumetric primitives、解析有限段 transmittance 与 single scattering；
- B：UE5.8 OpenVDB 转换、跨 Actor single pass、32×32 tile candidate、多预算 LOD/cross-fade、场景合成与诊断；
- 意义：把连续体积表示接入可测量的游戏运行时与生产回退，而不是为技术寻找题材。

## 保底与上探

- 保底是准确披露边界的 UE renderer／转换／LOD／性能诊断案例；表示质量失败时按研究内核和负结果结项。
- 唯一研究候选是多视角 transmittance＋silhouette 的层级拟合目标；它仍待本人确认与相关工作检索。
- Gabor Fields 目前只作为内部记录发现的相关工作/潜在对照。未经本人决定、训练和 UE 实验，不是主线。

## 必需证据

- 同条件源 VDB/SVT、当前失败基线和 exact correctness reference；
- silhouette、边界距离、transmittance、未见视角、运动和 LOD pop；
- GPU、所有 buffer/cross-fade 的峰值 VRAM、多实例与编辑器响应；
- moving-light 正确性与成本；
- 离线时间、资产体积、人工干预和失败率；
- 本人对最终画面的明确签字。

## 升格与停止

- 表示质量 Gate 通过，并在 matched-error 下相对 VDB/SVT 至少证明两项资源/流程收益，才可称 VDB 中远景 Proxy/LOD。
- 拟合两轮仍不能恢复可接受结构：停止产品化。
- 高数量路径无法保留所需光照、存在 candidate 截断或 cross-fade 峰值超预算：删除对应实时/重光照声明。
- 无最终效果、breakdown、基线和可复现证据：不进入正式作品集。

## 归档边界

Spline/Structured Gaussian Field FX 永久保留在 `notes/archive/`，除非本人明确重开。旧 Gabor 自动升格、Epanechnikov 支路和其他并行赌注不构成当前排期。
