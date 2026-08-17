# SSPR 全目录资产清理审计（2026-08-12）

## 执行结果（2026-08-13）

本审计提出的清理已按用户批准顺序执行完毕。下文主体保留为“清理前证据与决策依据”；本节是清理后的权威状态。

### 最终状态

| 口径 | 清理前 | 清理后 | 结果 |
|---|---:|---:|---:|
| 可见 `.uasset/.umap` | 192 | 40 | -152 |
| SSPR External Actor 包 | 851 | 154 | -697 |
| SSPR External Object 包 | 35 | 10 | -25 |
| Content 总占用 | 约 `223.96 MiB` | `42.86 MiB` | 约回收 `181.10 MiB` |

清理后 Asset Registry 精确返回 40 个资产：`M3` 29 个、`Versions/V4_AnisotropicSplat_20260730` 11 个。根目录、`Archive`、`M2`、顶层 `Performance`、顶层 `Recovery`、Versions V1/V3 均已无可见资产。当前关卡为 `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev/L_SSPR_AnisotropicSplat_V4_Dev_Validation`，live 读回 `dirty=false`；重启后的 UEAgent Doctor 为 `HEALTHY`。

### 已清理闭包

- 根旧 M2 验证地图、HLOD、ProjTest 与旧 Occupancy/P1Probe RT。
- 两条 Archive（IncorrectGasBootstrap、PingPong）及对应 M2 redirector。
- M2 AnisotropicSplat V2、ParticleTrails、M2 根 NS 与两张旧验证地图闭包。
- Versions V1/V3、旧顶层 Performance/Recovery。
- M3 的 PerfMinTest、三个失败 NeighborGather 候选、普通复制的 GatherCompat DenseG5 原型、旧 Multipass HQ。
- StarterMap 中唯一指向旧 HQ 的 `NiagaraActor_3` 已精确确认组件 Asset 后移除；只保存 StarterMap，随后 HQ referencer=0，分支资产读回 `exists=false`。

旧地图 ExternalActor、注销后残留资产和 Untitled 中的 `SSPR_ParticleTrails_Main` ExternalActor 均在 UE 完全退出后按绝对路径迁入可恢复备份：

`D:/Work/Company/Advance/Fluid/precisefluid/Saved/CodexBackups/SSPR_Cleanup_20260812_BeforeRestart`

终审时又把 7 个“递归文件数为 0”的旧空目录可恢复迁入该备份的 `EmptyDirectories` 子目录；Content 物理顶层现在也只剩 `M3` 与 `Versions`。

本次没有清理 `Saved/CodexBackups`，也没有修改插件、C++、USF、引擎源码或项目源码。

### 当前必须保留的 40 资产闭包

- `M3/AnisotropicSplat_V4_Dev`：正式视觉主线与当前验证图。
- `M3/_RecordPoint_12ms`：12ms 最佳效果锚点与 ReaderWrapped V1。
- `M3/Performance/P0_GatherOnly_Clean_V1`：当前活动 Gather-only 基线。
- `M3/Performance/P0_GatherCompat_RecordPoint_Binary_V1`：BinarySafe 静态候选，真实 SIE Gate 尚未完成。
- `M3/Performance/P0_Gather_RawMoments_V1`：不是活动视觉分支，但 GatherOnly 的 Camera、NeighborQuery、ParticleRead 三类内嵌默认对象仍直接指向该旧 NS 包；在完成 DI 本地化前属于当前运行依赖。
- `M3/Performance/NeighborGather_V1`：RecordPoint、ReaderWrapped 与 BinarySafe 候选均嵌入其私有 DI 对象路径；Asset Registry 不呈现这种包内默认对象依赖，当前不得删除。
- `Versions/V4_AnisotropicSplat_20260730`：当前 M3 验证图 ExternalActor 二进制中直接存在 V4 Level 与 V4 NS 路径，整个冻结闭包继续保留。

因此当前没有可继续安全删除的 SSPR 资产。若以后要进一步删 RawMoments 或 NeighborGather_V1，必须先在隔离候选上本地化 DI、编译与运行验证，再重新扫描二进制嵌入路径；不能只看 Asset Registry referencer=0。

