# QQTechDigest · LOG

> 决策流水。追加式，新条目加在文件末尾。

## 条目格式

```text
### YYYY-MM-DD HH:MM — 标题
一句话结论，或决策理由 + 否决方案。
```

---

### 2026-08-02 — [决策] 采用 OneBot HTTP 回调

MVP 只接收事件，不调用 QQ API；HTTP 回调可由 Python 标准库完成，比引入 WebSocket 依赖更小。

### 2026-08-02 — [决策] 身份字段在入口丢弃

仅在短期窗口保存哈希后的群/消息键、时间、正文和安全媒体 URL；发送者身份和原始事件不落盘。

### 2026-08-02 — [决策] 首版采用可解释规则筛选

本机没有可用模型服务或 API 密钥，先用故障、因果、技术词和代码/链接信号筛选；有真实样本后再决定是否接 LLM。

### 2026-08-02 — [发现] OneKey 安装器上游下载失效

NapCat v4.18.13 的 OneKey 引导器下载 QQ 时返回 404；本机已有 QQ 9.9.31.49738，改用官方 `NapCat.Shell.zip` 手动 Shell 路径并验证成功。

### 2026-08-02 — [验证] 专用账号与 OneBot 运行链路在线

NapCat 本地状态返回已登录且未离线；运行时配置确认 `qq-tech-digest` HTTP 客户端已启用，回调 URL 与 HMAC 密钥匹配。

### 2026-08-12 — [维护] NapCat 运行态迁到 tmp

将项目内 `.runtime/napcat` 整体迁到 `tmp/QQTechDigest/napcat/`，并修改 `setup-napcat.ps1` 使下载、解压和登录运行态都直接落到该位置。`config.json`、`data/` 与 `digests/` 继续留在项目目录作为本机持久状态，但保持 Git 排除；完成项已从 `BACKLOG.md` 移除。
