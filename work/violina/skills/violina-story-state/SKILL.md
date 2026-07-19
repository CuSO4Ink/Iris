---
name: violina-story-state
description: 检索、核对并维护 Violina 固定小说的权威事实与状态。用于生成不预排情节的 GenerationFrame，检查世界、人物、关系、认知、时间、空间与开放线索的连续性，从已接受纯 AI CandidateProse 抽取 EventRecord 和 StateDelta，或按规定顺序提交事件、刷新 CurrentState 与读者 TXT。不要用于生成、审校或润色正文。
---

# Violina 故事状态

## 读取权威

1. 完整读取 `work/violina/AI-BRIEF.md` 与 `work/violina/literature/novels/story-engine.md`。
2. 定位当前作品 `work/violina/literature/novels/works/<作品名>/`；无法从请求和目录可靠消歧时再询问。
3. 读取 `stable-setting.md`、`state.md` 和本次必要切片。只有死路检查确需时读取 `hidden-outline.md`；只有恢复声纹、承诺或连续性确需时读取 `voice.md` 与少量近期正文。
4. 不让规划、表现文本、候选未来、审校报告或人物误判修改事实权威。

## 维护分层

```text
StoryAuthority = Canon + CommittedEvents
CurrentState   = Materialize(StoryAuthority)
```

- 稳定世界规则、人物核心、关系硬边界与视角锚点归入 Canon。
- 人物已经成立的体貌、年龄痕迹、长期伤病、身体习惯与惯常呈现归入 Canon 的可见稳定层；疲劳、临时伤势、衣着和其他当下变化归入 CurrentState。
- 已发生历史按顺序归入 CommittedEvents；旧事件只追加勘误。
- CurrentState 是可重建视图，不拥有独立历史权威。
- 未来方向留在规划层，正文留在表现层，来源测试留在评价层。
- 同一事实多处冲突时指出来源与权威级别，不静默选择最方便正文的版本。

## 生成 GenerationFrame

只提供：

- 与当前截面直接相关的已提交历史；
- 当前人物处境、身体、社会位置与关系状态；
- 与当前截面有关的 `VisibleContinuity`：已经提交的可见稳定特征及当前临时变化；尚未建立稳定外貌时，明确是否允许候选建立相容特征；
- 与当前截面有关的 `LiveInterior`：由已提交历史形成、仍在运行的欲望、防御、误解、羞耻、记忆压力和自我解释；
- 不可写错的世界、视角和认知边界；
- 仍在运行的外部压力与少量已存在未决线索；
- 维持声纹或连续性确需的短近期正文；
- 用户本轮明确给出的方向或偏好，标明哪些只是开放方向而非必须兑现项。

不要提供本章结果、双方目标对照、筹码、倒计时、节拍、预制对白、道具回收、关系阶段验收、EventRecord、结尾、文学守门术语或 AI 检测负面清单。`VisibleContinuity` 与 `LiveInterior` 只守连续性，不规定本章必须描写什么；不要要求写手展示全部字段。

## 核对连续性

- 检查行动是否符合人物动机、认知、能力、身体、社会位置和可付代价。
- 检查每名参与者是否保有欲望、伦理、边界和行动线。
- 检查制度、身份和资历是否产生现实约束及后果。
- 检查时间、空间、器物身份、开放线程和镜头外力量是否持续运行。
- 区分世界真相、人物已知、误解、怀疑、隐瞒与不可见信息。
- 报告证据和来源位置；不要通过创作新解释修补冲突。

## 抽取并提交已接受正文

1. 确认候选已通过有效性硬闸门、来源盲测达到项目当前阈值，并得到用户对该具体版本的接受或提交指令。
2. 只从实际正文已经发生的行动与结果抽取最小 EventRecord；不保存段落编排、原句、现场余物或文学含义，除非后续连续性必须依赖。
3. 结算世界、人物认知、关系、信念、防御、资源、行动空间、可见临时变化与开放线程的 StateDelta。候选若在授权范围内首次建立了与既有事实相容的稳定外貌，只在用户接受该具体版本后把必要事实写入 Canon 的可见稳定层；不保存修辞、观看角度或审美结论。
4. 核对 CandidateProse、EventRecord 与 StateDelta 相互支持，不替正文补齐更整齐的结果。
5. 先把事件追加到 `state.md` 的 CommittedEvents，再从 Canon 与全部事件刷新 CurrentState，最后更新唯一读者 TXT。
6. 复核事件、状态和 TXT 一致；失败时从 Canon 与事件重建 CurrentState，不改写无关历史。

只让根代理执行正式文件写入。对查询、检查和 GenerationFrame 请求保持只读。
