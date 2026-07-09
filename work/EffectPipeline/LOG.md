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
