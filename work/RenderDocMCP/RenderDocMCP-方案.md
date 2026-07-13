# RenderDocMCP · 技术方案

> 通用 RenderDoc MCP 工作流——AI 解析每一帧 + 反编译 Shader。
> 创建：2026-07-10。

## 1. 目标

| 目标 | 描述 |
|---|---|
| **帧分析** | AI 通过 MCP 工具加载 `.rdc` 文件，逐 Draw Call 分析管线状态、资源绑定、纹理输出 |
| **Shader 反编译** | 反汇编任意 stage 的 Shader（DXBC / SPIR-V / ISA），并提取常量缓冲区变量值 |
| **通用性** | 不绑定特定图形 API（D3D11/D3D12/Vulkan/OpenGL 均通过 RenderDoc 抽象层） |
| **MCP 标准化** | 以 MCP Server 形式暴露工具，任何支持 MCP 的 AI 客户端均可接入 |

## 2. 架构总览

```
┌─────────────────────────────────────────────┐
│                AI Client (Box / Claude)      │
│              MCP stdio 传输                  │
└──────────────────┬──────────────────────────┘
                   │
        ┌──────────▼──────────┐
        │   renderdoc_mcp.py   │  MCP Server (FastMCP)
        │   ┌───────────────┐  │
        │   │  Tool Registry │  │  9+ 个 MCP 工具
        │   ├───────────────┤  │
        │   │  RDController  │  │  RenderDoc 会话管理
        │   │  (单例/多会话) │  │
        │   ├───────────────┤  │
        │   │  Shader Tools  │  │  反汇编 + Reflection + CBuffer
        │   ├───────────────┤  │
        │   │  Frame Tools   │  │  DrawCall 树 + 管线状态 + 资源
        │   └───────────────┘  │
        └──────────┬──────────┘
                   │
        ┌──────────▼──────────┐
        │   renderdoc module   │  renderdoc.pyd (Win) / .so (Linux)
        │   (Python C Extension)│
        └──────────────────────┘
```

### 2.1 关键设计决策

| 决策点 | 方案 | 理由 |
|---|---|---|
| **API 层** | `renderdoc` 模块（底层 Replay API），不用 `qrenderdoc` | UI API 依赖 Qt 事件循环，不适合 headless server |
| **传输** | stdio | MCP 标准方式，无需端口管理；如需远程可扩展 SSE |
| **会话模型** | 单例 ReplayController，支持多 capture 切换 | `InitialiseReplay()` 全局只能调一次，但可开多个 capture |
| **Shader 反编译** | `DisassembleShader()` + `GetCBufferVariableContents()` | 依赖 RenderDoc 内置反汇编能力，不自己写反编译器 |
| **数据序列化** | 所有 RenderDoc 对象 → dict/list/str 再返回 | MCP 工具返回值需 JSON 可序列化 |

## 3. 工具集设计

### 3.1 会话管理

#### `open_capture`

加载 `.rdc` 文件，初始化 replay。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `filepath` | str | 是 | `.rdc` 文件绝对路径 |

返回：
```json
{
  "capture_id": "cap_0",
  "driver": "D3D11",
  "frame_count": 1,
  "drawcall_count": 142
}
```

实现路径：
```python
rd.InitialiseReplay(rd.GlobalEnvironment(), [])  # 只调一次
cap = rd.OpenCaptureFile()
cap.OpenFile(filepath, '', None)
result, controller = cap.OpenCapture(rd.ReplayOptions(), None)
```

#### `close_capture`

关闭当前 capture，释放 ReplayController。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `capture_id` | str | 否 | 默认关闭当前活跃 capture |

#### `list_disassembly_targets`

列出当前 capture 支持的 Shader 反汇编格式。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `with_pipeline` | bool | 否 | 是否基于完整管线状态枚举（默认 true，某些 target 需要 PSO） |

返回：`["DXBC", "AMD GCN ISA", ...]`

### 3.2 帧分析

#### `list_drawcalls`

递归获取帧内所有 Draw Call，返回扁平化树结构。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `capture_id` | str | 否 | 默认当前活跃 |
| `filter` | str | 否 | 过滤关键词（如 "Draw" / "Dispatch" / "Clear"） |

