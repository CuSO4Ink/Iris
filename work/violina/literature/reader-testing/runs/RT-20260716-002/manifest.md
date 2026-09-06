# Test Manifest

> 内部文件。不得发送给盲测读者。

## Identity

- Run ID: `RT-20260716-002`
- Status: `packaged`
- Owner: ankoha
- Created: 2026-07-16
- Test type: `authorship-perception`

## Question

- Primary question: 匿名读者认为文本更像人类写作还是 AI 生成；这一判断从哪里形成，由哪些反复模式造成。
- Secondary questions: 哪些位置最具人写感；AI 感在全文如何分布；最值得优先消除的一个模式是什么。
- Out of scope: 情节好坏、设定偏好、人物是否讨喜、后续剧情、完整关系弧与逐句修改方案。

## Audience

- Intended reader profile: 能阅读中文类型小说的普通读者。
- Required genre familiarity: 无硬性要求。
- Exclusion conditions: 已读取 Violina、小说后台、写作规范或本轮测试假设的 AI。

## Materials

| Blind label | Private source | Reader-visible context | Order plan |
|---|---|---|---|
| A | `literature/novels/works/斩春/斩春.txt` 第一章 | 无书名、作者、版本、文案或题材标签 | 单包 |

- Source snapshot SHA-256: `0D2B97050B680F358DE6D692ACB1C09C5A4A74BB86FDAC291ECB31BD22FB24D1`
- Anonymous reader text: 6,029 characters

## Success Conditions

- Evidence that would support the text: 多数独立读者判断更像人写，且人写感证据具体、AI 感证据零散而不形成重复模式。
- Evidence that would reject the text: 多数独立读者判断更像 AI 写，并在不互相接触的情况下反复指出相同模式或相近位置。
- Minimum responses: 5
- Target AI-likelihood range if applicable: 不预设；先建立基线。

## Contamination Check

- [x] Packet contains no Violina/project path.
- [x] Packet contains no version meaning or change description.
- [x] Packet contains no writing-method terminology.
- [x] Packet contains no hidden setting or character knowledge.
- [x] Blind readers will run in fresh tasks without `/project violina`.
- [x] A/B order is randomized when applicable（本轮不适用）。

## Decision

- Result: `pending`
- Reason: 等待至少 3 份独立盲测响应。
- Follow-up: 收集原始响应后冻结本轮并生成 report。
