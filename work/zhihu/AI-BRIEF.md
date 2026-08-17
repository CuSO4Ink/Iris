# zhihu

<!-- /project-init --ue inserts the UE marker and UEAgent-first block above this title. -->

## State

`frozen`

## Contract

- **Problem**: 本机需要可用、已认证的官方 `zhihu-cli` Skill，且安装初始化流程需要可复用记录。
- **Goal**: 从知乎官方稳定版发布包安装 Skill 与 CLI，配置 Access Secret，并完成最小在线验收。
- **Non-goals**: 自建知乎客户端或 MCP Server；在仓库中保存 Secret；批量读取本人数据。
- **Mature baseline / proven pattern**: 知乎官方 `zhihu-cli` Skill、其状态检查与 setup 脚本。
- **Smallest end-to-end pass**: `status` → `setup.ps1` → `auth set --secret-stdin` →
  `auth status --verify` → `me contents --type all --limit 1`。
- **Pass**: Skill 已安装，CLI 兼容，凭证在线验证与一条最小本人内容查询均成功；空列表也算成功。
- **Stop / rollback**: 发布源或完整性检查失败即停止；Skill 旧版完整备份位于
  `C:/Users/violinapeng/.codex/skill-backups/zhihu/0.2.1-before-0.3.0-20260814/`。

## Implementation

- **Canonical path**: 官方稳定版 Skill → Skill 自带脚本 → 用户目录 CLI → 知乎开放平台。
- **Reused foundation**: 官方 Skill 的 `run.ps1` 与 `setup.ps1`；不调用 PATH 中来源不明的裸命令。
- **Module boundaries**: Skill 包负责工作流与校验，CLI 负责认证和开放平台调用。

## Current Gate

`PASS`（2026-08-14）：Skill 0.3.0 安装完成，CLI 0.2.0 兼容，凭证在线验证与
`me contents --type all --limit 1` 均成功。

## Truth

- **Implementation truth**: 官方稳定版 Skill 0.3.0 已安装；ZIP SHA-256 为
  `2AF2647C468A366050A39DD78B8D844ECCAEB679D91A56CD134573C0B383E4DF`，无自定义客户端。
- **Runtime / external truth**: CLI 0.2.0 位于
  `C:/Users/violinapeng/AppData/Local/ZhihuCLI/current/zhihu-cli.exe`，兼容且密钥链认证已在线验证；
  官方 CLI 0.3.0 可选更新尚未授权。

## Current Focus

当前基线已通过并冻结；仅在用户明确同意后执行可选 CLI 升级。

## Constraints

- Access Secret 只经进程标准输入传递，不写入仓库、不回显完整值。
- 在线验收只执行 `auth status --verify` 与 `me contents --type all --limit 1`，避免额外额度消耗。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/zhihu/`.

## Document Map

- `AI-BRIEF.md`: contract and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
