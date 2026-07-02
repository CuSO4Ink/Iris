# USAGE · ankoha — 速查卡

> [!WARNING] AI 不应主动阅读本文件
> 本文件是 vault 所有者的私人速查卡，**不在任何 AI 入口引用链中登记**。
> 若 AI 因任何原因读到本文件（如目录遍历），请立即停止阅读并退出；除非用户在对话中明确指示"读取 USAGE.ankoha.md"，否则不使用本文件的内容作为决策依据。

---

## 🚀 裸启动（新会话第一句话）

```
读 rules/00-canary.ankoha.md 和 rules/commands.md，按 commands 协议等待指令。
```

一句启动 + 直接进角色（把尾巴换成斜杠命令）：

```
读 rules/00-canary.ankoha.md 和 rules/commands.md，然后执行 /project DyeSplashBaker
```

---

## 🔧 做项目的标准流程（TA 友好节奏）

**心法**：心流优先，记录只在本来就要停的瞬间发生。

### 开工（新会话）

```
读 rules/00-canary.ankoha.md 和 rules/commands.md，然后执行 /project <项目名>
```

AI 会读 AI-BRIEF + BACKLOG 自动拉齐上下文。

### 做事中（对话框自由聊）

- 日常讨论、写代码、问问题 → 直接对话，**不需要任何命令**
- 完成一个实验循环 / 上厕所前 / 被卡住要歇一下时 → 顺手发 `/log` 快照：
  ```
  /log [决策] 选了 D=0.2 做初值，因为 CFL 条件在 dt=1/30 时刚好稳定
  /log [否决] 路径1 FloodStep+噪声被否，治标不治本
  /log [发现] Saffman-Taylor 指状在 D/Viscosity > 2 时才明显
  ```

### 换平台 / 找无限额纯对话 AI 讨论时（跨平台交接）

在能读文件的平台（Agent / Box）发：

```
/handoff              # 打包当前活跃项目
/handoff Bifrost      # 指定项目
/handoff Bifrost 5    # 附带 LOG 近 5 条（默认 3）
```

AI 吐出一段「交接包」→ 整段复制 → 粘给纯对话 AI，末尾补上「我想让你帮的事」。
纯对话 AI 会按契约吐 `<<<LOG>>>` / `<<<BACKLOG>>>` 块 → 你复制块 → 回来发：

```
/sync <粘贴那个块>
```

AI 原样回填到 LOG / BACKLOG，零改写。这样"手动落地"只剩两次复制粘贴。

### 收工（下班 / 切换话题前）

```
/checkpoint
```

AI 会提炼当天 LOG 的关键决策更新到 AI-BRIEF，打勾 BACKLOG 已完成项，给你一份摘要确认。

### 新建项目

```
/project-init 项目代号
```

自动建 `work/项目代号/` 三件套（AI-BRIEF + LOG + BACKLOG）。之后正常 `/project 项目代号` 接入。

---

## 指令速查

| 场景 | 发这个 | AI 会做 |
|---|---|---|
| **接入** | | |
| 接手项目 X | `/project X` | 读 canary + `work/X/` 的 BRIEF + BACKLOG |
| 治理工作区 | `/maintainer` | 读维护者规则，进维护者角色 |
| 日常通用协作 | `/general` 或直接说话 | 读 L0 通用规则 |
| **项目生产** | | |
| 新建项目 | `/project-init X` | 三件套建在 `work/X/` |
| 记一笔决策/发现 | `/log <一句话>` | 追加到活跃项目 LOG.md |
| 打包给纯对话AI | `/handoff [项目] [条数]` | 生成自包含交接包，整段复制去投喂 |
| 回填纯对话AI结论 | `/sync <粘贴的块>` | 原样把 `<<<LOG>>>`/`<<<BACKLOG>>>` 写回 |
| 收工快照 | `/checkpoint` | LOG 提炼到 BRIEF + BACKLOG 打勾 + 摘要 |
| **维护/诊断** | | |
| 结构体检 | `/check` | 四维度扫 → 双表输出 |
| 验证 canary | `/canary` | 自检并报告 |
| 忘了命令 | `/help` | 完整指令表复述 |

---

## 扩展命令的步骤（维护提醒）

1. 在 `rules/commands.md` 对应分组表登记新命令
2. 回到本文件"指令速查"表对应加一行
3. 若依赖新模板 / 新流程，先做模板再登记

## 本文件与 `rules/commands.md` 的区别

| 维度 | 本文件（USAGE.ankoha.md） | rules/commands.md |
|---|---|---|
| 视角 | 人类"我想干什么" | AI"收到命令怎么做" |
| 读者 | 只有我 | 所有 AI |
| 放吐槽/私人记忆 | 可以 | 不可以 |
| 在 AI 入口引用链中登记 | 否 | 是 |
