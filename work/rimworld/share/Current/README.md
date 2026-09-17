# RimWorld 当前跨设备配置包

导出日期：2026-09-16。以本机关闭游戏后的实际安装文件和参数为准。

本目录 Current 是当前安装入口；上一层的 Mods、Config、workshop_ids.txt 为旧分享包，不要混用。

| 目录 | 内容 | 安装目标 |
|---|---|---|
| Mods/ | 8 个已启用本地模组的运行文件，含实际安装的 DLL、补丁、翻译及资源 | RimWorld/Mods/ |
| Config/ModsConfig.xml | 272 项启用列表，保留完整加载顺序 | 玩家数据目录/Config/ |
| Settings/ModSettings/ | 144 份 ModSettings，含 Defaults、战斗平衡、人才、招募、灵能及关系等参数 | 玩家数据目录/Config/ |
| Settings/Game/ | 游戏偏好、键位及其他全局设置 | 玩家数据目录/Config/ |
| Settings/UserData/ | HugsLib 参数、RimHUD 配置、米莉拉全局图鉴 | 玩家数据目录，保留相对路径 |
| Manifests/mods.tsv | 按顺序记录包名、工坊 ID、声明版本和本地目录 | 对照用 |
| workshop_ids.txt | 258 个工坊订阅 ID | Steam 下载 |
| Install.ps1 | 检查、备份并安装完整配置 | 见下方 |

## 另一台机器如何恢复

1. 使用 RimWorld 1.6，导出机版本为 **1.6.4871 rev591**，安装 Royalty、Ideology、Biotech、Anomaly、Odyssey 五个 DLC。
2. 拉取此仓库。通过 Steam 订阅并完成下载 workshop_ids.txt 中的全部 258 个模组。同一个 Steam 账号通常已有订阅，仍需等待该机器下载完成。
3. 保存并完全退出游戏。进入本目录，在 PowerShell 执行（修改游戏路径）：

```powershell
.\Install.ps1 -GamePath 'E:\SteamLibrary\steamapps\common\RimWorld' -ValidateOnly
.\Install.ps1 -GamePath 'E:\SteamLibrary\steamapps\common\RimWorld'
```

安装脚本会确认包名、工坊下载和 DLC；缺失时不开始安装。替换前把已有本地模组和将覆盖的设置备份到玩家数据目录的 TransferBackups/时间戳。模组列表最后写入，避免使用不完整配置。**不会复制、编辑或覆盖 Saves。**

4. 在本地重新填写 AI 服务密钥：详见 Manifests/private-fields.json（只记录字段名，不含秘密）。模型、提示词和其他行为参数已保留。两份 AI 配置的密钥已清空；未填写前相关在线对话功能不能保证正常调用。
5. 开游戏，确认 272 项启用且没有缺失模组，再读取 Steam 云存档。

## 存档列表与当前配置的已知差异

导出时最新存档记录 270 项，当前配置为 272 项；新增的是：

- steve.vpe.revertsomenerf：VPE: Revert Some Nerfs (Continued)。
- local.irisstoragedefaults：Iris Storage Defaults。

这是最近主动添加造成的预期差异。读取时保留当前列表，不要用“从存档载入 Mod 列表”覆盖它。VPE 模组会处理旧献祭状态；储存规则更新的是 Defaults 模板，不会自动覆写已有柜子、已有小人的食物方案或现有账单。

## 一致性与范围

- 6 个官方内容 + 258 个工坊模组 + 8 个本地模组 = 272 项。
- 本地模组导出自安装目录，不混入尚未部署的 IrisFixes 性能分析器源码或构建版本。
- 144 份参数文件包含部分已停用模组留下的参数；这些不会自行启用对应模组，保留是为了避免误漏同一模组的设置类。
- 原始参数除两份配置的密钥外按字节复制。已核对启用列表完整、包名可解析，所有已复制运行文件与本机相同。
- 不上传存档、日志、贴图缓存、编辑器缓存、旧备份。IrisFixes 的 DiagnosticsOutputPath.txt 含导出机临时采样路径，未携带；因此目标机默认不进行那套临时诊断文件采样，游戏规则不受影响。
- Steam 工坊仍会自动更新第三方模组；本包同步的是当前本地补丁和参数，不锁定第三方工坊二进制版本。若另一台机器的工坊内容更新了，不能据此保证行为逐字节相同。
- 安装检查在本机通过；没有在另一台机器实际启动验证，也没有为测试启动游戏。

## 8 个本地模组

IrisTextureBudget、ZHBundle、IrisBalance、IrisFixes、IrisTalentProgression、IrisRitualRecruitment、IrisStorageDefaults。

无需重新编译。保留原目录名称，否则一些以目录名保存的 ModSettings 可能读不到。

## 残疫袭击频率更新

IrisBalance 已包含 8 种残疫专属事件的权重调整。尸潮和中心空投改为大型威胁；共用冷却默认 3 个游戏日，在 Iris 袭击平衡设置中可调整。冷却跨地图并随存档保存；第一次加载补丁给 3 天缓冲。任务／强制事件和地图上已有的巢穴刷怪不拦截；正常随机袭击冷却期间不选择残疫派系。不会取消已排队专属事件转出的真正 RaidEnemy。

## 空洞骑士第一版平衡

已加入独立 XML 补丁：收敛快速劈砍、力量护符、Boss永久奖励和两项特殊角色特性的全局倍率。Boss阶段机制保持不变。详细前后数值见 Manifests/HollowKnightBalance.md。无新增模组，仍为272项；需要重启生效，未做独立实战启动测试。

空洞武器补充调整：格林亲族可制作法杖、纯粹骨钉、巨型骨钉、冠军之锤已收敛数值。法杖使用独立玩家版弹丸，未改动Boss/召唤物共用弹丸。详见 Manifests/HollowKnightWeapons.md。

## 兽耳屋本体本地恢复

KemomimihouseLocal 已替代失效的工坊条目2075974335，保留原 packageId psyche.kemomimihouse 和原启用位置。使用9月10日本机备份的XML/DLL，并合并此前恢复的203张贴图。总数仍272项：258工坊、8本地、6官方；144份参数。不要再次同时启用同包名的工坊本体。完全重启后生效；尚未做新的运行验证。
