# AirWall · LOG

> 决策流水。追加式，新条目加在**文件末尾**。由 `/log` 命令维护。

## 条目格式

```
### YYYY-MM-DD HH:MM — 标题
（一句话结论，或决策理由 + 否决方案。3 行以内）
```

## 条目分类标签（可选，加在标题前）

- `[决策]` 选定了某方案
- `[否决]` 排除了某方案及原因
- `[发现]` 意外收获或反直觉观察
- `[回滚]` 推翻之前的决策

---

<!-- 新条目追加在下方 -->

### 2026-06-01 15:18 — [决策] 项目启动
将“空气墙处理”拆成独立项目，先建立可观测排查流程：复现点位 → 碰撞可视化 → 对象归因 → 最小修复 → 回归验证。

### 2026-06-01 15:24 — [决策] 目标改为 Spline + Niagara 空气墙系统
项目目标从单纯排查空气墙，升级为重构空气墙架构：Spline 负责可编辑路径，碰撞代理负责阻挡，Niagara/材质负责连续视觉和玩家接触波纹反馈。

### 2026-06-02 15:08 — [回滚] 坐标空间统一为 Local，撤销"Box 用 World"
之前建议 Box Collision 用 World 取点 + SetWorldLocation，SplineMesh 用 Local，这是错的根源。混用两套空间导致动态生成的 Box 整体偏移（实际是 World 坐标在组件注册/Attach 时机下被当成相对父级解析，且依赖 Actor 世界变换为 identity）。正确做法：Box 与 SplineMesh 全部用 Local 取点 + SetRelativeLocation/Rotation，跟 Actor 同一空间，对 Actor 移动/旋转/缩放天然鲁棒。当初"没碰撞/偏移"误判为碰撞设置问题，根因其实是坐标空间。

### 2026-06-03 21:52 — [决策] 分段改为弦高自适应步长 + 修末端外推
把均匀分段（Ceil(Length/SegLen) 后 D1=(i+1)*SegLen）换成弦高(sagitta)自适应：while 循环从 MaxStep 试探，取 P0/P1/Pm 三点，sagitta=点 Pm 到线段 P0P1 距离；sagitta>ChordTolerance 则 Step*=0.5 二分回退，直到够直/触底 MinStep/吃到末端才接受。直线一步迈到底，弯道自动加密，唯一画质旋钮是 ChordTolerance。
新增变量 MaxStep≈600 / MinStep≈50 / ChordTolerance≈5。先写 GetAdaptiveSegments 输出距离断点表(Array<Float>)，碰撞和视觉两个 Rebuild 复用同一张表，杜绝分段不一致。
末端外推 bug 根因：均匀分段最后一段 D1=(i+1)*SegLen 超过 SplineLength，GetLocationAtDistanceAlongSpline 沿末端切线外推，外推长度=SegCount*SegLen-Length，正好随 SegLen 变化。修复=D1=Min(D+Step, SplineLength)，自适应循环天然包含此夹断。护栏：内层二分必须有 Step<=MinStep 出口；外层用带硬上限(如 500/200 段)的 For+Break 代替 while 防编辑器卡死。

### 2026-06-03 22:42 — [发现] 末端"戳出去"真因是 Box 长度仍用 Step，非旋转/非取点
确诊证据：加了 Min 仍溢出；关掉 rotation 后所有 Box 横向(世界X)排列、不再溢出；溢出时最后一个 Box 中心点仍对准 spline 端点。结论：Box 中心(Mid)算对了，错的是长度——SetBoxExtent 的 X 仍在读 Step/SegmentLength 而非 VectorLength(P1-P0)。rotation 开时多出来的长度沿 spline 切线方向探出末端=可见溢出；rotation 关时长轴指向世界X、不再沿 spline，于是溢出"被旋转藏起来"，并非修好。修复：Len=VectorLength(P1-P0)（夹断后真实端点反算），Box X extent=Len*0.5；SplineMesh 切线同理用 Dir*(D1-D0) 不用 Dir*Step。一句话：Min 夹的是取点 D1，但凡任何"长度"还吃 Step，夹断就白做。

### 2026-06-04 10:30 — [回滚] 推翻"长度吃 Step"猜测，真因是 Box 尺寸走 Transform Scale 通道
用户发来真实蓝图导出（s.txt，GenerateSplineCollision @ BP_SplineGenerator_Mesh_AirWall），用 bp_clipboard_to_ai.py + 正则逐节点核对，确认此前 AI 全部猜测落空：
- 取点 GetLocationAtDistanceAlongSpline 两处都是 CoordinateSpace=Local（用户说的对，非 World）。
- D1 = FMin((Index+1)*SegLen, SplineLength) 确实存在（用户说"早加过 Min"是对的）。
- 长度 Scale.X = VSize(P1−P0)/2，用的是真实端点差，根本没碰 Step/SegmentLength（"长度吃 Step"判断错误，作废 06-03 22:42 那条结论）。
**真因**：Box 尺寸不是用 SetBoxExtent，而是塞进 MakeTransform 的 Scale 通道：Scale=(VSize(P1−P0)/2, WallThickness, WallHeight*1.5)。但 BoxComponent 默认 BoxExtent=(32,32,32)，真实尺寸=Extent×Scale，于是 X 半长=16·Len、Z 半高=48·H，约 32 倍放大 → 严重溢出。全文 grep SetBoxExtent/SetCollisionEnabled/BoxExtent 计数=0，确认从没设过 Extent 和碰撞响应。Scale.Z 还有未解释的 ×1.5 魔数；Mid 也没抬 WallHeight/2。
**完美解释"调小 SegLen 不溢、调大溢"**：Len 小时 16·Len 才勉强接近真实段长，Len 大时暴涨。
**修复**：MakeTransform.Scale 改 (1,1,1)；AddComponent 后对返回的 Box 调 SetBoxExtent(Len/2, WallThickness/2, WallHeight/2) 绝对半尺寸；去掉 1.5 魔数；按需 Mid.Z += WallHeight/2 抬到墙中心；补 SetCollisionEnabled(QueryAndPhysics)+SetCollisionResponseToChannel。
**教训**：连续 4 次凭逻辑猜 bug 全错，根因只有拿到真实节点导出才定位到。以后遇"反复修不好"应尽早要导出文件做静态核对，别再纯推理。

### 2026-06-03 22:53 — [决策] 视觉层改用单条 SplineMesh，碰撞仍分段 Box
放弃"分段 SplineMesh 拼墙皮"，视觉改成一整条 SplineMesh（沿整条 spline 一根到底），已完美对齐、不再有分段切线过冲/末端外推问题。碰撞层保持沿 spline 分段叠 Box（仍需阻挡精度）。意味着：① 分段 UV 连续 + Custom Primitive Data per-segment 那套不再需要（单条 mesh 自带连续 UV）；② 之前所有 mesh 溢出/切线/分段一致性讨论作废；③ 后续焦点只剩碰撞层——Box 长度若仍吃 Step，末端仍会溢一点（不可见，但若在意按 VectorLength(P1-P0) 修）；④ 波纹/接触 UV 后续直接基于这条 spline 的弧长算，喂给单条 mesh 的材质。

### 2026-06-04 10:40 — [决策] 自适应步长分段：弦高(sagitta)判据 + While前进式 + 内层细化
碰撞分段从固定步长 ForLoop（Ceil(Len/SegLen)）升级为自适应：直段步子大、弯段自动收小，减少 Box 数量同时保碰撞精度。
- **判据**：sagitta = VSize(SplineMid − ChordMid)，SplineMid=GetLocAtDist((D+D1)/2,Local)，ChordMid=(P0+P1)/2。物理意义=碰撞盒与真实墙面的最大缝隙，直接当质量旋钮。
- **结构**：外层 While(D<SplineLength) 每段 D=D1 前进（ForLoop 干不了，因总段数不定）；内层 do/while 细化：试 MaxStep→算 sag→太弯则 step*=0.5 重试，直到 sag<=Tolerance 或 step<=MinStep。
- **保命栓**：外层 guard++<4096 防死循环；内层 step<=MinStep 强制收手。自适应循环判据写错极易卡死编辑器，必加。
- **参数经验值**：MaxStep 400~800cm / MinStep 20~50cm / Tolerance 5~15cm（Tolerance=允许墙漏多少cm，调它最直观）。
- **与32倍bug衔接**：EMIT 时尺寸仍走 SetBoxExtent(Len/2,WallThickness/2,WallHeight/2)+Scale=1，自适应只管疏密不管尺寸，别把 Len 又塞回 Scale 通道。
- **技能边界澄清**：ue-blueprint-clipboard-simplifier 是解析器，只能核对已导出的蓝图；自适应是"待搭设计"，s.txt 里仍是固定步长，无导出可喂。下一步用户搭完导出，再用技能逐节点核对。

### 2026-06-04 10:35 — [设计] 玩家接触波纹管线（基于单条SplineMesh）
四段：① OnComponentHit 取 Hit.ImpactPoint（要撞击点非玩家中心）；② 世界点→FindInputKeyClosestToWorldLocation→GetDistanceAlongSplineAtSplineInputKey→U=Dist/SplineLength，V=(Z−BaseZ)/WallHeight，与连续UV同源圈才落对位置；③ 写 DMI：ContactUV=(U,V)、RippleStartTime=GameTime；④ 材质 GPU 扩散：age=Time−Start，d=length((TexCoord−ContactUV)*(SplineLength,WallHeight))换cm防椭圆，ring=1−saturate(|d−age*Speed|/Width)，fade=saturate(1−age/Life)，Emissive+=ring*fade*Color。坑：UV不换cm→椭圆；竖直UV若tiling需校准V；多人撞需多组参数轮转或RT。待确认：SplineMesh竖直UV是0→1还是tiling。

### 2026-06-04 11:00 — [发现] 新版s.txt已修复32倍bug；定位自适应step的最小改造点
用户发来修复后的 GenerateSplineCollision 导出（C:/Users/violinapeng/Documents/Work/s.txt，41节点），用 ue-blueprint-clipboard-simplifier 技能解析+正则坐实运算符：
- **32倍bug已修**：N40 SetBoxExtent 存在；N24 MakeTransform.Scale=(1,1,1)；取点 N17/N18 都是 Local；D1=FMin 仍在。结构干净。
- **当前仍是固定步长**：N5 GetSplineLength → N6 Divide(/SegLen) → N8 FCeil → N10 Subtract(B=1) → N9 ForLoop(0..LastIndex)。D0=N11(Index×SegLen)，D1=N16 FMin((Index+1)×SegLen, Len)。
- **自适应最小改造（只动3处，EMIT链N17→N40零改动）**：
  ① 删 N5→N6→N8→N10→N9 整条"预算总段数+ForLoop"。
  ② 换外层 While Loop 宏：Cond = (D<GetSplineLength) AND (guard++<4096)；体末 D=D1 前进。
  ③ D0/D1 来源改：D0=D；D1=FMin(D+step, SplineLength)（FMin 留着当末端夹断保险）。
  ④ 新增内层细化：step=MaxStep→D1=Min(D+step,Len)→Smid=GetLocAtDist((D+D1)/2,Local)、Cmid=(P0+P1)/2、sag=VSize(Smid−Cmid)→分支 sag<=Tol OR step<=MinStep ? 跳出EMIT : step*=0.5 重试。
