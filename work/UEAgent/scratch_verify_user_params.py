import re, os

p = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\NS_DyeBaker.uasset"
data = open(p, "rb").read()

# 找 ScatterRadius 的所有出现及上下文
for target in [b"ScatterRadius", b"User.ScatterRadius", b"User.SeedCount", b"SeedCount",
               b"User.DiffuseStrength", b"DiffuseStrength"]:
    positions = [m.start() for m in re.finditer(target, data)]
    print(f"\n'{target.decode()}': {len(positions)} hits")
    for pos in positions[:3]:
        ctx = data[max(0, pos-80):pos+80]
        visible = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
        print(f"  @{pos}: ...{visible}...")
