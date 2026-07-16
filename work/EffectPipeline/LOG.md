# EffectPipeline · LOG

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

### 2026-06-29 15:07 — [决策] 项目立项 EffectPipeline
外包交付 20+ 个形态不统一的 Houdini/UE 特效，目标：规范导入到已有主 UE 工程 + 统一材质。
关键决策：并入已有主工程（不新建）；统一母材质+MI 替换散材质；保留 Houdini Engine 插件依赖。

### 2026-06-29 15:16 — [决策] 演进路线：人工跑通→统计形态→工具自动化
不一上来写工具。先人工跑通1个完整导入+规范流程沉淀SOP，再统计全部外包制作形态确定覆盖面，最后写统一工具尽量自动化。
工具分两层：Python外壳（扫描/分类/命名映射/调度）+ UE内Editor Utility/Commandlet（Migrate/批量改材质/Fix Redirectors）。Houdini HDA 与视觉回归保留人工。

### 2026-06-30 10:48 — [发现] D20 Volume None 根因：资产缺失，非引擎问题
排查主工程日志 d.txt 实锤：D20 残缺包根本没打包 ZibraVDB Volume 资产，源 .zibravdb 也不在归档。关卡引用悬空→Volume 置 None→Actor 退化成 Cube。推翻"采样器超限/RHI冲突/引用丢失"等旧假设。详见 notes/ZibraVDB排查结论.md。

### 2026-06-30 10:48 — [发现] 外包归档实勘：15 工程，引擎统一 5.5
J:\vendors\漫行者\Final最终归档 共 1022GB，15 个 uproject 引擎均为 UE 5.5（C30 例外=GUID自定义引擎）。完整度分级：A45/B20 等 A 级完整可测；D20/C50 等 B 级残缺。详见 notes/外包归档清单.md。

### 2026-06-30 10:48 — [否决] 公版引擎复刻 ZibraVDB / Migrate 路线受阻
ZibraVDB 是预编译二进制（无源码），ABI 绑定 BuildId，跨引擎不可复用，Fab 也不提供 5.7.3。外包是 5.5 公版，主工程是自研 5.7.3，无 5.5 引擎则 Migrate 行不通。试点改为：优先用完整自包含工程（A45）验证资产依赖结构。

### 2026-06-30 10:48 — [决策] 试点样本改为 A45（完整自包含）
A45 含 Config+Content、带 ZibraVDB 且 .zibravdb 源在工程内、体量适中(7.5GB)。作为"完整参照样本"摸清资产依赖簇，反推 D20 缺料，形成导入 SOP。D20 因 Volume 全缺需先找外包补料。

### 2026-06-30 19:39 — [发现] BYDC 逐工程详查：9 个工程，输出严重不统一
BYDC 9 个工程只读检查完成。6 个有 uproject（C30/C60/D20/A45/B20/C50），3 个无（E20/C80 纯 Content 片段、E40 仅 .7z 未解压）。输出不统一问题：无 uproject×3、无 Config×3、目录命名混乱（C80 深层 WorkProjects/Outsource、C60 残留 C30 命名）、D20 资产平铺+Asstes 拼写错误、C30 引擎 GUID 异常、C50 工程嵌套 Cloud 子目录、插件配置不统一（仅 D20 启用 HoudiniNiagara）。详见 notes/外包归档清单.md §2、§5。

### 2026-06-30 19:48 — [决策] 制定外包特效交付规范 v1.0
基于 BYDC 9 工程详查发现的不统一问题，制定交付规范 v1.0（notes/外包交付规范.md）。核心要求：完整工程三件套（uproject+Config+Content）、目录结构标准化（FX_<镜头号>/ 子目录分层）、插件按需声明、ZibraVDB/HoudiniNiagara 资产依赖完整性、交付前自检清单。每个禁止项均附带反面案例引用。

### 2026-06-30 20:40 — [决策] 优先级调整：材质替换降级，Sequence 对齐为最高优先
用户明确当前目标：先把外包特效正确导入主工程并对上离线渲染 Sequence，材质替换不是当前优先项。BACKLOG 重新排序，新增"当前最高优先"区块；阶段 2 从"试点导入+材质替换"改为"试点导入+Sequence 对齐"。D20（HoudiniNiagara 已跑通）作为首选试点。

### 2026-07-01 10:40 — [修正] ZibraVDB Personal Key 获取方式更正
用户实测确认：Fab 下载的免费版插件包**不附带** Personal License Key。之前"随包附带"的假设错误。正确获取方式：邮件 support@zibra.ai 申请。已整理两份邮件模板（Studio 商用 + Personal 评估），存入 notes/ZibraVDB排查结论.md §7。

### 2026-07-01 11:25 — [实测] D20 Sequence 结构确认
主工程 Sequencer 为嵌套结构：Master Sequence → Camera Cuts Section → Shot 子序列。D20 子序列已含 4 条轨道（D20_cameraShape + baiying + N_baiyin_D20_1/2），Niagara Sim Cache 已烘焙（242帧/4s），特效能正常显示。缺灯光轨，部分轨道红色（bound object missing）。详见 notes/ZibraVDB排查结论.md §8。

### 2026-07-01 15:06 — [排查] ZibraVDB 临时验证 DLL 风险评估
用户提供第三方 DLL（微信传输）用于临时绕过 ZibraVDB License。对比主工程现有 DLL：Licensing 414KB→233KB、Runtime 932KB→883KB、Editor 868KB→813KB，大小均不一致，存在 ABI 兼容风险。业务排期等不了跨部门采购流程，作为权宜之计使用，正式发布前必须替换为正规授权。已记录风险提示。