- **参数**：MaxStep 400~800 / MinStep 20~50 / Tolerance 5~15 cm（Tolerance=允许墙漏缝隙，质量旋钮）。
- **遗留小坑（用户说先不管墙体，仅标记）**：N40 SetBoxExtent 的 Y 接 WallThickness 没/2（厚2倍）；Z 是 WallHeight×50（N41 Multiply B=50，魔数）。
- **下一步**：用户搭完 While+细化导出，用技能逐节点核对 While 条件/细化分支/D0/D1 接线。

### 2026-06-04 11:50 — [发现] while 缺 D=D1 自增 → Compile 触发死循环锁死引擎的救援法
搭自适应 While 时漏了段末 D=D1 自增，条件恒真成死循环；Compile 触发 Construction Script 执行 → 引擎 100% CPU 锁死、不 crash；杀进程重开仍卡（因重启自动加载上次关卡 → 关卡里 Actor 的 CS 又跑死循环 → 没进编辑器就锁死）。
**救援核心**：让引擎开空白关卡启动，绕过含问题 Actor 的关卡。
1. 任务管理器结束所有 UnrealEditor.exe + UnrealEditor-Cmd.exe（常有残留）。
2. 改 Saved/Config/WindowsEditor(或Windows)/EditorPerProjectUserSettings.ini：在 [/Script/UnrealEd.EditorLoadingSavingSettings] 下加 LoadLevelAtStartup=None（无 section 就整段贴末尾）。
3. 启动→进空图→Actor 不存在→CS 不跑→能进编辑器。
4. 别先开出问题的关卡；CB 双击 BP，先断 Construction Script 调用 GenerateSplineCollision 的执行白线（止血），Compile+Save 确认关卡能开，再补 while（D=D1 + 外层 guard++<4096 + 内层 OR step<=MinStep）。
5. 修好 Compile+Save，改回 ini（删该行或设回 LastOpened），开关卡验证。
**兜底**（开空图仍卡=非CS或别处自动加载它）：全杀进程，把 BP .uasset 剪切（非删）到工程外，开项目报缺引用但能进，进去再放回修。
**留底**：动手前复制 Saved/Config；移 .uasset 前备份 Content。死循环不损工程数据，纯 CS 跑死代码，断线即恢复。

### 2026-06-04 14:00 — [纠正] 卡顿真源是"蓝图编辑器预览实例跑CS",非项目启动/关卡;compile死锁机制
用户澄清精确现象(推翻之前"CS在项目启动/关卡触发"的归因):
- 开项目、开关卡编辑器都**正常**;仅打开该 BP 编辑器时操作卡顿(不卡死);断 while + 断整个函数调用后,**一按 Compile 就卡死,不按还能勉强操作**。
**机制三连**:
① 卡顿源=蓝图编辑器 Viewport 内的**预览实例**(Blueprint Editor preview scene 自动 spawn 该 BP 的 actor),它跑 Construction Script → 所以关卡/项目都正常,只有打开这个 BP 才卡。
② 断线/删节点等改动在 **Compile 成功前一行都不生效**,预览实例仍跑上次编译的旧字节码 → 不 compile 维持旧状态(能勉强操作)。
③ 按 Compile → UE 编译新图 + **立刻 rerun Construction Script on 预览实例** → 若 while/函数调用没断干净就撞死循环 → 卡死。
**死锁**:改动需 compile 生效,compile 却触发 CS rerun 卡死 → "改一点 compile 一次"永远卡。
**关键教训**:"断线"常断不干净(只断一根、节点还在、执行流绕得过去);消灭死循环唯一可靠动作是**删 while 节点本身**。
**破局**:① 趁"不 compile 能勉强操作"全选 Ctrl+C 导出,用 ue-blueprint-clipboard-simplifier 解析定位 while/调用真实状态,一次改对而非 compile 试错;② 或同一次 compile 前一并完成(删 while 节点 + 断 CS→GenerateSplineCollision 执行线),再 compile 一次,新图既无死循环、CS 也不调它,rerun 不卡。

### 2026-06-04 14:05 — [发现] 删while+断CS调用后compile仍卡死 → 死循环必经"隐藏可达路径"，停止猜测改静态核对
用户照建议做了两件事：①删掉 while 节点本身（非断线）②断开 Construction Script 调用 GenerateSplineCollision 的执行线。结果一按 Compile 仍彻底卡死。
**逻辑推论（铁律）**：Compile 卡死=编译后 rerun Construction Script 时撞进无限循环。若上述两件事真做到位，新编译图里这条路应已死，rerun 不该卡。既然仍卡 → **新编译出来的图里，仍有一个"可达的"无限循环**，藏在用户没看到的路径上。这不是工程损坏（仍不 crash，纯 100% CPU 空转）。
**4 个隐藏藏身处**：① 第二个循环节点（我们设计的是双层 while=外层前进+内层细化；用户可能只删了其一，或残留旧 ForLoop/重复 while）；② CS 调用没真断（断错线 / Sequence 第二输出 / 有第二个调用节点）；③ 函数被**另一个入口**调用（BeginPlay / Tick / Timer / 勾了 Call In Editor）；④ 改的是另一个副本 / 删除在卡死前没登记生效。
**决策（停止纯推理，连续猜错5次教训）**：
- 优先路 B：用户趁"不 compile 还能勉强操作"，对**函数图 + Construction Script 图各自** Ctrl+A→Ctrl+C 导出 txt 发来，用 ue-blueprint-clipboard-simplifier 静态核对到底哪条路还可达、while 是否真没了、CS 是否真不调、有无第二入口。导出只复制不 compile，安全。
- 或路 A 二分：把 CS 图 + 函数图**整体清空**（各 Ctrl+A→Delete）后只 compile 一次。过=循环在此二者内；仍卡=在 BeginPlay/Tick/别的函数或别处。
- 兜底：函数逻辑已在 LOG/airwall_s2.json 完整记录，可在干净新 BP 里重建，或关引擎移走 .uasset 后重建。

### 2026-06-04 14:12 — [决定性发现] 删节点(未编译)即卡死 → 推翻"Compile触发"论；真凶=图变更触发预览重构 + while很可能无辜
用户：一删这个 while 节点、**还没点 Compile 就卡死**。这一条推翻此前全部"Compile rerun CS 才卡"的归因。
**新机制（更准确）**：蓝图编辑器 Viewport 有预览实例(preview actor)。**任何图结构变更（删节点也算）都会触发 OnBlueprintChanged → 预览实例立刻 Rerun Construction Script**，不需要点 Compile。删 while 的瞬间触发重构 → 撞进死循环 → 卡死。
**关键推论**：既然删掉这个 while 后重构仍卡，说明**这个 while 不是真凶**（删了它真凶还在）。真死循环在别处——第二个循环节点 / BeginPlay/Tick / 另一个函数 / 另一个入口。用户一直盯错对象。
**另一条线索（现象1）**：开项目、开关卡都正常，仅打开此 BP 编辑器卡 → 关卡里的实例不卡（或无实例/参数不同没跑死循环），只有**预览实例**用默认参数跑进死循环。
**结论：GUI 内编辑此 BP 的路彻底堵死**——任何删/改都触发重构卡死，连"清空止血"都做不到。必须工程外解决。
**唯一确定脱困路（主推）**：关引擎 → 物理移走坏 BP .uasset（先备份 Content）→ 空图启动 → 新建 BP 按 LOG/airwall_s2.json 重建（逻辑已全留档）。
**可选救原图**：复制(Ctrl+C)是**只读操作、不改图、不触发重构**，即使现状也大概率不卡。趁能勉强操作 Ctrl+A→Ctrl+C 导出 函数图/CS图/EventGraph 三张发我，用技能定位真凶第二循环，重建时直接避开。
**教训**：删一个节点≠消灭死循环；当"动哪都卡"时应果断弃 GUI 走资产层隔离+重建，别再在编辑器里和预览实例拉锯。

### 2026-06-04 14:19 — [决定性证据] 引擎 Runaway loop log 坐实真凶 + 揭穿"引擎没死"
用户贴出引擎 log（打开 BP 时刷屏）：
```
LogScript: Warning: Runaway loop detected (over 1,000,000 iterations)
  Function ...:GenerateSplineCollision:0288
Script call stack:
  Function ...:UserConstructionScript
  Function ...:GenerateSplineCollision
```
**三个决定性结论**：
1. **真凶精确定位**：死循环就在 GenerateSplineCollision 字节码偏移 0288，由 UserConstructionScript（即 Construction Script）调用。**call stack 只有这一条链 → 排除 BeginPlay/Tick/第二函数/第二入口**（之前担心的 4 个藏身处全部排除）。偏移 0288 = 用户把 ForLoop 改成 While 后漏了 D=D1 自增的那个 while 恒真条件。
2. **引擎根本没"死"！** UE 有 Runaway Loop Protection：循环跑满默认 `MaximumLoopIterationCount=1,000,000` 次会**自动中断本次执行并报此 warning**，不是永久锁死。用户感受的"卡死"实为"每次图变更/重构 → CS rerun → 空跑 100 万次（耗时数秒~数十秒）→ 被掐断 → 界面恢复"。
3. **完美解释所有矛盾现象**："删 while 还卡""断 CS 还卡""一删没编译就卡"——全是因为**每次操作触发一次重构（跑满100万次），用户在 runaway 掐断、界面恢复之前就手动杀进程**，导致修改从未真正 Compile/Save 生效，下次打开仍是旧图。不是工程坏、不是操作笨，是**没等够**。
**脱困（两条，均利用"引擎会自己缓过来"）**：
- 路1（最稳，主推，逻辑已全留档于 LOG/airwall_s2.json）：关引擎→备份Content→移走 .uasset→空图启动→干净新BP重建（D=D1先连好+guard<4096+内层 OR step<=MinStep）。一次脱困不再拉锯。
- 路2（GUI治本，利用等待）：进图→Construction Script 删掉调用 GenerateSplineCollision 的节点→Compile→**双手离开键鼠，死等最多2分钟让 runaway 掐断、界面恢复，期间绝不杀进程**→Ctrl+S。只有CS一个入口，断它即根治。恢复后再从容修函数内 while。
**铁律教训**：UE 蓝图死循环≠真死机，有100万次保护伞；遇"操作后冻结"应先等 runaway 掐断（盯着等1-2分钟）再判断成败，切勿急着杀进程——杀进程=修改作废=陷入"改→卡→杀→白改"的死锁。

