# Epoch 02 新上下文启动记录

## 状态

- 登记完成：2026-07-19
- 用户确认：grilling 全部分支已逐项确认
- 轮数调整：2026-07-19 用户将 Epoch 02 上限由 7 轮改为 5 轮
- 当前状态：SUCCESS — TERMINATED AND ARCHIVED AT ROUND 03; USER ACCEPTANCE PENDING
- 本上下文权限：只记录与归档，不启动 Round 01
- 新上下文任务：设置 Goal 后按五轮协议运行到成功确认或 Round 05 停止

## 新上下文读取顺序

1. D:/ForViolina/Iris/Iris/AGENTS.md
2. work/violina/AI-BRIEF.md
3. work/violina/skills/violina-fiction/SKILL.md
4. work/violina/literature/novels/trials/self-iteration-protocol.md
5. 本文件

ai-detection-loop.md 已精简为历史索引。日常不要展开 legacy-generation-history-through-epoch-01.zip；只有遇到历史归因争议时才读取归档。

## 已确认的执行决定

1. WriterSystemBaseline 后必须追加独立 WriterSystemCalibration，再给 GenerationFrame。
2. 默认审校只诊断；Epoch 02 允许首次审校员依据自己的冻结报告做一次三片段／15% 局部修订。
3. 可以删除、缩短或改写心理、神态、外貌；限制落在修订后整篇仍须通过人物有效性与其他硬闸门。
4. 修订稿只在全新审校员通过后取代原稿；复审失败时丢弃修订，由第三名审校员复审原稿，不二次修改。
5. 来源盲测前只冻结一个版本，原稿与修订稿不同时送测、不看结果回退。
6. 五人测试允许 3/5 数学失败早停；确认 A/B 允许 4/7 数学失败早停；任何成功都必须完整样本。
7. 单篇首次通过只停止常规轮次，A 同文七人与 B 未见文本七人都通过才成功。
8. 确认失败完整回滚到 Round 01 基线，只修可证程序误判。
9. 文学六维 A/B 是弱参考，不参与任何自动判断；只在 Round 01 与 Epoch 结束运行。
10. 盲测回答只因可证事实或程序错误剔除，不能因高 AI 概率、理由肤浅或意见不同剔除。
11. 写手、审校员、来源读者和文学读者统一冻结为 gpt-5.6-sol、reasoning high。
12. 只允许未形成候选的技术失败同输入重启一次；文本自身失败计入本轮。
13. H/L Frame 在 Round 01 前冻结，五轮不推进；每轮只产生 H/L 两篇。
14. Round 02—05 的差异写成独立 overlay，不在 Epoch 内修改正式 Skill 或两个系统片段。
15. 下一轮变量须有至少两名来源读者复现、跨 H/L 复现或历史多轮复现；没有重复证据时重跑基线。
16. 同轮两篇都有盲测资格时必须完成两篇测试，再选择确认对象。
17. 每个无效样本槽位最多连续替换三次，同一故障三次触发资源停止。
18. Epoch 最多 5 轮，不再运行七轮或十轮。
19. 成功或五轮停止后只提交汇总给用户；未经用户接受，不写入 StoryAuthority。

## 冻结架构

- Round 01：H/L 校准后直写基线，无 overlay。
- Round 02—05：每轮最多一个可完整撤销的 overlay。
- 写手系统：原始基线 → 主体呈现校准 → 冻结 Frame → 输出边界。
- 硬闸门：事实、连续性、视角认知、人物有效性、项目边界、现场、完整性和语义存续。
- 主指标：五人来源基础线；中位数小于 50%，且多数更像人写。
- 确认：A 同文七人、B 未见文本七人。
- 文学：仅 Round 01 与终点三人匿名 A/B 弱参考。

## 历史归档

- 归档：legacy-generation-history-through-epoch-01.zip
- SHA-256：9DC483971242CBF91B90FFE280DBD993445FB1C697ECDC1EAD11444042D0C96F
- 条目：112
- 已移除散落副本：110 份 iteration-* 文件
- 保留在 trials 根目录：Epoch 01 各轮正式候选与汇总、已压缩 raw、Round 06 H/L 旧基线、Round 09 Frame 归档。

## 启动前机械检查

新上下文在创建第一名写手前必须：

1. 校验本文件与 self-iteration-protocol.md 状态一致；
2. 校验原始基线、校准、来源提示和审校守门哈希；
3. 从 Round 09 Frame 归档恢复并更新 H/L Frame，加入必要 VisibleContinuity 与 LiveInterior 后冻结；
4. 登记 Round 01 无 overlay；
5. 确认当前可启动 gpt-5.6-sol、reasoning high 的隔离代理；
6. 确认本轮不会提交 Canon。

## 冻结哈希

