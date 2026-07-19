---
name: violina-fiction
description: 统筹 Violina 纯 AI 固定小说的创建、续写、正文生成、候选审校、作者来源盲测、架构迭代与正式提交；维护女性主受、封闭女女关系、人物他者性、StoryAuthority、隔离写手、分层审校和 AI 概率低于 50% 的来源感目标。不用于互动文字或普通项目管理。
---

# Violina 纯 AI 固定小说统筹

## 权威入口

1. 完整读取 work/violina/AI-BRIEF.md；找不到时停止生产。
2. 服从仓库 AGENTS.md。生成实验再完整读取 literature/novels/trials/self-iteration-protocol.md 与精简历史索引 ai-detection-loop.md。
3. 事实、GenerationFrame 与提交使用 violina-story-state；候选完成后使用 violina-prose-audit。
4. 只加载当前作品和当前截面所需事实。写手、审校员与读者均不得自行搜索工作区。

## 冻结写手系统

1. 从 references/writer-system-baseline.md 的 WRITER_SYSTEM_BEGIN 与 WRITER_SYSTEM_END 之间逐字提取 WriterSystemBaseline。
2. 从 references/writer-system-calibration-epoch-02.md 的 WRITER_CALIBRATION_BEGIN 与 WRITER_CALIBRATION_END 之间逐字提取 WriterSystemCalibration。
3. 普通生产与新 Epoch 再从 references/writer-system-default-prose-profile.md 的 WRITER_DEFAULT_PROSE_PROFILE_BEGIN 与 WRITER_DEFAULT_PROSE_PROFILE_END 之间逐字提取 WriterSystemDefaultProseProfile。只有严格复现历史 Epoch 时按当时登记栈省略它。
4. 写手任务顺序固定为：WriterSystemBaseline、WriterSystemCalibration、WriterSystemDefaultProseProfile、冻结 GenerationFrame、输出边界。所有文学与场景内容逐字发送，不摘要、不换序；用户本轮方向先写入并冻结 GenerationFrame，根代理不得在写手任务里追加未文档化的文学提示。
5. 写手任务只可额外包含源自本 Skill 的隔离、一次生成、读写边界与纯正文输出等程序说明；不得把审校、来源反馈、根代理诊断或对候选的临场期待塞入写手上下文。
6. 原始基线恢复自 275558d；基线、校准、默认画像与 Frame 在一个 Epoch 内不可自修改。若要改变，停止当前 Epoch 并交用户确认。

## 当前默认正文画像

- `WriterSystemDefaultProseProfile` 合并已验证的认知通道解耦、注意驱动散文化呈现、直接且未完成的心理、动态神态进入话轮、完整标点权限、按 Frame 忠实保留情绪振幅，以及术语只守因果。
- 它允许高热情、黏人、暴躁、外显或低振幅等不同人设，不规定所有人物活泼，不把“超级黏人攻”设为项目统一性格。
- 新上下文只要调用本 Skill 开始普通生产，就必须读取并使用该画像；不得依赖旧对话记忆或临时口头补充才能取得这些效果。

## Epoch 02 历史复现配置

本节只用于严格复现已经停止的 Epoch 02；普通生产与新 Epoch 使用上面的当前默认正文画像。

- 最多 5 轮，每轮只生成 H、L 两篇 3000—5000 中文字符候选；Round 01 是无 overlay 的校准后直写基线。
- 写手、审校员、来源读者和弱文学参考读者统一使用 gpt-5.6-sol、reasoning high。
- H/L GenerationFrame 在 Round 01 前冻结，五轮不推进事实。VisibleContinuity 与 LiveInterior 只守连续性，不是展示清单。
- Round 02—05 的唯一差异写入当轮 trials overlay；不在 Epoch 内修改本 Skill、两个系统片段或 H/L Frame。
- CandidateProse 不是历史；整个 Epoch 成功也不自动提交 Canon。

## 候选生成

1. H、L 各使用一个 fork_turns none 的零继承写手，可并行生成，不共享正文。
2. 写手只见三个冻结系统片段、对应 Frame 与程序边界；不见完整 Skill、审校守门、历轮结果、来源提示或另一候选。
3. 每个截面只允许一次正式生成。只有任务中断、空返回或工具故障等未形成候选的技术失败，才可用完全相同输入重启一次。
4. 字数不足、句中截断、语义退化、人物失效或其他已经形成文本的失败都算本轮真实结果，不换种子补写。
5. 根代理是唯一文件写入者。候选结束前不补发诊断、引导结尾或追加刺激。

