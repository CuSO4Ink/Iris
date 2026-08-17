# T-P0.1 · blockout v2 实测数值记录（MCP 读取）

> **来源**：2026-07-07 通过 UE MCP 网关（`get_actors_in_folder` + `get_actor_transform`/`get_actor_bounds`）实读关卡 `/Game/Bifrost/Maps/L_Bifrost`。
> **单位**：米（m），1m = 100 UU。location = actor 世界坐标；size = 包围盒实测尺寸。
> **用途**：T-P0.1 灰模验收留档 + 下游 kitbash/摆位的坐标基准 + Portfolio breakdown 素材。

---

## 1. P0_Blockout — 4 段海滩走廊（20 actor · batch `W1_P0_blockout_v2`）

Outliner：`Bifrost/P0_Blockout/{S1,S2,S3,S4,_Markers}`

### 段体（Floor / 边界 / 门 / 锚点）

| label | loc (m) | scale | size (m) | 语义 tag |
|---|---|---|---|---|
| BLK_S1_Floor | (50, 0, -0.2) | (100,60,0.4) | 100×60×0.4 | Floor,PlayableArea,S1 |
| BLK_S1_Cliff_negY | (50, -30, 4) | (100,0.5,8) | 100×0.4×8 | Boundary,Cliff,S1 |
| BLK_S1_SeaEdge_posY | (50, 30, -0.6) | (100,0.5,0.6) | 100×0.4×0.6 | Boundary,SeaEdge,S1 |
| BLK_Gate_S1_10000 | (100, 0, 3) | (0.6,60,6) | 0.6×60×6 | SegmentGate,S1 |
| BLK_S1_Anchor | (50, -12, 12) | (8,8,24) | 8×8×24 | Anchor,S1 |
| BLK_S2_Floor | (170, 0, -0.2) | (140,48,0.4) | 140×48×0.4 | Floor,PlayableArea,S2 |
| BLK_S2_Cliff_negY | (170, -24, 4) | (140,0.5,8) | 140×0.4×8 | Boundary,Cliff,S2 |
| BLK_S2_SeaEdge_posY | (170, 24, -0.6) | (140,0.5,0.6) | 140×0.4×0.6 | Boundary,SeaEdge,S2 |
| BLK_Gate_S2_24000 | (240, 0, 3) | (0.6,48,6) | 0.6×48×6 | SegmentGate,S2 |
| BLK_S2_Anchor | (170, -9.6, 12) | (8,8,24) | 8×8×24 | Anchor,S2 |
| BLK_S3_Floor | (280, 0, -0.2) | (80,40,0.4) | 80×40×0.4 | Floor,PlayableArea,S3 |
| BLK_S3_Cliff_negY | (280, -20, 4) | (80,0.5,8) | 80×0.4×8 | Boundary,Cliff,S3 |
| BLK_S3_SeaEdge_posY | (280, 20, -0.6) | (80,0.5,0.6) | 80×0.4×0.6 | Boundary,SeaEdge,S3 |
| BLK_Gate_S3_32000 | (320, 0, 3) | (0.6,40,6) | 0.6×40×6 | SegmentGate,S3 |
| BLK_S4_Floor | (360, 0, -0.2) | (80,60,0.4) | 80×60×0.4 | Floor,PlayableArea,S4 |
| BLK_S4_Cliff_negY | (360, -30, 4) | (80,0.5,8) | 80×0.4×8 | Boundary,Cliff,S4 |
| BLK_S4_SeaEdge_posY | (360, 30, -0.6) | (80,0.5,0.6) | 80×0.4×0.6 | Boundary,SeaEdge,S4 |
| BLK_S4_Anchor | (360, -12, 12) | (8,8,24) | 8×8×24 | Anchor,S4 |

### Markers

| label | loc (m) | size (m) | 语义 tag |
|---|---|---|---|
| BLK_PlayerStart_Marker | (4, 0, 2) | 2×2×4 | SpawnMarker,S1 |
| BLK_HeroCam_Marker_S3 | (280, 0, 1.8) | 1×1×1 | HeroCam,Camera5,S3 |

### 走廊几何小结

- **总长 400m**：S1 floor 起点 X=0 → S4 floor 终点 X=400m，单向 +X。
- **段边界 X**：100 / 240 / 320m（Gate 门柱定位），与 ROADMAP §1 的 S1 0-100 / S2 100-240 / S3 240-320 / S4 320-400 完全一致。
- **走廊宽度**（floor Y 尺寸）：S1=60m · S2=48m · S3=40m · S4=60m。S3 最窄 → 主锚点区画面密度最高，符合"S3 精修"定位。
- **边界约定**：−Y = Cliff（8m 薄墙，玩家不可越）· +Y = SeaEdge（贴地薄板，海面方向）。走廊沿 Y=0 中心线对称。
- **出生点** X=4m · **主机位⑤ HeroCam** 在 S3 中心 X=280m / Z=1.8m（眼高）。
- **锚点**：S1/S2/S4 各一根 8×8×24m 竖块占位（远景巨构代摆），S3 用 HeroCam marker 定构图点。

---

## 2. P0_ScaleTest_L — 尺度参照关（5 actor · batch `W1_P0_scaletest_L_20260707`）

Outliner：`Bifrost/P0_ScaleTest_L/{Cliff,Ground,Megastructure,Ref,Star}`
**用途**：仅供尺度校准，不属正式走廊，后续可按 batch tag 单独清理。

| label | loc (m) | size (m) | 语义 |
|---|---|---|---|
| ST_HumanRef_1p8m | (280, 0, 0.9) | 0.4×0.4×1.8 | 人体 1.8m 参照 |
| ST_Cliff_300m | (450, -90, 150) | 160×140×300 | 悬崖 300m（07-07 移至 S4 终点 X=400 之外） |
| ST_Megastructure_180m | (450, -90, 390) | 60×60×180 | 巨构 180m（07-07 随悬崖同步移至 X=450，悬浮在悬崖顶部300m之上，保持对比柱关系） |
| ST_Star_GIANT_D3000m | (280, 1800, 1300) | Ø3000 | 巨星（07-09 由 Y=-1800m 悬崖侧移至 **Y=+1800m 海侧**，"海天恒星"构图，本人验收确认保留 / 高空 Z=1300m） |
| ST_SeaFloor_Ref | (280, 0, -0.5) | 400×300×0.6 | 海床参照面 |

---

## 3. 待验收项（对照 HANDBOOK §2 T-P0.1）

现在可验（灰模层面）：
- [x] 总长 400m / 宽 40-60m / 两侧边界（Cliff + SeaEdge）就位
- [x] 4 段边界切分明确，S1/S2/S3/S4 位置定死
- [x] 每段主锚点占位就位 + S3 HeroCam marker 定位
- [x] 玩家路径可通行（S1→S4 不卡/不掉海/不穿墙）—— T-P0.2 完成，用户自备角色 PIE 实跑验收通过（2026-07-07）
- [ ] 主机位⑤ FOV / 人物屏占比 / 景深分层 —— 需相机就位后量
- [ ] ⏸ 恒星屏占比 30-45% —— 恒星 W2 才做，届时用占位球复验（ScaleTest 关已放 Ø3000 巨星可先粗校）

> 完整原始数据（含 refPath / rotation / bounds）见同目录 `blockout-v2-raw.json`。
