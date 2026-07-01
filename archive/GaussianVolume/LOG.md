# GaussianVolume · LOG

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

### 2026-05-29 15:50 — [决策] 启动 Gaussian volume 预研

先按 Don't Splat your Gaussians 的论文结构做工程验证，暂时抛开最终精度，重点看 Gaussian volume primitive 的 runtime 结构、解析透射率、遍历/加速和 UE 落地可优化点。

### 2026-05-29 15:58 — [决策] 收窄 MVP 范围

第一版不追完整 VDB 拟合和多次散射；先用手工/程序化 Gaussian cloud 验证体积感、ray-Gaussian 积分、single scattering 与 primitive traversal 成本曲线。

### 2026-05-29 16:24 — [决策] MVP 通过标准

MVP 只回答三件事：能否形成基本体积感、解析 transmittance 是否替代大量固定步 raymarch、primitive traversal/candidate 数是否可控；通过后再接 VDB block → Gaussian primitives。


### 2026-06-05 16:30 — [发现] MVP 复现跑通，三问有结论

standalone CPU renderer（mvp/，纯 NumPy）跑通：手工 Gaussian cloud + ray-Gaussian 解析 optical depth（erf 区间积分，零固定步 raymarch）+ front-to-back single scattering。
① 体积感：✅ N=1024 出连续云团、明暗柔和、无硬边噪点。
② 解析 transmittance 替代 raymarch：✅ 每个 primitive 一次 erf 即得整段 tau，view/light 两个方向都解析。
③ traversal 可控性：⚠️ brute-force bounding sphere 的 candidate/ray 随 N 近似线性（稳定 ~45%，N=8192 时均值 3677），是后续头号瓶颈。

### 2026-06-05 16:30 — [决策] 下一步优先做加速结构

MVP 结构成立，瓶颈定位在 traversal。下一步先上 uniform grid / macro cell 把 candidate 比例从 ~45% 压下来，再谈精度与 VDB→primitive 转换。性能基线：N=1024、200x150、纯 Python 约 85s（355 ray/s），后续可向量化/分块加速。
