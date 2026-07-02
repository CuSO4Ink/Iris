# AirWall · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 定义 Spline AirWall 的最小可行架构：Spline 数据、碰撞代理、Niagara 视觉、玩家接触事件、材质参数传递。

## 待办

- [ ] 盘点旧方案：透明面片/模型碰撞的资产类型、摆放方式、碰撞通道、当前痛点。
- [ ] 设计 Spline 编辑层：支持拉伸、增删控制点、墙高/厚度/段密度参数。
- [ ] 设计碰撞代理层：沿 Spline 自动生成 Box Collision、Spline Mesh Collision 或分段 Shape Collision，并统一 Pawn/Camera/Projectile 响应。
- [ ] 设计 UV 连续方案：基于 Spline 弧长累计 U，墙高映射 V，避免每段 Niagara/mesh 断纹。
- [ ] 设计 Niagara 视觉层：墙面基础能量流、边界扰动、接触点波纹、远近 LOD。
- [ ] 设计玩家交互层：从碰撞 Hit/Overlap 获取接触点，转换到 Spline 距离或局部 UV，再传给 Niagara/材质。
- [ ] 限制性能预算：透明 overdraw、同时波纹数量、Niagara 粒子数、碰撞分段数量。
- [ ] 做 MVP 验证：一条可拉伸 Spline 墙 + 连续 UV + 玩家碰撞触发单点扩散波纹。
- [ ] 做回归检查：玩家胶囊阻挡、相机行为、投射物/交互 Trace、网络同步需求。

## 已完成（近期，便于回忆）

- [x] 新建 AirWall 项目三件套：AI-BRIEF / LOG / BACKLOG。
- [x] 明确项目方向：从透明面片/模型碰撞升级为 Spline 可编辑 Niagara 空气墙特效系统。

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。