### 2026-07-01 15:15 — [扫描] BYDC 全工程 Content 依赖映射完成
逐工程定向扫描 8 个可访问工程的 Content 目录（E40 未解压跳过）。关键发现：(1) C30/C60 的 __ExternalActors__ 跨引用 E40，导入有顺序约束（E40→C30→C60）；(2) C60 含 3 个 ZibraVDB Volume（far/middle/near_vdb_302）但无 .zibravdb 源（同 D20 缺料问题）；(3) C30/C60 使用 World Partition，ExternalActors 路径不可重组；(4) C80 含 27 个 uasset 深层嵌套+命名不规范；(5) E20 含角色骨骼动画资产。全部同步至 notes/外包归档清单.md §7。

### 2026-07-01 15:25 — [修正] 归档清单复核：B20 才是最完整 ZibraVDB 闭包样本
只读复核 BYDC 归档：A45 有 6 个大体积 ZibraVDBAssetData uasset 但未发现独立 .zibravdb 源；B20 同时具备 9 个 uasset + 9 个 .zibravdb 源，是现有最完整闭包；C50 仅极小 uasset 无源；C60 是 UE 原生 SparseVolumeTexture，不属于 ZibraVDB License 阻塞链。C30/C60 也缺 Config.

### 2026-07-01 16:30 — [修正] A45/C50/0623 误判已复核并更正
进一步定点核实发现：A45 的 6 个 `.zibravdb` 源在平级 `UE_to_vdb/A45/output/vol/`，C50 的 7 个极小源在平级 `vdb/zibra/`，0623 并非空目录而是含约 288GB `0623.7z`。旧结论“缺源/空目录”已同步修正到归档清单、整改说明和交付规范。

### 2026-07-01 17:25 — [决策] 外包整改资料成套完成
基于核实后的事实，已整理 `外包整改执行说明.md`、`notes/外包交付规范.md`、PDF 版 `漫行者外包BYDC交付规范与整改清单.pdf`，并生成 `FX_镜头目录结构示范.zip`。对外文档只保留可执行要求，不展开我方内部推理；C30 单独要求公版 UE 5.5 交付。

### 2026-07-02 11:39 — [决策] 项目阶段切到等待外包整改返包
当前不继续扩大导入面，进入”等外包按规范重新修改并返包”阶段。返包后先验收 P0 阻断项（E40/E20/C80/D20）、C30 公版引擎、A45/C50 源随工程、目录命名和引用闭包，再恢复主工程导入与 Sequence 对齐。

### 2026-07-07 16:39 — [进展] ZibraVDB Personal Key 已到位
用户已通过 support@zibra.ai 申请到 Personal License Key 并在主工程成功激活，临时 DLL 方案退出。ZibraVDB 不再是授权阻塞项。

### 2026-07-07 16:39 — [进展] 外包返包开始上传，6/9 已到
外包在 J:\vendors\漫行者\Final最终归档\BYDC\BYDC文件重新整理\ 新建目录，已上传 C30/C50/C60/D20/E20/E40 共 6 个工程，均含 uproject+Config+Content。缺 A45/B20/C80。开始逐工程验收规范问题。

### 2026-07-07 17:14 — [决策] C30/C60 WP 文件夹豁免 + E40 空 Actor 版本接受
外包反馈 __ExternalActors__/__ExternalObjects__ 是 World Partition 场景设置自动生成的产物，非手动创建，场景 Actor 全部保存在这两个文件夹下。用户同意在提交范围内保留。另：E40 因 ZibraVDB 载入内存占用过大导致外包侧电脑崩溃，用户同意接受不挂接 ZibraVDB、仅保留空 Actor 的版本；主工程侧需自行挂接 ZibraVDB 并在 Sequence 中添加 playback 轨道。

### 2026-07-07 17:14 — [发现] 外包提交备注说明 + E20 ZibraVDB 误判
读取外包 C30-C60-D20-E20-E40文件提交备注说明.docx（含4张截图）。三点备注：(1) 所有 ZibraVDB 镜头均只放 uasset 到 Assets/、未放 .zibravdb 源（通用问题，非仅 D20）；(2) E40 无 playback 轨道因 ZibraVDB 未挂入 Actor，挂入后添加即可；(3) ZibraVDB 会后景遮挡前景粒子，调 Volume Translucency Sort Priority 可解决。截图显示 **E20 实际使用 ZibraVDB**（ZebraVDB Playback 轨道 + ZebraVDB Actor 类型），原扫描误判为 SparseVolumeMaterial，E20 也需补 .zibravdb 源。

### 2026-07-08 11:51 — [进展] C50 源文件补齐，启动主工程导入试点
C50 的 `.zibravdb` 源已交齐（6 个源文件在 Volume/ 下），用户开始拿 C50 做"阶段2·试点导入+Sequence对齐"的全流程试验，不等 A45/B20/C80 到齐。给出的流程：普通资产用 UE Migrate 向上迁移+Fix Up Redirectors；ZibraVDB Volume 不能直接 Migrate uasset（5.5→5.7 Custom Version GUID 不匹配，A45 已实测踩过），须用 `.zibravdb` 源在主工程侧重新导入；落位 Actor 后挂进 Master Sequence→Camera Cuts→C50 Shot 子序列，重点排查 Sequencer 绑定 GUID 失效（D20 踩过的"red track / bound object missing"）需手动 Assign Actor 重绑。待确认：C50 是否已补 Sequence 资产（此前 BACKLOG 记录缺失）。

