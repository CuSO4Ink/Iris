<!-- iris-project-kind: ue -->
# Bifrost

> **UEAgent first（UE live/MCP 强制前置）**：先导航到 [UEAgent 入口](../UEAgent/AGENTS.md) 和 [HOTPATH](../UEAgent/skills/ue-mcp-workflows/HOTPATH.md)，再处理本项目 brief。定位目标工程 `Saved/UEAgent/route.json` 并按 `route.json` → `compact_context.ps1` → 必要时 `doctor.ps1` 的顺序执行；只有 `CACHE_READ` 才停止 MCP。纯离线 source/cache/config/log/文档分析可跳过 MCP，但不得声称 live Editor 状态。

## 当前状态

`active` · 2026-08-13 从归档恢复。当前唯一主线是把已有 UE 原生体积云落地为高质量、可扩展的天气系统。

外部实现真值：`D:\Work\Personal\Project\Abyss`，目标关卡 `/Game/Bifrost/Maps/L_Bifrost`。归档前的体积云 v1、海面 v1 和历史研究仍可查，但旧 Gaussian Field / GaussianVolume 路线不再是当前合同。

## 当前合同：Native Volumetric Weather

### 目标

保留现有 `AVolumetricCloud`、`M_Bifrost_Cloud_Nubis`、语义图集、天气图、3D 噪声和 Conservative Density SDF 跳步，把它们接到一套统一天气状态；同一状态同步驱动太阳/天空、大气雾和风，并为后续降水、湿润、水面、雷电、音频等效果提供单一入口。

### 基础与边界

- 唯一云渲染路径：UE 原生 Volumetric Cloud；不再接 GaussianVolume、3DGS 或 VDB 代理。
- 优先复用 UE 原生组件、现有云材质和一个 Material Parameter Collection；不建通用天气插件、接口工厂或第二套状态机。
- 时间流逝与天气是两个维度；首个 Gate 只建立天气状态，不顺带实现完整昼夜系统。
- 审美、构图和最终画面由用户验收；AI 可以完成结构、参数接线、编译、性能与一致性核查。
- 不使用 Computer Use 操作 UE；所有 live 读取、变更和保存必须经过 UEAgent gate。

### W0 Gate：Weather Spine

建立一条最小但耐久的端到端主干：

1. 一个权威天气状态和一个关卡控制器。
2. `Clear`、`Overcast`、`Storm` 三个数据预设，可按时长平滑过渡并可中途改目标。
3. 同一插值状态驱动云覆盖/密度/形态、主光、天空环境、大气雾和风。
4. 将归一化天气量写入 `MPC_BifrostWeather`，并广播一个 Blueprint 可订阅事件，供后续效果读取；消费者不得反向改天气真值。
5. 固定 1080p 镜头下记录当前云基线、三种状态和过渡中的 GPU/CPU 数据；控制层不得引入可测的逐帧资源创建、材质重编译或 SkyLight 高频 recapture。

### W0 通过条件

- 关卡中只有一个天气控制器和一个权威状态；重新载入后引用与预设有效。
- 三个预设都能稳定到达；任意过渡连续，无瞬时跳变、参数 NaN、密度闪烁或材质重编译。
- 云、光、雾、风读到同一插值进度；未来消费者只需读 MPC 或订阅事件，不需修改云控制器。
- Profile 数据区分原生云 GPU 成本与天气控制层开销；先冻结实测基线，再决定后续画质预算。
- 用户通过三态静帧与一段完整过渡的视觉 Gate。

### W0 非目标

降水粒子、地表湿润/积水、海况、雷电雷声、局部天气体积、预测调度、存档、网络同步和完整昼夜循环均不在 W0；它们在主干通过后逐个作为消费者接入。

### 停止与回滚

- 如果现有云材质无法用运行时参数连续控制，先修正现有参数边界，不复制材质或保留双实现。
- 如果天空组件某项不能安全逐帧更新，改为低频或状态落定时更新，不建立新的天空渲染器。
- 任何 live 变更前保存结构快照；失败时恢复当前体积云 v1 资产与关卡引用。

## 当前焦点

先经 UEAgent 读取 `/Game/Bifrost/Maps/L_Bifrost`、当前云材质参数和天空 Actor，冻结 W0 输入；随后只实现天气状态主干与三种预设。

## 文档地图

- [BACKLOG.md](BACKLOG.md)：当前可执行任务。
- [LOG.md](LOG.md)：耐久决策、发现和回滚。
- [HISTORICAL-BRIEF.md](HISTORICAL-BRIEF.md)：归档前旧合同，仅作历史。
- [RESTART-NOTES.md](RESTART-NOTES.md)：旧停止点快照，不是当前 backlog。
- `TECH-*`、`PIPELINE.md`、`ROADMAP.md`、`HANDBOOK.md`：历史设计与验证记录；与本页冲突时以本页为准。
