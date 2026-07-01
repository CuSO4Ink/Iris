import re

p = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\EUW_DyeBake.uasset"
data = open(p, "rb").read()
strs = {s.decode("latin-1", "replace") for s in re.findall(rb"[\x20-\x7e]{3,}", data)}

# 找所有以 "Setting" 开头/结尾 或 含 Panel/Box 的候选名
keys_end = ["Setting", "Box", "Panel", "Container"]
keys_start = ["Diffuse", "Init", "Bake", "VB_", "HB_"]

print("=== names containing container/setting keywords ===")
found = set()
for s in strs:
    if not re.match(r"^[A-Za-z_][A-Za-z0-9_]{2,60}$", s):
        continue
    if any(s.endswith(k) for k in keys_end) and s not in ("SlateChildSize","HorizontalBox","VerticalBox","CanvasPanel","SizeBox","Box","Panel"):
        found.add(s)
    if any(s.startswith(k) for k in keys_start):
        found.add(s)

for f in sorted(found):
    print(" ", f)
