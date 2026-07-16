# D10 脚本调试复盘：Spawnable 缩放恢复的 7 次失败

> **时间**：2026-07-16 15:10 ~ 16:00（约 50 分钟）
> **脚本**：`d10_integrate_level_actors.py`
> **目标**：将 D10 关卡中的 ZibraVDB Actor 接入 Sequence，转为 Spawnable，恢复 Scale `(1, -1, 1)`
> **结果**：Actor 接入与 Spawnable 转换最终成功，但运行时缩放始终被 ZibraVDB 组件覆盖为 `(1, 1, 1)`，未通过脚本完全解决

---

## 背景

D10 关卡 `/Game/FX_D10/Level/D10_gk` 中有一个 ZibraVDB Actor（`ZibraVDBActor_1`），Scale 为 `(1, -1, 1)`（Y 轴翻转）。需要将其接入 FX Sequence `/Game/FX_D10/Level/D10_sequence`，转为 Spawnable，并恢复缩放。此前 C40/C50 已用相同路线成功，但 D10 遇到了一系列 API 兼容性与组件行为差异问题。

---

## 失败时间线

### 第 1 次：`LevelSequenceEditorBlueprintLibrary.add_actors` 不存在

**报错**：`AttributeError: LevelSequenceEditorBlueprintLibrary has no attribute add_actors`

**原因**：UE 5.7.3 中该 API 已移至 `LevelSequenceEditorSubsystem`。

**修复**：改用 `unreal.get_editor_subsystem(unreal.LevelSequenceEditorSubsystem).add_actors(missing)`。

**教训**：C40 调试记录中已验证过正确 API，但 D10 脚本初版沿用了旧写法，未从已有经验复用。

---

### 第 2 次：`set_actor_location()` 缺少 `sweep` 参数

**报错**：`TypeError: set_actor_location() required argument 'sweep' (pos 2) not found`

**原因**：5.7.3 的 Spawnable Object Template 的 `set_actor_location()` 签名与普通 Actor 不同，不接受单参数调用。

**修复**：移除 Location/Rotation 写入，仅保留 Scale 恢复。

**教训**：Spawnable Object Template 不是完整的 Actor 实例，部分 Actor API 行为不同。

---

### 第 3 次：`repair_d10_scale()` 无效果——Sequence 没有 Transform Track

**现象**：脚本尝试写入 Transform Track 的 Scale 通道，但日志输出 `transform diagnostic sections=0`。

**原因**：D10 Sequence 中 ZibraVDB binding 下不存在 Transform Track，脚本按通道索引 `[6:9]` 写入的逻辑完全落空。

**结论**：不能假设所有 Spawnable binding 都有 Transform Track。D10 的缩放问题不在轨道层。

---

### 第 4 次：诊断函数 `diagnose_d10_spawnable_template()` 无法命中 binding

**现象**：函数重新加载关卡并重新打开 Sequence，但输出 `current sequence template matches=0`。

**原因**：
1. 重新加载关卡后，`load_asset(fx)` 拿到的 asset 对象与编辑器当前打开的 Sequence 状态不一致；
2. binding 名称筛选条件 `cloud/zibravdb` 没有命中实际 binding 名称。

**修复**：改为不重新加载关卡，直接读取当前已打开的 Sequence（`get_current_level_sequence()`）。但仍然 `matches=0`。

**教训**：UE Python 中 `load_asset()` 返回的对象与编辑器当前打开的 asset 可能不是同一个实例，尤其在关卡重新加载后。诊断脚本应优先使用编辑器当前上下文。

---

### 第 5 次：`add_actors()` 返回 UE `Array`，脚本未正确展开

**报错**：`binding_name(Array)` — 试图把整个 `unreal.Array` 当作单个 binding 处理。

**原因**：`add_actors()` 返回 `unreal.Array`，不是 Python `list/tuple`。脚本用 `isinstance(result, (list, tuple))` 判断失败，把整个 Array 包成单元素列表。

**修复**：改为 `returned = list(result)`，利用 Python 迭代协议展开 UE Array。

**教训**：UE Python 的 `unreal.Array` 实现了 `__iter__`，可以用 `list()` 展开，但不能用 `isinstance` 判断类型。

---

### 第 6 次：`add_actors()` 返回值不是 binding，是空 Array

**现象**：`add_actors returned: <Array ...>`，但 `list(result)` 展开后为空。

**原因**：UE 5.7.3 的 `LevelSequenceEditorSubsystem.add_actors()` 返回值不是新增 binding 列表，而是其他类型（可能是操作结果或空 Array）。

