# Bifrost Handbook

> 当前是 TechLab 执行规则。技术验收以 `TECH-VALIDATION.md` 为准；不做场景。

## 1. 当前工作边界

- 不处理 S3 构图、资产摆放、第三人称、路径或最终镜头。
- 每次只验证一个技术模块；测试 Actor 和资源必须可独立开关、删除和复现。
- 一项技术未通过正确性、可控性、性能、证据四项标准前，不接到另一项技术或场景中。

## 2. TechLab 规范

- 使用 `L_Bifrost_TechLab`，固定相机、分辨率、曝光、Directional Light、Sky 与 Fog。
- 每次测试记录：模块版本、UE 版本、GPU、测试分辨率、数据规模、GPU 时间、截图/视频、已知伪影。
- 所有 debug view 和参数开关保留到验收完成；不要只留最终漂亮画面。
- 高层控制必须在 Actor、Component、Blueprint 或 Material Instance 中暴露；不以改 C++ 常量/HLSL 常量作为用户接口。

## 3. 模块顺序

1. T0：测试底座。
2. T1/T2/T8/T9：恒星、GaussianVolume、海面、环境材质的独立事实验证。
3. T3/T5/T6/T7：Gaussian Field、Raymarch、HPVolumeCloud、Marching Cubes 的独立 demo。
4. T4：ONNX + NNE Neural Gaussian Decoder。
5. 全部模块评估后，才决定场景集成组合。

## 4. 禁止事项

- 不在测试期为“看起来像最终场景”而摆放环境资产。
- 不因为一个模块尚未通过就用后期、别的特效或复杂场景遮住问题。
- 不把外部方案、离线结果或材质预览当作 UE5.8 runtime 验收。
- 不删除现有用户资产；只停止对非当前模块的投入。
