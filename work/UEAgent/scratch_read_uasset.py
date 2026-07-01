import os, re, sys

path = r"C:\Work\UEProject\Study\study\Content\Test\Plan2\EUW_DyeBake.uasset"
print('size:', os.path.getsize(path))

with open(path, 'rb') as f:
    data = f.read()

strs = re.findall(rb'[\x20-\x7e]{5,}', data)
seen = set()
paths = set()
idents = set()
for s in strs:
    t = s.decode('latin-1', errors='replace')
    if t in seen:
        continue
    seen.add(t)
    if t.startswith('/') and ('/Game/' in t or '/Script/' in t):
        paths.add(t)
    elif re.match(r'^[A-Za-z_][A-Za-z0-9_]{3,60}$', t):
        idents.add(t)

print('\n=== Paths (refs) ===')
for p in sorted(paths):
    print(' ', p)

print(f'\n=== Identifiers ({len(idents)}), filtered ===')
# 过滤明显引擎噪音
noise_prefix = ('Edit', 'Kismet', 'Object', 'Widget', 'Blueprint', 'Default', 'Class')
keep = [i for i in idents if not any(i.startswith(n) for n in noise_prefix)]
for i in sorted(keep):
    print(' ', i)
