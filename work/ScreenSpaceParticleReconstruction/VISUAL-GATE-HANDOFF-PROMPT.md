# V2 G4 视觉 Gate 新上下文提示词

```text
/project ScreenSpaceParticleReconstruction

继续推进 precisefluid 工程的 V2 各向异性高斯 Splat 拉丝烟雾，当前任务只聚焦 G4/M3 最终视觉 Gate，不回退到旧 Ping-pong 主线。

开始前完整阅读：
- C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\AI-BRIEF.md
- C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\WISPY-FLUID-SPEC.md
- C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\ANISOTROPIC-GAUSSIAN-SPLAT-SPEC.md
- C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\NIAGARA-RASTER-MCP-PITFALLS.md
- C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction\LOG.md

环境：
- UE 项目：D:\Work\Company\Advance\Fluid\precisefluid
- UE 引擎：C:\Work\UEEngine\UnrealEngine-5.8.0-release
- MCP Gateway：C:\Work\AI\Iris\work\UEAgent\scripts\mcp_gateway.ps1
- V2 System：/Game/SSPR_Validation/M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main
- V2 Material：/Game/SSPR_Validation/M2/AnisotropicSplat_V2/M_SSPR_AnisotropicSplat_Display
- V2 MI：/Game/SSPR_Validation/M2/AnisotropicSplat_V2/MI_SSPR_AnisotropicSplat_HQ
- 验证关卡：/Game/SSPR_Validation/M2/AnisotropicSplat_V2/L_SSPR_AnisotropicSplat_Validation

当前已确认的技术基线：
1. GPU 粒子每帧按当前相机投影到 RasterizationGrid3D(2048×2048×1)。
2. Density 使用 Q10 整数原子加法，Raster Stage 保持 WritesParticles=False。
3. Resolve 覆盖写入 Niagara 自管 2048×2048 RGBA16F User.SSPR_SimRT。
4. SimRT 为 Bilinear、MipMapGeneration=Disabled。
5. Renderer 绑定 TrajectoryTexture <- User.SSPR_SimRT.RenderTarget，材质使用 ScreenPosition.ViewportUV。
6. 多尺度重建为 LOD0 7×7 Medium + 13×13 Body，函数内约 219 taps，当前质量优先。
7. Niagara Fixed Tick Delta=true，Fixed Tick Delta Time=0.01667s。不要关闭；它已解决整张面片忽明忽暗。
8. Niagara 上次检查为 UpToDate、零错误、零警告；一次活动 2048² SimRT 原始回读为 nonzero=32030、RMax≈6.77、RSum≈23390.58。动态粒子下数值允许变化，但不能归零、铺满或只剩单点。
9. 当前 HQ 参数：Filament/Medium/Body=0.18/0.50/0.32，Medium/Body Radius=14/48 px，DensityGain=2，Contrast=0.48，Extinction=2.4，OpacityScale=0.82，SmokeColor=(0.72,0.78,0.88)。
10. 中央暗块不是场景阴影，而是密度梯度光照；当前 Ambient=1、LightStrength=0，以中性光照先验收密度连续性。

当前未通过的核心目标：
- 标准相机距离下不能明显辨认独立粒子点或软泡。
- 同时看到尖细流丝、中尺度连接和柔软致密烟体。
- 静止观察、左右转镜头、平移、拉远都稳定对齐。
- 屏幕边缘无 Wrap/Clamp 拉花，长时间运行不画满。
- 关闭 TAA/TSR 时仍保留主要连续结构。

工作规则：
- 先读取当前资产和用户最新截图/描述再判断，不预设一定要加模糊或方向张量。
- 质量优先；视觉 Gate 通过前不要降 2048 分辨率、减少粒子数或减少采样数。
- 优先修改 MI 参数或独立材质函数，保持 Niagara 数据生产链和材质函数解耦。
- 若仅靠当前三尺度仍断裂，再提出并实施 G5 方向张量/沿流向卷积；不使用 History Ping-pong 制造拖尾。
- 每次资产修改前创建明确备份；修改后执行 Apply/Compile/Save、组件 Rebind/Reinitialize、当前活动 RT 原始 Gate 和 Niagara/材质编译 Gate。
- 不把 MCP 返回成功当成视觉成功，最终必须由用户观察动态画面确认。
- 未经用户明确允许，不使用 computer-use、鼠标控制、窗口切换或自动点击。必须界面操作时停下来给用户手动步骤。
- 当前 `MF_SSPR_MipPyramidDensity` 名称与内部 LOD0 算法不一致，MipBias 输入无效；视觉 Gate 期间不要贸然破坏接口。视觉通过后再新建干净函数完成更名和接口收口。

请先总结你读到的当前基线，然后告诉用户需要观察/截图的最小视觉对照；拿到结果后连续推进 G4，直到给出明确的视觉 Gate 结论或需要用户手动确认的画面。
```
