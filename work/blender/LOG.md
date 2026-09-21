# blender · LOG

### 2026-08-14 19:00 — [决策] 定位为 AI-DCC 执行层
BlenderAgent 与 UEAgent 统一 `Intent -> Plan -> Execute -> Readback -> Verify -> Save` 语义；当前
不抽取共享运行时，也不把聊天式任意 `bpy` 执行当默认路径。

### 2026-08-14 19:00 — [发现] 第二代上游的实际边界
`blender-ai-mcp` 的 guided 小入口面属实但实现很重；`glonorce/Blender_mcp` 的主线程、作业与检查
代码有参考价值且 499 项离线单测通过，但 raw code 仍是首要工具，`tools/list` 仍暴露全量 schema，
且仓库 MIT `LICENSE` 与 `pyproject.toml` 的 `Proprietary` 元数据冲突，暂不复制其代码。

### 2026-08-14 19:00 — [决策] 从一个可观测切片生长工具面
首个验收只覆盖创建、回读、度量、断言、截图和保存；15 个候选接口及
`prepare_game_asset` 不预建，等真实工作流证明需要后再加入。

### 2026-08-14 19:35 — [决策] Blender 路径使用机器级参数
各端以用户环境变量 `BLENDER_PATH` 保存完整可执行文件路径，不把绝对路径写入仓库；当前机器
已用该参数通过 Blender 5.2.0 LTS 的 factory-startup 后台 `bpy` 检查。

### 2026-09-17 11:35 — [决策] 地基改选 `ahujasid/mcp-for-blender`，`blender-ai-mcp` 降为设计参考
量化对比后推翻原计划。选定项：MIT、PyPI 2.0.0（MCP 层自报 1.30.0）、2026-09-16 仍在推送、
28.8k stars，依赖只有 `mcp>=1.9,<2` + `httpx`，支持 Blender 3.0+，本机便携版直接可用。
原计划基线 `PatrykIti/blender-ai-mcp` 仍是 v3.3.0（最后推送 2026-06-27，57 stars，
Apache-2.0），自撰写 Brief 起无进展，且 vision 默认 `mlx_local` 在 Windows 上是死重，
降为 goal-first routing 与 macro/atomic 分层的设计参考。`glonorce/Blender_mcp`
created == pushed == 2026-03-10，6 stars，只作研究输入。官方 Blender Lab MCP 要求
Blender 5.1+、设计上无护栏执行 LLM 代码（自带 `weak_sandbox.py` 明确不是安全边界），
devtalk 讨论帖 2026-09-08 被关闭、治理未定，暂不采用。
决定性技术理由：选定项 addon 已用 socket 线程 → `queue.Queue` → `bpy.app.timers` 排空
实现主线程 marshalling，且已修过 Windows 专属的 `WinError 10054`（daemon handler 线程
活过重启去关新 server 的连接），正是本项目约束里最难那条。

### 2026-09-17 11:35 — [发现] 主线程冻结与桥接 head-of-line blocking 已实测
以 10 Hz 心跳 timer 作探针（实测 9.19–9.23 Hz）。`time.sleep(6)` 期间心跳 0 次
（6.06 秒窗口预期 55.7 次），并发 `ping` 被拖到 5062 ms ≈ 剩余阻塞时长：主线程完全冻结，
且整条桥接对后续任何请求失聪。真实建模负载（600×600 grid = 361,201 顶点 + shade_smooth
+ 三轮顶点遍历）仅 0.561 秒，未触发阈值——本机交互级建模远在问题线以下，故不再加大负载
重复证明同一机制。桥接**没有取消与进度通道**（源码确认：排空是同步 `exec`，客户端断开
只在下一次 `recv` 才被发现），因此任何长操作走这条桥都会让 Blender 全程无响应；
阻塞类工作必须继续走 `--background` CLI 并返回 job id。

