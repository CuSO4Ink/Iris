RimWorld 1.6 整套 mod 配置安装说明(2026-09-10 导出)
====================================================
内容:Mods\ 下 3 个本地 mod(ZHBundle 聚合汉化 / IrisBalance 数值补丁 /
IrisFixes 兼容性修复)、Config\ModsConfig.xml(267 条启用清单与加载顺序)、
workshop_ids.txt(258 个工坊 mod,按加载顺序)。

安装步骤
1. 前提:RimWorld 1.6 + 全部 5 个 DLC(皇权/文化/生物技术/异象/奥德赛)。
   若缺某个 DLC:用文本编辑器打开 Config\ModsConfig.xml,删掉对应那行
   <li>ludeon.rimworld.xxx</li> 再继续,否则启动会报缺失。
2. 工坊 mod:让对方按 workshop_ids.txt 订阅全部 258 个。最省事的做法是
   你在 Steam 社区建一个「合集」(collection),把 258 个 id 全加进去,
   对方订阅合集即一键全订;Steam 无「文本批量订阅」通道,合集是唯一批量方式。
   单条订阅链接格式:https://steamcommunity.com/sharedfiles/filedetails/?id=<pfid>
3. 本压缩包 Mods\ 下三个文件夹复制进对方游戏目录的 Mods\(游戏关闭状态)。
4. 本压缩包 Config\ModsConfig.xml 复制进对方玩家配置目录
   (Windows: %LOCALAPPDATA%Low\Ludeon Studios\RimWorld by Ludeon Studios\Config\),
   覆盖前先备份对方原文件。
5. 启动游戏:Mod 界面应显示 267 条启用、无红字缺失。

注意
- 云存档只同步存档、不带 mod;mod 靠订阅(工坊)与手动复制(本地)到位。
- mod 设置(GD5 威胁规模 50%/炮塔 70%、EndlessGrowth maxLevel 30 且关
  unlimitedPrice 等)存在存档里:玩导出方的存档则自带;开新档需按上述值重设。
- IrisBalance/IrisFixes 是按导出方的 mod 清单与版本写的补丁:对方缺某个目标
  mod 或目标 mod 大改版时,对应补丁静默不生效(FindMod 不命中=跳过),不会崩。
- ZHBundle 为纯翻译,独立可用。

ZHBundle(聚合汉化,合并自 71 个翻译包)已随本仓库 Mods\ 分发,经所有者确认承担再分发责任;
安装时把 Mods\ZHBundle 整个文件夹放入游戏 Mods\ 目录即可。