### 2026-07-08 13:15 — [修正] 主Sequence挂接外包Shot的正确方式：子关卡整体流送+嵌套Sequence，非逐条重绑
纠正上一条记录里"逐条 Assign Actor"的建议——那是笨办法。Sequencer 的 Possessable 绑定认的是 Actor GUID，只要外包关卡整簇（连关卡文件本身，不只是资产）原样 Migrate 过去，作为 Sub-Level 流送进主关卡，Actor GUID 不变，绑定天然有效，不需要手动重绑。正确流程：①连关卡文件整簇 Migrate ②`C50_gk.umap` 作为子关卡加入主关卡（默认不常驻，按需流送）③主Sequence的C50 Shot里加 Level Visibility Track 控制该子关卡仅在对应时间区间可见 ④外包`C50_Sequence.uasset`作为嵌套子序列挂进C50 Shot，无需重建轨道 ⑤唯一手动改的是ZibraVDBActor身上的Volume属性指向重导资产，不影响Actor本身GUID故不影响绑定。真正需要重新Assign的场景只有"新建了Actor（GUID变了）"，推测D20之前的红色轨道就是当时没走子关卡路线、手动摆放Actor导致GUID不一致。

### 2026-07-08 13:46 — [方案对比] 子关卡流送 vs 直接搬运Actor，两条路径的取舍
用户问"能不能不挂Sub-Level，直接把C50关卡的Actor搬进主关卡"。答案：可以，但会破坏GUID。UE的"Move Selected Actors to Level"/复制粘贴本质是在目标关卡重新生成Actor实例，产生新GUID，导致外包Sequence里所有轨道绑定失效变红（同D20踩过的坑），需要逐条手动重新绑定。取舍结论：C50单个镜头轨道少，手动重绑几分钟能搞定，图省事可以直接搬运；但项目目标是20+镜头批量接入（阶段3已计划脚本化），子关卡方案一次学会可全自动化（Python Editor Scripting稳定调用"挂子关卡+加Level Visibility Track"），直接搬运方案每个镜头都要重复人工重绑、难以脚本化。用户可按当前是"验证单镜头"还是"顾虑后续批量"自行选择，未强制要求走子关卡路线。

### 2026-07-08 14:04 — [推翻] 主关卡是 World Partition，子关卡流送方案不可行，重新绑定是必经步骤
用户告知主工程的主关卡开了 World Partition（WP）。这推翻了 13:15 那条"子关卡流送保GUID绕开重绑"的方案——WP 与传统 Level Streaming/Sub-Level 是二选一体系，WP 主关卡上无法用 Window→Levels→Add Existing 挂传统子关卡，13:46 记录的"图省事直接搬运"反而成了 WP 下唯一可行路径，不再是"取舍选项"。
WP 世界对应机制是 Data Layer（非 Sub-Level 显隐）：Sequencer 有 Data Layer Track，可在 Shot 时间区间内设 Data Layer 为 Activated/Unloaded，替代 Level Visibility Track 的作用。但 Actor 仍需物理 Move Selected Actors to Level 搬进 WP 世界（与 C30/C60 现有 External Actors 机制一致），必然产生新 GUID，外包 Sequence 轨道必然变红，需逐条重新绑定——WP 前提下这一步无法绕开。
新流程：①C50_gk.umap 连资产整簇 Migrate ②单独打开该umap全选Actor→Move Selected Actors to Level搬进WP主关卡(变成External Actors) ③Window→Data Layers新建DL_C50，把搬入的Actor加入该层 ④主Sequence对应Shot加Data Layer Track控制DL_C50的Activated/Unloaded区间 ⑤外包Sequence.uasset嵌套挂入Shot，逐条重新绑定失效轨道 ⑥ZibraVDB Volume仍需源重导+改Actor的Volume属性(不变)。
批量化落点也要调整：既然重新绑定在WP下已是必经步骤，阶段3脚本化的重点应放在"自动化按名字规则批量重新绑定轨道"，而非"设法保留GUID绕开重绑"（WP下保不住）。BACKLOG.md 已同步更正为 WP 版流程（Move Selected Actors to Level + Data Layer + Data Layer Track + 逐条重绑）。

### 2026-07-08 14:11 — [操作细化] WP 方案六步详细操作说明已给出
把 14:04 的方案拆成可执行的点击步骤：①Migrate C50_gk.umap整簇 ②单独打开该umap，World Outliner全选Actor→右键Move Selected Actors to Level到WP主关卡 ③Window→Data Layers新建DL_C50，选中搬入的Actor加入该层，默认设Unloaded ④主Sequence对应Shot加Data Layer Track，Section范围=Shot时长，起点Activated终点Unloaded ⑤外包C50_Sequence.uasset作嵌套子序列插入Shot，红色轨道逐条右键重新Assign Actor指向搬入的对应Actor ⑥ZibraVDB源重导后在Actor上改Volume属性指向新资产。验证方式：播放Shot区间应自动显示/隐藏且轨道不再是红色。

### 2026-07-08 14:14 — [提醒] 用户实际用直接拷贝Content文件夹代替Migrate
用户实操时用"直接拷贝C50工程Content目录到主工程"代替Migrate。指出差异：直接拷贝对"资产全在Content/FX_C50/自身目录内、无跨目录/跨镶头引用"的情况等价于Migrate；但若存在指向文件夹外的引用（如C30/C60那种跨引用E40、C80引用外包方FX_Library共享库的模式），直接拷贝会漏掉依赖，导致Missing Reference，Migrate能自动带全部依赖而直接拷贝不能。C50当前未记录类似跨引用问题，但建议打开后主动检查（黄色警告条/Content Browser感叹号图标）确认无缺失引用再继续后续WP搬运步骤。

