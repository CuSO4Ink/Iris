# slime · LOG

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.

### 2026-08-14 15:10 — 回滚 SingleLayerWater
当前厚实 Marching Cube 网格与强日照会产生大块灰白/深蓝分区，因此恢复 `Default Lit`；
除非先具备可靠厚度或深度输入，否则不再走该路径。

### 2026-08-14 15:34 — 决策 本地化法线修复
插件 `MF_MarchingCube` 的单边差分会产生方向性块状明暗，故复制为 `MF_SlimeMarchingCube`
并改用中央差分，保持原插件函数不变；孤立且未接入 Grid3D 的 `Blur` 模块不直接启用。
