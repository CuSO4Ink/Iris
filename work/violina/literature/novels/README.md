# Novels

Violina 固定小说模块，默认由纯 AI 生成。

## Load Order

1. 根代理读取 `work/violina/AI-BRIEF.md` 与 `story-engine.md`。新建作品且明确调用关系偏好时，才短暂读取 `relationship-preference-pool.md`。
2. 从 `works/<作品名>/` 读取权威事实、CurrentState、认知边界、外部压力和必要近期正文，形成 GenerationFrame；不预写本章 EventRecord、节拍、道具用途、关系回报或结尾。
3. 根代理把 `skills/violina-fiction/references/writer-system-baseline.md` 标记范围内的原始原则逐字置于任务最前，再附 GenerationFrame；零继承隔离写手不读取完整 Skill、工作区、文学守门或盲测目标，直接生成纯 AI CandidateProse。
4. 候选结束后，隔离审校员读取白名单事实、候选和 `prose-generation-guard.md`。硬闸门只管有效性；来源风险画像不阻断盲测。
5. 硬闸门通过的候选按 reader-testing 协议交给至少 5 个零上下文读者。基础目标为 AI 概率中位数 `< 50%` 且多数判为“更像人写”。
6. 达标并经用户接受后，根代理从实际正文抽取 EventRecord 与 StateDelta，按“追加事件—刷新状态—更新 TXT”提交。

未达来源目标时，先汇总跨读者重复证据，再从冻结直写基线增加一项可撤销差异，改变模型族、训练目标、上下文切片、GenerationFrame、计划可见性、候选池与选择器、生成/修订拓扑或解码。失败差异不得累加到下一轮；不得把随机废话、故意错误、机械乱序、删漂亮句或同义负面提示当成新架构。

同一候选的生成、内审、盲测和提交必须串行；不同候选或作品可以并行。所有正式文件只由根代理写入。`works/` 中每部作品的事实文件收敛为 `stable-setting.md` 与 `state.md`，读者侧只保留 UTF-8 TXT。