### 2026-07-08 14:21 — [修正] WP关卡没有Move Selected Actors to Level，改用复制粘贴+OFPA
用户反馈右键菜单没有"Move Selected Actors to Level"，只有"Create Packed Level Actor"（打包成关卡实例资产，不是我们要的）。原因：Move to Level 是给传统 Level Streaming子关卡挂接体系用的，只能选已通过Levels面板加载的传统子关卡为目标，WP主关卡不通过这种方式工作，所以不会出现在目标列表里。
修正为：WP关卡加Actor的标准方式是复制粘贴——①打开C50_gk.umap全选Actor Ctrl+C ②切到主关卡且确保主关卡是Current Level ③视口内Ctrl+V粘贴 ④保存后UE自动用OFPA机制拆成独立External Actor文件(同C30/C60现有存盘结构)。效果等价于之前说的Move to Level(同样重新生成GUID，后续Data Layer+逐条重绑步骤不变)，只是操作方式换成复制粘贴。C50_gk.umap粘贴后变空，可关闭不保存。

### 2026-07-08 17:20 — [回滚/发现] C50 试点改走 Spawnable 路线，推翻 Data Layer + 逐条重绑方案
用户实测跑通更优路径，推翻 07-08 14:04 / 14:21 的"复制 Actor 进 WP + Data Layer Track + 逐条重绑"方案。
新路线（Spawnable，已由 C50 全流程验证）：
① C50 Content 已拷入主工程 Content/FX/C50/（直接拷贝代替 Migrate，C50 无跨工程引用故等价）。
② 外包 C50_Sequence.uasset 里的特效 Actor（ZibraVDBActor / Niagara）在能解析到实例的上下文（C50_gk 关卡）里逐个右键 Convert → Spawnable Actor。转完 Sequence 自包含，绑定不再依赖关卡实例，彻底绕开 WP 下 GUID 变动导致的红色轨道问题。
③ 删掉外包 Sequence 内部的相机 + Camera Cuts（外包只交付特效，相机/后处理/运镜由主工程 Shot 自带）。
④ 主 Sequence 对应 Shot 子序列内加 Subsequences Track，直接引用外包 C50_Sequence，特效整包嵌入，零轨道搬迁。
⑤ 时间对齐即完成。
关键优势：Spawnable 生命周期天然贴合"特效只在本 Shot 期间存在"，不需要复制 Actor 进 WP 主关卡、不需要建 Data Layer、不需要逐条重绑。相比重绑路线，批量脚本化难度大幅降低。
ZibraVDB 隐患已排除：用户实测确认，特效 Actor 全部转 Spawnable 后 ZibraVDB 体积正常显示，template 内嵌的 Volume 引用有效（前提：转 Spawnable 前 Volume 属性已指向主工程侧重导的正确资产，则 template 会正确带走该引用）。未出现旧引用失效问题。
批量化落点更新：阶段 3 脚本化重点从"按名字规则批量重绑轨道"改为"批量转 Spawnable + 清相机 + 挂 Subsequence Track"。脚本骨架已起草（integrate_fx_shots.py），唯一待引擎组确认的是 5.7.3 里 convert to spawnable 的 Python API 签名（官方 5.7 文档指向 LevelSequenceEditorSubsystem，MovieSceneSequenceExtensions.add_spawnable_from_instance 已 deprecated）。

### 2026-07-08 17:20 — [确认] C50 外包 Sequence 资产存在
全流程操作对象为外包 C50_Sequence.uasset（路径 /Game/FX_C50/Level/C50_Sequence），BACKLOG 旧记录"C50 无 Sequence 资产、只有 C50_gk.umap"应更新——该 Sequence 已存在/已补交（具体来源待用户顺手复核）。

### 2026-07-09 14:40 — [进展] C50 接入脚本 integrate_fx_shots.py 端到端实跑成功
两个脚本双双跑通并落地本地：
- copy_fx_content.ps1（C:\Users\violinapeng\paozi-local\）：J盘只读拷贝外包 FX_<镜头> Content 到主工程。目标平级放 Content 下。实拷 C50 15文件通过。
- integrate_fx_shots.py（c:\work\ai\iris\output\）：转Spawnable + 清相机/CameraCuts + 挂Subsequence + 时间对齐。方案B（自动load各镜头_gk关卡）。

### 2026-07-09 14:40 — [发现/关键] convert_to_spawnable 只对"已在Sequencer打开的序列"生效
5.6+ LevelSequenceEditorSubsystem.convert_to_spawnable 只作用于当前在Sequencer打开的序列，对仅load_asset未打开的序列静默无效（返回ok但不转，导致换关卡红轨）。修复：转Spawnable前先 unreal.LevelSequenceEditorBlueprintLibrary.open_level_sequence(seq) 打开。实锤：转换成功时日志出现 MovieSceneSpawnableActorBinding 序列化。这是本次卡最久的坑。

### 2026-07-09 14:40 — [澄清] ZibraVDBActor Cube 网格警告为无害占位，非退化损坏
MapCheck 报 ZibraVDBActor StaticMesh=Cube 警告是编辑器占位网格，不影响转Spawnable，特效正常Instantiating。之前怀疑"Volume=None退化成Cube导致转坏"的判断错误，真因是 open_level_sequence 未调用。

### 2026-07-09 14:40 — [脚本要点] API名与幂等
- 转Spawnable API 实测确认：LevelSequenceEditorSubsystem.convert_to_spawnable（add_spawnable_from_instance 5.6已deprecated）。
- get_display_name() 返回 unreal.Text，用前需 str() 转换。
- 脚本文件必须无BOM，否则UE Python报 U+FEFF SyntaxError。
- 幂等：已Spawnable跳过 + Subsequence已挂同一fx_seq跳过（skip dup）。

### 2026-07-09 14:40 — [待处理] 顶级目录规范：FX_<镜头> 不在主工程允许列表
主工程内容校验器报错：[CheckTopLevelFolder] /Game/FX_C50 不在允许列表（资源位于不允许的顶级目录）。当前"平级放Content下"违反规范。待确认主工程允许的FX资产顶级目录，调整 copy_fx_content.ps1 目标路径与脚本内 /Game 路径。