### 2026-06-04 14:30 — [关键澄清] 删CS调用后Compile仍有「最后一次」卡顿，必须等保护伞掐断再Ctrl+S
用户问：log是打开蓝图等几分钟后才出来的，删掉调用函数的节点后按compile还能信这个保护伞机制吗？
**答：能信**。log「等几分钟自己冒出来、界面随后能动」=Runaway Loop Protection 跑满100万次掐断本次执行的标准表现，已救过一次，删调用后照样生效。
**但有时序陷阱（前几轮失败真因）**：删调用节点本身触发一次重构（可能卡）；按Compile后UE立刻用新图rerun一次CS，旧预览实例可能再撞一次while→**还会冻结几秒~几十秒「最后一次」**。这一次必须挺住，等保护伞掐断、界面恢复，**立刻Ctrl+S**。保存成功后CS不再调该函数→任何重构都进不到死循环→根治。
**前几轮「删了还卡」根因坐实**：每次冻结时用户在保护伞掐断前就杀进程→删除/修改从未Compile+Save落地→下次打开仍旧图→原地打转。不是删错，是没等够+没保存。
**操作四步**：①CS删调用GenerateSplineCollision节点 ②Compile ③双手离键鼠死等≤2min，打死别开任务管理器 ④界面恢复立刻Ctrl+S。判断信号：盯着等若又刷一条新Runaway warning=刚掐断、界面将恢复，别杀，等弹回马上存。

### 2026-06-04 14:32 — [澄清] 蓝图 Ctrl+S 会隐式自动 Compile → 可合并操作减少一次重构窗口
用户问：改完不点 Compile 直接 Ctrl+S 会怎样、会自动编译吗？
**答：会**。蓝图被修改后处于「dirty/需重编译」状态，保存 .uasset 前 UE 必须先把图编译成最新字节码才能写盘，所以「直接保存」≈「先 Compile 再 Save」，**同样触发预览实例 rerun Construction Script → 同样会撞那「最后一次」死循环卡顿，躲不过**。
**但可借此简化操作（优于之前「②Compile ③死等 ④Ctrl+S」四步）**：删掉 CS 调用 GenerateSplineCollision 的节点后，**直接 Ctrl+S**（编译+保存一次完成）→ 死等保护伞掐断（≤2min，绝不杀进程）→ 保存落地即根治。比「先 Compile 等一窗、再 Ctrl+S 又可能等一窗」少一个重构窗口，更干净。
**铁律不变**：那「最后一次」卡顿必经，靠 Runaway Loop Protection（100万次掐断）自动恢复，恢复前打死别杀进程，否则修改不落地、原地打转。

### 2026-06-04 14:34 — [决定性翻转] CPU5%+内存10G持续涨 → 循环体在狂建组件，死等作废，立即杀进程走资产层
用户：等了5分钟仍卡，CPU占5%、内存占10G。
**关键解读（推翻"死等就能自愈"）**：
1. CPU 5% = 多核机上**单核满载**的体现（如20核机单核100%=5%总占比），符合蓝图单线程死循环，不矛盾。
2. **内存涨到10G且持续** = 死循环体里在反复执行 AddComponent(Box)（GenerateSplineCollision 本就是每段 spawn 一个 BoxComponent）。这不是纯空转，是**每次迭代都 new 一个组件并注册**。
3. **为什么5分钟还没被 Runaway Protection 掐断**：每次迭代要分配内存+注册组件（相对重），迭代速度被内存分配拖慢，迟迟到不了 100万次阈值；且内存仍在涨 → **有 OOM 拖垮系统的风险**。
**结论翻转**：之前"双手离开、死等保护伞掐断"的前提是纯空转无副作用。现在循环有内存副作用且持续增长，**死等可能等到 OOM**。立即止损 > 等待自愈。
**当前唯一正确动作**：① 立即任务管理器杀光 UnrealEditor.exe / UnrealEditor-Cmd.exe / CrashReportClient.exe；② 关引擎状态下备份 Content → 物理移走 BP_SplineGenerator_Mesh_AirWall.uasset 到工程外；③ 空图启动（报缺引用但能进）；④ 干净新 BP 按 LOG/airwall_s2.json 重建（D=D1先连+guard<4096+内层 OR step<=MinStep）。GUI 内一切自救路（删节点/断线/死等）全部作废，因为动作本身触发重构、且循环在涨内存。
**铁律修正**：UE 蓝图死循环若循环体含 Spawn/AddComponent 等分配操作，会内存暴涨，Runaway Protection 因迭代变慢而迟迟不触发——此时"死等"不再安全，应立即杀进程走资产层隔离。判据：看内存是否持续上涨，涨=有副作用=别等。

### 2026-06-04 14:46 — [补充] 连"关闭蓝图"都卡 = 主线程被死循环占满，UI指令排不上队
用户：蓝图复制后想关掉都会卡。
**机制**：蓝图死循环跑在**游戏主线程(Game Thread)**上。while 恒真 + 每圈 AddComponent → 主线程 100% 占死且内存涨。编辑器 UI 消息泵也在主线程 → 任何 UI 操作（点关闭/点空白/拖窗口）的消息**排在死循环后面执行不到** → 表现为"关也卡"。不是"关闭触发了死循环"，是主线程压根没空响应关闭。
**结论再确认**：GUI 内已无任何可走路径（删/改/关/存全要主线程，全被占）。唯一出路=任务管理器**杀进程**（绕过主线程），再走资产层移走 .uasset 重建。Ctrl+C 之所以有时"还能动"是趁主线程偶尔喘口气，但不可靠，别赌。

### 2026-06-04 15:05 — [决策] 自适应step重建版完整接线 + 搭建顺序(执行线最后接防rerun卡死)
死循环锁死引擎后走资产层移走坏BP重建。给出可照连的完整五阶段接线，关键是**搭建顺序**：先摆节点+连数据线+连D=D1，最后才把执行线接进外层While输入pin（在那之前While无执行入口，预览实例rerun进不去，怎么摆都不卡，规避之前"删/改即触发重构卡死"）。
- 阶段0 初始化：ForEach CollsionBoxes→Destroy→Clear；Len=GetSplineLength；新建局部变量 D=0.0、guard=0（必须是函数局部变量非只读输出）。
- 阶段1 外层While：Cond=(D<Len) AND (guard<4096)；LoopBody首节点 Set guard=guard+1（老实Set不用++）。
- 阶段2 内层While(Cond=True靠Branch Break)：step=MaxStep重置→D1=FMin(D+step,Len)→P0/P1/Smid=GetLocAtDist(Local)→Cmid=(P0+P1)/2→sag=VSize(Smid−Cmid)→Branch sag<=Tol OR step<=MinStep ? True不接回(走Completed进EMIT) : step*=0.5接回LoopBody内圈。
- 阶段3 EMIT(沿用旧链一字不改)：Mid=(P0+P1)/2(需覆盖身高则Mid.Z+=WallHeight/2)→Rot=FindLookAtRotation(Mid,P1)→Len_seg=VSize(P1−P0)→MakeTransform(Mid,Rot,Scale=1)→AddBox→SetBoxExtent(Len_seg/2,WallThickness/2,WallHeight/2)→CollsionBoxes.Add。Scale必须1，尺寸只走SetBoxExtent(32倍bug正解)。
- 阶段4 前进 ★Set D=D1★：EMIT后回外层前唯一改D处，上次锁死就是漏这句→D恒0→D<Len恒真死循环。
- 参数：MaxStep 400~800 / MinStep 20~50 / Tolerance 5~15 cm。
- 下一步：用户搭完Ctrl+A→Ctrl+C导出，用ue-blueprint-clipboard-simplifier逐节点核对D=D1/guard/内层Break接线。

### 2026-06-04 15:25 — [回滚] 内层While「Cond=True靠Branch Break」写法错误，改为「Condition真正会变」
用户看不懂之前「内层 Condition 恒 True、靠 Branch 跳出」的说法——因为它自相矛盾：While Loop 宏只看 Condition，恒 True 就永远不走 Completed = 死循环（正是昨天锁死引擎那种）。作废 06-04 15:05 阶段2 里「Cond=True靠Branch Break、False接回LoopBody」的接法。
**While Loop 宏真实模型**：每圈先重算 Condition→真则跑 LoopBody 并由宏**自动回连**重判（这根回连线宏内部自带，用户不接）→假才走 Completed。所以「跳出」唯一机制=让 Condition 自己变 false，没有 Branch break 这回事。
**正确内层接法（Condition 真正会变）**：
- 外层 LoopBody 进来：guard+=1 → Set step=MaxStep → **先用 MaxStep 算一次** D1=FMin(D+step,Len)、P0/P1/Smid/Cmid、sag=VSize(Smid−Cmid)（备好首次 sag，解决「进环前 Condition 没值」的鸡生蛋）。
- 内层 While Condition = **(sag > Tolerance) AND (step > MinStep)**（=「还太弯 且 还能再砍」才继续细化）。
- 内层 LoopBody：Set step=step*0.5 → 用新 step **重算** D1/P0/P1/Smid/Cmid/sag → 宏自动回连重判 Condition。
- 退出条件天然成立：sag 达标(<=Tol) 或 step 见底(<=MinStep) 任一为真 → Condition 变 false → 走 Completed → 进 EMIT。此时 D1/P0/P1 已是最终值。
**重复代码优化（可选）**：进环前与 LoopBody 里「算 D1+sag」是同一段，可封装纯函数 EvalSeg(D,step)→(D1,sag) 调两次，新手嫌烦就直接复制两份照连。
**关键认知**：内层无显式 break，靠 Condition=(sag>Tol)AND(step>MinStep) 自然变 false 退出；step 每圈砍半保证有限步必触底 MinStep，绝不死循环。

