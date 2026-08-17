# UE Neural Render Lab · BACKLOG

## 当前待办

- [ ] 启动 2026-08-16 完整链接后的 Abyss Editor，确认 `FNeuralVolumeProxyCS` 编译、`NRL_R4c_Box.fp16.bin` 加载且日志无绑定错误。
- [ ] 本人保持相机固定，在 Debug View 3 下只修改 Actor `Location.Z`；确认命中遮罩与选中 Actor 的 Box 线框同步移动，而不是只缩放。
- [ ] Z 向通过后检查 Debug View 1／0、Scene Depth 遮挡、相机平移／旋转和 `SunDirection` 响应。
- [ ] 在固定视口与分辨率下测量 `r.NeuralVolumeProxy.Enable=0/1` 的 matched GPU A/B；未测量前不声称 UE 实时成本优势。
- [ ] 若本人决定正式保留该 Actor，再单独决定是否保存 dirty 的 `L_Demo`；若本人明确授权清理，再删除已废弃的 `/Game/NeuralRenderLab` 资产。

## 不做

全屏 Neural Post Process、普通贴图材质回退、在线训练、动态云拓扑、自动架构搜索、通用蒸馏平台和 Bifrost 生产资产修改不进入当前路径。
