# RenderDocMCP · BACKLOG

> 待办清单。顺手加，做完打勾。复杂任务可转成 `tasks/T-xxx.md`。

## 进行中

- [ ] 搭建 MCP Server 骨架（stdio 传输 + renderdoc 模块加载）
- [ ] 实现 `open_capture` 工具（加载 .rdc → 返回 capture 句柄）
- [ ] 实现 `list_drawcalls` 工具（递归遍历 Draw Call 树）
- [ ] 实现 `disassemble_shader` 工具（枚举 target → 反汇编指定 stage）

## 待办

- [ ] 实现 `get_pipeline_state` 工具（完整管线状态快照）
- [ ] 实现 `get_cbuffer_variables` 工具（递归输出常量缓冲区变量值）
- [ ] 实现 `get_shader_reflection` 工具（输入/输出签名 + 资源绑定）
- [ ] 实现 `save_texture` 工具（导出指定事件的颜色/深度纹理）
- [ ] 实现 `get_mesh_data` 工具（解码顶点/索引缓冲区）
- [ ] 实现 `get_texture_data` 工具（读取纹理像素数据）
- [ ] 实现 `list_resources` 工具（列出帧内所有 GPU 资源）
- [ ] 实现 `get_frame_stats` 工具（帧统计信息）
- [ ] 编写 .mcp.json 配置示例和安装说明
- [ ] 补充 SPIR-V / HLSL 反编译对比测试
- [ ] `get_pipeline_state` 补充 blend state 读取（`PipeState.GetColorBlends()`），当前无法直接确认某材质是否启用Alpha混合，只能靠shader输出逻辑反推（瀑布水幕主体分析中遇到，2026-07-15）
- [ ] `get_pipeline_state` 补充 `render_targets`/`viewports`/`input_assembly`/`vertex_buffers` 字段的实际输出排查——代码里已有对应的try/except读取逻辑但实测始终不出现在返回结果里（可能被异常静默吞掉），需要定位根因

## 已完成（近期，便于回忆）

- [x] 项目初始化（三件套 + 技术方案文档）

---

完成超过 2 周的项移除；有保留价值的写进 LOG.md。
