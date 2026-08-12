import json
p = r'C:/Work/AI/Iris/work/ScreenSpaceParticleReconstruction/_out_emitterdata2.json'
d = json.load(open(p, encoding='utf-8'))
print(json.dumps(d.get('data', d), ensure_ascii=False, indent=1)[:2500])
