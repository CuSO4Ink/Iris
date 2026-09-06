<!-- iris-project-kind: ue -->
# ReflectCache

> **UEAgent first**: Use [UEAgent](../../AGENTS.md) and [HOTPATH](../../skills/ue-mcp-workflows/HOTPATH.md). For live work locate `Saved/UEAgent/route.json` and call the routed Gateway; it binds the project/Editor session. Optional saved-state cache routing returns CACHE_READ or LIVE_CALL. Doctor is diagnostic only. Offline source/cache/config/log analysis needs no MCP and makes no live-state claim.

> 五类生成器和统一 save handler 已在 2026-09-06 的 UE 5.8.1 临时工程中完成受控保存、
> 字段核验与重启验证。Blueprint 新增继承 CDO 覆盖值的 `## Defaults`；详细范围见
> [运行验证](../../notes/runtime-verification-20260906.md)。这不代替 Abyss 生产资产验证。

渐进式读取、MCP 路由、差异 receipt、大小审计和回滚表统一记录在
`../../PROGRESSIVE-DISCLOSURE.md`；本项目只补充 cache 的格式与边界。

## 何时进入

- 需要理解复杂 `UMaterial`、MaterialFunction、Blueprint 或 Niagara System，
  但不值得每次冷读整张图。
- cache 缺失、过期，或要验证保存触发的自动刷新。
- 要维护材质反射格式、VibeUE save hook 或回填命令。

普通材质 CRUD 仍走 `../../skills/ue-mcp-workflows/references/materials.md`。
任何 live rebuild、save-hook 验证或 UE 资产修改都通过项目路由调用 Gateway；Doctor 仅用于诊断；离线
sidecar 读取与格式分析不需要 MCP。

## 契约

- `.uasset` 是唯一真相；只允许 UE -> cache。
- 每份 cache 是源文件同目录的 sidecar：`X.uasset.ai.md`。
- VibeUE 的 package-save handler 为 Material、MaterialFunction、MaterialInstance、Blueprint
  和 NiagaraSystem 原子刷新对应 sidecar；五种类型已通过受控资产 smoke，
  新目标仍须先核对安装版本和实际保存结果。
- v2 `## Logic` 保存真实顶层节点、pin、连线和常用常量；不生成臆测语义。
- `## Deps` 保存直接资产边及可证实的 `relation/node/parameter`；Asset Registry 仍是全项目引用真源，
  cache 不保存反向图或第二套引用状态。
- 先读 cache；写 UE 前只验证目标局部和 dirty state；保存后检查 cache 时间戳。
- Blueprint cache 复用官方 graph DSL，`## Vars` 保存自有变量默认值，`## Defaults` 保存
  相对父类 CDO 的可编辑继承属性覆盖；Niagara cache 保存 stack/有效输入/renderer，
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
6. 修改后按授权保存，并检查 sidecar 时间戳、格式和目标逻辑是否同步推进；用可靠命令
   Receipt 加独立 live readback 验证结果，sidecar 文本差异只作为辅助证据。

## 部署

sidecar 不需要输出目录配置；UE 默认不会把 `.md` 注册为资产或 Cook。源码控制和
UE Migrate 不会自动管理它。精确源码差异只保存在
基础 profile 的 `../../patches/vibeue-ueagent.patch`，Niagara profile 使用其作者工具复合补丁。
`install_engine.ps1` 按 manifest 将选定补丁安装到引擎级 VibeUE；Bootstrap 只绑定项目路由。
route 记录 profile 与引擎/VibeUE revision。`install_engine.ps1 -CheckOnly` 验证源码补丁和
引擎默认配置，`bootstrap.ps1 -CheckOnly` 验证项目绑定；Doctor 证明运行时路由。
