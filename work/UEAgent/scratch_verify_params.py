import re, os

p = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\NS_DyeBaker.uasset"
data = open(p, "rb").read()

# 关键：看 "Damping" 在文件里出现几次 + 周围上下文
target = b"Damping"
positions = [m.start() for m in re.finditer(target, data)]
print(f"'Damping' occurrences: {len(positions)}")
for pos in positions[:5]:
    ctx = data[max(0, pos-60):pos+60]
    # 只打印可见字符
    visible = "".join(chr(b) if 32 <= b < 127 else "." for b in ctx)
    print(f"  @{pos}: ...{visible}...")

# 同样扫一下其他几个我列的关键参数
print()
for name in [b"DiffuseStrength", b"BaseStep", b"BaseDt", b"ForceStrength", b"Gamma", b"ArcScale",
             b"ArrivalThreshold", b"MinGradientValue", b"NoiseIntensity", b"NoiseScale",
             b"InitSpeed", b"MinSpacing", b"ForceDecay", b"ForceDirection", b"DomainSize",
             b"SeedRadius"]:
    n = len(re.findall(name, data))
    print(f"  {name.decode():20s} -> {n} hits")
