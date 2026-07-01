import re

p = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\EUW_DyeBake.uasset"
data = open(p, "rb").read()
# 所有 ASCII 字符串
raw = [s.decode("latin-1", "replace") for s in re.findall(rb"[\x20-\x7e]{3,}", data)]

# 策略：在 "DiffuseSetting" 字样出现位置的前后 500 字节里找候选名
target = b"DiffuseSetting"
positions = [m.start() for m in re.finditer(target, data)]
print(f"'DiffuseSetting' positions: {len(positions)}")

# 每个位置附近的上下文
for pos in positions:
    left = max(0, pos - 200)
    right = min(len(data), pos + 200)
    ctx = data[left:right]
    # 提取相邻的所有字符串
    tokens = [s.decode("latin-1", "replace") for s in re.findall(rb"[\x20-\x7e]{3,}", ctx)]
    print(f"\n@{pos}:")
    for t in tokens:
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]{2,60}$", t):
            print(f"   {t}")