### 2026-09-17 11:35 — [发现] 遥测默认开启，已硬关并落盘
服务端 `config.py` 硬编码 Supabase 端点与 anon key，`TelemetryConfig.enabled` 默认 `True`，
另有 `telemetry-screenshots` 存储桶与 `trajectory.py` 第二条上报路径。事件字段含
`prompt_text`、`tool_name`、`duration_ms`、`platform`、`customer_uuid`（持久化于
`%APPDATA%\BlenderMCP\customer_uuid.txt`）。addon 侧 `telemetry_consent` 默认 `True`，
即**不弹任何提示就开始采集**；无同意时仍发精简事件（`prompt_text`/`metadata` 置空）。
处置（评估期）：曾在 `.mcp.json` 的 blender 条目加 `BLENDER_MCP_DISABLE_TELEMETRY=1`
（`telemetry.py` 发送前硬门禁），实测三次调用无任何 supabase POST；addon consent 已置 `False` 并
`save_userpref` 落盘。该宿主注册随后按通用模式撤销（见同日 [决策] 条目），现路径根本不启动
server 包，遥测面在结构上不存在。**需记录的既成事实**：11:14–11:19 发现开关前已有事件出站，
携带本轮测试自填的 `user_prompt` 字符串，不含用户数据。

### 2026-09-17 11:35 — [发现] safe mode 与错误位对验证层的两条硬要求
`BLENDER_MCP_SAFE_MODE=1` 是 deny-by-default AST 校验，实测阻断 `import os`
（"import of 'os' is not allowed"），纯 `bpy` 脚本可通过；文件路径类操作因此不能走
`execute_code`，与"阻塞活交给 CLI"的约束同向。两个必须写进验证层的坑：MCP 层 `is_error`
**不反映** safe-mode 拒绝（返回 `is_error=False` 而正文是拒绝文本），必须查 payload；
存在性断言必须带 mtime 新鲜度，否则会匹配上一轮旧文件而误报 PASS（本轮已出现一次假阳性）。
`execute_code` 失败时返回结构化 `exception_type`/`message`/`traceback`，可直接用于断言。

### 2026-09-17 11:35 — [发现] `tools/list` 全量暴露，与当初否决 glonorce 的理由同构
MCP 层暴露 31 个工具、描述合计 21,536 字符，其中 21 个属于 PolyHaven / Sketchfab /
Poly Pizza / Hyper3D / Hunyuan3D 五个集成，而这五个在本机全部 `enabled: False`。
即三分之二的目录是调用即报错的死重，初始上下文成本照付。addon 自报 `protocol_version 7`、
`addon_version [1,7]`、capabilities 11 项，且该列表不含 handler 字典里实际存在的
`export_scene`——自报能力面与真实命令面不一致。结论：Brief 里"公开面保持小且按真实任务
生长"这条，选定基线并不满足，需在其上自建路由/过滤层，而那正是本项目要拥有的部分。

### 2026-09-17 11:35 — [里程碑] 最小垂直切片跑通（有界读 + 无界写）
`tmp/blender/slice.py` 经 MCP 层（非裸 socket）完成：status → 重置基线 → 创建具名
primitive → 回读 → 断言 → 视口截图 → `export_scene` 导出 → 保存 `.blend` 副本。
9 次 MCP 调用、23 项断言、0 失败。延迟：普通命令 18–63 ms，截图 114 ms（168,843 字节 PNG），
`export_scene` glb 1420 ms（1,824 字节）。回读含 `world_bounding_box`，实测 X/Y 跨度
2.8284 = 2·√2、Z 跨度 2.0，与绕 Z 旋转 45° 一致，证明回读是真实几何而非变换回显。
**未达成的验收项**：Brief 要求 "without arbitrary Python"，但该服务端唯一的写入动词是
`execute_blender_code`，没有 `create_object` 类契约；读与导出有界，创建无界。

### 2026-09-17 11:35 — [纠正] 本机 Blender 运行时事实
2026-08-14 记录的"`BLENDER_PATH` 已通过 Blender 5.2.0 LTS 检查"在本机不成立：2026-09-17
实测该变量在 User / Machine / 进程三个作用域均为空，`C:\Program Files`、
`D:\Program Files`、`AppData\Local\Programs` 下均无 `blender.exe`。本机实际可用的是
Kinesis 遗留的便携版
`D:\Violina\Iris\tmp\Kinesis\blender-portable\blender-4.5.13-windows-x64\blender.exe`
（4.5.13 LTS，hash `daeeeca98fb0`，built 2026-08-25），已验证 `--background
--factory-startup --version` 与 GUI 常驻两种用法。已按 Brief 的机器级参数约定把
`BLENDER_PATH` 设为该路径（User 作用域，未进仓库）。**遗留风险**：它位于另一个项目的
`tmp/` 下，随时可能被清理，需迁到稳定位置。

