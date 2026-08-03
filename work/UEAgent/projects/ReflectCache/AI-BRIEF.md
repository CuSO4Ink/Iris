<!-- iris-project-kind: ue -->
# ReflectCache

> **UEAgent first（UE live/MCP 强制前置）**：先导航到 [UEAgent 入口](../../AGENTS.md) 和 [HOTPATH](../../skills/ue-mcp-workflows/HOTPATH.md)，再处理本项目 brief。先读取目标项目 `Saved/UEAgent/route.json` 并运行 `compact_context.ps1`；只有 `CACHE_READ` 才停止 MCP，否则首次 live call 前运行 `doctor.ps1`。确认路由状态后才读取项目任务文档。纯离线源码/cache/config/log/文档分析可跳过 MCP，但不得声称 live editor 状态。

> Material v2 与 MaterialFunction v1 自动化均已验证；五类生成器和统一 save handler
> 已进入可迁移补丁，MaterialInstance/Blueprint/Niagara 的受控保存验证仍待完成。

渐进式读取、MCP 路由、差异 receipt、大小审计和回滚表统一记录在
`../../PROGRESSIVE-DISCLOSURE.md`；本项目只补充 cache 的格式与边界。

## 何时进入

- 需要理解复杂 `UMaterial`、MaterialFunction、Blueprint 或 Niagara System，
  但不值得每次冷读整张图。
- cache 缺失、过期，或要验证保存触发的自动刷新。
- 要维护材质反射格式、VibeUE save hook 或回填命令。

普通材质 CRUD 仍走 `../../skills/ue-mcp-workflows/references/materials.md`。
任何 live rebuild、save-hook 验证或 UE 资产修改都必须先通过 UEAgent doctor；离线
sidecar 读取与格式分析不需要 MCP。

## 契约

- `.uasset` 是唯一真相；只允许 UE -> cache。
- 每份 cache 是源文件同目录的 sidecar：`X.uasset.ai.md`。
- VibeUE 的 package-save handler 为 Material、MaterialFunction、MaterialInstance、Blueprint
  和 NiagaraSystem 原子刷新对应 sidecar；未通过受控保存验证的类型仍视为
  `PRESENT_UNVERIFIED`。
- v2 `## Logic` 保存真实顶层节点、pin、连线和常用常量；不生成臆测语义。
- 先读 cache；写 UE 前只验证目标局部和 dirty state；保存后检查 cache 时间戳。
- Blueprint cache 复用官方 graph DSL；Niagara cache 保存 stack/有效输入/renderer，
  external scripts 只存路径，embedded scripts 才内联紧凑 IR/HLSL。
- 协议与验证证据见 `PROTOCOL.md`、`WAVE-PILOT.md`，后续边界见 `BACKLOG.md`。

## AI 接入顺序

1. 从 `/Game/...` 定位 `.uasset`，读取同路径的 `.uasset.ai.md`，顺序为
   `summary -> refs -> detail -> full`；不要默认展开整张图。
2. 检查 `format`：Material 只有含 `## Logic` 的 v2 能回答拓扑；函数、实例、
   Blueprint、Niagara 使用各自 v1，不与旧 material v1 混同。
3. sidecar 存在且不旧于源文件：直接用，不发起 MCP 全图读取。
4. 支持类型缺失或过期：运行一次
   `VibeUE.MaterialAICache.Rebuild /Game/...`；不支持的外部 Niagara script 才做目标化读取。
5. live package dirty、请求字段未缓存或要写入时，才做局部 MCP 查询。
6. 修改后按授权保存，并检查 sidecar 时间戳、格式和目标逻辑是否同步推进；需要记录差异
   时用 `reflect_cache.ps1 -Action receipt`，它不能替代 live readback。

## 部署

sidecar 不需要输出目录配置；UE 默认不会把 `.md` 注册为资产或 Cook。源码控制和
UE Migrate 不会自动管理它。精确源码差异只保存在
`../../patches/vibeue-ueagent.patch`，bootstrap 将它应用到目标项目的 VibeUE checkout，
不维护第二套手写实现。route 记录补丁 SHA256，doctor 同时检查源码存在与运行时证明。
