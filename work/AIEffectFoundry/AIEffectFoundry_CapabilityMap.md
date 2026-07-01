# AIEffectFoundry · Capability Map

## 目的

把现有资源从“旧作品/旧实现”拆成可复用能力，作为新版作品集的能力底座。

核心原则：能力服务表达，不让单个技术 demo 决定美术方向。

## 资源总览

### 1. UE5.5 自定义渲染引擎

来源：UE55_CustomRendering_Patch.patch

可沉淀能力：自定义 Shading Model、NPR/Toon 光照、Light 参数扩展（shadow color/rim/penumbra）、Outline pass、Translucency Before Water、ToneMap/ACES/LUT、Material Instance/Editor/Pixel Inspector 工具化。

定位：作为 Stylized Rendering Stack。短期 UE5.5 稳定出图，中长期把核心能力迁 UE5.8，不全量硬迁 patch。

风险：与 UE5.5 源码绑定深；迁移成本高；不应让叙事变成“维护旧引擎魔改”。

建议：保留设计思路与核心功能；拆成 feature pack（Custom Toon、Outline、Light Control、ToneMap、TransBeforeWater）；后续做最小核心迁移。

### 2. 旧版技术拆解：动态表面/软体模拟

来源：技术拆解.pdf

可沉淀能力：PBF/SPH 路线判断、Neighbor Grid 3D、密度场/SDF、Ray Marching 取舍、Marching Cubes、RDG Compute、ProceduralMesh 接入、异步回读与性能控制。

定位：抽象为 Dynamic Surface Reconstruction Kernel，不是“史莱姆项目”，而是实时可变形体积/表面重建能力。

可转译：史莱姆/软体生物、液态金属、魔法墨水/灵液、腐蚀/吞噬场、动态雕塑、生物组织/黏菌、地形隆起/形态生长。

建议：列为高级效果内核第一优先级；补 debug view（particles/grid/SDF/mesh/normal/cost）；不绑定最终美术题材。

### 3. 旧版技术拆解：海洋/水体系统

可沉淀能力：无限海平面、Niagara 平面块生成、高度图/SDF 图、VDM 海浪、Single Layer Water 半透明遮挡分析、Translucency Before Water 路径扩展。

定位：作为 Water/Environment Kernel 备用，非第一优先级，除非最终 Art Direction 需要水体/环境表现。

建议：先归素材库，保留水体遮挡修复作为技术点。

### 4. 旧版技术拆解：角色/NPR 材质细节

可沉淀能力：SDF 脸部阴影、Kajiya 头发高光、Matcap 高光、ILM 贴图、Ramp/Curve Atlas 热更新、屏幕空间边缘光、半影着色。

定位：作为 Stylized Material Recipe Library，不单独作为主项目。

建议：拆成配方库，服务最终场景角色/道具/材质。

### 5. AI/MCP 常规生产层

方向：AI/MCP 负责普通材质、蓝图、Actor、参数面板、测试场景、截图记录；用户负责 Art Direction、LookDev、质量验证、底层效果内核。

可沉淀能力：EffectSpec、Material Recipe、Blueprint Scaffold、Verifier Checklist、自动截图/日志、人工审查流程。

定位：证明未来 TA 工作形态，不是“AI 替我做作品”，而是 Human-in-the-loop 生产系统。

## 第一版优先级

- P0：AI/MCP 常规生产层最小闭环；Dynamic Surface Reconstruction Kernel 抽象文档；代表场景候选筛选；Human vs AI 责任边界。
- P1：Stylized Rendering Stack 作为视觉基线；Verifier Checklist；AI 初版 vs 人工 LookDev 对比。
- P2：NNE Runtime Kernel；Gaussian/Neural Volume Kernel；Water/Environment Kernel；UE5.8 自定义渲染核心迁移。

## 结论

新版作品集不是重做旧项目，也不是抛弃旧资源。正确处理方式：旧项目 → 拆成能力 → 进入 Kernel/Workflow/Recipe Library → 根据代表场景重新组合。
