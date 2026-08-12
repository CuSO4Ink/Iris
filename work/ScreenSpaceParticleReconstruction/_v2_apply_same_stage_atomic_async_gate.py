ROOT = r"C:\Work\AI\Iris\work\ScreenSpaceParticleReconstruction"


def run_script(name):
    exec(open(ROOT + "\\" + name, encoding="utf-8").read(), {
        "__name__": "__main__",
    })


run_script("_v2_probe_same_stage_atomic.py")
run_script("_v2_select_main_actor.py")
