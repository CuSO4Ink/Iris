# Bifrost · CONCEPT（美术定案）

> **纯概念 / 美术向定案文档**。D1/D2/主机位/因果链均已锁。执行落地看 `ROADMAP.md`。技术实现看 `PIPELINE.md` / `D3-KERNEL.md`。

---

## §1 定位速览

- **一句话**：北欧神话 + 宏大奇幻 + 巨构瑰丽的**第三人称跑图海岸 diorama**，200m 单向沙滩走廊，扛得住玩家游览。作 AIEffectFoundry 方向3 首个落地样本 + 跨 P1+P3 垂直代表作。
- **命题红线**：风格化 > 写实；夸张巨构尺度；跑图规模下"每个可达角落都经得起看"是硬约束；内核是可复用能力。
- **场景形态**（07-07 重构）：从"单机位定点 diorama"改为"第三人称跑图 diorama"。主图 T-L2.2 降级为"场景内的最优机位截图"，不再是设计驱动因子；驱动整个场景设计的是"跑图叙事弧线"。

---

## §2 已锁定案

| 决策 | 结论 | 拍板日 |
|---|---|---|
| D1 奇观焦点 | 合成态「等离子恒星驱动天气」——恒星 hero + 光源 + 天气驱动源三合一 | 2026-07-02 |
| D2 色彩基调 | 冷神性（cold blue-white 巨星、pale azure/icy cyan）；守瑰丽≠俗艳、控高光曝光 | 2026-07-02 |
| D3 内核实现 | A 方案·轮廓局部化（材质三层堆 · `D3-KERNEL.md`） | 2026-07-06 |
| 主机位 | ⑤前景剪影环境镜（S3 段最优截图点，非设计驱动因子） | 2026-07-06 / 07-07 降级 |
| 场景形态 | 第三人称跑图 diorama · 200m 单向海滩走廊 · 4 段结构 | 2026-07-07 |

场景元素落层：

| 元素 | 落层 |
|---|---|
| 4 段海滩沙滩 + 两侧悬崖边界 | L1 量产（Nanite kitbash + 母材质） |
| 悬崖 + 古建筑群遗迹 | L1 量产（kitbash + 母材质） |
| 等离子恒星（isosurface 局部化） | L3 内核 · A 方案 |
| 天气 / god-rays / 大气散射 | 恒星光学衍生（基底） |
| 体积云 / 贝母云 | 恒星光散射衍生（**基底**，07-07 从点缀升级） |
| FluidFlux 主海面 | L1 基底（已复刻直接用） |
| 铁磁流体尖刺 | 点缀（融视觉不融物理，挂 FluidFlux，S3 段焦点） |
| 极光 | 点缀（磁场衍生，S3 天空区域） |
| 前景苔藓 / 石缝植物 | Foliage Tool 或 Python 撒点（局部工具，量少） |

---

## §3 定案提示词（冠军版本，锁定，勿改动措辞）

```
Norse-mythic fantasy coastal diorama, colossal cliffside ancient ruins and megastructures,
a tiny lone human silhouette for scale conveying oppressive grandeur,
stylized painterly non-photorealistic, epic cinematic wide shot, dramatic volumetric atmosphere,
highly detailed matte-painting quality, awe-inspiring monumental scale,
a cold blue-white giant star low on the horizon, solemn storm front and vast god-rays
in icy azure light, austere divine mood, pale cyan volumetric haze, hushed monumental silence,
an enormous close blue-white star filling the sky, its churning plasma surface alive with
roiling flares and merging tendrils, cold luminous liquid-metal isosurface detail,
pale azure hero light over austere ruins, sublime divine mood
```

**主机位⑤追加**：`, over-the-shoulder framing with the human silhouette in sharp foreground, the star glowing in the background`

> **教训存档**（07-02）：AI 曾用内部弱模型自行生图"验证"，误诊断"必须补强 metaball/isosurface 措辞"。用户实际工具验证：**原始简单措辞效果最好**，即上方定案版本。后续 AI 只负责提示词文本，不再自行生图验证。

---

## §4 跑图叙事弧线（4 段海滩，07-07 新增）

玩家从远端出生 → 沿沙滩单向前进 → 抵达 S3 主锚点区 → 走过后回望远景，30-60 秒走完一趟。跑图叙事的核心：让玩家在跑动过程中自然感受"渺小人视角的压迫性宏大感"，主图⑤号构图不是硬塞的静态素材，而是**跑图过程中的自然高光时刻**。

| 段 | 视觉重心 | 叙事作用 |
|---|---|---|
| **S1 远端**（0-50m） | 远景巨构 + 恒星建立镜头 | 出生即震撼，引导玩家往前走 |
| **S2 中景**（50-120m） | 遗迹 kitbash 群 · FluidFlux 主海面 | 走进环境，感受海面波动与遗迹质感 |
| **S3 主锚点区**（120-160m） | 主机位⑤最优截图点 + 铁磁流体尖刺 + 极光 | 叙事高潮，玩家走过时形成⑤号构图 |
| **S4 回望端**（160-200m 尾段） | 走过后回望远景，收束叙事 | 让玩家意识到"我刚穿过一个北欧神话世界" |

**walkthrough 视频叙事**：1 分钟单向走位 · S3 慢镜头 hold 主机位⑤构图 · 用于 Portfolio 视频页封面。作品集封面用 S3 静帧，视频用完整走位，双主线互相强化。

---

## §5 因果链（叙事骨架）

恒星是场景的唯一因果源，所有效果由它驱动：

```
等离子恒星（hero + 光源）
  ├─ 光 → 大气散射 / god-rays              【基底 · W3 交付】
  ├─ 光 → 体积云穿透散射                   【基底 · W3 交付】
  ├─ 磁场 → 极光沿磁力线分布（S3 上空）    【点缀 · W4 目标成片】
  └─ 磁场 → 海面铁磁流体尖刺（S3 段焦点）   【点缀 · W4 目标成片】
```

**交付基线明确**（07-07 修正）：W3 保底成片保 2 支（光→大气/云散射），W4 目标成片补齐磁场 2 支。宣传因果链 4 支时同步说明分档。

**叙事一句话**：*"恒星不只是光源——它的磁场牵引着脚下这片黑色液金海，恒星在天上翻涌，海面就应和着长出尖刺。"*

---

## §6 备选机位（追加短语）

主机位已定 ⑤（S3 段最优截图点），其余作储备参考（追加在 §3 定案提示词末尾即可）。跑图叙事下，这些机位可作为 walkthrough 视频的额外镜头素材：

| 机位 | 追加短语 | 跑图用途 |
|---|---|---|
| ① 全景建立（=§3 原版） | `（无需追加）` | S1 出生视角 |
| ② 低角度仰视 hero | `, extreme low-angle hero shot looking up, emphasizing towering vertical scale` | S2 走过遗迹时的仰角 |
| ③ 俯瞰鸟瞰 | `, high aerial bird's-eye overview, revealing coastline layout and silhouette against the horizon` | 视频结尾拉远镜头 |
| ④ 焦点特写（恒星表面） | `, tight close-up shot focusing on the surface detail and light interaction of the churning plasma star` | S3 慢镜头素材 |
| **⑤ 前景剪影（主机位）** | `, over-the-shoulder framing with the human silhouette in sharp foreground, the star glowing in the background` | **S3 抵达时自然形成的高光构图** |