### 终审证据与局限

- RecordPoint 与 GatherOnly live 编译读回均为 7/7 脚本 `UpToDate`、0 error、0 warning。
- 当前 M3 地图重载 MapCheck 为 0 error/0 warning；最终 live 读回仍是该地图且 clean。
- 正式 M3、ReaderWrapped、BinarySafe 的 `GetSystemCompileState` 首次包加载读出现超时/500，不能据此宣称实时编译通过或失败；三者保存态 sidecar 均经源文件 SHA 校验为 `FRESH`，且全项目扫描未发现指向已删除 SSPR 包的路径。后续冷启动 Gate 仍需单独完成这三项 live compile/readback。
- 缓存协调后 orphan sidecar=0；旧 HQ 的 3 个孤儿 sidecar 已隔离到 `Saved/UEAgent/cache-orphans`。现有 2 个 stale sidecar 只属于保留的 RawMoments R2 BodyDebug 材质/MI，不作为当前状态证据。
- 完成上述 live 终审后，UE 通过正常窗口关闭请求干净退出；没有强杀进程，最终不保留后台 UnrealEditor 内存占用。

## 审计范围与口径

- 范围：整个 `/Game/SSPR_Validation` 保存态资产、对应 World Partition External Actors/Objects，以及整个项目 `Content` 中对候选包路径的二进制引用扫描。
- 可见目录当前共 `192` 个 `.uasset/.umap`，约 `35.53 MiB`；隐藏的 World Partition 数据另有 `851` 个 External Actor 包和 `35` 个 External Object 包，约 `188.43 MiB`。合计约 `223.96 MiB`。
- 全目录共发现 `25` 个 `.uasset.ai.md` sidecar，其中只有 `1` 个没有对应 `.uasset`。
- `Saved/CodexBackups` 另有 `50` 个备份目录、约 `83.17 MiB`；它们不出现在 Content Browser，和 Content 资产清理分开处理。
- 本审计没有删除、移动、重命名或修改任何 UE 资产。二进制扫描只能证明保存态引用；执行删除前仍须在 UE Asset Registry 中做一次实时 referencer 复核。
- World Partition 地图必须从 UE 中按地图资产删除并让 UE 处理 External Actors/Objects；不要直接在文件系统中手工删 `__ExternalActors__` 或 `__ExternalObjects__` 子目录。

## 总结先看

当前真正需要保留的核心是：M3 正式视觉主线、12ms RecordPoint、Gather-only、ReaderWrapped，以及仍被当前验证地图引用的 V4 冻结闭包。其余内容可以分成三类：

| 类别 | 主要内容 | 当前结论 |
|---|---|---|
| 明确旧线，可组成闭包清理 | `Archive/IncorrectGasBootstrap_20260728`、`Archive/PingPong_M2_20260728` 及 M2 中两个 redirector | 两条 Archive 分支都只被各自 redirector 引用；把 Archive 与 redirector 一起处理即可，不应留下悬空跳转。 |
| 技术上独立，由历史保留策略决定 | `Performance/DenseG5SparseV2`、`Recovery/DenseG5_20260730`、Versions V1、Versions V3 | 保存态均无跨分支入向引用。若历史只保留 V4，这四组可以进入删除批次。 |
| 可清，但需先解除引用 | 根目录旧 M2 图、M2 Anisotropic V2、M2 ParticleTrails、根目录旧 NS/RT、M3 旧 HQ/RawMoments | 需要按下文依赖顺序处理，不能按文件名零散挑删。 |
| 当前保留 | M3 活动闭包、Versions V4 | V4 的 NS 仍被 M2 与当前 M3 验证地图 External Actor 引用；当前不进入清理批次。 |

若最终采用“只保留活动 M3 + V4 冻结源”的策略，清理整个旧 M2/Archive/V1/V3/Performance/Recovery，加上 M3 已识别冗余，候选回收上限约 `184.5 MiB`，另有孤儿 sidecar 约 `0.11 MiB`。这是依赖解锁后的上限，不是当前可一键删除量。

## 全目录体积分布

