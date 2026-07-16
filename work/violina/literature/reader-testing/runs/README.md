# Test Runs

每次测试使用独立目录：

```text
RT-YYYYMMDD-NNN/
├─ manifest.md
├─ packets/
│  ├─ packet-a.md
│  └─ packet-b.md
├─ responses/
│  ├─ reader-01.md
│  └─ reader-02.md
└─ report.md
```

- `manifest.md` 与版本映射属于内部信息，不发送给盲测读者。
- `packets/` 中每个文件必须能够脱离项目独立使用。
- `responses/` 保存原始回答；汇总和解释只写入 `report.md`。
- 测试冻结后不修改原始 packet 和 response；需要修订时建立新的 Run ID。
