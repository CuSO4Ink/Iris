# honor-project（DI40001 Honours Project · 模块层）

## State

`active`

## Goal

- **Problem**：DI40001 是 triple module（占毕业等级权重极大，挂科基本无法授予 honours degree），
  全程 25 个 project week、六项提交、两个必须导师签字的 gate（未交即算 academic misconduct），
  而全部约束都散在 My Dundee 的页面、附件和公告里，系统本身既不登记 deadline、也只建了少数
  submission 点位。靠"等提醒"必然漏。
- **Outcome**：把模块层的规则、日期、交付规格、签字 gate、沟通与会议流程集中成本文件作为唯一权威，
  每个 gate 按期达成（当前首个 gate = 2026-10-23 Risk Assessment 带签提交）；课题执行本身在
  `work/vlm-fidelity/`（HLi-7）。
- **Smallest working feature**：完成第一次导师会（线上）+ 定下会议节奏 + 用官方 Gantt 模板建立经
  导师认可的项目计划 + 交出一份已签名的 Risk Assessment。

## Current Focus

**2026-09-29 当天发出线上会面预约消息给 Hanhe Lin。** 官方要求首次会面在 **Week 3（2026-09-21~25
那一周）** 完成，该周已结束、今天进入 wk4，2026-09-29 15:44 学院二次发公告催办 → 属于补做，越快越好。
同时本周（wk4）就是 Risk Assessment workshop，且**空白 RA 模板目前不在 My Dundee 上**，要当场索要。

## Truth

- **Implementation truth**：本目录 2026-09-29 由 `/project-init honor-project` 初始化（三份
  project-kit 文档，无代码）。模块层事实的权威在本文件；课题层（问题定义、实验设计、文献）在
  `../vlm-fidelity/`。2026-09-29 逐页核实过 My Dundee 课程 `<course-id>` 全部内容页、5 条公告、
  Gradebook、Calendar、Messages、Discussions、Groups 与页面附件引用。
  **本仓库内的文档是去标识版**：学号、姓名、Teams 加入码、course id 分别写作 `<UoD_ID>` /
  `<student-name>` / `<teams-code>` / `<course-id>`（占位符不是真实值）；带标识原件只留在
  gitignored 的 `tmp/honor-project/identified/` 与 `tmp/vlm-fidelity/identified/`，tmp 属可丢弃区，
  需长期保留要另存。