| 可见分支 | 资产/地图 | 可见体积 | 隐藏地图数据 | 判断 |
|---|---:|---:|---:|---|
| 根目录 | 4 assets + 1 map | `0.48 MiB` | `31.25 MiB` | 旧 M2-A 验证图与投影/探针资源；候选，但根 NS/RT 需等旧引用归零。 |
| `Archive` | 23 assets | `9.169 MiB` | 无 | 两条明确归档旧线；建议按闭包清理。 |
| `M2` | 77 assets + 2 maps | `4.559 MiB` | `62.54 MiB` | V1/V2 历史开发目录；被 V1/V3、Performance/Recovery 和 Untitled 残留锁住。 |
| `M3` | 34 assets + 1 map | `16.77 MiB` | `0.79 MiB` | 当前主线与近期实验混合；详见 M3 分项。 |
| `Performance` | 1 asset | `0.788 MiB` | 无 | 旧 Sparse V2 旁路候选，无入向引用。 |
| `Recovery` | 1 asset | `0.799 MiB` | 无 | 旧 Dense G5 恢复点，无入向引用。 |
| `Versions` | 45 assets + 3 maps | `2.966 MiB` | `93.87 MiB` | V1/V3 可选历史快照；V4 当前保留。 |

## 必须保留的全局闭包

| 路径 | 理由 |
|---|---|
| `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev` | 正式视觉主线及当前验证图。 |
| `/Game/SSPR_Validation/M3/_RecordPoint_12ms` 中的 RecordPoint 与 ReaderWrapped | 当前最佳效果锚点及 Reader 封装实验。 |
| `/Game/SSPR_Validation/M3/Performance/P0_GatherOnly_Clean_V1` | 当前唯一活动 Gather-only 重启基线。 |
| `/Game/SSPR_Validation/Versions/V4_AnisotropicSplat_20260730` | 当前冻结源；其 NS 仍被 M2 与 M3 验证图引用。V4 地图本身约 `31.28 MiB` 的隐藏数据也暂时随闭包保留，后续只有在解除地图引用后才能再拆分讨论。 |

## M3：必须保留

| 路径 | 数量/体积 | 理由 |
|---|---:|---|
| `/Game/SSPR_Validation/M3/AnisotropicSplat_V4_Dev` | 10 assets + 1 map / 1.038 MiB | 正式视觉主线、验证地图、材质/MI/7 个材质函数；当前主线和 RecordPoint/ReaderWrapped 仍引用这套材质链。 |
| `/Game/SSPR_Validation/M3/_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms` | 1 / 1.061 MiB | 用户确认的最佳效果与干净锚点；验证地图的 World Partition External Actor 正在引用它。 |
| `/Game/SSPR_Validation/M3/Performance/P0_GatherOnly_Clean_V1` | 2 / 1.105 MiB | 当前唯一活动 Gather-only 数据基线；包含 NS 与最小 Raw Density 调试材质。 |
| `/Game/SSPR_Validation/M3/_RecordPoint_12ms/ReaderWrapped_V1` | 1 / 1.415 MiB | 当前 Particle Reader 封装实验；只在明确放弃封装路线后才可删。 |

## M3 第一批：明确失败且当前无入向引用

以下三个包在整个项目 Content 保存态扫描中没有其它资产引用；文档也已明确标为失败或错误落点。它们合计约 `3.322 MiB`，是风险最低的第一批候选。

| 可清理文件夹 | 数量/体积 | 失败原因 |
|---|---:|---|
| `/Game/SSPR_Validation/M3/Performance/NeighborGather_StageB_V1` | 1 / 1.087 MiB | 2048² 像素 × 3×3 cell × 无界 cellCount，满载造成卡死/GPU watchdog 风险。 |
| `/Game/SSPR_Validation/M3/Performance/NeighborGather_StageB_Safe_V2` | 1 / 1.064 MiB | 旧 DI/孤儿节点/partial update 等结构审计失败，禁止复用。 |
| `/Game/SSPR_Validation/M3/Performance/NeighborGather_V2` | 1 / 1.171 MiB | 粒子端 `P0_Gather_1` 原型，执行落点不符合像素端 Stage B 主线，且残留跨包 V1 引用。 |

