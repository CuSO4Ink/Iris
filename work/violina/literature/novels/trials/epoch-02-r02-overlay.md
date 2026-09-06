# Epoch 02 · Round 02 · Overlay

- 状态：`FAILED — CONFIRMATION A PASS; CONFIRMATION B FAIL-LOCKED 6/7; ROLLED BACK`
- 登记时间：2026-07-19（见 Round 02 候选前）
- WriterSystemBaseline SHA-256：`5773D170EDAE15D38C9FA863BF720FC25FA8FECA3F9ED65A35C33C9B433C1B3E`
- WriterSystemCalibration SHA-256：`BA3AD4CAF4B2F91D651C5C8C9D3D47BD9A16772B4142666E65D73865ECA67893`
- Frame H SHA-256：`CB4AE2BB2AB015EB22FB886C5336AF8D0FE0CD3A0F88F33B1B87BF1FF0F98A94`
- Frame L SHA-256：`76BA18439B9ACF304EE33C1C4F72ED1BC2AE6EC6977498813349E3D14EBADD9B`
- 写手、审校员、来源读者与文学读者：统一冻结 `gpt-5.6-sol / high`。

## 本轮登记

- overlay：`NONE — FROZEN BASELINE REPLICATION`
- 相对 Round 01 的架构差异：无。
- 生成拓扑：逐字 WriterSystemBaseline → 逐字 WriterSystemCalibration → 对应冻结 H/L GenerationFrame → 输出边界；单写手一次直写。
- 候选固定：H/L 各一名全新 `fork_turns: none` 写手、各一次正式生成；不换种子、不补写、不筛选多候选。
- Candidate H：4497 个汉字／5255 个非空白 Unicode 字符；SHA-256 `C373627B8AD974074BCC7E38CC03F66907639DDA842E5B1CB370D70DCB643849`。
- Candidate L：4440 个汉字／5384 个非空白 Unicode 字符；SHA-256 `1B129AEE2F2F4885640B86A73F9AC73030C896007E8FDC88D39523CC91C37409`。
- Confirmation B Candidate：4706 个汉字／5451 个非空白 Unicode 字符；SHA-256 `526DD2F8761B6CC8D211C19BC14A844568026FE4CC415E4D6A8CD470CEA08DAB`；全新未见文本截面，仅用于确认 B，不进入 StoryAuthority。

## 依据与反证

Round 01 的 H 以三票“更像 AI”形成 `FAIL-LOCKED 3/5`；L 五人中位数 `58%`、三票“更像 AI”。跨 H/L 的重复证据指向完整场景材料被过度统一组织为关系意义网络。但历史索引已封存信息裁切、私下认知、分段接力、双脉冲、多候选选择等相近支路；当前没有一个既真正新增、又不违反冻结系统和单写手边界的架构差异可安全归因。

因此本轮不从单轮失败临时制造提示词，也不擅自更换模型。复跑冻结基线，用第二组 H/L 估计采样噪声和失败机制的可复现性，再决定 Round 03 是否存在可登记的新变量。

最强反证是 Round 01 已有跨 H/L、多读者重复证据，纯复跑可能不改善来源指标；其价值只在于区分稳定机制与单轮样本波动，不能把偶然单篇低分自动解释为架构改善。

## 指标与撤销

- 硬指标：各候选先通过完整有效性硬闸门；有资格者再按五人来源协议测试。
- 来源通过线：AI 概率中位数 `< 50%`，且多数读者判断“更像人写”。
- 复现判断：比较 Round 01 与 Round 02 的 H/L 分布、最早判断位置、重复证据与反证；无架构差异时不声称因果改善。
- 回滚：本轮没有 overlay 差异可撤销；Round 03 仍从同一冻结基线登记独立变量或再次复跑。
- Canon：本轮不提交 StoryAuthority。
