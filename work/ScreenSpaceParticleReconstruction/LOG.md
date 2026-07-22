# Screen Space Particle Reconstruction · LOG

> 决策流水。追加式，新条目加在**文件末尾**。只记录决策、否决方案和重要发现。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

### 2026-07-22 16:47 — [决策] 先搭可插拔架构，不锁定密度算法
项目主干固定为粒子投影/分桶、场处理、Particle G-buffer、材质解析四层；KDE、各向异性 splat、MLS/RBF、深度平滑等都作为可替换 Field Operator。

### 2026-07-22 16:47 — [决策] 材质与场重建解耦
场处理层只产出标准化深度、厚度/密度、法线相关量和粒子属性；水、烟、能量、卡通等外观由 Resolve Material 组合，避免每种效果重写前端粒子管线。

### 2026-07-22 16:47 — [发现] 参考文档用于算法候选而非架构前提
RBF/各向异性 MLS 可用于特定线状点云边缘，但不应绑死基础设施；有序线链、无序点云和液体粒子的几何前提不同，应允许选择不同 Field Operator。

### 2026-07-22 16:47 — [决策] 保留每像素深度重建能力
相机朝向广告牌只作为材质载体，不把“跟随相机旋转”当作三维信息；需要立体感时由 RT 深度与逆视投影矩阵恢复视图/世界位置。

### 2026-07-22 17:00 — [发现] Niagara Fluids 有同构分层，但不是同一坐标域
Niagara Fluids 已有源粒子 scatter 到 Grid2D/Grid3D、Simulation Stages 处理、Renderer/Material 消费的分层；Grid3D Gas 和 FLIP 保留模拟域数据，公开资料未证明其通用模板采用每帧屏幕空间前后深度 G-buffer。
来源：Epic `fluid-simulation-in-unreal-engine---overview`、`niagara-fluids-reference`；80 Level 对 Epic TA Asher Zhu 的 Niagara Fluids 拆解。

### 2026-07-22 17:00 — [发现] Niagara 3D Liquid 是最近的表面重建参照
公开拆解包含 PIC/FLIP、粒子球 rasterizer、SDF/Jump Flood 与水材质路径，本质同样是“粒子 → 连续表面表示 → 材质”，但其目标是液体表面，不是通用的可插拔 Particle G-buffer。
来源：https://80.lv/articles/working-with-niagara-fluids-to-create-water-simulations

### 2026-07-22 17:00 — [发现] FluidNinja LIVE 更接近场缓冲与表现解耦
Fab 公开功能确认 LIVE 可把 Density、Velocity、Pressure 暴露到 Render Targets，支持 Niagara 双向数据流并驱动 Niagara/Volume 组件；其接口思想可直接参考，但公开资料不足以把它等同于“3D 粒子经相机矩阵投影为前后深度”。
来源：https://www.fab.com/ja/listings/80fcf53e-49f7-4635-a71c-ba81280c6618

### 2026-07-22 17:00 — [决策] 借鉴接口，不复制求解器
从 Niagara Fluids 借鉴 Grid/Simulation Stage/scatter/debug slice，从 FluidNinja 借鉴 RT 暴露、组件化和 Niagara 双向数据；项目仍保留独立 Projection 与 Field Operator 接口，不绑定 FLIP、2D Navier-Stokes 或某个商业插件的数据布局。
