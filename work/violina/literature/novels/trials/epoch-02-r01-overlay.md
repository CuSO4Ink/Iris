# Epoch 02 · Round 01 · Overlay

- 状态：`NONE`
- 登记时间：2026-07-19（见候选前）
- WriterSystemBaseline SHA-256：`5773D170EDAE15D38C9FA863BF720FC25FA8FECA3F9ED65A35C33C9B433C1B3E`
- WriterSystemCalibration SHA-256：`BA3AD4CAF4B2F91D651C5C8C9D3D47BD9A16772B4142666E65D73865ECA67893`
- Frame H SHA-256：`CB4AE2BB2AB015EB22FB886C5336AF8D0FE0CD3A0F88F33B1B87BF1FF0F98A94`
- Frame L SHA-256：`76BA18439B9ACF304EE33C1C4F72ED1BC2AE6EC6977498813349E3D14EBADD9B`
- Candidate H 原稿：4969 个汉字／5898 个非空白 Unicode 字符；SHA-256 `30B780CBB4F28B4A6BE42A5DA8B855641D7BF0C1E53F28C91973368E8F783021`
- Candidate L 原稿：4417 个汉字／5265 个非空白 Unicode 字符；SHA-256 `B77C137FF9EE24D60392D8FDDC2E8DEC07787B9CEA5F5769E7E14D2983DCD148`
- 生成结果边界：Frame 使用“中文字符／汉字”口径，两篇均在 3000—5000 内；原稿冻结，不裁切、不换种子。
- 生成拓扑：冻结 `WriterSystemBaseline` → 冻结 `WriterSystemCalibration` → 对应冻结 H/L GenerationFrame → 输出边界；单写手一次直写。
- 相对 Epoch 02 冻结直写基线的差异：无。
- 候选：H/L 各一篇，每篇一次正式生成，目标 3000—5000 中文字符。
- 主指标：通过硬闸门后的五人来源盲测；中位数 `< 50%` 且多数判断更像人写。
- 回滚：Round 01 本身即冻结基线，无 overlay 可撤销。
- Canon：本轮不提交 StoryAuthority。
