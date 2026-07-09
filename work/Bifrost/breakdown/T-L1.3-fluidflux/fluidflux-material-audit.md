# T-L1.3 · FluidFlux（Wave）材质结构核查

> MCP 只读查询，2026-07-08。目的：接入 S2-S4 主海面前先摸清真实资产结构，避免猜连线返工。

## 0. 身份澄清
用户确认"FluidFlux"不是市场同名插件，是自己基于内容自带 Demo 素材 `/Game/Materials/DemoPublic/Wave` 魔改的海面方案，内部代号沿用"FluidFlux"（代号实际来自网格命名 `SM_FluxPlane*`）。

## 1. 资产清单

| 路径 | 类型 | 用途 |
|---|---|---|
| `Wave/Model/NS_InfiniteMesh` | NiagaraSystem | 驱动分级平面按镜头距离摆放/切 LOD——"无限海面 clipmap" |
| `Wave/Model/SM_FluxPlane{1x1…1024x1024}` | StaticMesh ×9 | 分级细分密度平面网格（1x1 到 1024x1024 段） |
| `Wave/Model/SM_Distant` | StaticMesh | 远景低模海面 |
| `Wave/M_Wave_Base` | Material | 母材质，**SingleLayerWater** 着色模型，约150+节点 |
| `Wave/M_Wave_Base_Inst` | MaterialInstanceConstant | **生产实例**，43个暴露参数，挂在上述网格上 |
| `Wave/MF_CoastlineWave` | MaterialFunction | 方向性波形计算（Gerstner-wave 式：cos/sin+arctan2+Forward/Upward 向量） |
| `Wave/M_WaveTest` / `M_WaveTest_Inst` | Material / MIC | 独立简化原型，未被 `NS_InfiniteMesh` 引用，判定为遗留测试品，接入时可忽略 |
| `Wave/T_OceanWave` / `T_OceanWave_Volume` / `T_WaveFoam_N` / `T_DetailWaveTexture_01` / `T_DefaultWaveProfile_Forard` | Texture | 波形/泡沫/细节纹理 |

## 2. 当前使用状态
`NS_InfiniteMesh` 目前只被 demo 关卡 `/Game/Environment/Mediterranean_Coast/Maps/Mediterranean_Coasts` 引用放置，**尚未接入 `L_Bifrost`**——T-L1.3 是真实待办，非已完成误记。

## 3. `M_Wave_Base_Inst` 暴露参数分类（调参 checklist）

- **波形/位移**：`WaveTex`(Tex) `HeightTex`(Tex) `WPOIntensity` `HeightBiasIntensity` `WaveForwardIntensity` `OceanMoveSpeed` `Speed` `Frenquency` `NoiseTilling` `WPosTilling` `WorldUVRotator` `SlopeIntensity` `OffsetIntensity` `DDistance` `WorldBiasDistance` `Min`/`Max`
- **法线/细节**：`NormalIntensity` `DetailNormalIntensity` `DetailHeightBiasIntensity` `DetailUVWeight` `UTilling`
- **水体光学（SingleLayerWater）**：`BaseColor`(Vec) `ScatteringCoefficients`(Vec) `AbsorptionCoefficients`(Vec) `PhaseG` `ColorScaleBehindWater` `DepthFadeMin` `DepthFadeMax`
- **海岸/泡沫**：`CoastTex`(Tex) `CoastOffset` `FoamFlatness` `Flatness (S)` `SDFThreshold`
- **区域/朝向**：`LandScapePosition&Size`(Vec) `Upward`(Vec)
- **基础材质属性**：`Metallic` `Specular` `RoughnessMin`
- **调试**：`Debug`

## 4. 关键发现——潜在的区域遮罩接口
`LandScapePosition&Size`（Vector 参数，位置+尺寸形式）结构上很可能可以直接复用为 **07-06 LOG 铁磁流体决策**里要预留的"局部区域遮罩"（S3 恒星磁场影响区），不用新增参数。

**未完全确认**：只读了参数列表，未逐节点追踪它在 `M_Wave_Base` 图里具体怎么消费（原意可能是配合海岸线/Landscape 做距离遮罩）。具体是否能挪用、怎么挪用，建议用户在材质图里打开肉眼确认连线，比 AI 猜连线靠谱——这条留给 HANDBOOK §8"人必须亲自上"清单。

## 5. T-L1.3 接入建议顺序
1. 决定 `NS_InfiniteMesh` 套件是复制一份到 `/Game/Bifrost/Ocean/`（守 07-07 命名空间隔离决策）还是跨文件夹直接引用 demo 原资产（体量大，Niagara+9套mesh，复制成本需权衡）——**待用户拍板**
2. 按 S2-S4 走廊实测宽度（40-60m）与分段（S2:100-240m / S3:240-320m / S4:320-400m，见 `blockout-v2-measured.md`）配置 `NS_InfiniteMesh` 覆盖范围
3. 人工验证 `LandScapePosition&Size` 是否可挪作磁场区遮罩（见上第4节）
4. 冷神性调色：`BaseColor` / `ScatteringCoefficients` / `AbsorptionCoefficients` 往冷白蓝调靠，呼应恒星色域

