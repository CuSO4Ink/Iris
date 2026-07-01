# Kernel Brief v0 · Dynamic Surface Reconstruction

## 定位

Dynamic Surface Reconstruction Kernel 是一个高级效果内核，不是某个固定美术题材。

核心能力：把动态粒子/场数据实时重建成可渲染表面，并允许根据 Art Direction 转译成不同视觉对象。

不要把它等同于“史莱姆”。史莱姆只是一个可选应用。

## 可服务的视觉表达

软体生物/史莱姆、液态金属、魔法墨水/灵液、腐蚀/吞噬场、动态雕塑、生物组织/黏菌、地形隆起/表面生长、形态残影/体积变形。

## 技术组成

1. 数据表示：粒子位置、密度场、SDF 场、外部力场、交互点、状态参数。
2. 邻域查询：Neighbor Grid 3D、粒子录入 grid、邻域采样、密度/约束计算（只抽象通用经验，不把旧工作项目细节变主线）。
3. 表面场生成：粒子→密度场/SDF、多源场混合、可控 smoothing、局部权重/材质属性写入。
4. 表面提取：Marching Cubes、RDG Compute、输出顶点/法线/索引、接 ProceduralMesh 或后续 GPU-only 绘制。
5. 渲染接入：Mesh、SDF volume、Debug volume、材质参数、Niagara/particle coupling。

未来优化：GPU indirect draw、减少 CPU readback、更稳定 topology/normal、支持材质属性场。

## 与 AI/MCP 的关系

AI/MCP 不负责实现该内核。可负责：生成测试 Actor、材质实例、Debug 控制面板、参数 UI、测试场景、自动截图不同状态。

用户负责：内核算法、性能控制、数据流设计、Debug view、最终视觉转译。

## 与 Art Direction 的关系

该内核不能决定美术基调。正确流程：先确定 Art Direction → 再决定内核转译成什么对象 → 再选材质、颜色、运动节奏与镜头。

示例：东方幻想→灵液/墨水/玉髓；科幻→纳米流体/液态金属；黑暗奇幻→腐蚀肉质/诅咒场；抽象→动态雕塑/记忆体。

## 第一版验收目标

最低可展示：一个动态体积/表面对象；可切换 debug view（粒子/field/surface）；至少 2 种视觉转译材质；能在代表场景承担明确视觉功能；有性能与限制说明。

不要求第一版：完整物理真实、全 GPU 最优路径、多应用全做完、与最终美术主题强绑定。

## 作品集展示重点

展示的不是“我做了一个史莱姆”，而是：我实现了一个可复用的动态表面重建内核，并能根据不同 Art Direction 把它转译成多种视觉表达。

breakdown：输入数据 → 场生成 → 表面提取 → 渲染接入 → Debug view → 不同视觉转译 → 在代表场景中的最终用途。