- **Runtime / external truth**（除标注"推断"外均为站点原文或实测）：

  **六项提交与权重**
  | 提交 | 周次（CSU） | 精确时间 | 权重 | 状态 |
  |---|---|---|---|---|
  | Project Choices | wk1–2 | 2026-09-15 22:00 | — | 已交（Gradebook 显示 Submitted / Mark is incomplete） |
  | Risk Assessment Form | wk7 | **2026-10-23 (Fri) 22:00 UTC+8** | 不计分（slot 1 point） | 需导师电子签，未交即 misconduct |
  | Ethics Declaration | wk9 | 站点只给"week 9"；按 RA 同口径推断 Fri 2026-11-06 22:00 UTC+8 | — | 需导师签字，未交即 misconduct |
  | Mid-term report | wk15 | 2026-12-14 那周 | 10% | submission point 未建 |
  | Honours Project Report | sem2 wk6 | 2027-04-05 那周 | 70% | Turnitin via My Dundee |
  | Presentation Slides | sem2 wk6 | 与终稿同期 | 20% | 答辩 sem2 wk7 = 2027-04-12 周，Teams 线上、录像 |

  **师生关系与会议流程**
  - Supervisor Role：导师每周**上限 30 分钟**；可选**每周 30 分钟**或**隔周 1 小时**，节奏在项目
    开始时双方商定；会面**可线下可线上**；**booking 完全在学生侧**。导师定位是 coaching（澄清期望、
    共同定 SMART 目标、引导而非给答案、检查进度与产出速率）。
  - Student Role：项目是学生自己的责任 —— 约并参加会议、规划与执行、按期交付；强烈建议**每周例会**；
    **必须记 meeting minutes，且 minutes 作为终稿 appendix 提交**；建议同时维护 logbook（想法、草图、
    计划、任务、反思、原型）；缺席要主动告知并尽快改约；项目周平均投入 **≥18 小时/周**（阅读、思考、
    设计都算）；**MSc/PhD/postdoc 等组员不得对项目提供实质帮助**；计划修改须导师同意。
  - Learning Outcomes 显式把"independent organisation of work, project planning, time management,
    report writing, **project meetings**, communication and presentation"列为考核项 → 会议本身是评分面。
  - 官方分配要求首次会面在 **Week 3（2026-09-21~25）**；学生-导师分配表**不含导师邮箱**，联系方式
    从 Teams 组 `<teams-code>`（AY2026-27 DIICSU Honours Project）或 DIICSU/UoD 官网取。
  - 导师可向学院申请最多 **900 CNY** 材料费（被试小礼品一类可走此渠道，需导师发起）。

  **范围硬约束（Definition of Honours Project）**
  - honours project **不得是原创的、可发表的研究成果**；必须是**建立在已发表结果之上**的工作 ——
    官方给出的合法形态：比较两篇以上已发表结果 / 把已发表结果用于新域或新问题 / 据已发表结果做出
    artefact / 研究新的工作方式（如 AI 在行业中的用法，用已知系统）/ 解决自身学习体验并做出帮助性
    artefact。
  - 全体 honours project 必须遵守 UoD **Trusted Research Policy**。真人被试 + 中英双机构（spec：
    指导分配为 1/3 UoD、2/3 CSU）→ 数据来源、招募与跨境处理要在 ethics 阶段问清。
  - 推论（非站点原文）：HLi-7 的叙事应定位为"用已发表主观实验协议做受控复现 + 客观指标与人类判断
    的相关性检验"，不能写成"提出新基准/新方法"。

  **交付规格**
  - 终稿报告 **20~40 页**（不含 references 与 appendices；理论型偏短、实验型可更长）；结构
    Introduction / Literature Review / Methodology / Results-Findings / Discussion / Conclusion；
    评分为 project portfolio + demonstration。
  - 学术诚信与 Turnitin 为必守项；成绩在 exam board 确认前均为 provisional；mitigating circumstances
    有专门通道（uod.ac.uk/mitcircs）。

  **Semester 1 workshop 历（9 场，Andrei Pisliakov + Ya Ou 主讲，CSU 周序；出席并参与是学生的义务）**
  wk1 Choices · wk3 Project Management · **wk4 Risk Assessment（= 本周 09-28 起）** · wk7 Ethics ·
  wk9 Use of AI · wk11 Research Integrity · wk13 Creating Mid-Term Report · wk15 Structure and
  synthesis in final report writing · wk17 Creating final project deliverables。

  **My Dundee 系统机制实测（2026-09-29）**
  - **Calendar 不登记任何 deadline**：本周与下周均 0 scheduled items → 时间线必须自维护。
  - **Gradebook 只建了 2 个点位**（Project Choices、Risk Assessment Submission：1 point、
    attempts unlimited、取最后一次有分尝试）；其余四项**尚未建点**。
  - Messages 空、Discussions 空；Groups：已加入 `Cohort 26/27 → Computing`（59/275）。
  - 顶层 9 个模块：Welcome / Module Guide (7 of 9 started) / Assessment and Feedback (1 of 6) /
    Library Resources (Completed) / Project Allocation (5 of 8) / Project Planning / Risk Assessment /
    Support and Wellbeing / Getting help with My Dundee。
  - Course staff 仅列 instructors（Luiz Carlos Barbosa da Silva、Yang Chengxing、Deva Brinda Deepak、
    Sheng Ding、Guozhi Dong 等）；module leader Prof Karen Petrie（k.petrie@dundee.ac.uk）；
    行政邮箱 Ssen-Education-Computing@dundee.ac.uk。
  - 公告共 5 条（最新 2026-09-29 15:44「Arrange the first meeting with your supervisor」；
    2026-09-20 14:38 分配结果 + 要求学生主动联系导师；2026-09-16 Teams 组加入码；
    2026-09-15 志愿提交截止与 cohort 分组）。

  **文件与本地落点**
  - 已下载解析（`tmp/honor-project/files/`）：`COMMON Project HAZARD EXAMPLES.docx`（hazard 词表，
    其中 Display Screen Equipment、时间压力、压力、lone/remote working、重复性劳损直接适用于
    desk-based + 线上收数课题）、`Advice from previous year students.docx`（上一届建议；对
    "验证已有工作"型项目明确要求**先写 thorough test plan 再动手**、research 尽量在 semester 1 内
    完成、写作至少留 3 周、从第一天维护引用与 appendices、每天至少 2 小时）。
  - 已知存在、尚未下载：RA desk-based 示例 112KB、土木工程示例 80KB、`Project Gantt Chart
    Template-2627.xlsx` 与 Example、Project Planning workshop pptx 1.3MB。
  - **RA 空白模板目前未上架**（模块描述称"the template you need to complete"会在这里，实际只有
    hazard 清单与两份已填示例）→ 须从 wk4 RA workshop 材料或 submission instructions 取。
  - 官方 `DIICSU Project Schedule-2627.docx` 解析件：`../../tmp/vlm-fidelity/schedule.txt`。

## Implementation

- **Canonical path**：`work/honor-project/`
- **Reused foundation**：`work/vlm-fidelity/`（HLi-7 课题层）；My Dundee 课程 `<course-id>` 与
  Teams 组 `<teams-code>` 为外部事实源；`browser-use` 为读取通道（Microsoft SSO 需人工登录一次，
  隐藏视口下 pointer 点击无效 → 用 navigate_page + evaluate_script）。

## Constraints

- 两个签字 gate（RA 2026-10-23 / Ethics 预计 2026-11-06）**未交即 academic misconduct**，且都要
  导师签字 → 必须给导师留出签署时间，不能压线。
- 首周（wk3）会面义务已过期，任何新公告都可能升级催办；联系渠道目前只有 Teams。
- 项目定位受 Definition of Honours Project 约束（不得原创可发表 + Trusted Research Policy）。
- 会议预算固定为每周 30 分钟上限（或隔周 1 小时），议程必须预先压缩到 3~4 个决策点。
- 本周与 DI41009 Industrial Team Project 收尾（report 2026-10-13、deliverables ZIP 2026-10-21）并发。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/honor-project/`.

## Document Map

- `AI-BRIEF.md`: goal and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
