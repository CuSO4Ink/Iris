# NPR_rendering · LOG

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.

### 2026-08-13 18:08 — [发现] 旧 CustomToon 资产兼容迁移
Abyss 的 47 个旧资产因已移除的 `MSM_CustomToon` 枚举在编辑时断言；备份后统一重存为
`MSM_DefaultLit`，无永久 Redirect，零旧标记且 47/47 在干净 5.8.1 下通过幂等加载。

### 2026-08-13 19:45 — [发现] 5.8.1 引擎二进制错配
18:01 的新崩溃来自旧 `UnrealEditor-Renderer.dll` 引用已删除的 `TransBeforeWater` Shader，而非资产；
完整重建 `UnrealEditor` 后原命令退出码 0，且 47/47 资产再次通过零改写加载。

### 2026-08-13 20:38 — [决策] VRoid 样例采用六类最小目录
`AvatarSample_A` 的 98 个资产保持原名，集中到角色根目录下的 `Textures`、`Materials`、`Rig`、
`Animation`、`Model`、`Metadata`；保留 VRM4U 生成的描边材质，不再细分脸、头发或服装。

### 2026-08-13 21:25 — [发现] VRoid 样例缺少量产表面数据
35 张贴图仅有 3 张真实法线，17/23 材质区使用占位法线，且无 ORM、各向异性、SSS、Ramp、
Style 或 Face SDF；先用 Base Color + Scalar 验证原生 Toon，不预制缺失资源。

### 2026-08-13 21:25 — [决策] 首轮材质复用现有成熟图
从 Bifrost 已验证的原生 `SubstrateToonBSDF` 与 Default Lit 图复制项目内母材，创建八个部位实例；
不新增 Material Function、Renderer 修改或第二套 Toon 母材，视觉 Gate 前使用内建 Profile 0。

### 2026-08-13 21:45 — [决策] 23 个导入实例原位接入 Toon
不复制 23 个新实例；将现有实例分别挂到 Face/Body/Cloth/Hair 分类 Toon 实例并显式保留各自贴图，
再逐槽回绑网格。23 张独立 Base Color 保留，四个原 BLEND 叠层先以 Masked 接受视觉 Gate。

### 2026-08-13 22:05 — [决策] 角色采用 Toon 与 Default Lit 混合基线
Face/Body/Hair 的 12 个实例继续使用原生 Toon，Cloth 的 11 个实例改挂 Default Lit Cloth，并以
Specular 0.50、分组 Roughness 0.50–0.78 起步；细节阶段只做两张共享法线，不猜制 UV 专属 ORM。

### 2026-08-13 23:04 — [发现] 共享中间材质实例热切换存在缓存窗口
UE 5.8 的父级切换只刷新被改实例本身；已加载后代可能以旧 Uniform Expression Cache 配合新 ShaderMap
进入渲染断言。崩溃命令未落盘；恢复后改为叶子实例直连，禁止运行时改共享中间父级。

### 2026-08-13 23:05 — [决策] Cloth 使用单张 BC7 PackedNMR
T__12–T__22 各生成一张 R/G Normal XY、B Metallic、A Roughness 的启发式贴图，Normal Z 在材质中重建；
11 个叶子实例直连 `M_NPR_CharacterClothPBR`，保留 Specular 0.50，后续以视觉 Gate 校准而非增建材质路径。

### 2026-08-13 23:26 — [发现] Base Color 梯度不能产生布料微表面
PackedNMR 的 R/G 只能放大 Base Color 已有边缘，平坦色块仍接近中性法线；改为在 UV0 叠加一张共享
`TechnicalWeave` 切线空间细节法线，以 `1 - Metallic` 遮罩并保留 Scale/Strength 两个视觉校准参数。