### 2026-09-17 12:15 — [决策] 撤销宿主 MCP 注册，改走 route + gateway 通用模式
按用户纠正：接进 `.mcp.json` 会把 Blender 绑死在单一 agent 宿主上，违背 UEAgent 的通用模式。
已还原 `.mcp.json` 为只有 `abyss-ue`。改为仓库自有 `work/blender/scripts/bl_gateway.py`，
契约对齐 UEAgent HOTPATH：机器本地 `route.json`（不进仓库）记录 host/port、解析到的
`BLENDER_PATH`、探测到的 addon 与 Blender 版本；请求以 `--request-file` 或 UTF-8
`--request-base64` 传入（从对象构建，从不手工转义）；本地等待；回执写 `--out-file`。
任务级薄 driver `tmp/blender/gw.sh` 钉机器路径，与 `tmp/UEAgent/flux-river/gw.ps1` 同构。
附带结论：遥测与 safe-mode 校验都在 `blender_mcp` server 包内，addon 裸 socket 协议不含它们，
因此直连 addon 在结构上没有遥测面——代价是写入护栏必须自有，已由 gateway 承担。

### 2026-09-17 12:15 — [发现] addon 裸协议与 MCP 包装的两处差异
1. `get_viewport_screenshot(max_size, filepath=None, format="png")` **需要 `filepath`**：addon
   自己把 PNG 写盘，并在回执里报告产出路径与尺寸（实测 800×477、168,843 字节）。
   "文件 → base64" 的翻译是 MCP server 做的，不在 addon 侧；直连时若按 base64 取值会得到
   `{"status":"success","result":{"error":"No filepath provided"}}`。
2. 这同时是第二个"成功位在撒谎"的案例：传输层 `status` 为 `success`，命令错误藏在
   `result.error` 里。gateway 现已对两种形态都判失败——此前一版把这次截图判成了 succeeded，
   是与 MCP `is_error` 同类的漏洞。源码另注：`screen.screenshot_area` 抓的是 OS 窗口
   framebuffer，窗口未被合成时全黑，故优先离屏渲染，无 GPU 上下文才回退窗口抓取。

### 2026-09-17 12:15 — [里程碑] gateway 路由跑通，六条策略经实测生效
`tmp/blender/slice_gw.py` 经 gateway CLI（base64 请求）完成 11 项检查、0 失败：切片五步
（scene info / create+readback / capture / export glb / save `.blend` 副本）全绿，普通命令
18–59 ms，截图与导出走文件落盘。六条策略实测：同一 `commandId` + 同一请求 → `replayed`，
返回已记录终态回执而不重新触碰 Blender；同一 `commandId` + 不同请求 → `rejected`；
`execute_code` 缺 `escapeHatch.reason` → `rejected`；mutation 缺 readback → `rejected`；
readback 不过 → `failed` 且**不落盘**（负向探针确认目标文件不存在）；`wait=false` → 结构化
`rejected` 并指向 `--background` CLI 路由。readback 的 expect 语义照抄 UEAgent：
对象子集匹配、数组严格匹配、数值 1e-6。

### 2026-09-17 13:55 — [里程碑] `wait=false` 真 job 路由跑通，19 项检查 0 失败
上一条里 `wait=false` 只是结构化拒绝，现已实现：gateway 以独立 `blender --background` 进程
（分离启动，在 gateway 每次调用退出后仍存活）承担长活并返回 `jobId`。提交要求稳定 `commandId`
（重放返回同一 job、不启第二个进程，实测 jobId 一致）、`job.script` 与 `job.code` 二选一、
非空 `job.expectArtifacts`。轮询解析六态：running / succeeded / failed / crashed（进程消失且无
状态文件）/ timeout / cancelled。三项关键证明：
1. **job 运行期间交互会话完全可用**：对 GUI Blender 的 `ping` 38.3 ms，对比桥接被阻塞时的
   5062 ms——这是交互/批处理拆分的量化依据。
2. **干净退出但没产出仍判失败**：脚本正常结束却未写 `expectArtifacts` → `failed`，
   error 为 "job reported success but its expected artifacts did not verify"；产物校验要求
   存在 + 非空 + mtime 新于 job 起点。抛异常的 job 则完整保留 traceback。
