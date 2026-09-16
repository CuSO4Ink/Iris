# Iris Ritual Recruitment

独立仪式招募种族白名单。首次安装需重启；随后可在 MOD 设置 → Iris 仪式招募白名单 中随时勾选。默认仅允许 Kiiro_Race；新增种族不会自动勾选。

- 仅作用于原版 RitualAttachableOutcomeEffectWorker_RandomRecruit 奖励流程，保留原本50%触发判定、仪式信仰与其他生成参数。
- 在 WalkIn 最终 GeneratePawn 请求处选定普通居民模板，晚于 HAR 的玩家派系种族替换。非仪式上下文原样生成。
- 每个已勾选种族一个候选、种族间等概率。标准居民类型优先；拒绝名字标识为 Child/Baby/Slave/Boss/Leader/Royal/Combat/Special 的自动候选。这里的识别是保守命名规则，不是全 MOD 语义鉴定。界面仅列出可识别普通居民模板的类人种族，并显示居民名称；没有模板的种族不猜选。
- 空或全部失效的白名单会取消本次招募奖励，并提供说明，不回退到未授权种族。支持禁用开关恢复原逻辑。
- 只筛 race，不筛同一 race 下的 xenotype；不额外强制性别或性取向。已有角色、普通流浪者、种族专属任务不修改。
- 当前 Def 白名单按实际种族保存；未启用/卸载种族的勾选可留存，恢复该种族后重新可用。

验证：编译零警告/错误；离线真实类型测试覆盖默认名单、空名单、单种族排他、模板去重、Boss/幼儿过滤、异常恢复上下文和实际游戏 IL 唯一生成调用替换。未启动游戏，不宣称完成运行时UI/招募验收。

Source: Source/RitualRecruitment.cs. 本地启用 local.irisritualrecruitment，位于 HAR 和其他本地补丁之后。