另有一个没有对应 `.uasset` 的孤儿 sidecar，可与空目录一起清理：

`/Game/SSPR_Validation/M3/_Import_12ms/NS_SSPR_V4Dev_RecordPoint_12ms.uasset.ai.md`

## M3 第二批：方向已冻结，但必须先解除引用

### 1. 旧 Multipass HQ

- 文件夹：`/Game/SSPR_Validation/M3/Performance/P0_Multipass_HQ_V1`
- 资产：3 个，约 `3.972 MiB`。
- 状态：18-stage 滤波/扩散路线已被用户否决并冻结；已有逐文件哈希一致备份。
- 当前阻塞：`/Game/StarterContent/Maps/StarterMap` 仍引用 `NS_SSPR_V4Dev_P0_Multipass_HQ_V1`。
- 解锁条件：先在 StarterMap 中删除对应 Actor 或把组件替换为保留资产并保存地图，再复核 referencer=0，才能整夹删除。

### 2. 旧 RawMoments + Stage C 视觉分支

- 文件夹：`/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1`
- 资产：12 个，约 `2.386 MiB`。
- 内容：旧 NS、2 个主材质、2 个 MI、4 个材质函数、R2 BodyDebug 的材质/MI/纹理。
- 状态：其 Gather 历史证据仍有效，但 Streamline、Normalized Field、R2 Body/Stage C 视觉实现均已冻结，不再是活动分支。
- 当前阻塞：
  - `P0_GatherOnly_Clean_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1` 的 Emitter DI 默认对象仍指向此旧 NS 包；
  - `P0_Multipass_HQ_V1` 也仍指向此旧 NS 包。
- 解锁条件：先把 GatherOnly 的 NeighborQuery/ParticleRead/Camera DI 默认对象本地化，并先清理旧 HQ；确认无跨包引用后再整夹删除。

### 3. NeighborGather_V1

- 文件夹：`/Game/SSPR_Validation/M3/Performance/NeighborGather_V1`
- 资产：1 个，约 `1.760 MiB`。
- 状态：设计上是失败候选，但当前仍是旧 DI 默认对象的依赖包，不能直接删。
- 当前保存态入向引用：
  - `_RecordPoint_12ms/NS_SSPR_V4Dev_RecordPoint_12ms`
  - `_RecordPoint_12ms/ReaderWrapped_V1/NS_SSPR_V4Dev_RecordPoint_12ms_ReaderWrapped_V1`
  - 上述三个第一批错误候选中的 StageB V1、Safe V2、NeighborGather V2。
- 第一批删除后仍有 RecordPoint 与 ReaderWrapped 两个引用。由于 RecordPoint 是冻结锚点，不建议只为省 `1.760 MiB` 修改它；当前最稳妥做法是把 V1 标成“Legacy Dependency，勿运行”，暂时保留。

## M3 第三批：由用户决定是否继续保留

| 路径 | 数量/体积 | 建议 |
|---|---:|---|
| `/Game/SSPR_Validation/M3/PerfMinTest` | 1 / 0.709 MiB | P1 Enabled Binding 的已完成验证载体；无项目内入向引用。若不再需要复测 P1，可归档或删除。 |
| `/Game/SSPR_Validation/M3/_RecordPoint_12ms/ReaderWrapped_V1` | 1 / 1.415 MiB | 当前正在做的标准 Position+Velocity Reader 封装；不是走叉线。只有决定改走 GatherOnly Portable 新封装并完成替代后才删。 |

## 不能单独清理的正式材质函数

`AnisotropicSplat_V4_Dev/Functions` 下的七个函数虽然包含 Raw、Streamline、HQBaseline、HQFluidV2 等历史命名，但当前 `M_SSPR_AnisotropicSplat_G5_V4_Dev` 仍直接引用它们，MI、正式 NS、RecordPoint 和 ReaderWrapped 又继续引用该材质链。因此现在不能按名字挑删；必须先建立新的自包含材质并重定向所有保留 NS，才可能剥离。

## 关键跨分支依赖