## 审校与单次局部修订

1. 原稿先交审校员 A 执行完整硬闸门与非阻断来源风险画像。硬闸门拒绝时，本候选停止，不用局部修订抢救。
2. 当前轮次只有在见文前明确登记局部修订拓扑时，A 才在盲测前选择 LOCAL_REVISION 或 NO_LOCAL_REVISION；未登记时原稿通过硬闸门后直接冻结，不授权修订。当前已有登记只包括 Epoch 02。
3. LOCAL_REVISION 只能处理 A 报告中逐字定位的片段。风险无法在三处、原稿非空白字符 15% 内可靠处理时必须选择 NO_LOCAL_REVISION。可以删除、缩短或改写心理、神态、外貌及其他局部；不要求原位补回同类描写。修订后整篇仍须保有人物有效性、事实、时空与关系边界。
4. A 返回完整修订稿和变更说明，不写文件、不自判成功。审校员 B 只审修订稿。
5. B 通过时，修订稿取代原稿，成为唯一来源盲测版本。B 拒绝时立即丢弃修订，不作第二次修改；审校员 C 再独立复审原稿。C 通过则原稿进入盲测，C 拒绝则候选作废。
6. 正式盲测前只冻结一个版本。原稿和修订稿不得同时送来源测试，也不得看见盲测结果后回退补测。

## 来源盲测

1. 使用 literature/reader-testing/authorship-reader-prompt.md；读者只见匿名正文与中性问题。
2. 每篇目标 5 份有效回答。先冻结 3 份；只有三份结果已使五人基础线数学必败时，记 FAIL-LOCKED 3/5 并停止后两名，否则补足 5 名。
3. 基础通过线固定为 AI 概率中位数小于 50%，且多数判断更像人写。不能成功早停。
4. 同轮只要 H、L 均通过硬闸门，就完成两篇来源测试后再选择确认对象；不得因返回顺序偏向先通过者。
5. 回答只有在程序或可证事实错误时才可剔除：错误文本、缺失必答字段、引用不存在、上下文泄漏或明显未执行任务。审美不同、理由肤浅或概率极端都不是误判。
6. 每个必需样本槽位最多连续替换 3 次；同一故障持续三次则触发资源停止。
7. 正式回答冻结后，不向同一正文写手或修订审校员反馈。

## 反馈、overlay 与回滚

1. 下一轮变量至少要有两名独立来源读者复现同一机制、同一机制跨 H/L 出现，或当前结果复现历史多轮证据。审校画像只能佐证，不能替代来源证据。
2. 没有重复机制时，下一轮重跑冻结基线估计噪声，不从单名读者意见制造提示词。
3. 每轮 overlay 必须登记新增量、最相近旧实验、最强反证、成功判据与完整撤销方法。提示同义改写、随机废话、故意错误、机械乱序和事后删漂亮句不算架构变量。
4. 失败差异立即撤销。确认失败也完整回滚到 Round 01 基线；除可证流程误判外，不补测同一正文、不改名叠加失败变量。
5. 文学六维 A/B 只在 Round 01 和 Epoch 结束时运行，是弱参考附录；不参与候选有效性、版本选择、overlay 保留、确认或停止，也不反馈给写手与审校员。

## 首次通过与确认

1. 同轮若多篇首次过线，依次按来源中位数、均值、H/L 固定顺序选择唯一对象。
2. 立即冻结生成系统，执行同文确认 A：同一正文一字不改，目标 7 名新读者。
3. A 通过后执行未见文本确认 B：冻结系统生成一个新建女女长篇截面，通过硬闸门后由目标 7 名新读者测试。
4. A、B 均可先取 4 份回答；只有七人失败数学锁死时才记 FAIL-LOCKED 4/7，成功必须补足 7 人。
5. A、B 都满足原基础线才判 Epoch 成功。任一步失败即回滚并进入下一轮；Round 05 确认失败则按五轮失败停止。

## 停止与提交

- 只在 A、B 确认成功、Round 05 仍失败、授权边界或资源无法继续时停止。
- 停止后生成 epoch-02-summary.md，报告全部有效结果、失败锁定、文学弱参考、变量证据与限制，然后交用户确认。
- 未经用户接受，不把任何实验候选写入 StoryAuthority。
- 用户接受具体版本后，才由根代理按追加 EventRecord、刷新 CurrentState、更新读者 TXT 的顺序提交。
- 用户文本可作为可选输入，但纯 AI 生成仍是默认作者路径。