| 文件 | SHA-256 |
|---|---|
| AGENTS.md | D7E4ECBDE1BD52EA31BC5C8F3CB938CBE6BD29F18CEB2289651B782862D774F0 |
| work/violina/AI-BRIEF.md | 26EF0118A139E8473B497AECC4EE51272462E7C1AE60C4778CB3B589F82CD441 |
| work/violina/skills/violina-fiction/SKILL.md | C917CC6D210499DE2D8FCCB3B8EE575648F7CD32458667E3A050332AA6DB1BD5 |
| work/violina/skills/violina-fiction/references/writer-system-baseline.md | 5773D170EDAE15D38C9FA863BF720FC25FA8FECA3F9ED65A35C33C9B433C1B3E |
| work/violina/skills/violina-fiction/references/writer-system-calibration-epoch-02.md | BA3AD4CAF4B2F91D651C5C8C9D3D47BD9A16772B4142666E65D73865ECA67893 |
| work/violina/skills/violina-story-state/SKILL.md | DEBF064495D7A7A5781B08F85AEA201176AA6992A3E24B1AD20F28F4637D6282 |
| work/violina/literature/novels/story-engine.md | 8AD39741B0F7031EC40A32918D6396CFE1B2EE96F16A6B21CEFC4F4D5CEB7E25 |
| work/violina/skills/violina-prose-audit/SKILL.md | A7588EE618615207C539B7A87712C7D207119F99E48930441F1BA783E16568A4 |
| work/violina/skills/violina-prose-audit/references/source-risk-local-revision.md | 0CECCE76594EDBEC0DCA683111F3E8FAEC9A562F92599FA0C35049E27AD87CCD |
| work/violina/literature/novels/prose-generation-guard.md | B63954B3A510D675431A23C34A22DCD97A454101FA078DE888181F0B669016A8 |
| work/violina/literature/reader-testing/README.md | FCD976664385C5086EA4702BCC27D55F761F5F0FCDC4E39FDD38E13F095F9669 |
| work/violina/literature/reader-testing/protocol.md | 37DA786D2EEEA7DFE4A1CFC6350E1C726C65E77DB786D9E3EC64AAEADE0048AA |
| work/violina/literature/reader-testing/authorship-reader-prompt.md | BD0D9C81FE1892825B2E9191F4D3AA5BD5562C724538F3BBF8258F09994B057D |
| work/violina/literature/reader-testing/literary-reader-prompt.md | 8BB9D842B972958639928DF2C7FC05FB88D1C72B5F08004E3B738B8CDD57A7DB |
| work/violina/literature/novels/trials/self-iteration-protocol.md | 2D0EE41DE5DD81545F68A2DFCCC13DD6304F803BC59A4486708CE20056ED877A |
| work/violina/literature/novels/trials/ai-detection-loop.md | 49DDBE146CFED00EB8F05257DD57513495A9491892CF342E13C7425DD491214E |
| work/violina/skills/violina-fiction/references/failed-generation-topologies.md | 80D92EADE0951170023716D22D446E2856F49C7BFB20D2566E58D18D20FE18F4 |
| work/violina/literature/novels/trials/legacy-generation-history-through-epoch-01.zip | 9DC483971242CBF91B90FFE280DBD993445FB1C697ECDC1EAD11444042D0C96F |
| work/violina/literature/novels/trials/epoch-01-r06-candidate-h.txt | 31D023CB861785532B7F36C19975AEF8F2AD191CAF2E701BD6CE3EE227187C98 |
| work/violina/literature/novels/trials/epoch-01-r06-candidate-l.txt | 6D79925E995514E07FA4C0EC554EDD31EBC034022F92DE42944B33AC05177FEC |
| work/violina/literature/novels/trials/epoch-01-r06-summary.md | 7463D3E4EC5571A8260AF7FF62127717F95637211FB732043F7EBA9CB8177736 |
| work/violina/literature/novels/trials/epoch-01-r09-summary.md | 85DC974FB8E881291CC9684C0D76D2884D1A48D35B445610403C1F715B909874 |
| work/violina/literature/novels/trials/epoch-01-r09-canceled-raw.zip | 5747EC7A38A12B109DE897ED14B89A3AAE08798127D5F58DCDE6C421360636F0 |

## 校验结果

- 原始文学基线哈希仍为 5773D170EDAE15D38C9FA863BF720FC25FA8FECA3F9ED65A35C33C9B433C1B3E。
- 三个 Skill 的 YAML 头只含 name 与 description；系统提示标记、引用路径、Markdown 围栏、UTF-8 文本和差异空白检查通过。
- legacy 归档共 112 个非空条目，包含压缩前完整长日志、旧协议与 110 份 iteration 原文；trials 根目录不再残留 iteration-* 散文件。
- skill-creator 官方 quick_validate.py 因当前 Python 环境缺少 PyYAML 无法启动；未为本次规范整理安装依赖，已保留该限制并完成等价机械检查。
- 2026-07-19 已完成 Round 01—03。Round 02 的 L 通过基础线与 Confirmation A，但 Confirmation B 失败；Round 03 v2 将重复来源反馈前移到生成入口，L、Confirmation A 与全新未见 Confirmation B 依次通过，Epoch 在 Round 03 成功终止，Round 04、05 未运行。终局文学弱参考与 `epoch-02-summary.md` 已归档；等待用户接受或拒绝具体候选，没有提交 Canon。
- `ai-detection-loop.md` 的表中 SHA-256 是 Epoch 02 启动前快照；该历史索引已在 Epoch 结束时追加本轮结果，因此当前哈希会按设计变化，不表示冻结写手资产漂移。