返回：
```json
[
  {
    "event_id": 1,
    "name": "ClearRenderTargetView",
    "type": "Clear",
    "children": []
  },
  {
    "event_id": 5,
    "name": "DrawIndexed(36, 1, 0)",
    "type": "Draw",
    "children": [...]
  }
]
```

实现路径：
```python
draws = controller.GetDrawcalls()
# 递归遍历 draw.children，提取 event_id / name / flags
```

#### `get_pipeline_state`

获取指定事件处的完整管线状态快照。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | Draw Call 事件 ID（EID） |
| `capture_id` | str | 否 | 默认当前活跃 |

返回（按 stage 组织）：
```json
{
  "vertex_shader": {
    "shader_id": "rdc-vsid-xxx",
    "entry_point": "VSMain",
    "resources": [...],
    "cbuffers": [...]
  },
  "pixel_shader": { ... },
  "render_targets": [...],
  "depth_target": "...",
  "blend_state": { ... },
  "rasterizer_state": { ... },
  "depth_stencil_state": { ... }
}
```

实现路径：
```python
controller.SetFrameEvent(event_id, True)
state = controller.GetPipelineState()
# 遍历各 stage：state.GetShaderReflection(stage)
# 资源绑定：state.GetReadOnlyResources(stage) / GetReadWriteResources(stage)
# 常量缓冲区：state.GetConstantBlock(stage, slot, idx)
```

#### `get_frame_stats`

获取帧级统计信息。

返回：
```json
{
  "total_drawcalls": 142,
  "drawcalls_by_type": {"Draw": 80, "DrawIndexed": 30, "Dispatch": 5, "Clear": 27},
  "resource_count": 256,
  "api": "D3D11"
}
```

### 3.3 Shader 反编译

#### `disassemble_shader`

反汇编指定事件的指定 Shader Stage。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | Draw Call 事件 ID |
| `stage` | str | 是 | Shader 阶段：`vertex` / `pixel` / `geometry` / `hull` / `domain` / `compute` |
| `target` | str | 否 | 反汇编格式，默认首个（合理默认） |
| `capture_id` | str | 否 | 默认当前活跃 |

返回：
```json
{
  "stage": "pixel",
  "target": "DXBC",
  "shader_hash": "9dd8337a-c75dd787-1fa0f07e-5f39f955",
  "disassembly": "ps_5_0\n  dcl_constantbuffer cb0[8]...\n  ...\n  ret\n",
  "entry_point": "PSMain"
}
```

实现路径：
```python
controller.SetFrameEvent(event_id, True)
state = controller.GetPipelineState()
pipe = state.GetGraphicsPipelineObject()
entry = state.GetShaderEntryPoint(stage_enum)
shader = state.GetShaderReflection(stage_enum)
disasm = controller.DisassembleShader(pipe, shader, target)
```

#### `get_shader_reflection`

获取 Shader 反射信息（输入/输出签名、资源绑定、常量缓冲区结构）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | 事件 ID |
| `stage` | str | 是 | Shader 阶段 |
| `capture_id` | str | 否 | 默认当前活跃 |

返回：
```json
{
  "stage": "pixel",
  "resource_id": "rdc-id-xxx",
  "entry_point": "PSMain",
  "input_signature": [
    {"name": "POSITION", "type": "float", "rows": 1, "cols": 3, "reg": 0},
    {"name": "TEXCOORD", "type": "float", "rows": 1, "cols": 2, "reg": 1}
  ],
  "output_signature": [
    {"name": "SV_Target", "type": "float", "rows": 1, "cols": 4, "reg": 0}
  ],
  "resources": [
    {"name": "gDepthMap", "type": "Texture2D", "reg": 0, "view_dim": "Tex2D"},
    {"name": "gGBufferMap", "type": "Texture2D", "reg": 1, "view_dim": "Tex2D"}
  ],
  "cbuffers": [
    {"name": "cb0", "reg": 0, "size": 512, "variables": [...]}
  ],
  "samplers": [
    {"name": "gDepthSam", "reg": 0, "mode": "default"}
  ]
}
```

#### `get_cbuffer_variables`

递归获取常量缓冲区中所有变量的当前值。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | 事件 ID |
| `stage` | str | 是 | Shader 阶段 |
| `slot` | int | 否 | CBuffer 寄存器槽位，默认 0 |
| `capture_id` | str | 否 | 默认当前活跃 |