### 2026-06-04 15:32 — [决策] 波纹特效改用世界空间定位，与贴图UV解耦（修正旧"连续UV"设计）
开始做玩家碰撞波纹。上一轮(06-04 10:35)设计是"波纹圆心用同源连续UV"，但用户要把竖直UV改tiling → 与波纹定位冲突(tiling后圈会复制+错位)。**改为解耦**：
- **贴图采样路**：用 TexCoord*(UTile,VTile)，想tiling随便tiling，与波纹无关。
- **波纹定位路**：用世界空间——材质里 d=Distance(AbsoluteWorldPosition, ContactWS)，真实cm距离，天然正圆，不碰UV，tiling改了也不受影响。一刀解决"换tiling"纠结。
- **四段数据流**：①OnComponentHit→Break Hit Result→ImpactPoint(世界坐标撞击点，非玩家中心)；②DMI.SetVectorParam("ContactWS",ImpactPoint)+SetScalar("RippleStartTime",GameTime)；③贴图采样独立tiling；④材质GPU：age=Time−Start，d=Distance(AbsWorldPos,ContactWS)，ring=1−saturate(abs(d−age*Speed)/Width)，fade=saturate(1−age/Life)，Emissive=Base+ring*fade*Color。
- **参数经验值**：RippleSpeed 300cm/s、RippleWidth 25cm、RippleLife 1.5s。
- **DMI**：BeginPlay对SplineMesh组件CreateDynamicMaterialInstance存变量；Hit来自Box但改SplineMesh的DMI(同Actor，ImpactPoint世界坐标无换算)。
- **三坑**：①ring漏abs→变实心圆盘(abs是环带灵魂)；②没乘fade或Start没更新→圈永不灭；③Distance是3D两面都亮，只要正面用TwoSided或法线点乘。
- **TA推进纪律**：先固定ContactWS+Start=0把材质调出正圆扩散圈，再接Hit蓝图。ShadingModel Default Lit开自发光或Unlit。

### 2026-06-04 15:40 — [决策] 动态Box统一绑Hit + 澄清primitive data代替不了mid/传不到波纹 + 单机单面简化
用户问：生成的一堆Box怎么绑碰撞事件；原蓝图自带传primitive data能否代替mid；明确单机、单面、只挡正面、不考虑多人/墙后。
**① 动态Box绑Hit**：建一个自定义事件 OnWallHit（签名同OnComponentHit委托）。在EMIT链末尾(AddComponent后)加 Bind Event to OnComponentHit：Target=刚生成的Box、Event=OnWallHit。在生成循环里每个Box都绑一次→全部指向同一个OnWallHit→运行时撞任意段都触发同一逻辑，只写一份。
  - 两个触发前提（默认关，常栽）：① Box勾 Simulation Generates Hit Events 或生成后 SetNotifyRigidBodyCollision(true)；② Collision对Pawn必须Block（非Overlap）OnComponentHit才来。要穿过去触发则改 OnComponentBeginOverlap+Overlap，另一套。空气墙挡人=Hit+Block。
**② primitive data 不能代替 mid（关键认知）**：mid=Box的Transform位置(摆盒子几何)，primitive data=逐primitive的材质数据通道(喂shader按index读float/vector)，两者维度不同不可替代。且**波纹接触点也传不过去**：primitive data逐primitive，写到Box上只有Box自己材质能读；波纹画在SplineMesh(另一个primitive)读不到；何况Box是不可见碰撞盒无材质，喂了等于喂空气。波纹接触点只能走DMI：ImpactPoint→SetVectorParameterValue写进SplineMesh的DMI。原蓝图那套primitive data是分段Box可见mesh时代喂连续UV偏移用的，现已换单条SplineMesh→该primitive data已无用可删，与波纹不搭界。
**③ 单机单面简化**：不考虑多人→波纹单组参数(一个ContactWS+一个RippleStartTime)即可，不用4~8组轮转/RT，撞一下覆盖上一下可接受。不考虑墙后→材质TwoSided关或不管背面，世界距离Distance算正面正常即可，不用法线点乘屏蔽背面。单面→UV/波纹只按正面一层，不管两面镜像/接缝。
**蓝图改动清单**：①EMIT末尾加Bind Event to OnComponentHit(Target=Box,Event=OnWallHit)；②生成后SetNotifyRigidBodyCollision(true)+确认对Pawn Block；③OnWallHit里Break Hit→ImpactPoint→DMI.SetVector("ContactWS")+SetScalar("RippleStartTime",GameTime)；④删原primitive data节点(单SplineMesh时代无用)。

### 2026-06-04 15:55 — [核对] 用户Bind Event导出核对通过；澄清单一OnWallHit事件共享
用户发来 K2Node_AddDelegate + K2Node_CreateDelegate 导出，问"只能create一个event、会在Event Graph弹一个"是否正确。
**核对结论：接得全对**。
- K2Node_AddDelegate = 蓝图"Bind Event to On Component Hit"：DelegateReference=PrimitiveComponent::OnComponentHit；execute←AddComponent输出；then→下一CallFunction；self(Target)←AddComponent返回的Box组件；Delegate(Event)←CreateDelegate。五pin全对。
- K2Node_CreateDelegate：SelectedFunctionName="OnWallHit"，输出接AddDelegate的Delegate引脚=已创建OnWallHit并喂给Bind。
**澄清"只能create一个event"困惑**：CreateDelegate只是创建一个"引用"指向Event Graph里唯一的OnWallHit事件本体（弹出来那个红事件节点）。事件本体只有一个、待在Event Graph。循环转N次绑N个Box但全指向同一OnWallHit→运行时撞任意段进同一事件，只写一份逻辑。不需要也不应每个Box建一个事件，一个通吃=动态绑定精髓。
**还差两步(导出里没看到，否则不触发)**：①SetNotifyRigidBodyCollision(true)即勾Simulation Generates Hit Events(默认关)；②Box对Pawn必须Block(非Overlap)。
**验证**：OnWallHit里接Break Hit Result→ImpactPoint→Print String，进游戏撞一下打印出坐标=Bind链通，再接DMI/材质。

### 2026-06-04 16:02 — [发现] OnComponentHit 每帧狂触发，波纹必须节流
玩家贴墙/沿墙走，CharacterMovement 每帧扫掠顶墙面→物理引擎每帧(甚至 sub-step)重新生成 blocking contact→Hit 事件狂刷，这是物理引擎真实行为非 bug。对波纹致命：若每次 Hit 都 SetScalar(RippleStartTime=Now)→起始时间每帧被重置→波纹永远卡第0帧成死圈，看不到扩散。
**节流方案**：加 LastRippleTime(float)+RippleDuration(float,如1.5s)。OnWallHit 里 Branch:(GetGameTimeInSeconds - LastRippleTime)>RippleDuration → True 才 Set LastRippleTime=Now + SetVector(ContactWS=ImpactPoint) + SetScalar(RippleStartTime=Now)；False 直接吃掉。一次撞击=一个完整波纹扩散完。Print String 验证完即删。多波纹同时扩散才需数组/多通道，单面单机 YAGNI 不做。

### 2026-06-04 16:22 — [发现] 蓝图 GameTime 与材质 Time 同源，但 float 长跑精度退化
蓝图 GetGameTimeInSeconds 与材质 Time 节点默认都取 World TimeSeconds(同源、同尺度、都受 time dilation、暂停不走)，所以(材质Time − RippleStart)合法。坑不在"溢出"(float 上限 3.4e38，到那要 1e30 年级别)，而在精度退化：float 仅约 7 位有效数字，time 到几万秒后小数增量开始抖(1e5 秒时最小增量约 0.008s)，长跑会出现时间动画抖动/闪烁(UE 论坛常见报告)。对波纹真正受影响的是两个大数相减(catastrophic cancellation)。
**规避(YAGNI 分级)**：单局几小时内精度够用，先不管。真要长期挂机才需绕开材质内部 Time——改由蓝图侧跑 1.5s Timeline 每帧 SetScalar(RippleProgress 0→1)喂材质，材质用 progress 直接算半径/fade，彻底不碰材质 Time。单面单机可接受每帧 tick。

### 2026-06-04 16:45 — [纠正] DMI 该留在 CS，运行时操作 MID 成员变量而非 mesh 本体
解析 GenerateSplineCollision 函数(s.txt,48节点)：SplineMesh 是 AddComponent 动态生成的 local(N9→N21 SET SPM→N15 SET GeneratedMesh)，运行时确实找不到 mesh 引用。但函数内 N5 GET MID→N4 SetMaterial(self=GeneratedMesh, Material=MID)，MID 是【成员变量】(只 GET 不 SET，CS 里调函数前 CreateDMI 建好)。
**关键洞察**：波纹要改的是材质实例 MID，不是 mesh 本体。MID 是成员变量、已贴在 mesh 上，运行时 OnWallHit 直接 GET MID→SetVector/SetScalarParameterValue 即可，完全不碰 mesh。**推翻上一轮"DMI 挪 BeginPlay"建议**——mesh 在 CS 动态生成，BeginPlay 摸不到，CS 里 CreateDMI 才正确，保留。
隐患：若 spline 分多段→多条 SplineMesh，CS 若每段各自 CreateDMI 并覆盖 MID 成员变量→只有最后一段响应。单条 mesh 共享一个 MID 则无碍(改一次全亮)。函数另含 N2 SetDefaultCustomPrimitiveDataVector2+N3 MakeVector2D 传 tiling 用的 Vector2D(NoTiling 分支)，与波纹无关。

### 2026-06-04 17:00 — [决策] 波纹美化：软边+HDR+径向衰减，本轮加边缘噪声涟漪
波纹从纯白硬圈优化：① smoothstep 软边(1-smoothstep(0,Width,abs(dist-radius)))+可选 Power(2~3)成光带；② HDR 带色相 Color×Intensity(5~20)+后期 Bloom 才发光；③ radialFade=1-saturate(dist/MaxRadius)加耗散层次。
本轮重点【边缘扰动涟漪】：distOffset=(Noise(AbsWorldPos×NoiseScale + Time×FlowSpeed)-0.5)×Wobble；dist'=dist+distOffset 替原 dist 进 ring。起手 NoiseScale=0.02/Wobble=20/FlowSpeed=0.5。
**两坑**：①UE Noise 节点默认 3D World Noise 巨贵→Function 选 Gradient/Simplex+低 Quality+Levels1~2，或直接换噪声贴图采样(更省，推荐定稿后换)。②+Time 平移整个噪声场→边缘"飘"非"抖"，要原地颤动则 FlowSpeed<0.2+大 Wobble。进阶：Wobble_dynamic=Wobble×saturate(radius/300)让波纹初生利落、扩散后才涟漪化。