```text
验证地图 External Actor
  -> _RecordPoint_12ms
      -> NeighborGather_V1（旧 DI 默认对象）
      -> 正式 MI -> 正式 Material -> 7 个 Material Function

ReaderWrapped_V1
  -> NeighborGather_V1（旧 ParticleRead 默认对象）
  -> 正式 MI -> 正式 Material -> 7 个 Material Function

P0_GatherOnly_Clean_V1
  -> P0_Gather_RawMoments_V1 的旧 NS（旧 DI 默认对象）
  -> 本地 M_SSPR_GatherRawDensity_Debug

StarterMap
  -> P0_Multipass_HQ_V1
      -> P0_Gather_RawMoments_V1 的旧 NS
```

## 建议清理顺序

1. 第一批删除三个无入向引用的错误候选，并清理 `_Import_12ms` 孤儿 sidecar。
2. 给保留资产补清晰标识：`ACTIVE`、`ANCHOR`、`LEGACY_DEPENDENCY`，避免以后误用 V1。
3. 将 GatherOnly 的三个 Emitter DI 默认对象本地化，解除对旧 RawMoments NS 的跨包引用。
4. 处理 StarterMap 对旧 HQ 的引用，随后删除整个 `P0_Multipass_HQ_V1`。
5. 再复核并删除整个 `P0_Gather_RawMoments_V1`，不要拆散删其中材质/函数。
6. 最后由用户决定是否保留 `PerfMinTest`；ReaderWrapped 要等 Portable 替代完成后再决定。

按上述顺序，暂不触碰正式主线、RecordPoint、GatherOnly 和 ReaderWrapped：

- 第一批可减少约 `3.322 MiB`、3 个可见版本；
- 完成依赖解锁后，再减少约 `6.358 MiB`、15 个资产（旧 HQ + 旧 RawMoments）；
- 若再归档 PerfMinTest，总计可减少约 `10.389 MiB`、19 个资产。

## 非 M3：保存态清理候选

### A. Archive 两个旧闭包

| 闭包 | 可见资产/体积 | 必须一并处理的 redirector | 依据 |
|---|---:|---|---|
| `/Game/SSPR_Validation/Archive/IncorrectGasBootstrap_20260728` | 3 / `7.966 MiB` | `/Game/SSPR_Validation/M2/GridTrails/BP_SSPR_GridTrails_Main` | 文件夹已标为 Incorrect Gas Bootstrap；其中旧 Niagara System 单包约 `7.93 MiB`。保存态唯一跨分支入向引用就是这个 ObjectRedirector。 |
| `/Game/SSPR_Validation/Archive/PingPong_M2_20260728` | 20 / `1.203 MiB` | `/Game/SSPR_Validation/M2/BP_SSPR_TemporalOrchestrator` | 文档明确为旧 Current/History Ping-pong、多 RT、相机跟随 SmokeCard 原型，不再定义生产架构；保存态唯一跨分支入向引用就是这个 ObjectRedirector。 |

这两组应按“Archive 文件夹 + redirector”删除，合计约 `9.175 MiB`。只删 Archive 而保留 redirector 会制造悬空跳转；只删 redirector 而保留 Archive 则不会减少版本噪声。

### B. 已隔离的历史候选

| 路径 | 可见体积 | 地图隐藏体积 | 保存态入向引用 | 建议 |
|---|---:|---:|---:|---|
| `/Game/SSPR_Validation/Performance/DenseG5SparseV2` | `0.788 MiB` | 无 | 0 | 旧 Sparse V2 性能旁路候选。当前 Gather-only 与 RecordPoint 都不依赖；若不再复测旧 G5，可删。 |
| `/Game/SSPR_Validation/Recovery/DenseG5_20260730` | `0.799 MiB` | 无 | 0 | 旧 Dense G5 二进制恢复点。当前已有 V4 与 RecordPoint 锚点；若不再需要旧 V2 恢复，可删。 |
| `/Game/SSPR_Validation/Versions/V1_ParticleTrails_20260729` | `1.018 MiB` | `31.28 MiB` | 0 | 圆形 ParticleTrails 冻结快照；若历史只保留 V4，建议整图删除。其地图 Actor 反而仍引用 M2 ParticleTrails NS，删除 V1 会解除这条旧锁。 |
| `/Game/SSPR_Validation/Versions/V3_AnisotropicSplat_20260730` | `0.970 MiB` | `31.29 MiB` | 0 | V3 冻结快照；若历史只保留 V4，建议整图删除。其地图 Actor 仍引用 M2 Anisotropic NS，删除 V3 会解除这条旧锁。 |

