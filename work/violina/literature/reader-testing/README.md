# Reader Testing

Violina 的独立读者测试模块。它验证读者实际经历了什么，不验证作者是否正确执行某套写作方法。

核心指标包含读者对作者来源的判断：文本更像人类创作还是 AI 生成。该指标记录的是感知结果与证据，不作为作者身份鉴定。

当前阶段默认使用 **Authorship Perception**：重点不是询问读者喜不喜欢情节，而是定位 AI 写作感何时形成、由哪些反复模式造成、哪些段落仍保有人类写作感，以及最值得优先消除的一个模式。通用阅读体验测试仅在另有目标时使用。

## Two Entry Modes

### Framework Operator

负责建立测试、制作匿名包或汇总结果。她不是盲测读者，可以精确读取本目录的框架文件。启动指令必须由用户在对话中直接给出 `work/violina/literature/reader-testing/README.md` 和 `protocol.md` 的准确路径；不能依赖本目录内另一个入口文件帮助 AI 找到本目录。

### Blind Reader

负责评价正文。不得执行 `/project violina`，不得读取本目录或任何项目文件，只接收已经生成的匿名 packet。把测试框架交给盲测读者阅读会造成污染。

## Boundary

- 测试开发者可以知道 Violina 的写作架构，但不能冒充盲测读者。
- 盲测读者必须使用全新 AI 任务，不执行 `/project violina`，不读取项目文件。
- 盲测读者只接收一个自包含匿名测试包；包内不得出现作品路径、版本来源、测试假设、写作规范或后台信息。
- 原始响应先冻结，再做汇总。反馈不会自动改写小说事实或长期生成规范。

## Files

- `protocol.md`：角色隔离、运行流程、测试类型和质量门槛。
- `blind-reader-prompt.md`：提供给全新 AI 读者的中性提示。
- `authorship-reader-prompt.md`：以识别和定位 AI 写作感为唯一主目标的提示；当前默认使用。
- `templates/manifest.md`：测试所有者使用的内部清单，不交给读者。
- `templates/packet.md`：匿名、自包含的盲测包。
- `templates/authorship-packet.md`：专门用于 AI 写作感诊断的匿名包模板。
- `templates/response.md`：单名读者的标准响应结构。
- `templates/report.md`：多名读者的汇总报告。
- `templates/authorship-report.md`：作者来源诊断专用汇总；当前默认使用。
- `runs/`：每次实际测试的独立目录。

## Quick Start

1. 在 `runs/` 下按 `RT-YYYYMMDD-NNN/` 新建一次测试。
2. 从 `templates/manifest.md` 建立内部清单，写明测试目标、版本映射与成功条件。
3. 从 `templates/packet.md` 生成匿名包；只放读者可见信息和待测文本。
4. 在全新 AI 任务中直接粘贴完整测试包，不执行 `/project violina`，也不要求它读取 reader-testing。
5. 将原始回答按 `templates/response.md` 原样保存。
6. 收集完成后按 `templates/report.md` 汇总共同反应、分歧和证据。

详细要求见 `protocol.md`。