### 2026-06-04 17:30 — [产出] 自适应step汇报总结文档
应用户要求产出可汇报材料：work/AirWall/自适应Step分段_汇报总结.md。六节结构：问题(固定步长直段浪费/弯段穿漏/末端外推)→核心思路(弦高sagitta=曲线中点到弦中点距离当唯一画质旋钮)→算法(外层While前进D=D1+guard、内层While砍半细化Cond=(sag>Tol)AND(step>MinStep)、EMIT)→效果对比表→参数(MaxStep400-800/MinStep20-50/Tol5-15)→三个坑(漏D=D1死循环/32倍Scale/搭建顺序)。配流程图widget。

### 2026-06-05 11:05 — [决策] 自适应分段升级：MaxStep 从写死常量改为"控制点段长"
用户洞察：固定 MaxStep 在长直段会强制切成 长度/MaxStep 个 Box(浪费)，且遇到两控制点拉很长的直线会生成大量不必要密集 Box。
**新结构(两层变三层)**：①外层 For Loop 0→GetNumberOfSplinePoints−2 遍历相邻控制点对，D_start/D_end=GetDistanceAlongSplineAtSplinePoint(i/i+1)；②中层 While(D<D_end)段内前进 D=D1；③内层 While 二分，step 初值=(D_end−D)即剩余整段长当 maxstep，体内 step*=0.5。直段第一刀弦高即达标→一个 Box 带过，二分不进。
**收益**：弯段精度不变，直段 Box 数大减；Box 边界天然落控制点(曲率突变处)，朝向更服帖，顺带缓解 FindLookAtRotation 高低差接缝隐患。
**必留兜底**：step 初值=min(D_end−D, MaxStepSafety)，MaxStepSafety 给很大值(如 2000)。因单点中点采样在 S 形/超长段会低估弦高(旧固定 MaxStep 无意中当了安全网)，两控制点拉几千 cm 又绕形时第一刀采样会看走眼漏切，兜底强制先切一刀逼出第二次采样。
新节点：GetNumberOfSplinePoints + GetDistanceAlongSplineAtSplinePoint(i)。闭合 spline 上限取 N−1 并对末段特殊处理。

### 2026-06-05 11:15 — [产出] 自适应分段 v2 方案文档（控制点段长）
应用户要求把"按控制点段长当 MaxStep"优化思路落成正式方案：work/AirWall/自适应Step分段_v2_控制点段长.md。八节：v1 残留浪费(长直段被固定MaxStep强切)→核心思路(控制点段长当MaxStep)→三层结构(①For遍历控制点对0→N-2 取D_start/D_end ②While段内前进D=D1+guard ③While二分step初值=min(D_end−D,MaxStepSafety))→兜底MaxStepSafety=2000(防S形长段中点采样漏切，v1固定MaxStep原是无意安全网)→v1/v2效果对比→白赚好处(边界落控制点缓解FindLookAtRotation接缝)→新节点(GetNumberOfSplinePoints/GetDistanceAlongSplineAtSplinePoint)→参数(MaxStepSafety替代MaxStep,MinStep/Tolerance不变)。配三层结构流程图widget。

### 2026-06-05 11:40 — [决策] 短 S 形漏切根治：中点采样升级为三点取最大
用户追问：MaxStepSafety 防不住【短】S 形(段长<Safety 时 min 永远取段长，兜底形同虚设)，中点恰穿弦 sag≈0 误判直段漏切。
**根治方案(解法一，采纳)**：内层算 sag 从"采中点一个"改为"采 t=0.25/0.5/0.75 三点取最大"：Si=GetLocationAtDistanceAlongSpline(D+(D1−D)×t)，Ci=P0+(P1−P0)×t，sag=max(VSize(S¼−C¼),VSize(S½−C½),VSize(S¾−C¾))。原理：S形"先鼓后凹"，峰落1/4谷落3/4，中点恰在拐回弦处≈0，1/4+3/4天然抓住两极值。从此与段长无关，短/长S形一起根治，MaxStepSafety 可保留可删(三点后基本失效)，不牺牲直段优化(三点都≈0仍一Box带过)，性能无感(构建期一次)。
**否决解法二**：step初值×0.5 无条件先砍半→直段Box翻倍吃掉v2收益。**记录解法三备查**：用GetTangentAtDistanceAlongSpline比较两端切线摆动判S形，最严谨但要算角度定阈值，单面墙YAGNI不做。

### 2026-06-05 11:45 — [发现] sag 采样是近似范式，优雅正解是递归二分细分
用户直觉：sag 中点采样不优雅，导致不断为特殊情况打补丁(MaxStepSafety/三点取最大)。确认：补丁填的全是同一个洞【采样盲区】——采有限点必有反例(采1点→S形躲中点；采3点→更高频波躲1/4 1/2 3/4；采N点→N+1拐)，是采样近似范式的原罪，盲区只能缩小消不掉。
**优雅正解=递归二分细分(recursive subdivision/curve flattening)**：细分(seg){ if 够直 → 生成Box; else 从中点劈两半，递归左、递归右 }。不判断哪里弯，弯就劈半，S形/任意形都被无脑劈到简单，采样误判前提(段里藏没抽到的弯)被结构消灭，无特殊情况无补丁。
**杀手锏判据**：cubic Bézier 偏离弦的最大距离有闭式【上界】=两控制柄B1/B2到弦垂距取max(B1=P0+T0/3,B2=P1−T1/3)。是真上界非采样估计，<Tol 即数学保证整段无穷点都达标，反例无法构造。
**工程判断：现在不重写**。①蓝图不支持自调用递归，要用数组模拟显式栈，比当前循环更难写难调(刚出死循环地狱)；②控制点段长+三点取最大漏切概率已近零，美术正常摆墙触发不了；③YAGNI。结论：采样+补丁=工程合理近似(蓝图单面墙留着别动)；递归细分+控制点上界=理论正解(若将来要C++通用高精度曲线工具才上)。知道有更优雅解≠现在就该换，看ROI。

### 2026-06-05 14:20 — [纠正] "采N点给N+1拐"只对跨控制点固定步长成立，按控制点分段后单段至多一个S
用户质疑：两点之间不可能高频S，最多一个S。确认用户对，纠正我之前的对角线吓唬话适用边界。
**单段三次曲线拐数硬上界**：单轴 f''(t)=6at+2b 是一次式→至多1解→每轴至多1拐点；平面/3D合成理论极限至多2拐点(=至多一个S)。高频波需更高次多项式，单段三次画不出。
**我之前错在哪**："采N个点→给N+1拐反例"偷换前提，只在【跨控制点固定步长】(一刀横跨多控制点、拼接多条三次→可藏任意多弯)成立。按控制点分段后每段钳死成单条三次→前提被掐断→该吓唬话不成立。
**对采样判据的含义(好消息)**：按控制点分段后"短S形"是唯一要防的形状，无更刁钻高频反例。三点取最大(¼½¾)对"一个S"足够(峰≈¼谷≈¾各抓一极值)，无需七点九点。反例空间从"连续无穷"塌缩成"有限种且三点够覆盖"。之前"采样范式原罪永远填不完"的论述是描述旧的跨控制点固定步长世界，对v2控制点分段过度悲观。

### 2026-06-05 14:25 — [决策] 开工：v1 固定 MaxStep 改造为 v2 控制点段长（三层结构）
讨论收口，开始施工。改造原则：①只新增最外层 For(遍历控制点对) ②只改内层二分 step 初值=min(D_end−D, MaxStepSafety) ③v1 的内层二分/EMIT/D=D1 前进全部照搬不动。施工纪律重申(上次漏 D=D1 锁死引擎教训)：先把 guard 保命栓和 D=D1 接好再 compile，外层 For + 中层 While + 内层 While 三层 guard 各自独立。进每个新控制点段时 Set D=D_start 防误差累积(虽段连续 D 理论自然续上)。EMIT 的 Len_seg/Rot/Mid 维持 v1 接法。

### 2026-06-05 14:30 — [发现] 核对 s.txt(87节点)：当前仍是 v1 固定 MaxStep，改造未开始但 v1 结构健康
用户导出 s.txt 让先确认。解析(out/airwall_v2.json,87节点)结论：**还没改成 v2 控制点段长**，没有 GetNumberOfSplinePoints/GetDistanceAlongSplineAtSplinePoint，外层 While 条件 N37=(N44:D<SplineLength)AND(N39:guard<N)，内层 step 初值 N45<-N46(MaxStep) 仍是写死常量。
**v1 结构本身健康(关键命门都在)**：①外层前进 N87 SET D<-N88(D1)✅(上次锁死就是漏这个，这次接上了)②D1链 N6=N53(N52:D + N54:step)+N50:SplineLength？——注意 N6.B 接了 SplineLength 存疑，但 N6 输出→N51 D1，且 N8.Distance<-N51，逻辑上 D1=D+step 才对，SplineLength 进 D1 计算可疑(可能 clamp Min(D+step,Len)，需用户确认)③内层 While 条件 N75=(N67:Tol<VSize sag)AND(N69:MinStep<step)✅会变④step砍半 N72<-N74(N73:step × ?)✅⑤guard 自增 N40<-N42(N41:guard+?)、guardd N84/N81 双重置✅。EMIT 链 N18 AddComp→N85 AddDelegate→N27 SetBoxExtent→N25 AddArray→N87 SET D 完整闭合。
**待澄清**：N6.B=SplineLength 进 D1 是否 clamp；若要 v2 仍需新增 For 层。下一步等用户决定是继续按 v2 改还是先验证 v1。

### 2026-06-05 14:40 — [决策] v2 正式开工：用户确认 N6 是 Min、v1 已跑通，给出节点级施工清单
用户确认 N6=Min(D+step, SplineLength) 是末端 clamp(非 bug)，v1 早已正常运行，决定在 v1 基础上直接上 v2 控制点段长优化。
**精确到四处改动(对照 s.txt 真实节点 ID)**：
①新增最外层 For：GetNumberOfSplinePoints→N，For(0→N−2)，体内 D_start=GetDistanceAlongSplineAtSplinePoint(i)/D_end=(i+1)，Set D=D_start 再进现有 While，Completed 接原收尾。
②N44 条件右值：D<SplineLength 改 D<D_end(比较节点 B 引脚改接 D_end)。N37=N44 AND guard<4096 不动。
③N45 step 初值(灵魂)：删 MaxStep 连线，改 Min(D_end−D, MaxStepSafety=2000)，新增 Subtract+Min。
④★N6 clamp 右值：Min(D+step, SplineLength) 改 Min(D+step, D_end)。理论上因 step 初值=min(D_end−D,Safety)→D+step 永≤D_end，留 SplineLength 不会错(D_end≤Len clamp 不触发)，但改 D_end 语义干净双保险，强烈建议改。
**接线纪律(防锁死)**：先接 For 骨架+Completed 接 Print 验证跑完 N−1 次→再嵌 While→改 ②③④ 三个右值→最后 Completed 改接真收尾。三层退出：For 有界 N−2 / 中层 D<D_end+guard<4096 / 内层 MinStep<step 触底。
等用户改完导出，用技能核对 N44/N45/N6 右值与 For 的 i+1 路。