## 6. 待确认问题
- [x] 资产复制 vs 跨文件夹引用——用户拍板**复制**，见第 7 节
- [ ] `LandScapePosition&Size` 遮罩可用性人工确认

## 7. 复制执行记录（2026-07-08 14:xx）

### 7.1 操作与踩坑
`AssetTools.duplicate("/Game/Materials/DemoPublic/Wave", "/Game/Bifrost/Ocean/Wave")` 一次性复制整个文件夹（44 个资产，比第 1 节清单更全，额外发现 `BP/Tool/`子目录：`BP_HeightMapCreate`+`RT_HeightMap`+`MPC_TopHeightABottomHeight`+`M_Calculate`/`M_PostHeightMap`/调试材质/`MI_DebugPlane*`，以及独立的 `M_StylizedWater`/`M_StylizedWater_Inst`——这些是高度图生成/调试工具链，未纳入本轮修复范围）。

**关键坑**：UE 的 `duplicate` 是**浅拷贝**——只把每个资产单独复制一份，但**不会**把新资产之间的相互引用重定向到彼此，新资产的内部连线仍指向复制前的原始资产。复制完直接验证发现：新 `M_Wave_Base_Inst` 的 Parent 仍指向旧 `/Game/Materials/DemoPublic/Wave/M_Wave_Base`，新 `M_Wave_Base` 材质图里的 6 个 TextureSample 节点、3 处 `MF_CoastlineWave` 函数调用节点，仍指向旧路径下的贴图/函数——新文件夹形同虚有，实际还在"寄生"demo 原资产。（`get_dependencies`/`get_referencers` 这两个查询接口在资产刚被复制/编辑后返回的是陈旧缓存，不能用来验证是否修复成功，需要用 `ObjectTools.get_properties` 直接读对象属性才是真值。）

### 7.2 已修复（材质层，MCP 脚本化批量重定向）
用 `ProgrammaticToolset.execute_tool_script` 遍历 `M_Wave_Base`/`MF_CoastlineWave` 全部节点，凡引用属性（`Texture`/`MaterialFunction`）指向 `/Game/Materials/DemoPublic/Wave/*` 的一律重定向到 `/Game/Bifrost/Ocean/Wave/*` 同名资产：
- `MF_CoastlineWave`：1 个 TextureSampleParameter2D（`T_DefaultWaveProfile_Forard`）
- `M_Wave_Base`：6 个 TextureSample（`T_OceanWave_Volume` ×1 / `T_DetailWaveTexture_01` ×3 / `T_Seafoam_03_NSH` ×1 / `T_WaveFoam_N` ×1）+ 3 个 MaterialFunctionCall（均指向 `MF_CoastlineWave`）
- `M_Wave_Base_Inst.Parent` → 重定向到新 `M_Wave_Base`
- 两个材质均 `recompile` 通过，全部资产已 `save_assets`

以上均用 `get_properties` 逐一读回确认生效（非依赖缓存）。**结论：`M_Wave_Base`/`M_Wave_Base_Inst`/`MF_CoastlineWave` 这套生产材质现在是真正独立、自洽的拷贝**，后续对它做冷神性调色/加遮罩等"魔改"不会影响 demo 原资产。

### 7.3 未修复 / 已知局限
- **`NS_InfiniteMesh`（Niagara）**：内部 Emitter 的网格渲染器（9 级 `SM_FluxPlane*`）与材质绑定极可能仍指向旧路径原始资产——Niagara 的渲染器绑定是深层嵌套属性，当前 MCP 工具集**没有 Niagara 专用工具**，通用 `ObjectTools` 按名取属性够不到这层，风险太高没有强行改。**接入前必须人工在 UE Niagara 编辑器里打开新 `NS_InfiniteMesh`，把 Mesh Renderer 的网格列表和材质覆盖手动重新指向 `/Game/Bifrost/Ocean/Wave/` 下的新资产**，否则新系统摆到关卡里视觉上仍会用旧数据（功能可能不受影响，但违反命名空间隔离目的）。
- `BP/Tool/` 高度图生成工具链（`BP_HeightMapCreate`/`RT_HeightMap`/`MPC_TopHeightABottomHeight`/调试材质）、独立的 `M_StylizedWater(_Inst)`：文件已复制，未做引用核查，是否被 `NS_InfiniteMesh` 运行时依赖（高度图回读做碰撞/交互）待用户确认，本轮不阻塞材质接入。
- `M_WaveTest`/`M_WaveTest_Inst`：确认未被引用的遗留原型，维持不修复。