这四组保存态没有来自其它分支的入向引用；若用户确认只保留 V4 作为历史冻结源，可回收约 `66.15 MiB`。其中 V1/V3 的大头是 World Partition 外部包，必须通过 UE 删除地图资产。

### C. M2 历史开发目录

| 路径 | 可见内容 | 隐藏地图数据 | 当前跨分支阻塞 | 解锁方式 |
|---|---:|---:|---|---|
| `/Game/SSPR_Validation/M2/AnisotropicSplat_V2` | 49 assets + 1 map / `3.255 MiB` | `31.27 MiB` | V3 地图 Actor；`Performance/DenseG5SparseV2`；`Recovery/DenseG5_20260730` | 删除或重定向这三组引用后，整目录删除。不要拆着删 30 个函数和 2 个性能 NS。 |
| `/Game/SSPR_Validation/M2/ParticleTrails` | 25 assets + 1 map / `1.017 MiB` | `31.27 MiB` | V1 地图 Actor；`/Game/Untitled` 的残留 External Actor | 删除 V1 后，再在 UE 中处理 Untitled 残留 Actor；referencer=0 后整目录删除。 |

`M2/AnisotropicSplat_V2` 内部还有 `DuplicateControlV1` 与 `PerfSparseV1` 两个约 `1.568 MiB` 的历史性能 NS，以及两个分支各自的 `Archive/M_SSPR_ParticleTrails_Display_M2Frozen`。因为整个 M2 分支均已被 M3/V4 取代，优先按目录闭包处理，不建议再做逐函数微清理。

M2 根部另外有：

- `M2/BP_SSPR_TemporalOrchestrator`：2.6 KiB ObjectRedirector，随 Archive PingPong 闭包处理；
- `M2/GridTrails/BP_SSPR_GridTrails_Main`：2.6 KiB ObjectRedirector，随 IncorrectGasBootstrap 闭包处理；
- `M2/NS_SSPR`：约 `0.282 MiB`，只被旧 Archive PingPong 蓝图引用；Archive 清理后可作为尾项删除。

### D. 根目录旧 M2 验证闭包与公共旧资源

- `/Game/SSPR_Validation/L_SSPR_M2_Validation` 没有来自其它主线的入向引用；扫描出的 `140` 个 External Actors、`5` 个 External Objects 与 HLOD 都属于该图自身闭包。地图本体很小，但整图约 `31.26 MiB`，可列入旧地图删除批次。
- `/Game/SSPR_Validation/NS_SSPR_ProjTest` 仍被根 M2 图、M2 ParticleTrails 图、Versions V1 图、Versions V3 图引用。上述旧图全部移除后再删。
- `/Game/SSPR_Validation/RT_SSPR_Occupancy` 仍被旧图、Archive PingPong、`NS_SSPR_ProjTest` 与 M3 `PerfMinTest` 引用。若保留 PerfMinTest，就继续保留该 RT。
- `/Game/SSPR_Validation/RT_SSPR_P1Probe` 只被 M3 `PerfMinTest` 引用；与 PerfMinTest 同生共灭，不应先删 RT。
- `L_SSPR_M2_Validation_HLOD0_Instancing` 只属于根地图闭包，随地图处理。

## World Partition 实际占用

