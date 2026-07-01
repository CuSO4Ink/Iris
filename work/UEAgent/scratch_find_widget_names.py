import re, os, sys

p = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\EUW_DyeBake.uasset"
data = open(p, "rb").read()
strs = {s.decode("latin-1", "replace") for s in re.findall(rb"[\x20-\x7e]{3,}", data)}

# 关键词过滤：你新命名的三个 Border
keys = ["Diffuse", "Init", "Bake", "Setting", "setting"]

# 留下看起来像 widget / 变量名的
candidates = set()
for s in strs:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{1,60}$", s):
        continue
    if s in ("None", "True", "False", "Object", "Class", "Function"):
        continue
    if s.startswith("K2Node_") or s.startswith("CallFunc_"):
        continue
    candidates.add(s)

# 一：直接 match keys
print("=== matches keys (Diffuse/Init/Bake/Setting) ===")
hits = sorted(c for c in candidates if any(k in c for k in keys))
for h in hits:
    print(" ", h)

# 二：所有 Border 命名
print()
print("=== anything with Border ===")
for h in sorted(c for c in candidates if "Border" in c):
    print(" ", h)

# 三：打印所有候选中长度 >=8 的驼峰
print()
print("=== CamelCase >=8 chars (potential widget names) ===")
camel = sorted(c for c in candidates if len(c) >= 8 and re.search(r"[a-z][A-Z]", c))
for h in camel[:80]:
    print(" ", h)
