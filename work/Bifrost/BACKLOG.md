# Bifrost Backlog

> TechLab 验收仍是技术主线；S3 固定镜头构图已由用户恢复，范围仅限现有资产重排与 Hero 画面收口。

## 当前

- [ ] **T2 / G4：确认 GaussianVolume 落地与性能基线**。复用 GaussianVolume 项目已完成的 UE 5.8 G0-G3 主体，在固定机位记录 1080p 下 `N=1/32/64/128` 的 GPU 时间、伪影与失效点；先确认 64 primitives / ≤2ms 初始预算，再决定是否优化。
- [x] S3 第一轮构图重排：隐藏非 Floor blockout/ScaleTest 参照；按包围盒重排 cliff、column、rock、Gaussian 和恒星；固定 Hero viewport 并保存 `L_Bifrost`。
- [x] S3 岸边浪最小接入：修复 Wave MI/HeightMap BP 的旧路径引用，放置高细分 Hero 水面与 Height Capture；保留 Niagara infinite clipmap 为后续性能/远景项。
- [~] S3 第二轮 LookDev（**未验收，暂停**）：陆地改为约 4° 主沙滩坡 + 右侧沙嘴 + 水下浅滩，三块 Rock_S3 半浸打断岸线；沙地改深冷湿沙，水面提高粗糙度并压暗；Directional/Sky 改为冷色填充；恒星上移并降低 emissive；Gaussian 恢复 Spline 生成。需在 T-SCENE-SUPPORT 后重新审视，不把当前摆位当定案。
- [ ] `T0` 创建 `L_Bifrost_TechLab` 和统一记录模板。

## 后置

- [ ] **T-SCENE-SUPPORT**：建立 AI 场景编辑支撑结构。最低内容：Actor 语义角色与锁定级别、资产真实尺度/包围盒/接地面、Hero 镜头投影与屏占、前中后景区、焦点/负空间/遮挡约束、海岸线与水位约束、变更前快照、变更后数值检查、用户审美 Gate。完成前暂停大批量场景重排。

## 随后独立验收

- [ ] `T1` 恒星 Layer 1 + 标准光照/大气链。
- [ ] `T3` Spline -> Gaussian Field Authoring。
- [ ] `T4` Neural Gaussian Decoder：训练、ONNX、NNE runtime。
- [ ] `T5-T6` 可复用 Raymarch Core 与 HPVolumeCloud UE 适配。
- [ ] `T7` Layer 2 Marching Cubes 的 SDF 输入链与局部化性能。
- [ ] `T8` FluidFlux 材质、Niagara、Height RT。
- [ ] `T9` 环境材质 LookDev。

## 暂停

第三人称、S1-S4 跑图和全场景扩张仍暂停；S3 LookDev 也暂停到 T-SCENE-SUPPORT 完成。