返回：
```json
[
  {
    "name": "gLight",
    "type": "struct",
    "members": [
      {
        "name": "pos",
        "type": "float",
        "rows": 1,
        "columns": 3,
        "value": [-2.022, 2.000, -3.694]
      },
      {
        "name": "diffuse",
        "type": "float",
        "rows": 1,
        "columns": 4,
        "value": [0.300, 1.000, 0.600, 1.000]
      }
    ]
  },
  {
    "name": "gWorldViewProj",
    "type": "float",
    "rows": 4,
    "columns": 4,
    "value": [1.567, 0.000, ..., 6.306]
  }
]
```

实现路径：
```python
controller.SetFrameEvent(event_id, True)
state = controller.GetPipelineState()
pipe = state.GetGraphicsPipelineObject()
shader = state.GetShaderReflection(stage_enum)
entry = state.GetShaderEntryPoint(stage_enum)
cb = state.GetConstantBlock(stage_enum, slot, 0)
vars = controller.GetCBufferVariableContents(
    pipe, shader.resourceId, stage_enum, entry, slot, cb.descriptor.resource, 0, 0
)
# 递归遍历 vars：var.members / var.rows / var.columns / var.value.f32v
```

### 3.4 资源与纹理

#### `save_texture`

导出指定事件处某个纹理到磁盘文件。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | 事件 ID |
| `resource_id` | str | 否 | 纹理资源 ID，默认输出当前渲染目标 |
| `output_path` | str | 是 | 输出路径（.png / .dds / .exr） |
| `capture_id` | str | 否 | 默认当前活跃 |

实现路径：
```python
controller.SetFrameEvent(event_id, True)
# 获取资源 ID 或用当前输出目标
controller.SaveTexture(resource_id, mip, slice, output_path)
```

#### `list_resources`

列出帧内所有 GPU 资源（纹理、缓冲区）。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `filter_type` | str | 否 | 过滤类型：`texture` / `buffer` / 空=全部 |
| `capture_id` | str | 否 | 默认当前活跃 |

返回：
```json
[
  {"id": "rdc-id-1", "type": "Texture2D", "width": 1920, "height": 1080, "format": "R8G8B8A8_UNORM", "name": "BackBuffer"},
  {"id": "rdc-id-2", "type": "Buffer", "size": 65536, "name": "VertexBuffer_0"}
]
```

#### `get_mesh_data`

解码指定事件的顶点/索引缓冲区数据。

| 参数 | 类型 | 必填 | 说明 |
|---|---|---|---|
| `event_id` | int | 是 | 事件 ID |
| `max_vertices` | int | 否 | 最多返回顶点数，默认 1000 |
| `capture_id` | str | 否 | 默认当前活跃 |

实现路径：
```python
controller.SetFrameEvent(event_id, True)
state = controller.GetPipelineState()
# 获取 IA 阶段的顶点缓冲区和索引缓冲区
# 调用 controller.GetBufferData() 解码
```

## 4. API 映射速查

| MCP 工具 | RenderDoc Python API |
|---|---|
| `open_capture` | `rd.OpenCaptureFile()` → `cap.OpenFile()` → `cap.OpenCapture()` |
| `close_capture` | `controller.Shutdown()` → `cap.Shutdown()` |
| `list_drawcalls` | `controller.GetDrawcalls()` → 递归 `draw.children` |
| `get_pipeline_state` | `controller.SetFrameEvent()` → `controller.GetPipelineState()` |
| `list_disassembly_targets` | `controller.GetDisassemblyTargets(True)` |
| `disassemble_shader` | `state.GetGraphicsPipelineObject()` → `state.GetShaderReflection()` → `controller.DisassembleShader()` |
| `get_shader_reflection` | `state.GetShaderReflection()` → `.inputSignature` / `.outputSignature` / `.Resources` |
| `get_cbuffer_variables` | `state.GetConstantBlock()` → `controller.GetCBufferVariableContents()` |
| `save_texture` | `controller.SaveTexture()` |
| `list_resources` | `controller.GetResourceList()` / `state.GetReadOnlyResources()` |
| `get_mesh_data` | `controller.GetBufferData()` |
| `get_frame_stats` | `controller.GetFrameStats()` |