3. **取消可用**：`job_cancel` 杀进程树（`taskkill /T /F`），状态转 `cancelled`，二次取消幂等
   （返回 `replayed`）。这是 addon 桥接在结构上给不了的能力。
实现要点两个坑：Windows 下**不能**用 `os.kill(pid, 0)` 探活——CPython 把非
CTRL_C_EVENT/CTRL_BREAK_EVENT 的信号直接接到 `TerminateProcess`，会杀掉正在检查的 job，
改用 `tasklist /FI "PID eq n" /NH`；无 `blendFile` 时默认 `--factory-startup`，顺带把 addon
排除在 job 进程外，避免与 GUI 抢 9876 端口。job 脚本不经 `blender_mcp` server，因此 safe mode
不适用（`import os` 可用），路径类工作本就该落在这条路由。切片与策略套件重跑无回归（11 项 0 失败）。

### 2026-09-17 14:15 — [里程碑] 有界 job kind 取代 caller 脚本，25 项检查 0 失败
manifest 驱动：每个 kind 声明参数 schema、生成的 Python 与自己承诺的产物，因此有界 job
**不接受** `expectArtifacts`（两者同给 → `rejected`），postcondition 归契约而非调用方。
`job_kinds` 按需返回目录与 schema。参数在启动任何进程之前校验完毕，14 条拒绝分支实测全部命中：
未知 kind、kind 与 script/code 混用、完全无输入、后缀不支持、format 与后缀矛盾、未知参数名、
类型错、枚举越界、必填缺失、列表元素类型错、convert 输入不存在、`blendFile` 不存在。
三个 kind 实测：`export` 由后缀推导 glb/fbx（glb 1,824 字节、fbx 28,988 字节）；`render` 单帧 PNG，
**按 PNG 头里的实际尺寸断言**（EEVEE 96×54、Cycles 32×32）而非只看文件存在；`convert` 走 Kinesis 配方。
两个实现事实均由算子签名探针先行确认、未凭记忆书写：glTF 导出的修改器开关叫
`export_apply` 而非 `apply_modifiers`，`render.render` 只有 6 个属性，
输出路径/引擎/分辨率全部走 `scene.render.*`。`render` 明确拒绝动画：帧序列不是单个可验证产物，
宁可留缺口也不做半个契约。
**更正（同日 14:40）**：本条曾写"`--factory-startup` 下引擎枚举只有 `BLENDER_EEVEE_NEXT`，
Cycles 未注册，故 render kind 自行 `addon_enable('cycles')`"。该机制结论无效——
`RenderSettings.engine` 的 `enum_items` **不穷举可赋值项**，实测 `engine = "CYCLES"`
不抛异常且赋值后确为 `CYCLES`，Cycles 也随包发布于 `4.5/scripts/addons_core/cycles`。
kind 里的 `addon_enable` 无害但从来不是决定因素；k06 的 Cycles 渲染结论仍然成立。

### 2026-09-17 14:15 — [发现] convert kind 与 8 月产物语义等价（789/789 通道）
用同一份 `walk_00.bvh` 跑 `convert`，与 Kinesis 2026-08-26 产出的 `walk_00.fbx` 对比：体积同为
1,167,884 字节；armature 同为 `walk_00`、78 骨、root `Root`、动作帧范围 [1,120]、789 条 fcurve；
fps 30、场景帧 1..250、unitScale 1.0；dummy 同为 8 顶点 + `Hips` 顶点组 + 1 个 armature modifier。
按 `data_path` + `array_index` 匹配后逐通道摘要比对：**789 比对、789 相同、0 不匹配、0 单侧**。
唯一差异是 dummy 名（`ConvertDummy` vs `SomaDummy`），系本轮有意改名。
方法教训两条：字节比对在此无用（体积相同但 93% 字节不同，来自 FBX 创建时间戳与对象名）；
而第一版比对脚本取"第一条 location 曲线"，因 fcurve 顺序在两次导出间不稳定，把 `Root.location`
与 `LeftHandThumb3.location` 相比而报出**假阴性**——比对必须按键匹配通道，不能按位置取样本。