### 2026-07-09 16:00 — [进展] 两脚本联动改造：共享配置 + 自动探测 + 代号入口
消除两脚本割裂感（PowerShell拷贝在Win跑 / Python接入需UE），三项改造完成并预演验证：
- 共享配置 shot_config.json（本地两份：paozi-local 供PS、iris/output 供Py）。只列镜头代号数组 shots=["C50","C30","C60","D20","E20","E40"]，路径差异全靠脚本自动探测，配置不硬编码。
- 自动探测：PowerShell端探测源FX目录大小写(FX_/Fx_)并自动带WP产物(__ExternalActors__/__ExternalObjects__)；Python端 resolve_shot() 探测/Game下FX目录大小写 + Sequence后缀(_Sequence/_Sequencer)。
- 代号入口：copy_fx_content.ps1 -Shot C30 [-Execute]（单/全）；UE内 integrate_shot("C30") / integrate_all()。
预演结果(6镜头全通过)：C50=FX_C50(15)；C30=Fx_C30(22)+ExtActors(21)+ExtObjs(5)；C60=FX_C60(16)+ExtActors(18)+ExtObjs(7)；D20=FX_D20(21)；E20=FX_E20(16)；E40=FX_E40(14)。C30小写目录、C30/C60的WP产物均正确识别。
一键启动方案(PS自动拉起UE)已评估但放弃：convert_to_spawnable依赖Sequencer UI就绪，无头/自动启动时序有风险。

### 2026-07-09 16:00 — [状态] 当前仅C50已实际导入主工程
C30/C60/D20/E20/E40 已扫描确认J盘源完整、脚本预演通过，但尚未实拷进主工程、未接入。真导入需跑 copy_fx_content.ps1 -Execute + UE integrate_all()（写Company目录+改资产，待用户确认后执行）。

### 2026-07-09 17:45 — [障碍/引擎] D20 批量脚本触发两个引擎级崩溃(非脚本逻辑问题)
脚本探测/转换/挂接逻辑已验证正确(diagnose显示识别全对), 但 D20 实跑遇到两个引擎/硬件层崩溃:
1) [CPU/save崩溃] FAssetProtect::EncryptAsset int32数组越界(index 2^31, package 5.4GB)。自研引擎资产加密模块处理超大package时int32溢出。栈: SaveLoadedAsset -> SavePackage -> FAssetProtect::EncryptAsset (AssetProtect.cpp:256)。应对: 脚本加 AUTO_SAVE=False, 完成后手动Ctrl+S。根治需引擎组改int64。
2) [GPU崩溃] 打开D20_gk渲染时 GPUCrash / Device Hung / Aftermath。D20关卡含10个ZibraVDBActor(0~9)同时PreRenderView+Decompress, RTX3080(10GB)显存/算力过载, GPU挂起。崩在 ZibraVDB_PreRenderView(ZibraVDBActor_7/8) active态。
症状: 重启UE后自动恢复上次关卡(D20_gk)->一加载就渲染10个ZibraVDB->秒崩, 陷入"一开就崩"循环。
恢复: 启动UE时避免自动加载D20_gk(开空关卡/清Saved里上次关卡记录)。
待解决: 超重ZibraVDB镜头(D20 10个/18GB, E20 11GB, E40 36GB)光打开渲染就可能GPU崩溃, 超出脚本范围, 属硬件/引擎负载问题(需分批渲染/降采样/更强显卡, 或引擎组优化ZibraVDB批量渲染)。
D20特殊性: Volume空缺.zibravdb源(BACKLOG已记), 18GB超大, 10个ZibraVDB。是问题镜头, 不适合作常规批量样板。

### 2026-07-09 17:45 — [进展汇总] 本周脚本化成果
- C50: 全流程跑通并导入主工程(拷贝+转Spawnable+删相机+挂Subsequence)。
- 两脚本落地: copy_fx_content.ps1(J盘拷贝, 支持大小写探测/WP产物/后台大文件模式) + integrate_fx_shots.py(转Spawnable接入, 黑名单式识别只删相机留其余, 自动探测目录大小写和Sequence后缀, diagnose/integrate_shot/integrate_all入口)。
- 共享配置 shot_config.json 统一两脚本上下文。
- 关键技术确认: convert_to_spawnable需先open_level_sequence; get_display_name返回unreal.Text需转str; 脚本无BOM; 5个待导入镜头J盘源完整。
- D20暴露引擎级障碍(见上条), 超重镜头待专项处理。

### 2026-07-09 19:00 — [发现/机理] Spawnable膨胀: 重体积特效转Spawnable会把Actor状态烘进Sequence导致资产爆炸
根因解释"D20切Spawnable前没事、切后突然超2G": Possessable只存Actor引用(GUID指向关卡实例), Sequence很小; convert_to_spawnable会把每个Actor完整序列化副本(Object Template)内嵌进Sequence。D20有10个ZibraVDBActor, template可能烘进Volume运行时数据(日志见save时清理Transient.TextureRenderTargetVolume), 10个累积撑爆Sequence -> 撞2G(int32)加密崩溃线。
C50没爆是因为其ZibraVDB template只存轻量uasset引用。
边界结论: Spawnable路线适合轻量特效(C50), 对重体积特效(D20/E20/E40)会导致Sequence资产爆炸性膨胀+save崩溃。重镜头可能需回退Possessable+关卡引用路线(WP下需处理GUID重绑), 或先查清template到底烘进了什么、能否轻量化。待明日/引擎组深究。
待确认: D20崩溃时到底是D20_Sequencer膨胀超2G, 还是D20_gk.umap(本身5.2GB)save触发——脚本save了fx和sh两个, 需区分。

