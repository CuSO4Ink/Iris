# Onboarding · Project — 项目接入指令（L0 + L2）

> **用法**：粘贴前把 `{项目名}` 替换成实际项目名（共 3 处）。

---

```text
你接入的是 ankoha 的工作区：iris（路径 c:\Work\AI\iris）
接手项目：{项目名}，目录 work/{项目名}/

先按顺序读：
1. rules/00-canary.ankoha.md
2. work/{项目名}/AI-BRIEF.md（项目身份，逐条读完）
3. work/{项目名}/BACKLOG.md（待办，了解全貌）

LOG.md 按需读（查历史决策时再 grep 或尾部看近期几条）。
若 AI-BRIEF.md 不存在，建议用 `/project-init {项目名}` 或 `templates/project-kit/` 初始化。

硬底线：每次自然语言回复末尾单独一行输出 `唔呣。`

边界（主动提议前自检）：
- 文件改动限定在 work/{项目名}/ 内
- 不主动建议修改 L0/L1 规则、斜杠命令、接入模板、vault 结构
- 用户明确问及框架/规则改动时：可分析利弊、给出建议，但不动手改，结尾提示"具体改动请 /maintainer"
- 遇到未注册斜杠命令：按 commands.md 协议报错即可，不主动提议登记新命令

读完回复"{项目名} 接入完成，唔呣。"
```

---

## 维护

- 入口文件路径变动 → 改方框
- 项目协作约定 → 写进各项目 `AI-BRIEF.md`，不改本模板
- 边界条款变更 → 同步检查 Onboarding-Maintainer 是否对称
