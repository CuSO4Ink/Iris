# ZibraVDB 排查结论

> 2026-06-30 两次排查。证据：`d.txt`（D20 残缺包）+ `JGame.log`（A45 完整包导入主工程）。

## 1. 结论：两条独立阻塞链

| 场景 | 根因 | 表现 | 状态 |
|---|---|---|---|
| D20 残缺包 | **资产数据缺失**——归档无 ZibraVDB Volume uasset / .zibravdb 源 | Volume None → Cube 占位 | 待外包补交 |
| A45 完整包 | **License 未激活**——解压器需在线授权，主工程无 active license | 6 个 Volume 数据完整但无法解压 → Cube 占位 | 待激活授权 |

## 2. A45 导入实测（JGame.log 2026-06-30 14:43）

**好的消息**——之前 d.txt 里的 shader 编译错误（`TriangleIntersectsAABB`）本次**未复现**，插件 v1.5.3 正常加载，6 个 Volume 全部 Instantiating 成功（帧数/尺寸正确），资产数据跨版本升级 OK。

**阻塞点**——16 次 `Failed to initialize decompressor: Decompression of this file requires active license.` → `.zibravdb` 私有压缩格式需 ZibraVDB 在线授权才能解压，未激活 = 体积数据无法解压 = Cube 占位。

**伴生**——`Missing custom version GUID: 3DC15BB1...`（5.5→5.7 Custom Version 不匹配），Asset Registry 标记 unloadable，但插件 Runtime 可绕过标准加载自行读取帧信息（所以有 Instantiating 日志）。

## 3. 被推翻的旧假设

| 旧判断 | 实际 |
|---|---|
| 静态采样器超限致 shader 崩 | ❌ 未超限；A45 日志无 shader 编译错误 |
| Volume None = 引用丢失 | ❌ D20 是资产没给；A45 是 License 没激活 |
| 自研引擎 RHI 冲突是根因 | ❌ RHI ensure 是伴生症状 |

## 4. ZibraVDB 三层判读法

| 层 | 形态 | 判读 |
|---|---|---|
| ① 源数据 | `.zibravdb`（私有压缩）/ `.vdb`（OpenVDB） | 看扩展名 |
| ② UE 资产 | uasset，类 `ZibraVDBAssetData` | 扫导出类名字表 |
| ③ 关卡引用 | umap 里 `ZibraVDBActor` | 有 Actor 无 uasset = 悬空 |

⚠️ `SparseVolumeTexture`/`VolumeTexture` ≠ ZibraVDB——那是 UE 原生 SVT。

## 5. 跨引擎 ABI 死结

主工程 ZibraVDB 为纯预编译二进制（无源码），DLL ABI 绑定 BuildId，跨引擎不可复用。要重编需源码（Studio 计划）。

## 6. 授权调查（2026-06-30 补充）

### 6.1 授权模型

ZibraVDB 当前版本 **1.5.3**，授权状态：**NotActivated**（INI 中 `ZibraLicensingSettings` 值全空）。

采用 **Floating License** 模式，支持三种激活方式：

| 方式 | 说明 | 适用场景 |
|---|---|---|
| **LicenseKey** | 在线输入 Key 激活，联网验证 | 开发机可联网 |
| **LicenseServer** | 指定 License Server 地址，浮动分配 | 团队多机共享 |
| **OfflineLicense** | 联网激活后导出离线授权文件，拷到隔离机器导入 | 内网隔离环境 |

⚠️ 三种方式**前提均需一个有效 License Key**——OfflineLicense 不是免授权旁路，只是把联网验证替换成文件验证。

### 6.2 免费密钥获取渠道

- **Fab 下载页**（`free-zibravdb-key`）：仅为 Fab 下载引导页，**不直接发放密钥**
- **Personal 免费版**：Fab 下载包**不附带** License Key（2026-07-01 实测确认），需邮件 **support@zibra.ai** 单独申请
- **外包方 License Key 不可复用**——需独立注册

### 6.3 激活入口

`Project Settings > Plugins > ZibraVDB License`

### 6.4 建议路径

1. **先用 Personal 免费 Key 做技术验证**——确认 A45 的 6 个 ZibraVDB Volume 能正常解压显示（消除占位 Cube）
2. 验证通过后走公司采购流程购买商用授权
3. 主工程若为内网隔离环境，拿到商用 Key 后用 OfflineLicense 方式离线激活