### 2026-07-13 16:55 — [方案] D20 打开即吃 7GB 显存：隐藏渲染代替调画质，先完成 Sequence 迁移
用户目标是先跑通 Sequence 迁移，不需要看效果，问能否把画质调到最低甚至不显示。
排查 ZibraVDB 官方文档结论：运行时显存≈2~3×最大单帧解压体积，由压缩时烘死的分辨率决定；Illumination Downscale / 关闭 Voxel Interpolation 等画质旋钮最多省 30~50%，量级不够砍到接近 0，"调画质"此路不通。
正确方案是"隐藏不渲染"：D20 上次 GPU Hung 崩溃点是 `PreRenderView`（渲染阶段才分配显存），Actor 隐藏后不会走到这一步。批量做法：`EditorActorSubsystem.get_all_level_actors()` 遍历，类名含 ZibraVDB 的 Actor 调 `set_is_temporarily_hidden_in_editor(True)` + `set_actor_hidden_in_game(True)`，隐藏后再正常跑 `integrate_shot`/转 Spawnable/挂 Subsequence，与 Sequence 数据层操作完全解耦、可逆。
边界提醒：隐藏只解决"打开关卡不崩"，不解决 07-09 19:00 记录的"重体积特效转 Spawnable 导致 Sequence 资产爆炸"隐患，D20/E20/E40 仍在 heavy_shots 名单，是否走 Spawnable 待验证完再定。

### 2026-07-13 17:04 — [修复] 主工程编辑器启动崩溃循环：LoadLevelAtStartup 改为 None
用户授权改动主工程 `D:\Work\Company\UE\Jianlai\TMR\UnrealEngine\Games\JyGame` 一次。修改 `Saved\Config\WindowsEditor\EditorPerProjectUserSettings.ini` 的 `LoadLevelAtStartup`：`LastOpened` → `None`。避免编辑器每次启动自动重新加载上次打开的重体积关卡（如 B20_gk/D20_gk），从而复现 GPU Hung/崩溃循环。原文件已备份为 `EditorPerProjectUserSettings.ini.bak_20260713`，可随时改回。此为 Epic 官方论坛认可的标准修复方式（社区惯用做法），不是项目特有方案。

### 2026-07-13 17:11 — [方案/修正] ZibraVDB 显存问题的正确旋钮：Volume Resolution 降采样，非完全隐藏
用户补充约束：不能完全关掉 VDB，否则看不到效果对不上；可以接受"超一点显存慢慢调"。这与上一条"隐藏不渲染"的约束不同，需要"看得见但显存降低"的中间方案。
查官方 ZibraVDB for UE 1.4 参数文档（Render 分类）确认：`Volume Resolution`——"Allows rendering of a downscaled version of the effect"，直接砍解压帧本身（显存公式 VRAM≈2~3×最大解压帧体积 的主项），量级足够；上次提的 Illumination Downscale 只砍伴生光照贴图，量级不够，这个判断维持。
量级估算：降采样系数 s 对显存影响约 s²~s³（体积型烟雾偏 s³，薄层偏 s²）。s=0.3 大致可把 7GB 砍到 200~700MB 量级。
另发现官方原生开关 `Visible`（Playback parameters）："Toggles decompression and rendering of the effect"——比泛用的 Actor 隐藏更精确（连解压这步也关/开），推荐优先用这个而非通用 hide-actor 技巧。
安全顺序：先用隐藏方式安全打开关卡 → 隐藏状态下批量设 Volume Resolution 低值 → 用 Visible 属性打开 → 边看显存边迭代。
待办：Volume Resolution / Visible 的真实 property 名未从文档拿到内部字段名，实操前须在 Details 面板核实，避免重蹈 convert_to_spawnable 那种"API 名字猜错静默无效"的坑。

### 2026-07-13 17:14 — [实测/计算] B20 实测显存 7GB/10GB，与 D20 同属重风险但仍在 spawnable_shots 名单
用户实测：B20 单独打开吃 7GB 显存，GPU 总显存 10GB（占用 70%，逼近 D20 当时崩溃前的危险区）。
按目标压到 50%(5GB) 计算，Volume Resolution 降采样系数 s³=5/7≈0.714 → s≈0.89，建议先试 0.85（留缓冲），不够再降到 0.7（目标约 35%/3.5GB）。此为体素三维网格降采样的理论估算(s³关系)，ZibraVDB 未公开具体实现，需实测微调。
关键提醒：查 notes/外包归档清单.md，B20 是 9 个 ZibraVDBAssetData + 9 个 .zibravdb 源的"最完整闭包样本"，体积数量(9个)与 D20(10个)几乎同量级，风险特征相同。但 shot_config.json 当前把 B20 分在 spawnable_shots（安全批量名单），未与 D20/E20/E40 一起进 heavy_shots。若不调整，integrate_all() 会把 B20 当轻量镜头自动转 Spawnable，可能重演 D20 的"Sequence资产爆炸撞2GB加密崩溃"坑。**待用户确认是否将 B20 移入 heavy_shots**。

### 2026-07-13 19:07 — [排查] B20_gk 迁移/改名弹窗排查：主工程无硬编码引用，可安全 Continue
用户迁移/改名 B20_gk 关卡时弹出 UE 标准提示："Source code, config INI, and text files may need Find/Replace...Otherwise assets can be missing from cooked builds."
排查主工程 `D:\...\JyGame` 的 Config、Designer、JGameAI、JGameAIHub、Plugins（cpp/h/ini/cs/json/txt）、JGame.uproject，搜索 "B20_gk" 全部零命中；且该项目无 Source/ 目录（Content-only，无 C++ 层）。结论：此弹窗是 UE 对任意资产改名/移动的通用保守提示，非针对 B20_gk 检测到实际问题，可点 Continue。
唯一排查不到的盲区是 Content 内二进制资产（Blueprint/Sequence）里可能硬编码的字符串路径，文本搜索排除不了，但 B20 尚未接入主 Sequence/主关卡逻辑，此类硬编码几乎不可能已存在。建议迁移后用 Reference Viewer 肉眼复核一次。

