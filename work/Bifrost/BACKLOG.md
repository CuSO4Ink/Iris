# Bifrost Backlog

## W0 · Weather Spine

- [ ] 经 UEAgent gate 读取并冻结 `L_Bifrost` 的云、主光、Sky Atmosphere、Sky Light、Exponential Height Fog 与风组件真值。
- [ ] 记录当前原生体积云固定 1080p 基线：机位、曝光、关键 CVar、GPU pass 和 RHI 工作集。
- [ ] 在现有 `Abyss` Runtime 模块实现一个天气状态、三个预设和一个控制器；补一个最小自动化测试覆盖插值边界与中途换目标。
- [ ] 创建并接入 `MPC_BifrostWeather`，只暴露后续消费者真正需要的归一化量。
- [ ] 将现有云材质参数、太阳/天空、雾和风接到同一插值状态；禁止逐帧材质创建、重编译和 SkyLight recapture。
- [ ] 在 `L_Bifrost` 放置唯一控制器，创建 `Clear`、`Overcast`、`Storm` 预设并保存。
- [ ] 复测三态与完整过渡的性能、连续性和引用；提交用户视觉 Gate。

## W1 · First Consumers（W0 通过后）

- [ ] 接入降水 Niagara 与镜头近场遮挡。
- [ ] 接入地表湿润 MPC，并联动海面粗糙度/风浪；不先做真实积水模拟。
- [ ] 接入暴风状态下的闪电事件与雷声延迟。

## Later（有真实需求时再启用）

- [ ] 局部天气体积与室内遮蔽。
- [ ] 天气调度、预测、存档和网络同步。
- [ ] 将时间流逝作为独立输入接入太阳轨迹，不与天气预设合并。
