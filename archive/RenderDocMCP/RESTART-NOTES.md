# RenderDocMCP · Restart Notes

> [!NOTE] **归档重启记录。** 以下 Gate 不再执行，只在用户重新立项后作为范围输入。
> 旧 headless 工具清单已过期；任何恢复都必须先证明“更快且不越界”。

## P0 — 文档与证据边界

- [x] 2026-07-22 作品集审计：准确定位为 qrenderdoc 扩展＋文件 IPC＋Replay API＋MCP/AI。
- [x] 在正式瀑布参考文档顶部把 A2C 降为假设；仍须补读 blend state、sample count 与 A2C state 后再定性。
- [ ] 把 37015 脚印／贴花用途保持为未确认推断，不再写成原游戏事实。
- [ ] 核对所有旧 TLOU2、Dual CSM 与错误游戏身份引用，确保只作为被推翻记录。
- [ ] 确认捕获、截图、Shader 和报告的公开/匿名化权限。

## P1 — 工具事实

- [x] qrenderdoc bridge、文件 IPC、帧统计、事件、Pipeline State、GPU timing 与证据导出已跑通。
- [ ] 修复/验证 `GetColorBlends()`、render targets、viewports、input assembly 和 vertex buffers 的结构化输出。
- [ ] 为大响应改成原子写入/完成标记；现有稳定轮询修复作为基线。
- [ ] 为每条语义声明附 source event/resource/shader/state、证据等级和“无法判断”状态。

## P2 — 作品 Gate

- [ ] 选一个身份正确、允许展示的捕获，定义本人手工分析基线。
- [ ] 同一问题 A/B：记录总时间、覆盖率、事实准确率、无法判断率、高置信错误、人工修正和复现率。
- [ ] 只有时间收益大于复核成本且高置信错误被门禁阻止，才进入作品包装。
- [ ] 输出确定性 bridge、证据追溯 breakdown 和一个经人工复核的准确报告。

## 冻结

- 不扩“通用 AI 自动逆向”工具集；
- 不把 A2C、脚印或材质意图作为已证实卖点；
- 不在 P0/P2 通过前做作品集包装。