### 2026-07-13 19:20 — [根因确认] B20 迁移崩溃/掉引用：走了 Migrate 直迁 uasset，跳过 .zibravdb 重导流程，复现 A45 老坑
用户反馈迁移 B20_gk 关卡会 crash，且 3 个 ZibraVDB 掉引用。查主工程日志（Saved/Logs/JGame-backup-2026.07.13-*.log）实锤：
- 9 个 Volume 资产（B20_cloud_01_v01 ~ 04_v05）Asset Registry 加载阶段全部报 `Missing custom version GUID: 3DC15BB1E4C9409C9E5409529E555017`，标记 unloadable。
- b20_sequence 打开/关闭时触发标准加载路径，7 个 Volume 明确报 "dependent package ... was not available ... Perhaps it has been deleted or was not synced"。
根因：B20 走了 Migrate/直拷 uasset 路线，而不是 07-08 11:51 条目已定的规则——"ZibraVDB Volume 不能直接 Migrate uasset（5.5→5.7 Custom Version GUID 不匹配，A45 已实测踩过），须用 .zibravdb 源在主工程侧重新导入"。B20 复现的是 A45 当年一字不差的失败模式。
"表面正常"原因：ZibraVDB Runtime 有旁路机制可绕开标准 Asset Registry 自行读帧（日志能看到 Instantiating 正常），平时不触发标准加载路径就不报错；一旦 Sequence 引用重新解析（迁移操作触发），旁路失效，暴露为掉引用/崩溃。9 个 Volume 全部处于同样病态，用户观察到的"3 个"只是暴露程度不同，不代表其余 6 个没问题。
修复方向：不是修迁移方式，而是回滚重新导入——①删除当前主工程 9 个坏 Volume uasset ②用 B20 的 .zibravdb 源（外包归档记录源在 houdini/B20/output/vol/，9 个齐全）在主工程侧通过 ZibraVDB 插件重新导入（非 Migrate/拷贝）③重导后核对 b20_sequence 的 Volume 引用是否自动关联 ④再执行 Sequence 迁移。
待确认：B20 的 .zibravdb 源文件是否已经拷进主工程（还是只拷了 uasset）。

### 2026-07-13 21:24 — [崩溃实锤] B20 GPU Hung 崩溃日志分析：显存超预算触发设备挂起
用户提供崩溃日志 `Saved/Crashes/UECC-Windows-1A14AF1E408CEEE837349B9EE0786A95_0001/JGame.log`。分析结论：与上面 19:20 条目（GUID不兼容/掉引用）是同一 B20 场景下的**另一类独立问题**——这次是真正的 GPU 崩溃，不是资产加载问题。
关键证据：`"Device state": "Hung"`, `"CrashType": "GPUCrash"`, `"ErrorMessage": "Aftermath crash dump"`；显存统计 `Local Budget: 9285.00 MB` vs `Local Used: 9361.73 MB`——实际用量超出本地显存预算约77MB，驱动判定设备挂起。触发着色器为 `ZibraVDBBBoxRender`（ZibraVDB 体积包围盒渲染），确认是 ZibraVDB 渲染阶段显存溢出。硬件 RTX 3080（本地预算9285MB）、内存128GB不是瓶颈（`bIsOOM:0`）。
与今日 17:14 条目的显存计算互相印证：B20 静止基线已测得约7GB(70%)，此次崩溃发生在渲染叠加负载后瞬时冲高到9.3GB+，正好越线。结论：Volume Resolution 降采样方案（目标压至约50%/5GB）方向正确且更紧迫——当前使用量已逼近甚至超过硬件上限，需要比原计算更激进的压缩比才够安全冗余。同时印证 B20 应立即移入 heavy_shots（此前是待确认项，现有崩溃实锤，不必再等确认）。

### 2026-07-13 21:27 — [定位] B20 崩溃真凶锁定单体积：B20_cloud_04_v03 占体素总量56%，是唯二异常大的体积
用户反馈：挂其他体积都正常，只挂 B20_cloud_04_v03 时才炸。核实崩溃日志里 9 个体积的实例化分辨率，换算体素数排序：v03(1040×912×928)≈8.8亿体素，占9个体积总量56%，是第二大 v04(880×464×928≈3.79亿)的2.3倍；其余7个体积体素量级都在v03的1/10以下甚至更小。
结论：GPU Hung（显存超预算77MB）主要由 v03 一个体积的解压缓冲撬动，此前挂其他8个体积时已把显存吃到接近预算线（薄余量），v03 一挂上去直接击穿。修正17:14的"整批9个体积压到50%"方案为**只需单独对 v03 做降采样**（Volume Resolution 先试0.8，体素砍到约51%即约4.5亿，量级回落到v04附近），其余8个体积体素本来就小，无需一起压画质，避免过度牺牲。
澄清与19:20 GUID条目的关系：两者是B20身上两个独立问题（GUID是全部9个体积的资产兼容性问题，GPU Hung是v03一个的显存问题），实操顺序建议先做.zibravdb重导（修复全部9个的GUID问题），重导完成后再单独对v03调Volume Resolution，避免调完画质资产本身还是坏的。