## 7. 授权申请邮件模板（2026-07-01 整理）

### 7.1 方案 A：Studio 商用授权（正式采购）

收件人：`support@zibra.ai`，主题：`Studio License Inquiry for ZibraVDB — Tencent`

英文正文要点：
- 团队：Tencent VFX/game dev team
- 引擎：UE 5.7，场景：.zibravdb 体积资产导入 + 离线/影视级 Sequence 渲染
- 需求：Floating License（并发席位）+ Local License Server（内网部署）
- 索取：报价、采购流程、License Server 部署文档、SDK 获取方式

### 7.2 方案 B：Personal 免费版 Key 申请（技术验证）

收件人：`support@zibra.ai`，主题：`Personal License Key Request for ZibraVDB (Evaluation)`

英文正文要点：
- 已从 Fab 安装插件但包内无 Key
- 申请 Personal（免费）License Key，2 台设备 Floating License
- 用途：技术评估——.zibravdb 导入/解压/体积渲染
- 平台：Windows，引擎：UE 5.7

### 7.3 临时验证方案（权宜之计）

- 业务排期等不了跨部门采购流程，临时使用第三方 DLL 绕过 License 验证做效果验证
- 正式发布前必须替换为正规商业授权
- ⚠️ 替换 DLL 版本与主工程现有 DLL 大小不一致（Licensing 414KB→233KB, Runtime 932KB→883KB, Editor 868KB→813KB），存在 ABI 兼容风险，替换前必须备份原件

## 8. D20 Sequence 实测状态（2026-07-01）

### 8.1 Sequencer 结构

主工程 Master Sequence → Camera Cuts 轨道 → 各 Shot 子序列（嵌套 Sub-Sequence）

D20 子序列现有轨道：
- `D20_cameraShape`（摄像机）
- `baiying`（绑定对象）
- `N_baiyin_D20_1`（Niagara，Sim Cache 242帧/4s，已烘焙）
- `N_baiyin_D20_2`（Niagara，Sim Cache 242帧/4s，已烘焙，含 Location 关键帧）

### 8.2 当前状态

- ✅ Niagara 特效可正常显示（Sim Cache 已烘焙）
- ✅ Transform/Location 关键帧在，特效有位移动画
- ❌ **灯光缺失**——Sequence 无灯光轨，关卡可能无 Light Actor
- ⚠️ **红色轨道名 + "bound object is missing"**——部分绑定对象在当前关卡找不到

### 8.3 待确认

1. 外包 D20 原始关卡 `Jlai_baiyin_D20.umap` 的 World Outliner 是否含灯光 Actor
2. 红色轨道右键提示的具体绑定丢失原因
3. 灯光是否由主工程侧负责（外包只做特效+摄像机）

## 9. 待办（更新）

- **获取 ZibraVDB License Key**——Personal 免费版需邮件申请（Fab 包不含 Key），Studio 版走采购
- **D20 补交 Volume uasset 或 .zibravdb 源文件**
- **D20 灯光排查**——确认外包关卡是否有灯光 Actor，或主工程侧补灯光
- **D20 红色轨道绑定修复**——右键检查 bound object missing 具体原因
- **E40 解压**——C30/C60 导入前必须先解压 E40（跨工程 ExternalActors 依赖）
- **D20 路径拼写错误**（`Asstes` → `Assets`）——已在主工程按错误路径放置资产，后续需批量修复引用

## 10. 归档复核修正（2026-07-01）

只读复核 `J:\vendors\漫行者\Final最终归档\BYDC` 后，修正两处早期误判：

1. **A45**：有 6 个大体积 `ZibraVDBAssetData` uasset（最大约 5.536GB），但未发现独立 `.zibravdb` 源文件。当前仍可作为 License 验证样本；正式交付仍应要求补独立源文件。
2. **B20**：9 个 `ZibraVDBAssetData` uasset + 9 个 `.zibravdb` 源文件均存在，是现有最完整的 ZibraVDB 闭包样本。
3. **C50**：仅 6 个极小 `ZibraVDBAssetData` uasset，未发现独立 `.zibravdb` 源，疑似低模/占位或测试资产。
4. **C60**：虽然 uproject 启用了 ZibraVDB，且文件名含 `vdb`，但资产头部标记为 UE 原生 `SparseVolumeTexture/VolumeTexture`，不是 `ZibraVDBAssetData`；不要把 C60 归入 ZibraVDB License 阻塞链。