| 地图 | External Actors | External Objects | 当前处理意见 |
|---|---:|---:|---|
| 根 `L_SSPR_M2_Validation` | 140 / `31.24 MiB` | 5 / `0.01 MiB` | 旧 M2-A 图，候选删除。 |
| M2 `L_SSPR_AnisotropicSplat_Validation` | 139 / `31.26 MiB` | 5 / `0.01 MiB` | 解除三处跨分支引用后删除。 |
| M2 `L_SSPR_ParticleTrails_Validation` | 140 / `31.26 MiB` | 5 / `0.01 MiB` | 解除 V1 与 Untitled 引用后删除。 |
| M3 `L_SSPR_AnisotropicSplat_V4_Dev_Validation` | 13 / `0.78 MiB` | 5 / `0.01 MiB` | 当前主线图，保留。 |
| Versions V1 验证图 | 140 / `31.27 MiB` | 5 / `0.01 MiB` | 可选历史快照；建议只留 V4 时删除。 |
| Versions V3 验证图 | 140 / `31.28 MiB` | 5 / `0.01 MiB` | 可选历史快照；建议只留 V4 时删除。 |
| Versions V4 验证图 | 139 / `31.27 MiB` | 5 / `0.01 MiB` | 当前仍有 M3 引用，保留。 |

五张旧图（根 M2、M2 Anisotropic、M2 ParticleTrails、V1、V3）的隐藏数据合计约 `156.36 MiB`。这解释了为什么 Content Browser 看起来资源不大，但项目磁盘仍然臃肿。

## 全目录关键依赖图

```text
M2/GridTrails redirector
  -> Archive/IncorrectGasBootstrap

M2/BP_SSPR_TemporalOrchestrator redirector
  -> Archive/PingPong_M2
      -> M2/NS_SSPR + RT_SSPR_Occupancy

Versions V3 地图 Actor
  -> M2/AnisotropicSplat_V2/NS_SSPR_AnisotropicSplat_Main
Performance/DenseG5SparseV2 -----------^
Recovery/DenseG5_20260730 -------------^

Versions V1 地图 Actor
  -> M2/ParticleTrails/NS_SSPR_ParticleTrails_Main
/Game/Untitled 残留 External Actor ----^

M2 验证图 Actor
  -> Versions/V4/NS_SSPR_AnisotropicSplat_V4
M3 当前验证图 Actor -------------------^

旧 M2/V1/V3 地图 + Archive + PerfMinTest
  -> 根目录 NS_SSPR_ProjTest / RT_SSPR_Occupancy / RT_SSPR_P1Probe
```

## 建议执行批次（全 SSPR）

1. **低风险旧线闭包**：实时复核后，清理两个 Archive 文件夹及各自 redirector；清理根 `L_SSPR_M2_Validation` 整图闭包；执行 M3 第一批三个失败候选与孤儿 sidecar。
2. **确定历史保留策略**：若只保留 V4，删除 Versions V1、Versions V3、旧 Performance 与 Recovery。删除 V1/V3 时从 UE 删除地图，连同各自 External Actors/Objects 一并处理。
3. **清旧 M2**：处理 `/Game/Untitled` 残留 Actor，复核 M2 Anisotropic 与 ParticleTrails 都无外部 referencer 后，分别整目录删除。
4. **清公共尾项**：复核后删除 `M2/NS_SSPR`、根 `NS_SSPR_ProjTest` 和不再被 PerfMinTest 使用的旧 RT/HLOD。
5. **按 M3 专项顺序解锁**：本地化 GatherOnly DI，处理 StarterMap 的旧 HQ Actor，再清旧 HQ/RawMoments；RecordPoint、ReaderWrapped、GatherOnly 与正式 M3 不动。
6. **重启与验证**：Fix Up Redirectors、保存受影响地图、重启 UE，检查 Asset Registry referencer、主线地图、RecordPoint、GatherOnly 与 ReaderWrapped。通过后再单独讨论 Saved/CodexBackups。

任何一步若 UE 实时 referencer 与本审计不一致，以 UE 实时 Asset Registry 为准并停止该闭包；不要用文件系统强删绕过引用。

## Saved/CodexBackups

当前 `50` 个目录约 `83.17 MiB`，但不会造成 Content Browser 版本混乱。第一轮不建议连同 UE 资产一起删除。更稳妥的做法是：保留少量已验证恢复点和哈希清单，把其余历史备份整体移出项目到离线归档；待 Content 清理和 UE 重启验证通过后，再单独批准删除旧备份。
