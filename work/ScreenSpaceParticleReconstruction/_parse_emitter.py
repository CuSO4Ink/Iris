import json, re, sys
p = r'C:/Work/AI/Iris/work/ScreenSpaceParticleReconstruction/_out_emitterdata2.json'
d = json.load(open(p, encoding='utf-8'))
rv = d.get('data', {})
rv = rv.get('returnValue', rv)
s = json.dumps(rv, ensure_ascii=False)
print('INTERP_FIELDS:', re.findall(r'"[A-Za-z_]*[Ii]nterp[A-Za-z_]*"\s*:\s*[^,}\]]+', s))
print('SPAWN_FIELDS:', re.findall(r'"[A-Za-z_]*[Ss]pawn[A-Za-z_]*"\s*:\s*[^,}\]]+', s)[:10])
if isinstance(rv, dict):
    print('TOP_KEYS:', list(rv.keys()))
