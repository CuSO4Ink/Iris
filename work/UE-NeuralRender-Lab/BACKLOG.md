# UE Neural Render Lab · BACKLOG

## 已完成裁决

- [x] 运行 smoke check，验证 Teacher/PBR/Student 的形状、有限值和反向传播。
- [x] 训练 tiny Student，并保存最佳 checkpoint、指标与训练配置。
- [x] 在 held-out light/view 组合上生成 PBR／Student／Teacher 对比与角度 sweep。
- [x] 完成数值裁决：held-out RMSE 比值 `0.3876`，FP16 表示 `0.0739 MiB`，通过固定阈值。
- [x] 本人允许进入 R2，R1 视觉 Gate 完成签字。
- [x] 导出五张 UE 输入纹理与 inline HLSL，建立并编译 PBR／Student／Teacher 三个隔离材质。
- [x] 在相同视口、相机、测试面和采样参数下完成三者 GPU A/B。
- [x] R2 裁决：Student/Teacher GPU mean 比值 `1.042`，未达到 `<= 0.60`，停止 R3。
- [x] 删除临时 Probe 与测试 Actor，恢复关卡和视口基线；未保存 `L_Demo`。

## 当前待办

- [x] R4a：实现固定程序化云的体积步进 Teacher 与单次求值神经代理 Student。
- [x] R4a：训练并保存 held-out camera/sun 对比、重光照 sweep、模型大小与 CUDA matched timing。
- [x] R4a：仅把每组训练射线从 96 提高到 384，验证并缓解稀疏监督造成的颗粒和轮廓误差。
- [x] R4a：加入太阳方位 `±22.5°` 连续监督，消除离散方向之间的侧／逆光亮环。
- [x] R4a：将 triplane 从 `64²` 收缩到 `32²`，降低残余高频并把 FP16 表示缩至 `0.0656 MiB`。
- [x] R4a：数值、机器检查与本人视觉 Gate 全部通过。
- [ ] R4b：设计 UE RHI／Tensor 路径并做 matched A/B；不得回退到普通全屏 NNE 或标量 Custom HLSL。

## 不做

全屏 Neural Post Process、风格迁移、扩散遮罩、自动架构搜索、通用材质蒸馏平台、动态云模拟和 Bifrost 生产资产修改不进入当前合同。
