# Bifrost Technical Baseline

> 当前唯一技术基线见 `TECH-MAP.md`。本文件只记录执行结论。

## 要做

1. 在独立 TechLab 中逐项验收恒星、GaussianVolume、Raymarch、HPVolumeCloud、Marching Cubes、FluidFlux 和环境 LookDev。
2. GaussianVolume 的运行时验收与 `Spline -> Gaussian Field` 创作接口。
3. 解析体积渲染、half-res、深度合成与性能证据。
4. 以 ONNX + UE NNE 接入轻量 decoder，驱动 Gaussian Field 的局部动态残差。
5. 技术验收结束后，才选择模块进入固定镜头场景。

## 不做

- 第三人称玩法、S1-S4 跑图和完整游戏化验收。
- 铁磁流体、泛用 VDB 代理、场景扫描 3DGS、Landscape、PCG、Foliage 量产。
- 未验证前扩展 GaussianVolume 的大规模 primitive 加速或通用生产管线。

## 延后但可恢复

自定义 Raymarch、HPVolumeCloud 的 UE 适配、恒星 Layer 2 Marching Cubes 都是独立验收模块，不是废弃项，也不等待场景推进。它们的验收卡见 `TECH-VALIDATION.md`。

## 事实状态

- `L_Bifrost`、blockout、环境材质与首批 Lordenfel 资产存在，但当前不参与技术验收。
- `M_Star_PlasmaCore` Layer 1 已有骨架，尚未在目标镜头验收。
- GaussianVolume 已有 UE Runtime 插件与解析体积 renderer 代码；先确认真实运行状态，再开始 Bifrost 应用层。
- FluidFlux 保留为海面候选，但 Height RT / Niagara 无限网格暂不构成前置条件。
