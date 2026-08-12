import json
p = r'C:/Work/AI/Iris/work/ScreenSpaceParticleReconstruction/_out_emitterdata2.json'
d = json.load(open(p, encoding='utf-8'))
rv = d.get('data', {})
rv = rv.get('returnValue', rv)
pv = rv.get('propertyValues', rv) if isinstance(rv, dict) else rv
print('TYPE', type(pv).__name__)
if isinstance(pv, dict):
    for k, v in pv.items():
        print(k, '=', str(v)[:80])
elif isinstance(pv, list):
    for item in pv:
        print(item)
