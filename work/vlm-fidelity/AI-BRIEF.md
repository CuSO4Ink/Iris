# vlm-fidelity（HLi-7 · DI40001 Honours Project）

## State

`active`

## Goal

- **Problem**：VLM/生成式图像修复（SUPIR、DiffBIR、SeeSR 一类）会 hallucinate 内容——结果清晰但
  偏离原图语义；PSNR/SSIM/LPIPS 等现有指标测失真与感知质量，抓不住 content fidelity 漂移。
- **Outcome**：设计并执行一场受控主观实验，产出带人类 content-fidelity 标注的小型数据集 +
  现有客观指标 vs 人类判断的相关性分析（SRCC/PLCC）；交付 DI40001 mid-term（wk15, 10%）与
  final report（semester-2 wk6, 70%）+ 10+5 min 答辩（20%）。
- **Smallest working feature**：pilot 链路——少量源图 × 3~5 个修复模型 × pairwise fidelity
  对比界面，跑通"生成图像 → 展示收数 → 统计分析"全流程。

## Current Focus

第一次导师会前的课题层准备：问题清单（GPU 资源、ethics 流程、被试招募、导师期望的最小交付物、他对
content fidelity 的既有定义或量表偏好）+ 文献摸底 + 实验设计草案 v0。

模块层的预约动作、签字 gate 与流程机制已迁到 `../honor-project/`（DI40001 唯一权威）；首次会面的
官方要求窗口是 **Week 3 = 2026-09-21~25 那一周**，现已进入 wk4 → 预约见 `../honor-project/BACKLOG.md`。

## Truth

- **Implementation truth**：无代码，项目 2026-09-21 初始化；分配已确认（`Downloads\Computer
  Science.xlsx`：<student-name> <UoD_ID> → HLi-7，supervisor Hanhe Lin，UoD，IQA/JND 方向）。
- **Runtime / external truth**：课题相关的外部事实以 `../honor-project/AI-BRIEF.md` 为权威（六项
  提交、签字 gate、角色义务、报告规格、workshop 历、My Dundee 系统机制均在那里）。对本课题直接
  生效的结论：Risk Assessment **2026-10-23 22:00 UTC+8** 需导师电子签；Ethics Declaration wk9
  （预计 Fri 2026-11-06 22:00 UTC+8，未核实）是实质关卡 —— 真人被试需要协议、知情同意与招募渠道；
  mid-term wk15 = 2026-12-14（10%）、终稿 sem2 wk6 = 2027-04-05（70%）、答辩 sem2 wk7 = 2027-04-12
  周（10+5 min Teams 录像，20%）。官方 `DIICSU Project Schedule-2627.docx` 解析件：
  `tmp/vlm-fidelity/schedule.txt`。
- **学术坐标**：LL-Bench (arXiv 2606.02535) 做过大规模 pairwise 偏好 + MLLM evaluator；CodecArena
  (2608.09139) 把 fidelity 拆五维；被测方法侧代表 arXiv 2512.17292。

## Implementation

- **Canonical path**：`work/vlm-fidelity/`
- **Reused foundation**：开源修复模型权重做 inference（不训练）；实验与统计用 Python
  （本机 `uv run --with` 可用）；pairwise → Thurstone/Bradley-Terry 量表。

## Constraints

- wk9 Ethics Declaration 是实质关卡：真人被试需要实验协议、知情同意、招募渠道，时间线倒排。
- GPU 资源未确认：diffusion restorer（SUPIR 级）显存需求大，首次周会必须问清实验室算力。
- Honours 体量：聚焦 fidelity 单一维度做严格小协议，不做大规模基准、不训练模型。
- 用户偏好：prose 中文、技术术语英文；导师沟通语言中文（Hanhe Lin）。

## Artifact Policy

- Durable source and final evidence: this project directory.
- Disposable environments, runs, screenshots, generated evidence, and one-off scripts:
  `../../tmp/vlm-fidelity/`.

## Document Map

- `AI-BRIEF.md`: goal and current truth.
- `BACKLOG.md`: unresolved executable work.
- `LOG.md`: durable decisions and findings.

Method: [Project Progress Methodology](../../notes/project-progress-methodology.md).
