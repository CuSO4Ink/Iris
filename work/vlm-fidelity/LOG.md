# vlm-fidelity · LOG

Append only information that would otherwise be forgotten:

```markdown
### YYYY-MM-DD HH:MM — [决策|否决|发现|回滚] 标题
结论，以及必要时的原因或回退点；三行以内。
```

Do not record command-by-command operations or duplicate current state from `AI-BRIEF.md`.

### 2026-09-21 — [发现] 分配确认 HLi-7
`Downloads\Computer Science.xlsx`（staff 侧结果表）：<student-name> <UoD_ID> → HLi-7，supervisor
Hanhe Lin；为用户志愿第 2 位，第 1 位 S.L-45 分给 Yixuan Pan。

### 2026-09-21 — [决策] 项目初始化，范围划界
`work/vlm-fidelity/`；范围 = 主观实验 + 指标相关性分析 + 开源模型 inference，明确不含模型训练。
候选项目名按命名规范取英文 kebab-case。

### 2026-09-21 — [发现] My Dundee 官方公告确认分配与下一步
课程 `<course-id>` 公告（2026-09-20 14:38）：分配结果挂在 Project Allocation → Student to
Supervisor – Final Allocation（附件即用户 Downloads 的 Computer Science.xlsx）；多数学生拿到
top-5；**学生需主动联系导师安排首次会面**。另有公告要求加入 Teams 组
"AY2026-27 DIICSU Honours Project"，加入码 `<teams-code>`。

### 2026-09-21 — [发现] 官方学期时间表到手（DIICSU Project Schedule-2627.docx）
经 browser-use 会话内下载解析（签名 URL 6h 过期，正文存 `tmp/vlm-fidelity/schedule.txt`）。
CSU wk1=2026-09-07，分配公告当周即 wk3=Project week 1；全部里程碑精确日期已写入 AI-BRIEF。
终稿 2027-04-05，答辩 04-12 周，项目总长 25 个 project week。

### 2026-09-29 17:50 — [决策] 模块机制迁出本目录
DI40001 的六项提交、签字 gate、师生角色义务、报告规格、workshop 历与 My Dundee 系统机制统一收在
`../honor-project/`，本目录只留课题层；旧副本同轮删除，不留别名。关键结论摘要仍留在 `AI-BRIEF.md`
的 Runtime truth 段（RA 2026-10-23 22:00 UTC+8 需签字、Ethics 是实质关卡）。

### 2026-09-29 — [否决] HLi-7 不可按「提出新基准/新方法」定位
Definition of Honours Project 明文：honours project 不是原创可发表的研究成果，必须建立在已发表
结果之上（对比、迁移到新域、据其做 artefact），并受 UoD Trusted Research Policy 约束。
→ 课题叙事改为「用已发表主观实验协议对 VLM 修复的 content fidelity 做受控复现与指标相关性检验」。