## 5. 实现计划

### Phase 1 — 骨架 + 最小闭环（M1）

**目标**：AI 能加载 .rdc → 看到所有 Draw Call → 反汇编任意 Shader

- [ ] `renderdoc_mcp.py` 主框架（FastMCP + `renderdoc` 模块加载 + 全局生命周期管理）
- [ ] `open_capture` / `close_capture`
- [ ] `list_drawcalls`
- [ ] `disassemble_shader` + `list_disassembly_targets`
- [ ] `.mcp.json` 配置示例
- [ ] 用一个真实 .rdc 跑通验证

### Phase 2 — 管线状态 + 常量（M2）

**目标**：AI 能查看完整管线状态和 CBuffer 变量值

- [ ] `get_pipeline_state`
- [ ] `get_shader_reflection`
- [ ] `get_cbuffer_variables`
- [ ] `get_frame_stats`

### Phase 3 — 资源与纹理导出（M3）

**目标**：AI 能导出纹理、列出资源、解码 Mesh

- [ ] `save_texture`
- [ ] `list_resources`
- [ ] `get_mesh_data`
- [ ] `get_texture_data`（读取像素值，不写文件）

### Phase 4 — 打磨与扩展

- [ ] 多 capture 会话管理（切换/对比）
- [ ] SPIR-V Cross 反编译为 GLSL（如 RenderDoc 内置不提供 HLSL 反编译）
- [ ] 错误处理与友好的错误消息
- [ ] 单元测试
- [ ] README 安装文档

## 6. 环境与安装

### 前置条件

| 依赖 | 版本 | 说明 |
|---|---|---|
| RenderDoc | 1.x | 安装后 `renderdoc.pyd` 在安装目录下 |
| Python | 与 RenderDoc 编译版本一致（通常 3.6+） | `renderdoc.pyd` 要求版本匹配 |
| `mcp` 包 | 最新 | `pip install mcp` |

### 安装步骤

```powershell
# 1. 确保 RenderDoc 已安装，记录安装路径（如 C:\Program Files\RenderDoc）
# 2. 确保 renderdoc.pyd 所在目录加入 PYTHONPATH 或代码中手动 sys.path.insert
# 3. 安装 MCP SDK
pip install mcp
# 4. 配置 .mcp.json（见下方示例）
```

### .mcp.json 配置示例

```json
{
  "mcpServers": {
    "renderdoc": {
      "command": "python",
      "args": ["C:/path/to/renderdoc_mcp.py"],
      "env": {
        "RENDERDOC_PATH": "C:/Program Files/RenderDoc"
      }
    }
  }
}
```

### 代码中加载 renderdoc 模块

```python
import sys, os

# 方法 1：通过环境变量
renderdoc_path = os.environ.get("RENDERDOC_PATH", r"C:\Program Files\RenderDoc")
sys.path.insert(0, renderdoc_path)

# 方法 2：直接指定 pyd 路径
# sys.path.insert(0, r"C:\Program Files\RenderDoc")

import renderdoc as rd
```

## 7. 关键注意事项

> [!NOTE] `InitialiseReplay()` 全局只能调一次，`ShutdownReplay()` 只能在程序退出时调。MCP Server 生命周期内维护一个全局 replay 上下文。
> — ai 2026-07-10

> [!NOTE] `renderdoc.pyd` 是 C 扩展，必须用与 RenderDoc 编译时相同的 Python 版本加载。版本不匹配会直接 crash。
> — ai 2026-07-10

> [!NOTE] `SetFrameEvent(eid, True)` 的第二个参数 `True` 表示阻塞等待 replay 完成。MCP 工具调用是同步的，这没问题。
> — ai 2026-07-10

> [!NOTE] 所有 RenderDoc 枚举值（`ShaderStage` / `ResourceType` / `TextureType` 等）需要做 str↔enum 映射表，让 AI 用可读字符串调用。
> — ai 2026-07-10

> [!NOTE] 参考 [UEAgent MCP 坑册](../UEAgent/notes/mcp-坑册.md)：子进程环境不继承 shell，spawn MCP 时 `python` 可能找不到，需写绝对路径。
> — ai 2026-07-10