### 2026-07-14 11:00 — [关键实测] 换公版UE5.7.4测试B20：GUID问题消失，但显存超支从77MB暴增到5.8GB
用户在独立缓存目录 `D:\Work\Cache\B20`（干净公版UE5.7.4，非主工程自研5.7.3）单独测试B20，又崩了，提供崩溃日志 `Saved/Crashes/UECC-Windows-A89B4BF34AB4979C0A09669CA10E1E15_0000/B20.log`。
核心发现：①该日志中搜索"Missing custom version GUID"**完全零命中**，证实19:20条目"GUID不兼容根因是主工程自研5.7.3装的ZibraVDB插件构建版本、与外包用的公版5.5插件构建版本注册的私有版本表不匹配"这一判断——换到公版5.7.4（插件构建版本对得上）后GUID问题不再出现。②但代价是：全部9个体积（包括元凶v03）这次都被成功实例化并参与渲染（`Instantiating ZibraVDB B20_cloud_04_v03...`等9条全部出现），显存暴涨：`Local Budget 9285MB` vs `Local Used 15077.81MB`，超支5792MB（62%），比昨天77MB的轻微超支严重得多。CrashType仍为GPUCrash/Hung，GPU断点显示崩溃时`ZibraVDBActor_6`的`VolumeDownscale`步骤为Active（说明降采样管线本身在跑，只是需求量依然远超预算）。
结论：GUID修复和显存问题是接力关系，不是二选一——解决GUID只是让全部9个体积"有资格"被加载渲染，代价是显存需求从"部分体积"变成"全部9个体积"，负载不降反升。之前17:14/21:27算的Volume Resolution方案目标(压到~50%/5GB)基于旧基线(7GB/9.3GB)，现在实测基线已是15GB量级，需要重新计算：15GB→5.5GB目标，s³=5.5/15≈0.367，s≈0.72（比之前给的0.85起始值更激进）。且现在看不能只压v03一个，因为全部9个同时加载时总量已经很大，可能需要普遍性降采样而非单点。

### 2026-07-14 11:05 — [应急方案] B20场景连打开都直接崩，物理挪走v03资产文件绕开GPU崩溃
用户反馈场景现在连打开都会crash，没有机会进编辑器调Volume Resolution参数。给出应急方案：利用已确认的"依赖包缺失→ZibraVDBActor退化Cube占位→不触发解压渲染"机制（19:20条目已验证的效果），主动把 `B20_cloud_04_v03.uasset` 从 `Content/.../FX_B20/Volume/` 剪切到临时目录，使其变成缺失引用。v03是占体素总量56%的元凶，挪走后其余8个体积（约44%总量）应该能在预算内正常加载，可借此窗口完成Sequence迁移工作，事后需将文件挪回原位。
备选正规方案：用 `-nullrhi` 命令行标志启动无渲染管线的editor-cmd进程+Python脚本，在没有GPU设备的情况下加载关卡改Volume Resolution属性再存盘，从根本上避免GPU Hung，但具体命令行标志组合和headless模式下Python子系统可用性未经验证，建议先跑纯诊断（只打印不改）版本确认可行。

### 2026-07-15 14:54 — [发现/约束] Git LFS 单文件上限 5GB，22 个工程超限需 cp 回本地切分返工
实测返包目录 `BYDC\BYDC文件重新整理\` 各工程大小。返包分"云雾效果"（27 个工程）和"金沙效果"（6 个工程）两大类，共 33 个目录条目。
超过 5GB 的有 22 个（去重 17 个镜头代号）：E40(51.54G云雾+35.29G金沙)、C11(46.14G)、C30(31.54G云雾+12.79G金沙)、C10(27.80G)、C60(27.05G云雾+5.83G金沙)、F50(20.16G)、B10(15.22G)、A45(14.17G)、B20(14.02G)、D20(13.12G云雾+17.96G金沙)、D40(11.68G)、C80(10.47G云雾)、E30(9.25G)、D30(8.97G)、D60(7.72G)、E20(7.23G云雾+11.08G金沙)、D70(5.14G)。这些工程必须 cp 全部回本地做切分返工。
未超 5GB 可正常导入的有 11 个：D10(4.51G)、B30(2.78G)、B40(2.00G)、A50(1.98G)、D50(1.22G)、B60(0.89G)、C40(0.88G)、B55(0.30G)、B50(0.22G)、C50(0.01G已导入)、C80金沙(2.42G)。BACKLOG 已同步完整分诊表。
注意：超限工程若走 `.zibravdb` 源在主工程侧重导路线（非 LFS 推 uasset），则不受 LFS 5GB 限制，需逐个确认导入路线后排除。

### 2026-07-15 15:15 — [进展] 10 个未超 5GB 镜头已全部拷贝到主工程 Content
用 copy_fx_content.ps1（云雾9个）+ robocopy（金沙C80）完成拷贝，全部验证文件数和大小匹配：
- 云雾：D10(4.6G/4files)、B30(2.8G/38f)、B40(2.0G/26f)、A50(2.0G/10f)、D50(1.2G/4f)、B50(226M/10f)、B55(307M/18f)、B60(910M/14f)、C40(899M/8f)
- 金沙：C80(2.4G/77f)
- C50 此前已导入（试点完成），本次不重复
shot_config.json 两份（paozi-local + iris/output）已同步更新，新增 copied_shots 字段。下一步：UE 内跑 integrate_fx_shots.py 的 integrate_all() 或逐个 integrate_shot() 接入 Sequence。

### 2026-07-16 16:50 — [进展] B20 + D10 导入完成，已完成 4/23 镜头
B20 和 D10 完成导入，项目进度同步更新至 AI-BRIEF / BACKLOG / LOG 三份文档与企微在线文档。
- B20：v03 外包切片体素分辨率 1040×912×928 触发 GPU TDR 超时（非 OOM），按体素分辨率切分为 11 段（000_050 ~ 501_534），通过 Spawned Track 互斥帧段避免同时加载爆显存。
- D10：Spawnable 转换完成，注意保存超大 ZibraVDB 资产可能触发 32 位数组索引溢出（2147483648）。
- 当前总进度：已完成 4（C50/C40/B20/D10）· 阻塞 4（A45/D20/E20/E40）· 待导入 15。