### 2026-09-17 14:40 — [发现] 美术资产管线的可用算子面（已探明）
为回答"能否跑通美术资产生产全流程"，在便携版 4.5.13 上以 GUI（经桥接）与 `--background`
两种上下文分别探测。**先记两条方法教训**：`getattr(bpy.ops.<space>, <name>)` 对任意名字都返回
代理对象，只有 `get_rna_type()` 抛 `KeyError` 才能判定算子未注册；`RenderSettings.engine` 的
`enum_items` 同样不能作为可用性依据。两者都会把"不可用"误报成"可用"。
**可用**：`object.quadriflow_remesh`(11)、`object.data_transfer`(18，蒙皮权重传递)、
`object.modifier_add` 且 SUBSURF / SOLIDIFY / BEVEL / SHRINKWRAP / REMESH / TRIANGULATE /
DECIMATE / ARRAY / ARMATURE / UV_PROJECT / NORMAL_EDIT / WEIGHTED_NORMAL **一个不缺**、
`mesh.subdivide`、`image.new`(9)、`uv.unwrap`(11)、`uv.lightmap_pack`(5)、`uv.pack_islands`(10)、
`uv.seams_from_islands`(2)、`uv.average_islands_scale`(2)、`import_scene.fbx`(26)、
`export_scene.fbx`(42)、`export_scene.gltf`(108)、`object.duplicate` / `parent_set` /
`transform_apply` / `shade_smooth`。
**不可用（GUI 与后台均为 PHANTOM）**：`render.bake`、`uv.smart_uv_project`、
`paint.image_from_viewport`。三者在 shipped Python 中都没有定义（`render.bake` 只在
`addons_core/cycles/ui.py` 与 `version_update.py` 里被引用），属 C++ 内建算子；
即使先把 `engine` 真正切成 `"CYCLES"` 再探，`RENDER_OT_bake` 仍未注册。只剩 legacy
`object.bake_image`(1 prop)，且无法枚举出法线/AO/曲率/厚度这类 bake type。
**结论**：烘焙这一段在当前 Blender 构建上无法自动化，因此完整 PBR 资产流程跑不通；
UV 阶段可改用 `uv.unwrap` + `pack_islands` 绕过 smart UV project。

### 2026-09-17 14:40 — [越界记录] UE 编辑器身份不一致（不属本项目范围）
本项目的 canonical path 止于 save/export，UE 编辑器状态**不是资产生产的依赖**，此条只因回答
"能否跑通全流程"时把范围误扩到消费侧而记下，归属应在 UEAgent 而非此处。
事实本身仍成立：`127.0.0.1:8000` 在听、`UnrealEditor` 在跑（PID 38840），但 `state.json` 记
`editor_pid 4632`、`doctor.json` 记 `listenerPids [17732]` 且 `checkedAtUtc 2026-09-05`，
三者互不一致；`state.json` 的 `protocol_version` 仍是 `2.0.0`，而仓库已迁到 3.0；
`route.json` 的 `profile` 是 `niagara-authoring`。
与本项目唯一真实的关联是**静态配方知识**：`convert` kind 里的 Y/X 骨轴、`armature_nodetype=NULL`、
以及蒙皮到根骨的 dummy 立方体，都是当年为 UE 导入验证出来的常量，已固化进模板，
执行时不需要任何活的 UE 进程。

### 2026-09-17 15:05 — [里程碑] 首次完整资产构建：低多边形小车，15 项检查 0 失败
经 gateway 构建 `IRIS_CAR_*`：车身 + 座舱（bevel）、四轮 + 轮辋、前后灯、7 个材质、
双机位相机 + 太阳灯 + Track-To 空物体。每步 mutation 带 `commandId` + `escapeHatch` + readback；
几何按 14 个部件的 `world_bounding_box` 联合体校验，实测尺寸 4.04 × 1.965 × 1.54
且 min z ≈ 0（确实落地）。渲染与导出走 job 路由；`render` kind 新增 `camera` 参数
（同一份 .blend 渲两个机位，系被真实需求逼出的接口生长）。为不污染用户活会话里的工厂
Cube/Light/Camera，另用一个 job 生成只含 `IRIS_CAR_` 前缀的 `car-clean.blend` 作为渲染/导出源。
产物在 `tmp/blender/evidence/`：car.blend(788,056 B)、car-clean.blend、car-34.png 与
car-side.png（720×405，按 PNG 头校验尺寸）、car.glb(71,572 B)、car-viewport.png。
**同时确认了 Doing 项的必要性**：建模六步全部走 `execute_code` 逃生口，因为尚无有界 mutation
契约；渲染、导出、存盘则全部走有界 kind。美学判断仍归用户。

