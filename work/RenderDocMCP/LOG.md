# RenderDocMCP · LOG

> 决策流水。追加式，新条目加在**文件末尾**。由 `/log` 命令维护。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签（可选，加在标题前）

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

<!-- 新条目追加在下方 -->

### 2026-07-10 14:15 — 项目初始化

[决策] 采用 RenderDoc Python Replay API + MCP Python SDK (FastMCP/stdio) 方案。核心路径：`OpenCaptureFile()` → `ReplayController` → `GetDrawcalls()` / `DisassembleShader()` 等。否决了 "调用 qrenderdoc UI API" 方案——UI 依赖 Qt 事件循环，不适合 headless MCP server。

### 2026-07-10 14:15 — Shader 反编译策略

[决策] 反编译分两层：① `DisassembleShader()` 拿反汇编（DXBC / SPIR-V / ISA）；② 常量缓冲区值通过 `GetCBufferVariableContents()` 递归输出。不自己写 DXBC→HLSL 反编译器，依赖 RenderDoc 内置能力，后续可扩展接入 dxc/ spirv-cross。
