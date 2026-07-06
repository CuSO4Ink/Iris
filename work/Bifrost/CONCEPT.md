# Bifrost · CONCEPT

> **纯概念 / 美术向设计文档**。D1（奇观焦点）/ D2（色彩基调）**均已拍板**，见 `LOG.md` 2026-07-02 19:45 / 17:10、`BACKLOG.md` 决策框架。本文件现聚焦：固化定案方向 + 定案提示词（冠军版本）+ 多角度扩展。
> 不写技术实现细节（marching cubes 集成 / overdraw 调优等留到 D3 阶段）。

---

## §1 定位速览

- **一句话**：北欧神话 + 宏大奇幻 + 巨构瑰丽的海岸 diorama，作为 AIEffectFoundry 方向3 的首个落地样本，用来跑通 Human-in-the-loop 的 AI TA 工作流。
- **命题红线**：风格化 > 写实；夸张巨构尺度，强调渺小人视角下的压迫性宏大感；内核是可复用能力。
- **约束松绑（2026-07-06）**："内核只做 1 个、做深不摊大"已松绑 → 允许多元素分层挂载（基底层必做 + 点缀层独立模块增量加），详见 `PIPELINE.md` §1。

---

## §2 已拍板方向

**D1 奇观焦点 = 合成态「等离子恒星驱动天气」**：一颗巨大冷白等离子恒星（翻涌熔融的 isosurface 表面，复用 NS_Slime marching cubes）既是视觉 hero，也是光源——它驱动风暴前锋、god-rays、大气散射。天气不是独立内核，是恒星的光学衍生效果。内核只有 1 个（等离子恒星），满足硬约束。

**D2 色彩基调 = 冷神性**：冷白/蓝巨星，肃穆神性光，pale azure/icy cyan 色域。守住"瑰丽 ≠ 俗艳"，避免高光过曝糊成一片。

| 元素 | 落层 | 结论 |
|---|---|---|
| 悬崖 + 古建筑群遗迹 | L1 量产 + L2 构图 | 舞台，非内核；kitbash + 岩石母材质量产 |
| 等离子恒星（isosurface） | **L3 内核（已定）** | D1 落点，复用 NS_Slime marching cubes |
| 天气 / god-rays | 恒星的衍生效果 | 不独立占内核名额 |
| FluidFlux 主海面 | L1 基底 | 已复刻，直接接入（用户自带） |
| 铁磁流体尖刺 | 点缀层 | 融视觉不融物理，挂 FluidFlux（见 `PIPELINE.md` §4） |

> **恒星因果链**（2026-07-06 定案）：恒星光→云散射、恒星磁场→极光、恒星磁场→海面尖刺——天象与海面全是恒星的衍生，叙事自洽。技术落法见 `PIPELINE.md` §2-§4。

> [!NOTE] **教训存档**：此前 AI 曾未经要求自行用内部弱模型生图"验证"，误诊断"恒星必须显式补强 metaball/isosurface 措辞"。用户在自己实际工具上验证：**原始简单措辞效果最好**，最终定案版本（见 §3）就是未经该补强的原始写法。已记入 `LOG.md` [发现]。后续 AI 只负责提示词文本，不再自行生图验证。
> — ai 2026-07-02

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

> 中文注释：这版是"天气焦点段"+"等离子恒星段"拼接后的合成态，用户在自己工具上确认**最有感觉**，正式锁定为 Bifrost 的定案美术方向。§4 在此基础上拓展多角度。

---

## §4 多角度扩展（备选机位）

**目的**：基于 §3 定案版本换机位。主机位已定 **⑤前景剪影环境镜**（T-L2.2，见 LOG 2026-07-06）。下表为机位短语，**追加在 §3 末尾**即可，无需重写主体。

| 机位 | 追加短语 |
|---|---|
| ① 全景建立（=§3 原版） | `（无需追加）` |
| ② 低角度仰视 hero | `, extreme low-angle hero shot looking up, emphasizing towering vertical scale` |
| ③ 俯瞰鸟瞰 | `, high aerial bird's-eye overview, revealing coastline layout and silhouette against the horizon` |
| ④ 焦点特写（恒星表面） | `, tight close-up shot focusing on the surface detail and light interaction of the churning plasma star` |
| **⑤ 前景剪影环境镜（主机位）** | `, over-the-shoulder framing with the human silhouette in sharp foreground, the star glowing in the background` |

> 工具提示：2D 文生图无法精确旋转同一三维场景；用图像参考 / IP-Adapter 锁风格身份（权重中等）+ 固定 seed + 机位短语只加末尾，即可在保持视觉身份下换角度。
> [!TODO] 主机位⑤已定，下一步推进 D3 内核技术选型 —— 见 `D3-KERNEL.md`。
> — ai 2026-07-02

---

## §5 因果链总览（2026-07-06 定案）

恒星是整个场景的唯一因果源，所有衍生效果由它驱动：

```
等离子恒星（A1，hero + 光源）
  ├─ 光 → 大气散射 / god-rays
  ├─ 光 → 体积云穿透散射（A3）
  ├─ 磁场 → 极光沿磁力线分布（A2）
  └─ 磁场 → 海面铁磁流体尖刺（B2 融合，挂 FluidFlux）
```

**叙事一句话**：*"恒星不只是光源——它的磁场牵引着脚下这片黑色液金海，恒星在天上翻涌，海面就应和着长出尖刺。"*

> 落法细节见 `PIPELINE.md` §2（恒星）/ §3（天象）/ §4（铁磁流体融合）。
