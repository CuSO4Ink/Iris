# QQTechDigest

> **L2 项目身份**。接手本项目的 AI 必读。

## 一句话介绍

用 NapCatQQ + OneBot 11 监听 QQ 群消息，只保留匿名化后的技术线索并生成 Markdown 摘录。

## 当前状态

活跃运行中；MVP、专用 QQ 账号登录和 OneBot 在线配置均已验证。

## 当前焦点

观察首批真实群消息，依据误报/漏报调整规则阈值。

## 技术栈与硬约束

- Windows + Python 3.12 标准库；运行时不安装 Python 第三方包。
- NapCatQQ v4，以 OneBot 11 HTTP 客户端向 `127.0.0.1` 推送事件。
- 必须校验 NapCat 的 `X-Signature` HMAC-SHA1；服务默认只监听回环地址。
- 不保存 `user_id`、昵称、群名片、`self_id`、`raw_message` 或完整原始事件。
- 不使用 UI 自动化；QQ 登录由用户亲自扫码或确认。

## 术语表

- 技术窗口：同一群中，相邻消息间隔不超过 15 分钟的一段对话。
- 技术摘录：规则命中后写入每日 Markdown 的匿名化内容。
- 待处理消息：窗口尚未静默 5 分钟、暂存在 SQLite 中的精简消息。

## 文档地图

- `README.md`：运行、接入与验收方法。
- `LOG.md`：关键决策。
- `BACKLOG.md`：当前与后续工作。
- `qq_tech_digest.py`：MVP 全部运行逻辑。

## 文件边界

- `work/QQTechDigest/` 保留代码、正式文档，以及本机敏感/持久状态 `config.json`、`data/`、`digests/`（均由 `.gitignore` 排除）。
- NapCat Shell、压缩包和登录运行态放在 `tmp/QQTechDigest/napcat/`，删除后由 `setup-napcat.ps1` 重建。
- 测试缓存、临时响应与一次性排查输出不进入项目目录。

## 协作约定

- 默认追求最少数据留存；新增身份字段、原始消息或公网监听前必须明确确认。
- 没有真实误报/漏报样本前，不增加 LLM、OCR、消息回溯或分布式组件。

---

## 维护

- 阶段切换、术语变更或技术栈升级时更新本文件。
- 保持在 100 行以内。
