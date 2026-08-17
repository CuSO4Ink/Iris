# RenderDocMCP 项目索引

这个目录按“原始捕获不动、当前交付优先、旧内容可恢复归档”的原则整理。

| 位置 | 用途 |
| --- | --- |
| `captures/` | 原始 RenderDoc 捕获文件；体积很大，禁止清理或覆盖。 |
| `outputs/` | 对外分析交付。当前凉亭滴水交付位于 `outputs/tlou2_frame11719_drip_breakdown/delivery/`；瀑布交付位于 `outputs/瀑布水体实现拆解/`。 |
| `evidence/` | 死亡搁浅瀑布分析的原始导出证据和模型资源。 |
| `tools/` | RenderDoc 可执行文件、源码构建和构建日志。一键截帧脚本依赖其中的 `renderdoc_src_2fc0bc04`，不要移动。 |
| `skills/` | 可安装的 `renderdoc-vfx-breakdown` Skill 及安装/打包说明。 |
| `archive/` | 已被新版本替代、空目录或临时验收产物；不删除，保留恢复路径。 |

## 交付入口

- 凉亭滴水：`outputs/tlou2_frame11719_drip_breakdown/delivery/`
- 凉亭滴水压缩包：`outputs/tlou2_frame11719_drip_breakdown/TLOU2_凉亭滴水_RenderDoc交付包.zip`
- 瀑布：`outputs/瀑布水体实现拆解/`
- 一键截帧：`启动TLOU2_RenderDoc截帧.cmd`
- MCP 配置与使用：[MCP配置与使用指南.md](MCP配置与使用指南.md)

## TLOU2 截帧里程碑（已验证）

这不是普通的系统版 RenderDoc 截帧：TLOU2 的 `sl.interposer.dll 2.7.2` 会自行导出并调用
`D3D12CreateDevice` / `CreateDXGIFactory*`，使真正的 Device、Factory、SwapChain 绕过原版
RenderDoc 对 `d3d12.dll` / `dxgi.dll` 的 Hook；同时原版默认置空 NVAPI 会令游戏稳定崩溃于
`tlou-ii.exe+0x1291B99`。最终路径如下：

1. 2026-07-17：排除运行中 `inject`（已错过图形 API 初始化）、启动器二次拉起及仅开
   `--opt-hook-children` 的方案；后者虽注册 D3D12 Hook，但因 NVAPI/Streamline 冲突崩溃。
2. 2026-07-18：基于官方提交 `2fc0bc04` 定制编译 RenderDoc：在 `nvapi_hooks.cpp` 放行启动所需
   NVAPI 查询并继续拦截未包装的 `NvAPI_D3D12_*`；在 `d3d12_hooks.cpp` / `dxgi_hooks.cpp` 补挂
   `sl.interposer.dll` 的 D3D12/DXGI 导出。
3. 验证成功：Frame 3460，`3,716,522,887` bytes（约 3.46 GiB），原始 Capture Section 约
   13.65 GiB；日志同时出现 Streamline D3D12 wrapping、frame capturer、`Finished capture` 与
   `Written to disk`。

日常只需在游戏完全退出后运行 `启动TLOU2_RenderDoc截帧.cmd`，在启动器点“开始游戏”，确认左上角
Overlay 后按一次 F12 并等待写盘完成。截帧必须使用 `tools/renderdoc_src_2fc0bc04/x64/Development/`
中的定制 `renderdoccmd.exe`；系统版 RenderDoc 仅用于打开 `.rdc`。完整的排查、补丁、编译与手动命令
见 `TLOU2-RenderDoc注入排查操作记录.md`。

## 维护约定

1. 新分析统一创建在 `outputs/<游戏>_<帧号>_<效果>/`，对外交付放在其 `delivery/` 子目录。
2. 跨帧验证、RenderDoc 原始导出、渲染验收图分别放在该分析目录的 `evidence/`、`qa/`；不要散落到项目根目录。
3. 被替代的版本移入 `archive/YYYY-MM-DD/`，不要直接删除；确认无误后再由人工决定是否清理。