### 2026-06-05 15:20 — [发现] 闭合 spline 只污染最外层控制点遍历，中层/内层免疫，分两级解耦
用户洞察：v2 方案默认开放 spline，没单列闭合情况，应分两级讨论。确认正确。
**分两级本质**：①分段策略(最外层 For 决定切几段+每段里程边界[D_start,D_end])受闭合影响；②段内细化(中层 While 前进 D=D1 + 内层 While 二分采样算 sag)完全免疫——它俩只跟里程数字打交道，不知道也不关心曲线首尾是否相连。这是分三层的额外红利：形状拓扑被挡在最外层，里面两级永远干净。
**开放 vs 闭合(仅最外层)**：开放 N点→N−1段，For i:0→N−2，每段(P[i],P[i+1])，当前代码就对不用动。闭合 N点→N段(多一条回环段 P[N−1]→P[0])，For i:0→N−1(上限+1)，每段终点 P[(i+1)%N](i+1 对 N 取模防越界)。
**★UE 闭合真坑(不是上限是里程)**：回环段 D_end 不能写 GetDistanceAlongSplineAtSplinePoint(0)→返回0→D_end=0<D_start→中层 While 第一次判断即 false→整条回环段被跳过→环缺最后一段碰撞。正确：回环段 D_end=GetSplineLength()(闭合后总长已含回环段)。
**工程判断(YAGNI 现在不动)**：单面开放墙 IsClosedLoop()永远false，当前代码完全正确一行不改。真做环形墙：最外层 For 前读 Get Is Closed Loop，上限=isClosed?N−1:N−2，每段 D_end=(i==N−1 && isClosed)?GetSplineLength():GetDistanceAlongSplineAtSplinePoint(i+1)。中层内层零改动——闭合的活全在最外层一个分支。

### 2026-06-05 15:35 — [发现] v2 跑通但直段仍多格子：Box 下限被控制点段数钉死
用户反馈 v2 跑通但"已经很直的地方还是好多格子"。真因：**v2 每个控制点段至少 EMIT 一个 Box**——最外层 For 遍历控制点对，每对必进一次中层 While(D=D_start 起 D<D_end 首次必真)→至少一个 Box。所以 Box 数下限=控制点段数，跟直不直无关。v2 只解决"单个长直段被固定 MaxStep 强切"，管不了"直墙上控制点本身就密"，反而因每个控制点强制断开把直段 Box 下限钉死在控制点段数上。弦高判据只能在一段之内省，跨不过控制点边界。
**自查**：进游戏数 Box 数 vs 控制点段数(点数−1)。≈ 段数→证实此因；远多于→Tolerance/MinStep 过小过度细化(另查)。
**三解法(按 ROI)**：①跨段贪心合并(推荐治本)：外层从当前控制点贪心往后吞并控制点，整段弦高≤Tol 就继续吞，超了才断，单段就超退回段内二分。直墙多控制点一口气吞成 1 Box。代价：跨段采样打破"单段至多一个 S"保证→必须用回三点取最大(¼½¾)防漏切，这次补丁是必要的。②生成后后处理合并(最省心不碰主循环)：EMIT 完所有 Box 后加 pass，相邻 Box 朝向夹角<2°且共线就合并成长 Box。主循环零改动风险最低，精准命中直段冗余。③接受现状(YAGNI)：碰撞 Box 数量对性能影响极小(broadphase 剔除)，若只是看着多不掉帧就别动。
**待用户答**：①典型墙 Box 数 vs 控制点数 ②真掉帧还是单纯看着难受。实际性能问题→推解法二(不碰刚跑通的主循环)；只是看着难受→解法三别动。

### 2026-06-05 15:42 — [发现] 项目收口看板：碰撞+波纹跑通，性能审计仍空白
两大系统(碰撞分段v2 / 波纹特效)均跑通可交付。盘点交付前待补(按ROI)：
①★性能审计(TA本职目前空白,最该补最快30min)：波纹是半透明+Noise+每像素Distance三重GPU杀手却从没量过。两工具：视口ViewMode→Optimization→Shader Complexity(绿/黄安全,红需砍,大概率Noise节点)+Quad Overdraw(半透明叠层)。这步决定③要不要做。
②半透明排序/深度(刚开refraction撞上)：Translucent默认不写深度,多面墙叠加/墙后有透明物时排序穿帮(波纹忽前忽后)。查Translucency Sort Priority或Render After DOF。单面墙暂不显。
③Noise节点定稿换噪声贴图(之前埋的伏笔)：默认3D World Noise巨贵,涟漪手感定了换Texture采样便宜一个数量级。是①红区最可能元凶,与①一起做。
④多波纹/沿墙走(体验向YAGNI)：节流只放一个波纹,快速连撞第二下无反馈。要多波纹需参数数组/多通道,单面单机不做除非觉得出戏。
可选档(YAGNI)：跨段贪心合并/后处理合并(直段多格子不掉帧别动)、闭合spline(环形墙才需)、float长跑精度退化(挂机十几小时)、递归细分正解(C++通用工具)、Box朝向高低差(竖直墙已规避)。
建议：先做①,最快最该有且决定③；②5min顺手确认；④及灰色档全YAGNI。够用比完备重要。

### 2026-06-11 17:30 — [产出] S弯中点采样陷阱示意图 + MaxStep 救援原理讲解
用户已把分段改为"按顶点间线段比例步进二分"，并手动加了步进最大值 MaxStep 兜底，请求画图说明 S 弯陷阱。
**画了对比图(widget)**：左panel单点采样——S弯先鼓后凹，曲线中点Smid恰穿弦落在弦中点Cmid上→sag=VSize(Smid−Cmid)≈0→误判直段→真实弦高(峰)被漏；右panel MaxStep强制中点切一刀→把S劈成左右两个单弯→各自中点采样不再落穿弦处→sag量得准。
**讲解要点**：①比例化只换 step 表达单位，没改"单点采中点"采样结构，S弯陷阱原样还在，与比例/cm无关。②MaxStep 本质=强制第一刀不取满整段(step初值=min(比例×段长, MaxStep))，逼着先切一刀破坏S弯"中点穿弦"对称性，不是控精度而是封采样盲区。③用户调 MaxStep 在"判断精确↔少碰撞格"折中=采样近似原罪，一个参数拿不到零漏切+最少Box。④真正消 trade-off=三点取最大(¼峰/¾谷各抓一极值)，加了后 MaxStep 可放大、直段Box减少、S弯照抓，平衡点整体推向少格子。单面墙现状够用，是否上三点看嫌不嫌格子多。

### 2026-06-25 11:20 — [决策] AirWall 使用 VFX Uber 母材质时的函数分层
用户询问：空气墙使用特效 Uber 母材质 + 实例调参，是否需要在母材质内写空气墙专属函数。建议分三层：① Uber 母材质只放通用 VFX 能力（Flow/Fresnel/Noise/Distortion/Emissive/Refraction）；② `MF_AirWallCore` 只放空气墙必需的数据桥和遮罩；③ 材质实例负责颜色、强度、速度、开关等风格调参。
**AirWallCore 应包含**：ContactWS/RippleStart/RippleDuration 的交互波纹桥；世界坐标定位与 UV/tiling 解耦；边缘淡出、高度遮罩、厚度/正反面遮罩；Opacity/Emissive/Refraction/NormalOffset 输出分路；Static Switch 性能开关（EnableRipple/EnableRefraction/UseNoiseTex/EnableEdgeFade）。
**不要塞进去**：具体花样特效、一次性美术风格、复杂多波纹数组、非空气墙通用的重逻辑。原则：空气墙函数只解决“这类墙都需要的数据语义”，具体视觉用实例调。

### 2026-06-25 14:08 — [纠正] 波纹不是需求，材质函数应抽象为通用 VFX building blocks
用户澄清：波纹只是之前演示效果，不是明确需求；写函数时希望通用一点。修正上一版“AirWallCore”倾向：不要把 Ripple/ContactWS 写成空气墙函数核心，也不要把函数命名/设计成波纹专用。
**新建议**：拆为通用函数层：① `MF_VFX_SurfaceSpace`：统一输出 UV、WorldPosition、Local/Object 空间、EdgeFade、HeightFade、Facing/Fresnel Mask；② `MF_VFX_EventMask`：可选事件遮罩，输入 EventPositionWS/EventStart/EventAge/EventRadius/EventWidth/EventFalloff，输出 EventMask/DistortionMask，波纹只是 point event 的一种实例化表现；③ `MF_VFX_Compose`：把 Flow/Noise/Fresnel/EventMask 组合到 Emissive/Opacity/Distortion/Refraction。
**空气墙定位**：空气墙只是使用者，不是函数边界。可保留一个很薄的 `MF_AirWallPreset` 或材质实例，把墙需要的默认开关/参数整理好；核心函数保持通用，能服务屏障、能量门、护盾、扫描面、交互平面。

### 2026-06-25 14:15 — [决策] 空气墙默认底部火苗：AI 生成遮罩，材质负责动画
用户希望空气墙默认有下方火苗生成效果：AI 生成上半透明/下半火苗扰动感贴图，材质内使用。建议：AI 只生成形状遮罩，不烘动画；材质负责流动、闪烁、扭曲和颜色。提示词核心：horizontal seamless tileable grayscale alpha mask / black background / upper 60-70% pure black transparent / bottom 30-40% flame wisps / soft smoky turbulent edges / no object no text no frame。若 AI 不能出 alpha，则用黑底白火苗灰度图，UE 内用亮度当 alpha。
**材质使用**：导入为 mask 贴图（sRGB off，TC Masks/Grayscale，Mip on，U Wrap，V 可 Clamp）；采样 UV：U*Tiling，V 映射到底部区域；用 Panner + Noise/flowmap 扰动采样 UV；mask 接 Opacity，mask*ColorRamp*EmissiveIntensity 接 Emissive，可选 mask*DistortionStrength 接 Refraction/PixelNormalOffset。颜色不要烘进贴图，实例调 FireColorLow/High、Intensity、Tiling、FlowSpeed、DistortionStrength、BottomHeight。
**判断现有 Uber 能否直接做到**：检查是否已有 TextureMask 输入、UV Tiling/Panner、UV Distortion/Noise、ColorRamp/Emissive、Opacity mask、Refraction/Distortion 开关。如果全有→直接用实例调；若缺 TextureMask 或 Distortion 输入→补通用 `MF_VFX_SurfaceMaskFlame`/`MF_VFX_TextureMaskAnim` 函数，不要写成 AirWall 专属。

