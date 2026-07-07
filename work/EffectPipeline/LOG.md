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
