# Gaussian Volume

UE 5.8 中可重光照体积 Gaussian 表示的实验项目。当前主线是 H12（1.112M 7DRGS 质量参考）与 H13（50K Gaussian Volume 紧凑候选）；SVT 是同源画质和资源基线。

## 入口

- [`SPEC.md`](SPEC.md)：目标、约束、Gate 与测量口径。
- [`CLOUD_VERSIONS.md`](CLOUD_VERSIONS.md)：H0–H13 版本账本。
- [`LOG.md`](LOG.md)：实验与失败记录。
- [`mvp/`](mvp/)：数据准备、训练评估、烘焙与 UE 部署脚本。
- [`training/7drgs/`](training/7drgs/)：7DRGS 训练代码及其许可证。
- [`ue-plugin/GaussianVolume/`](ue-plugin/GaussianVolume/)：自研 UE 插件源码快照。
- [`ue-plugin/GaussianSplattingForUnrealEngine/`](ue-plugin/GaussianSplattingForUnrealEngine/)：clean-room 7DRGS runtime 的完整源码／shader 快照。
- [`patches/`](patches/)：历史基线或外部依赖的最小补丁。
- [`evidence/`](evidence/)：可提交的 CSV/JSON 测量结果；原始日志留在本地。

## 本地部署

把 `ue-plugin/GaussianVolume` 和 `ue-plugin/GaussianSplattingForUnrealEngine` 分别复制到 UE 项目的 `Plugins/`。训练资产、VDB/PLY、UE 地图、Actor 实例覆盖、构建目录和运行日志不进入 Git；本地 TechLab 现场不能由一次 fresh checkout 自动恢复。