### 2026-06-25 14:25 — [发现] 空气墙半埋地下：pivot/component origin 问题，不是重心
用户反馈空气墙拖出来总有一半在地下，怀疑重心设置。判断：通常不是 Center of Mass，重心只影响物理模拟；拖放/生成高度由 Actor Root、组件 transform、StaticMesh pivot/origin、Box/SplineMesh 的局部原点决定。
**真因**：当前墙的路径/Actor Location 大概率代表地面线 Z=0，但视觉 mesh / collision box 以组件中心为原点展开。`SetBoxExtent.Z=WallHeight/2` 是从中心上下各半高，若组件 Location.Z=地面Z，则一半在地下。
**修法**：若 spline 表示底边/地面路径，生成 P0/P1/Mid 或组件 RelativeLocation 时加 `WallHeight*0.5` 的 Z 偏移；Box/SplineMesh 视觉和碰撞统一抬高。或者把静态 mesh pivot 改到底部，但动态 Box 仍要注意中心展开。若 spline 表示中心线，则半埋是预期，应改路径高度或 Actor 默认 Z。

### 2026-06-25 15:23 — [发现] 材质函数可用 FunctionOutput 输出 UV，但必须语义化而非万能 UV
用户疑问：材质函数计算 UV 后怎么传给母材质，感觉 UV 无法规范。说明：UE Material Function 通过 `FunctionOutput` 输出值，连接 float2/Vector2 后，母材质 Function Call 节点会出现对应 output pin，可直接接 Texture Sample 的 UV 输入。若输出是 float3/float4，要 ComponentMask RG 成 float2 再接。
**规范建议**：不要输出一个叫 `UV` 的万能线，而输出带语义的 UV：`UV_Base`（原始/传入）、`UV_Tiled`（平铺后）、`UV_Flow`（Panner 后）、`UV_Mask`（遮罩贴图用）、`UV_Distort`（扰动后）。母材质按用途选择接哪个。函数输入必须有 `BaseUV`，外部可接 TextureCoordinate/mesh UV/world UV；函数内部不要硬读 TextureCoordinate，避免无法复用/多 UV 通道失控。
**边界**：如果函数本身是“采样模块”（如 `MF_VFX_TextureMaskAnim`），也可以输入 TextureObject + UV 并直接输出 Mask/Color，母材质不用拿 UV；如果是“UV 工厂”，就只输出 UV 和 mask，不在函数里采样具体贴图。两种模式别混乱。

### 2026-06-26 15:00 — [决策] AirWall 收口：交互参数协议 + 多层视觉 SplineMesh
用户总结 AirWall 现剩两个主问题：
1) 特效需求：VFX Uber 母材质需要接收玩家碰撞交互信息，并写通用规范给特效配置；同时准备备选方案：在交互位置直接生成独立特效。
2) 视觉层需求：在原 spline 生成基础上沿侧向横移一点点叠多层 mesh，方便多层特效配置。
**建议架构**：定义统一 `InteractionPayload`：`InteractionPositionWS`、`InteractionNormalWS`、`InteractionStartTime`、`InteractionStrength`、`InteractionRadius`、`InteractionDirectionWS`、`InteractionId/LayerMask`。路径 A=把 payload 写入各层 MID/MPC，让母材质内响应；路径 B=同一 payload 作为 Spawn VFX actor/Niagara 的初始化参数。表现方式可切换，但事件语义统一。
**多层 mesh 规范**：Collision 保持单层，只负责阻挡和 Hit；Visual SplineMesh 允许 `VisualLayerCount` 多层。每层用 `LayerSpacing` 沿墙法线/右向偏移：`LayerOffset = LayerNormal * ((LayerIndex - (LayerCount-1)/2) * LayerSpacing)` 或只向玩家侧偏移。生成视觉层时 P0/P1/Mid 同步加 Offset，切线不加/只加同向平移后的端点，材质每层可独立 MID/MaterialOverride，并写入 LayerIndex/LayerDepth/LayerSeed（CPD 或 MID）。
**TA 约束**：特效层可叠，碰撞不要叠；多层半透明会增加 overdraw，LayerCount 默认 2-3，需在 Shader Complexity/Quad Overdraw 下验；每层开关用 Static Switch/实例参数避免 Uber 全开。

### 2026-06-26 15:03 — [发现] 横向 UV 已可重复但纵向拉伸：V 仍是 0-1，需改为世界高度重复
用户反馈：现在计算了横向 UV 可控制重复，但纵向拉伸严重。判断：U 已按 spline 长度/横向距离做 repeat，V 仍沿用 mesh 原始 `UV.y` 0→1，导致一整张贴图被拉满 `WallHeight`。墙越高，纵向越糊/越拉。
**修法**：把 V 也从“归一化 0-1”改成“世界/局部高度除以重复尺寸”。通用公式：`VHeight = dot(AbsoluteWorldPosition - WallBottomWS, WallUpWS) / VTileWorldSize`；竖直墙简化：`VHeight = (AbsoluteWorldPosition.Z - WallBaseZ) / VTileWorldSize`。例如希望纹理每 100cm 重复一次，`VTileWorldSize=100`，400cm 墙会重复 4 次而不是拉伸 1 次。
**函数规范**：输出 `UV_SurfaceWorld = float2(UAlongWall, VHeight)`，其中 `UAlongWall=沿墙距离/UTileWorldSize`，`VHeight=高度/VTileWorldSize`。不要混用 `V01` 采样重复纹理；`V01=(height/WallHeight)` 只用于高度渐隐、底部火苗限制等 mask。
**参数**：`UTileWorldSize`、`VTileWorldSize`、`WallBottomWS/WallBaseZ`、`WallUpWS`、`WallHeight`。若 spline 贴地且墙竖直，蓝图只需给每层 MID 传 `WallBaseZ` 和 `WallHeight`，或直接用 Actor 底部位置。

### 2026-06-26 15:19 — [决策] V 轴双模式：ClampOnce 与 RepeatWorld
用户补充：空气墙有些效果不希望竖直重复，因此不应只有“V 世界重复”一种模式。采纳：材质函数同时输出两套纵向 UV。
**两套 V**：① `VClampOnce = saturate((HeightFromBottom - ClampOffset) / ClampHeight)`：固定竖直范围内 0→1，超出 clamp，适合底部火苗、上下渐变、hero mask、一次性图案、非平铺符文；② `VRepeatWorld = HeightFromBottom / VTileWorldSize`：按世界 cm 持续重复，适合噪声、流光、网格、扫描线、可平铺细节纹理。
**函数输出**：`UV_ClampOnce = float2(URepeat, VClampOnce)`、`UV_RepeatWorld = float2(URepeat, VRepeatWorld)`，另输出 `V01`/`HeightFromBottom`/`BottomMask`。每个 TextureSample 自己选 UV，不要全局一刀切。
**火苗用法**：底部火苗主形状贴图用 `UV_ClampOnce`（只在底部固定高度出现，不随墙高拉伸也不重复到顶部）；扰动 Noise/flow 贴图用 `UV_RepeatWorld`（保证扰动密度不随墙高变化）。

### 2026-06-26 15:24 — [发现] 核对当前 CPD 与材质函数：横向 U 成立，需规范 EndOffset 与补两套 V 输出
用户提供最新蓝图 s.txt 与材质函数导出。解析蓝图：`SetDefaultCustomPrimitiveDataVector2(DataIndex=0)` 写 CPD0/1；`Divisor = SelectFloat(FullUV ? SplineLength : UVTiling)`；`X = StartP / Divisor`；`Y = EndP / Divisor - 1`；写入 `MakeVector2D(X,Y)`。材质函数：`StartOffset=CPD0`，`EndOffset=CPD1`，`U = Lerp(StartOffset, EndOffset + 1, BaseUV.R)`，`V = BaseUV.G`，输出 Append(U,V)。因此横向全局 U 逻辑正确：等价 `U=lerp(StartP/Divisor, EndP/Divisor, LocalU)`。
**问题/建议**：①当前 CPD1 实际是 `EndOffsetMinusOne`，名字叫 `SplineMeshEndOffset` 容易误导；建议蓝图直接存 `UEnd=EndP/Divisor`，材质 Lerp 直接接 UStart/UEnd，删 `-1/+1`。②当前 V 仍是 `BaseUV.G`，纵向仍可能拉伸；在材质函数新增语义化输出：`UV_KeepV`（当前）、`UV_ClampOnce=float2(U,VClampOnce)`、`UV_RepeatWorld=float2(U,VRepeatWorld)`。③若继续 CPD 扩展，注意 Vector2 DataIndex=0 消耗 CPD 0/1，后续 LayerIndex/Seed 等从 CPD2 开始，避免覆盖。

### 2026-06-26 15:32 — [决策] 施工清单：多重视觉 Mesh + 保留 UV_KeepV 并新增 UV_ClampOnce/UV_RepeatWorld
用户要求“不写代码，给连的过程”。整理施工：
**蓝图多重 Mesh**：在“每段视觉 GenerateSplineMesh 调用”外套 ForLoop LayerIndex=0→VisualLayerCount-1；Collision 生成逻辑不进这个循环。新增变量 VisualLayerCount、LayerSpacing、LayerMaterials、VisualLayerMIDs、VisualMeshes。LayerOffsetAmount 居中公式 `(LayerIndex - (Count-1)*0.5)*LayerSpacing`，或单侧 `LayerIndex*LayerSpacing`；OffsetDir 用墙 Right/Normal。StartP_Layer=StartP+Offset，EndP_Layer=EndP+Offset，传入原 GenerateSplineMesh；Tangent 不加 Offset。生成后每层 SetMaterial/Create MID，存数组，并设置 LayerIndex/LayerOffset/LayerSeed（MID 或 CPD，从 CPD2 开始，CPD0/1 已被 UStart/UEnd 占用）。
**材质函数 UV**：保留当前横向 UGlobal 计算。当前 FunctionOutput 改名为 `UV_KeepV`，接 `Append(UGlobal, BaseUV.G)`。新增 `VClampOnce = Saturate((HeightFromBottom - VClampOffset)/VClampHeight)`，接 `Append(UGlobal, VClampOnce)` → FunctionOutput `UV_ClampOnce`。新增 `VRepeatWorld = HeightFromBottom / VTileWorldSize`，接 `Append(UGlobal, VRepeatWorld)` → FunctionOutput `UV_RepeatWorld`。HeightFromBottom 竖直墙先用 AbsWorldPos.Z - WallBaseZ；若斜墙再升级 dot(WorldPos-WallBottomWS, WallUpWS)。
**验收**：LayerCount=1 时效果应与旧版一致；LayerCount=3/Spacing=3cm 可看到三层平行视觉面；旧材质继续接 UV_KeepV 不破坏；底部火苗接 UV_ClampOnce，噪声/流光接 UV_RepeatWorld。