**修复**：改为**前后 binding ID 差集**识别新增 binding：
```python
before_ids = {str(b.get_id()) for b in get_bindings(sequence)}
subsystem.add_actors(missing)
after = list(get_bindings(sequence))
added = [b for b in after if str(b.get_id()) not in before_ids]
```

**教训**：`add_actors()` 的返回值在 5.7.3 不可靠。用前后差集是更稳健的方式，这一经验已在 working_memory 中记录。

---

### 第 7 次：缩放值在 `add_actors()` 后被重置为 `(0, 0, 0)`

**现象**：`restored returned binding scale: D10_cloud_01_v01 -> (0, 0, 0)`

**原因**：脚本在 `add_actors()` 之后才读取 `actor.get_actor_scale3d()`，但 `add_actors()` 改变了关卡 Actor 的临时状态，Scale 已被重置。

**修复**：在**任何 Sequence 操作之前**缓存场景 Actor 的 Scale：
```python
captured_scales = [actor.get_actor_scale3d() for actor in actors]
# ... add_actors, convert_to_spawnable ...
scale = scales[index]  # 用缓存值
```

**教训**：`add_actors()` 会修改关卡 Actor 状态。所有需要从关卡 Actor 读取的属性必须在调用前缓存。

---

### 中间 Bug：残留变量 `actors` 导致连续 3 次 `NameError`

在修复第 7 次问题时，将函数签名从 `convert_bindings_and_restore(bindings, actors)` 改为 `(bindings, scales)`，但函数体内仍有多处引用 `actors`。由于 PowerShell 字符串替换未命中实际文件内容（换行符差异），连续 3 次执行都报 `NameError: name 'actors' is not defined`，最终用 `[regex]::Replace()` 才彻底清除。

**教训**：
1. 重构函数签名时必须全文搜索所有引用，不能只改定义处；
2. PowerShell 的 `.Replace()` 对多行字符串匹配不可靠，应使用正则或逐行处理；
3. 每次修改脚本后应在本地校验（至少 `grep` 一遍 `actors`）再让用户执行。

---

## 最终结论

经过 7 次失败 + 多次中间 Bug，脚本最终成功完成了：
- Actor 接入 Sequence（前后 binding 差集识别）
- Spawnable 转换
- Actor Template Scale 写入 `(1, -1, 1)`

**但画面缩放仍为 `(1, 1, 1)`**，确认 ZibraVDB 组件运行时会覆盖 Actor Template Scale。后续尝试写入组件 `relative_scale3d` 也未能解决。

最终 D10 通过**手动在编辑器中调整组件缩放**完成导入，脚本未能完全自动化缩放恢复。

保存阶段还触发了 32 位数组索引溢出崩溃（`Array index out of bounds: 2147483648`），疑似超大 ZibraVDB 资产序列化问题。

---

## 经验总结

| 问题 | 根因 | 正确做法 |
|------|------|---------|
| `add_actors` API 不存在 | 5.7.3 API 迁移 | 用 `LevelSequenceEditorSubsystem.add_actors()` |
| `set_actor_location` 参数不兼容 | Spawnable Template 非完整 Actor | 避免对 Template 调用需要 sweep 参数的 API |
| Transform Track 不存在 | D10 没有变换轨道 | 诊断时先检查轨道是否存在，不能假设 |
| 诊断函数拿不到 binding | `load_asset` 与编辑器状态不一致 | 用 `get_current_level_sequence()` |
| `add_actors` 返回 UE Array | 类型不兼容 | `list(result)` 展开 |
| 返回值不是 binding | 5.7.3 返回值不可靠 | 用前后 binding ID 差集 |
| Scale 被重置为 (0,0,0) | `add_actors` 修改 Actor 状态 | 操作前缓存 Scale |
| 残留变量 NameError | 重构不彻底 | 改完后全文搜索 + 本地校验 |
| 运行时 Scale 仍为 (1,1,1) | ZibraVDB 组件覆盖 Template Scale | 需写组件 `relative_scale3d`，或手动调整 |

---

## 涉及文件

- 脚本：`C:\Work\AI\Iris\output\d10_integrate_level_actors.py`
- D10 关卡：`/Game/FX_D10/Level/D10_gk`
- D10 Sequence：`/Game/FX_D10/Level/D10_sequence`
- D10 VDB：`D10_cloud_01_v01`（156 帧，1056×600×1192）
- 崩溃日志：`D:\Work\Company\UE\Jianlai\TMR\UnrealEngine\Games\JyGame\Saved\Crashes\UECC-Windows-28916D6E49F9B0776A6CC994EA7F694C_0002\JGame.log`