### 2026-09-17 15:20 — [纠正] 烘焙并非不可用：14:40 的结论探错了算子名
14:40 那条"烘焙在当前构建上无法自动化"**作废**。我探的是 `render.bake`——2.7x 时代的名字；
Blender 2.8+ 的烘焙算子是 `bpy.ops.object.bake`，实测 **PRESENT(22 props)**，且 bake type 全齐：
COMBINED / AO / SHADOW / POSITION / NORMAL / UV / ROUGHNESS / EMIT / ENVIRONMENT / DIFFUSE /
GLOSSY / TRANSMISSION。UV 同理：真名是 `uv.smart_project`(7 props)，PRESENT；
`uv.smart_uv_project` 只是不存在的旧名。
**教训**：算子名跨大版本会改。`PHANTOM` 只证明"这个名字没注册"，不证明"这个能力不存在"；
探针必须覆盖新旧两套名字，或先解析 UI 菜单实际绑定的 idname。这正是我自己记下的
"`getattr(bpy.ops...)` 不可靠"教训的下一层：连名字本身都不可靠。
14:40 条中关于 modifier 面、`object.data_transfer`、`object.quadriflow_remesh` 的结论不受影响。

### 2026-09-17 17:40 — [里程碑] 剩余美术生产流程链跑通：UV → 烘焙 → 贴图回接 → LOD → QC → 导出
四个独立 job 串联（每步吃上一步的 .blend、产自己的产物与 QC JSON），4 项检查 0 失败。
**UV**：15 个网格全部 `uv.smart_project` + `pack_islands`，每个恰好 1 层 UV；layout 预览 6 个岛，
与盒体六面一致、无重叠。**烘焙**：`bpy.ops.object.bake`（Cycles CPU，AO 8 采样 / DIFFUSE 1 采样，
1024²）对 Body 与 Cabin 各出 AO + basecolor 共 4 张，耗时 0.6 / 0.2 / 0.4 / 0.1 秒；AO 图肉眼可辨
座舱压出的遮挡矩形与轮子的遮挡圆，是真烘焙而非空图。**贴图回接**：新建 `*_Baked` 材质，
把烘出的 basecolor 接进 Principled Base Color 并赋回部件。**LOD**：先应用 authored 修改器再
DECIMATE，LOD0/1/2 = 1128 / 564 / 232 tris（14 个对象），单调递减。**导出**：`car-lods.glb`
180,488 B，含三级 LOD 与贴图。
**两处中途纠正**：首跑 LOD 三角数数的是未应用 bevel 的基础笼（778），修正为先应用修改器再减面；
Ground 属渲染布景而非可交付资产，已从 LOD 与导出中排除。
**新能力边界**：`uv.export_layout` 在 `--background` 下抛
`SystemError: GPU functions for drawing are not available in background mode`——GPU 绘图类操作
只在有窗口的进程可用，用短命 GUI 进程打开 `car-uv.blend` 导出后退出解决。
即：烘焙与渲染可无头，GPU 绘图不可。

### 2026-09-17 18:00 — [决策] 与 UEAgent 做架构同构，不做全量对齐
用户明确只问架构、不要求完全对齐。逐条对照 HOTPATH 五项执行责任后的结论：两条路由在七件
承重件上同构——机器本地 route 文件、仓库自有 gateway、base64/文件请求编码、回执 out file、
commandId 重放（canonical 比对 + terminal 记录）、targeted readback + expect、`wait=false`
job 路由。剩余差距是**域差异而非架构差异**：UE 有引擎内建的资产包 / epoch / dirty 状态可绑，
Blender 的"包"就是 .blend 文件、epoch 只能自造，硬对齐会造出假抽象（save packages、scopes
两项在 Blender 域无自然对应物）。两处**故意保留的差异**：readback 在 mutation 上强制
（UEAgent 为 optional），以及 `job_cancel`（UEAgent 契约没有）。
真正值得补的两个缺口与 UEAgent 无关、是 Blender 域内真实风险：重启后身份不可辨（epoch）、
并发 gateway 进程写坏 ledger（one-writer）。按"按观察到的任务生长"的约束，等真实并发或重启
事故逼出来再建，不预建。
