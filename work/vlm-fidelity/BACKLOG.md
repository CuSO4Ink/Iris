# vlm-fidelity · BACKLOG

## Doing

- [ ] 会前备好课题层问题清单（GPU/算力、ethics 申报流程与被试招募渠道、导师期望的最小交付物、
  他对 content fidelity 的既有定义或量表偏好）；会面预约本身在 `../honor-project/BACKLOG.md`

## Next

- [ ] 文献摸底：SUPIR / DiffBIR / SeeSR / X-Restorer 等 VLM 修复方法 + LL-Bench (2606.02535)、
  CodecArena (2608.09139) 的实验协议 + Hanhe Lin 自己的 IQA/JND 论文；叙事按"已发表协议的受控
  复现与指标检验"定位（见 LOG 2026-09-29 否决项）
- [ ] content fidelity 操作化定义草案：objects / face identity / text / structure 四维候选，
  与"perceptual quality"的区分边界
- [ ] 实验设计草案 v0：协议选型（pairwise 2AFC vs reference rating）、样本量估算、展示界面、
  观看条件控制（DSE/远程收数条件与 ethics 表一致）
- [ ] 候选修复模型清单：传统 baseline（SwinIR / Real-ESRGAN）vs VLM 系，附显存/算力需求估算
- [ ] thorough test plan（上一届建议对"验证已有工作"型项目的硬要求）：先定测试顺序与被测项，
  再动手跑实验，避免时间耗在"想下一个测试"

Keep only unresolved, executable work. `/checkpoint` removes completed operations after durable
facts are reflected in `AI-BRIEF.md` or `LOG.md`.