### 2026-06-26 15:47 — [发现] LayerMaterials 可只放一个默认 MI，LayerLoop 中做 fallback
用户问 `LayerMaterials: Material Interface Array` 能否只加一个元素，把默认材质实例挂上去。回答：可以，Material Interface 数组可存 Material Instance。推荐逻辑：LayerLoop 内先 `IsValidIndex(LayerMaterials, LayerIndex)`，true 用该层材质；false 用 `LayerMaterials[0]`；若 0 也无效则用硬默认 DefaultMaterial。
关键注意：若后续要给每层写 Interaction/LayerIndex/Seed 等运行时参数，每层都要 `CreateDynamicMaterialInstance` 得到独立 DMI 并存到 `VisualLayerMIDs`；不要把同一个 MID 对象 Set 给所有层，否则参数共享/覆盖。只共用同一个 MI 资产作为 SourceMaterial 没问题，DMI 每层独立。

### 2026-06-26 15:46 — [决策] 多层特效 MI 配置：不要自动创建资产，预置 MI + 运行时 DMI，资产生成只做手动按钮
用户担心多层特效不好配，问是否“开一个层就自动在文件夹创建一个 MI”。判断：不要在 Construction Script/拖拽/调整 LayerCount 时自动创建 MI 资产。原因：CS 会频繁 rerun，自动创建资产会污染 Content Browser、造成脏包、重名/覆盖风险、版本管理噪音，且运行时不应写 Content 资产。
**推荐方案**：准备少量可复用 MI asset/preset（如 `MI_AirWall_Default`、`MI_AirWall_Flame`、`MI_AirWall_Main`、`MI_AirWall_Highlight`），填到 `LayerMaterials`。LayerLoop 中根据 LayerIndex 选择 source MaterialInterface（越界 fallback 到 [0]），然后每层 `CreateDynamicMaterialInstance` 得到独立 DMI 并存入 `VisualLayerMIDs`。这样 source MI 可复用，运行时参数独立不串。
**如果确实需要自动产 MI 资产**：只做 Editor Utility / CallInEditor 按钮 `GenerateLayerMIAssets`，用户手动点才生成；命名固定 `MI_<ActorName>_Layer00`，先查存在，不存在才创建，已存在就复用/更新；默认目录可配置；绝不在 Construction Script 自动生成。

### 2026-06-26 20:50 — [决策] 交互两套方案接线：共享 OnWallHit + 节流 + 数据，分流材质响应/Spawn特效
施工清单：① OnWallHit 入口接 SetNotifyRigidBodyCollision(true) 已具备；② 节流 Branch：(GameTime - LastRippleTime) > RippleDuration，True 才放行并 Set LastRippleTime=Now；③ Break Hit Result 取 ImpactPoint(撞击点) + ImpactNormal，时间用 Get Game Time in Seconds(非 Break Hit 的 Time)；④ enum ResponseMode(MaterialOnly/SpawnOnly/Both) 分流。
**方案A 材质响应**：For Each VisualLayerMIDs → SetVectorParameterValue("ContactWS", ImpactPoint) + SetScalarParameterValue("RippleStart", GameTime) + 可选 Strength/Radius。材质内 (Time - RippleStart) 驱动扩散。每层 MID 都要写(共享数据)。
**方案B 生成特效**：SpawnSystemAtLocation(Niagara) Location=ImpactPoint，Rotation=MakeRotFromX(ImpactNormal) 或 FromZ；Set Niagara User 参数(Strength/Color/Radius)。独立粒子，不依赖墙材质，适合爆点火花。
**节流对两套都生效**：Branch 在分流之前，避免每帧狂触发(物理引擎贴墙每帧生成 contact)。验证完 Print String 删除。

### 2026-06-26 21:23 — [发现] 波纹穿墙 bug：3D 世界距离导致弧形/C形/O形墙对面误响应
用户反馈：空气墙弯成包围形（C/O 弧形）时，撞一处对面墙也扩散出波纹。
**真因**：波纹当前用 `Distance(AbsoluteWorldPosition, ContactWS)` 算 3D 欧氏距离——直线距离，穿透墙体几何。C/O 形墙撞击点 A 与对面 B 的直线距离可能远小于波纹半径（临界：RippleRadius > 开口宽度/2 即穿），但沿墙表面走 A→B 要绕半圈很远。3D 距离误判 B 在范围内→对面扩散。
**根因修法（推荐）**：波纹从"世界3D球形"改"墙表面2D圆形"。dist=‖(AlongWall,Height)−(ContactAlongWall,ContactHeight)‖。AlongWall=沿spline里程cm，Height=离墙底高度cm。C形对面那段 AlongWall 与撞击点差很远→距离大→不响应。
**蓝图改动**：撞击时①FindDistanceClosestToWorldLocation(ImpactPoint)→ContactAlongWall(cm)②ContactHeight=ImpactPoint.Z−WallBaseZ。多传2标量给每层MID。
**材质改动**：材质函数多输出 AlongWallDist(cm，不除Divisor)。波纹算距离用(AlongWallDist,HeightFromBottom)vs(ContactAlongWall,ContactHeight)。U/V尺度统一成cm。
**替代方案（治标）**：①法线朝向筛选 dot(pixelNormal,ImpactNormal)>0——弧形墙每段法线不同且对面法线可能也朝外，不一定挡住；②纯MaxRadius限制——小开口C形仍穿。都不如表面距离根治。
**量化临界**：穿墙条件=RippleRadius > 开口宽度/2。RippleRadius越大、墙弯越狠越易穿。配图widget对比3D直线vs表面2D。

### 2026-06-26 21:38 — [决策] 材质交互方案收口：Interaction Contract + 固定插槽，特效实例自由调但不改母材质拓扑
用户问题：材质函数交互若不是直接 Spawn 特效，而是走母材质/MI，怎么写得足够通用；能否只提供位置和时间信息，剩下交给特效自由发挥，同时不让特效随意改母材质。
**建议边界**：蓝图只负责标准化 InteractionPayload，不负责具体表现。最小 payload：`InteractionPositionWS`、`InteractionStartTime`、`InteractionStrength`、`InteractionRadius`；为空气墙表面距离修复再加 `InteractionSurfaceU/ContactAlongWall`、`InteractionHeight`；可选 `InteractionNormalWS`。这些由 OnWallHit 节流后写入每层 MID。
**母材质职责**：提供固定 `MF_VFX_InteractionSlot`，把 payload 转成通用中间量：`InteractionAge`、`InteractionDist`、`InteractionMask`、`InteractionRingMask`、`InteractionFade`、`InteractionDirMask`。母材质不写“具体波纹/火花/溶解”风格，只输出 mask/权重。
**特效自由区**：MI 内通过参数/StaticSwitch 决定 mask 用法：接 Emissive、Opacity、Refraction、NoiseStrength、ColorLerp、DissolveThreshold；调 Color/Intensity/Radius/Width/Duration/Curve/Texture/DistortionStrength。自由发生在实例参数与预留插槽里，不发生在母材质拓扑里。
**控制策略**：母材质只预留 1-2 个 InteractionSlot（单次交互/备用），不开无限模块；所有 exposed 参数分组 `Interaction` / `Appearance` / `Internal(Auto)`，自动写入参数放 Internal。若特效需要新表现，优先通过已有 mask 组合；确实不够，再由 TA 扩展 slot，不允许每个效果直接改 Uber 母材质。

### 2026-06-26 21:44 — [发现] 核对当前交互蓝图：已有 ForEach 多层材质响应，下一步应泛化为 Interaction 参数并清理 FallbackMID
用户提供 `s.txt` 问“这个特效怎么加合适”。解析结果：当前 EventGraph 18 节点。OnWallHit → 节流 Branch；True 后进入 ForEach `VisualLayerMIDs`，对每层 MID 执行 `SetVectorParameterValue("ContactWS", ImpactPoint)` 与 `SetScalarParameterValue("RippleStart", GameTime)`；ForEach Completed 后又对 `FallbackMID` 写同样 ContactWS/RippleStart，并最终 Set `LastRippleTime`。
**判断**：当前链路作为“材质响应”入口是对的，但参数仍是波纹语义，且 FallbackMID 多层阶段容易变成 legacy 双写。
**建议施工**：①保留现有 ContactWS/RippleStart 先不破坏；②新增通用参数：`InteractionPositionWS`、`InteractionStartTime`、`InteractionSurfaceU`、`InteractionHeight`、`InteractionStrength`、`InteractionRadius`；③OnWallHit 节流通过后先计算 SurfaceU/Height（Find Input Key Closest To World Location → Get Distance Along Spline at Spline Input Key；ImpactPoint.Z−WallBaseZ）；④ForEach VisualLayerMIDs 串行写这些参数；⑤材质母材质里用 `MF_VFX_InteractionSlot` 吃这些参数输出 mask/age/dist，具体效果由 MI 参数决定。
**FallbackMID 清理**：正式多层后建议 Branch：`VisualLayerMIDs.Length > 0` 时只写数组；否则才写 FallbackMID。避免数组存在时仍写一个可能过期/不相关的 MID。

### 2026-06-26 21:48 — [产出] AirWall 迁移上下文文档
用户要求把当前需求/上下文整理给其他平台使用。已生成 `work/AirWall/AirWall_迁移上下文_2026-06-26.md`。内容覆盖：沟通偏好、项目目标、当前完成状态、碰撞自适应分段、S弯/MaxStep、材质函数/UV/CPD/MID 分工、多层视觉 SplineMesh、DMI 创建策略、OnWallHit 当前结构、InteractionPayload 泛化、弧形墙3D距离穿墙bug与表面2D距离修法、材质响应/Spawn Niagara 两套方案、FallbackMID 清理建议、坑位总结、下一步施工顺序和给新AI的一句话任务描述。
