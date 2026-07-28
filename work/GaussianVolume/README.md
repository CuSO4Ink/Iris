# Gaussian Volume

UE 5.8 中可重光照体积 Gaussian 表示的实验项目。当前主线是 H12（1.112M 7DRGS 质量参考）与 H13（50K Gaussian Volume 紧凑候选）；SVT 是同源画质和资源基线。

## 入口

- [`SPEC.md`](SPEC.md)：目标、约束、Gate 与测量口径。
- [`CLOUD_VERSIONS.md`](CLOUD_VERSIONS.md)：H0–H13 版本账本。
- [`LOG.md`](LOG.md)：实验与失败记录。
- [`mvp/`](mvp/)：数据准备、训练评估、烘焙与 UE 部署脚本。
- [`training/7drgs/`](training/7drgs/)：7DRGS 训练代码及其许可证。
- [`ue-plugin/GaussianVolume/`](ue-plugin/GaussianVolume/)：自研 UE 插件源码快照。
- [`patches/`](patches/)：第三方依赖的最小修改，不复制依赖本体。
- [`evidence/`](evidence/)：可提交的 CSV/JSON 测量结果；原始日志留在本地。

## 本地部署

把 `ue-plugin/GaussianVolume` 复制到 UE 项目的 `Plugins/GaussianVolume`，再按需应用 `patches/` 中的第三方插件补丁。训练资产、VDB/PLY、构建目录和运行日志均可再生，不进入 Git。
