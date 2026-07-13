# Bifrost AI Brief

最后更新：2026-07-13

## 项目身份

Bifrost 是固定镜头优先的 UE 场景作品。核心是恒星驱动的 Gaussian Field：Spline 和宏观参数生成 Gaussian primitive，GaussianVolume 在 UE 中进行解析体积渲染；后续用轻量 ONNX decoder 生成局部动态残差。

## 读文档顺序

1. `TECH-MAP.md`：技术范围与系统架构。
2. `ROADMAP.md`：当前阶段。
3. `BACKLOG.md`：下一项最小工作。
4. `TECH-VALIDATION.md`：当前 TechLab 验收标准与依赖。

## 当前约束

- 不再做第三人称玩法、S1-S4 跑图或全场景扩张。
- 不启用铁磁流体、VDB 代理或场景扫描 3DGS。
- Raymarch、HPVolumeCloud 的 UE 适配、Marching Cubes 均进入独立 TechLab 验收，不再依赖场景推进。
- GaussianVolume 先证明 renderer，再做 field authoring，最后才接神经模型。
- 用户已于 2026-07-12 恢复 S3 场景构图工作；允许围固定 Hero 镜头重排现有资产，但仍不扩张为 S1-S4 全场景制作。
- 2026-07-13 用户判断当前 AI 场景编辑质量不足，S3 画面**尚未验收**。暂停继续靠临场包围盒/截图试摆；场景编辑支撑结构后置，当前先确认 GaussianVolume 的 UE 落地与性能基线。

## 场景编辑交接

- 当前关卡：`/Game/Bifrost/Maps/L_Bifrost`；Hero viewport 暂定约 `(28000,-7000,900)`、`Pitch=5.5 / Yaw=87.7`，仅作工作机位，未锁最终镜头。
- 已接入：S3 高细分 Hero 海面、Height Capture、连续斜坡沙滩、右侧沙嘴、水下浅滩、半浸岩石；巨崖与近距离恒星已恢复压迫尺度。
- 已调 LookDev：深冷湿沙、较粗糙暗水、冷色 Directional/Sky 填充、恒星降曝；均为工作参数，未获用户审美验收。
- Gaussian Actor 已改为从 Spline 生成（64 primitives、Thickness 180、Density 1.6、Emission 2.6），但本次停止前尚未完成最终画面复核。
- 已知编辑器干扰：水面出现的蓝色三角线是 viewport Mesh Edges 覆盖，不是材质输出；最终画面验收前需关闭。
- 场景编辑恢复前仍需定义“场景语义清单 + 空间/镜头约束 + 可编辑/锁定范围 + 变更快照 + 量化检查 + 用户 Gate”；当前不推进该项，先做 GaussianVolume 验证。
