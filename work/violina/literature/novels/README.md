# Novels

Violina 当前固定小说模块。

## Load Order

1. 项目根目录 `AI-BRIEF.md`。
2. 新建或规划作品时，读取 `story-engine.md`；只有明确调用关系偏好时再读取 `relationship-preference-pool.md`，提取种子写入稳定设定后让关系池退出。
3. 运行章节事件时，读取 `story-engine.md` 与 `works/<作品名>/` 中必要的稳定设定、当前状态和隐藏方向，追索一条当前主脉络，有限择向后提交 EventRecord 并刷新状态。
4. 写首稿时，只读取已提交事件、主受当前切片、`voice.md` 与必要近期正文；沿视角注意顺写，不读取关系池、隐藏规划或 `prose-generation-guard.md`。
5. 初稿完成后才读取 `prose-generation-guard.md` 做拒绝测试与返修；结构问题退回事件阶段。审校观察全文噪声分布，不逐项审问路径残余的用途或来源。

每个阶段除 `AI-BRIEF.md` 外最多加载两份规范文档，不批量载入作品后台和旧正文。`works/` 保存固定小说；每部作品的事实文件收敛为 `stable-setting.md` 与 `state.md`。
