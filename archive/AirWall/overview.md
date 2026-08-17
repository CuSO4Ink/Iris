# AirWall 生成后无碰撞排查概览

## 最高概率原因

动态生成 Box Collision 后完全没有碰撞，优先查：

1. 组件是否真正注册：`Register Component`。
2. 是否 Attach 到 Actor 根组件或容器组件。
3. `Collision Enabled` 是否为 `Query and Physics` 或至少 `Query Only`。
4. `Collision Response to Pawn` 是否为 `Block`。
5. Box Extent 是否填了半尺寸且不为 0。
6. World/Local 坐标是否混用，导致 Box 生成在错误位置。
7. Preview SplineMesh 是否仍开着碰撞并干扰判断。

## 推荐蓝图生成顺序

```text
Add Box Collision Component
→ Attach Component to Component Root / CollisionContainer
→ Register Component
→ Set World Location / Rotation
→ Set Box Extent
→ Set Collision Enabled QueryAndPhysics
→ Set Collision Object Type WorldStatic / AirWall
→ Set Collision Response to All Channels Ignore
→ Set Collision Response to Channel Pawn Block
→ Set Generate Overlap Events false/true 按需求
→ Add 到 CollisionBoxes 数组
```

## 立刻验证

- 在视口打开 `Show > Collision` 或切换 `Player Collision` 视图。
- 给每个 Box 临时打开 `Hidden In Game = false`，或加 debug draw。
- 打印每段 `Length` 和 `Extent`，确认不是 0。
- 用角色胶囊实际撞，不要只用鼠标选择判断。

## 快速判断

如果视口完全看不到 Box：大概率是没注册、没 attach、生成在错误坐标。  
如果看得到 Box 但穿过去：大概率是 Collision Enabled 或 Response 没设对。  
如果只在编辑器有，运行时没了：检查 Construction Script 生成的组件是否运行时重建，或数组清理逻辑是否误删。
