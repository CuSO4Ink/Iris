"""
GaussianVolume MVP — 场景 / 复现脚本
程序化生成一团 Gaussian cloud，渲染主图 + debug view，并跑 candidate 曲线。
输出 PNG 到 output 目录。
"""
import sys, os, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaussian_volume import GaussianCloud, render, candidates_along_ray


def random_quats(n, rng):
    q = rng.normal(size=(n, 4))
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def make_cloud(n, rng, radius=2.2):
    """球状团块内程序化撒 Gaussian primitives，中心密、边缘稀。"""
    # 中心向内聚集
    u = rng.random(n) ** 0.6
    dirv = rng.normal(size=(n, 3))
    dirv /= np.linalg.norm(dirv, axis=1, keepdims=True)
    center = dirv * (u * radius)[:, None]
    # 各向异性 scale
    scale = rng.uniform(0.25, 0.6, size=(n, 3))
    quat = random_quats(n, rng)
    # 中心密度高
    r = np.linalg.norm(center, axis=1)
    sigma_t = 3.5 * np.exp(-(r / radius) ** 2) + 0.4
    albedo = np.tile(np.array([0.92, 0.94, 1.0]), (n, 1))
    return GaussianCloud(center, scale, quat, sigma_t, albedo)


def to_srgb(img):
    img = np.clip(img, 0, None)
    img = img / (1.0 + img)                 # Reinhard tonemap
    return np.clip(img ** (1 / 2.2), 0, 1)


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(7)

    N = 1024
    cloud = make_cloud(N, rng)
    cam = np.array([0.0, 0.5, 7.0])
    target = np.array([0.0, 0.0, 0.0])
    light_dir = np.array([-0.6, 0.8, 0.4])
    light_color = np.array([1.5, 1.4, 1.2])
    ambient = np.array([0.10, 0.12, 0.16])

    W, H = 200, 150
    t0 = time.time()
    res = render(cloud, cam, target, 45.0, W, H,
                 light_dir, light_color, ambient)
    dt = time.time() - t0
    print(f"[render] N={N} {W}x{H} took {dt:.2f}s "
          f"({W*H/dt:.0f} ray/s)")

    # ---- 主图 ----
    plt.figure(figsize=(6, 4.5))
    plt.imshow(to_srgb(res["color"]))
    plt.axis("off")
    plt.title(f"Gaussian Volume MVP (N={N}, single scatter)")
    plt.tight_layout()
    main_png = os.path.join(out_dir, "mvp_render.png")
    plt.savefig(main_png, dpi=130, bbox_inches="tight")
    plt.close()

    # ---- debug 拼图 ----
    fig, ax = plt.subplots(1, 3, figsize=(13, 4))
    im0 = ax[0].imshow(res["optical_depth"], cmap="magma")
    ax[0].set_title("optical depth (tau)"); ax[0].axis("off")
    fig.colorbar(im0, ax=ax[0], fraction=0.046)
    im1 = ax[1].imshow(res["transmittance"], cmap="viridis")
    ax[1].set_title("transmittance T"); ax[1].axis("off")
    fig.colorbar(im1, ax=ax[1], fraction=0.046)
    im2 = ax[2].imshow(res["candidates"], cmap="cividis")
    ax[2].set_title("candidate count / ray"); ax[2].axis("off")
    fig.colorbar(im2, ax=ax[2], fraction=0.046)
    plt.tight_layout()
    dbg_png = os.path.join(out_dir, "mvp_debug.png")
    plt.savefig(dbg_png, dpi=120, bbox_inches="tight")
    plt.close()

    cmax = int(res["candidates"].max())
    cmean = float(res["candidates"][res["candidates"] > 0].mean())
    print(f"[candidates] max={cmax} mean(non-empty)={cmean:.1f} "
          f"of N={N} ({100*cmean/N:.1f}%)")

    # ---- candidate 曲线：不同 primitive 数下，每条 ray 平均 candidate ----
    counts = [512, 1024, 2048, 4096, 8192]
    means, maxs = [], []
    # 固定一束中心区域的 ray 做采样统计
    fwd = (target - cam); fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    half = np.tan(np.radians(45.0) * 0.5)
    sample_dirs = []
    for jj in np.linspace(-0.6, 0.6, 25):
        for ii in np.linspace(-0.6, 0.6, 25):
            dd = fwd + ii * half * right + jj * half * up
            sample_dirs.append(dd / np.linalg.norm(dd))
    for c in counts:
        cl = make_cloud(c, np.random.default_rng(7))
        ns = [candidates_along_ray(cl, cam, d)[0].size for d in sample_dirs]
        means.append(np.mean(ns)); maxs.append(np.max(ns))
        print(f"[curve] N={c:5d}  mean_cand={np.mean(ns):6.1f}  "
              f"max={np.max(ns):4d}  ratio={100*np.mean(ns)/c:.1f}%")

    plt.figure(figsize=(6, 4))
    plt.plot(counts, means, "o-", label="mean candidates/ray")
    plt.plot(counts, maxs, "s--", label="max candidates/ray")
    plt.xlabel("primitive count N"); plt.ylabel("candidates per ray")
    plt.title("Traversal cost (brute-force bounding sphere)")
    plt.legend(); plt.grid(alpha=0.3)
    plt.tight_layout()
    curve_png = os.path.join(out_dir, "mvp_candidate_curve.png")
    plt.savefig(curve_png, dpi=120)
    plt.close()

    print("OUTPUTS:", main_png, dbg_png, curve_png)


if __name__ == "__main__":
    main()
