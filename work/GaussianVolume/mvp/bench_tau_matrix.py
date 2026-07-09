"""
Benchmark: tau 矩阵预计算 vs 逐 candidate 计算
验证正确性（color diff）并对比性能。
"""
import sys, os, time
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaussian_volume import (
    GaussianCloud, render, shade_ray, precompute_light_tau_matrix,
    candidates_along_ray, ray_gaussian_taus
)


def random_quats(n, rng):
    q = rng.normal(size=(n, 4))
    return q / np.linalg.norm(q, axis=1, keepdims=True)


def make_cloud(n, rng, radius=2.2):
    u = rng.random(n) ** 0.6
    dirv = rng.normal(size=(n, 3))
    dirv /= np.linalg.norm(dirv, axis=1, keepdims=True)
    center = dirv * (u * radius)[:, None]
    scale = rng.uniform(0.25, 0.6, size=(n, 3))
    quat = random_quats(n, rng)
    r = np.linalg.norm(center, axis=1)
    sigma_t = 3.5 * np.exp(-(r / radius) ** 2) + 0.4
    albedo = np.tile(np.array([0.92, 0.94, 1.0]), (n, 1))
    return GaussianCloud(center, scale, quat, sigma_t, albedo)


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

    # ---- 正确性验证：单 ray 对比 ----
    fwd = target - cam; fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, [0, 1, 0]); right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    half = np.tan(np.radians(45.0) * 0.5)
    d = fwd + 0.1 * half * right + 0.05 * half * up
    d /= np.linalg.norm(d)

    # 预计算 tau 矩阵
    t0 = time.time()
    tau_light = precompute_light_tau_matrix(cloud, light_dir)
    t_pre = time.time() - t0
    print(f"[precompute] tau matrix {N}x{N} took {t_pre:.3f}s "
          f"({t_pre / N**2 * 1e6:.1f} µs/entry)")

    # 逐 candidate（原始路径）
    L1, tau1, T1, n1 = shade_ray(cloud, cam, d, light_dir, light_color,
                                 ambient, tau_light=None)
    # tau 矩阵查表
    L2, tau2, T2, n2 = shade_ray(cloud, cam, d, light_dir, light_color,
                                 ambient, tau_light=tau_light)

    color_diff = np.max(np.abs(L1 - L2))
    tau_diff = abs(tau1 - tau2)
    T_diff = abs(T1 - T2)
    print(f"[correctness] candidates={n1} (should be {n2})")
    print(f"[correctness] color max diff = {color_diff:.2e}")
    print(f"[correctness] tau diff = {tau_diff:.2e}")
    print(f"[correctness] T diff = {T_diff:.2e}")
    if color_diff < 1e-8:
        print("[correctness] PASS ✓")
    else:
        print("[correctness] FAIL ✗ — 检查 tau 矩阵计算")

    # ---- 性能对比：全画面渲染 ----
    # 原始路径（逐 candidate）
    t0 = time.time()
    res1 = render(cloud, cam, target, 45.0, W, H,
                  light_dir, light_color, ambient, tau_light="disable")
    dt_old = time.time() - t0
    print(f"\n[render OLD] N={N} {W}x{H} took {dt_old:.2f}s "
          f"({W*H/dt_old:.0f} ray/s)")

    # tau 矩阵路径
    t0 = time.time()
    res2 = render(cloud, cam, target, 45.0, W, H,
                  light_dir, light_color, ambient, tau_light=tau_light)
    dt_new = time.time() - t0
    print(f"[render NEW] N={N} {W}x{H} took {dt_new:.2f}s "
          f"({W*H/dt_new:.0f} ray/s)")
    print(f"[speedup] {dt_old/dt_new:.2f}x")

    # 全画面 color diff
    full_diff = np.max(np.abs(res1["color"] - res2["color"]))
    print(f"[full-image] color max diff = {full_diff:.2e}")

    # ---- 不同 N 的性能曲线 ----
    print("\n--- N scaling ---")
    for Nt in [256, 512, 1024]:
        cl = make_cloud(Nt, np.random.default_rng(7))
        # precompute
        t0 = time.time()
        tl = precompute_light_tau_matrix(cl, light_dir)
        t_pre_n = time.time() - t0
        # render old
        t0 = time.time()
        render(cl, cam, target, 45.0, W, H, light_dir, light_color, ambient,
               tau_light="disable")
        dt_o = time.time() - t0
        # render new (incl precompute)
        t0 = time.time()
        render(cl, cam, target, 45.0, W, H, light_dir, light_color, ambient,
               tau_light=tl)
        dt_n = time.time() - t0
        # render new (excl precompute, amortized)
        dt_n_amort = dt_n - t_pre_n
        print(f"  N={Nt:5d}  precompute={t_pre_n:.2f}s  "
              f"old={dt_o:.2f}s ({W*H/dt_o:.0f} r/s)  "
              f"new={dt_n:.2f}s ({W*H/dt_n:.0f} r/s)  "
              f"new(amort)={dt_n_amort:.2f}s ({W*H/dt_n_amort:.0f} r/s)  "
              f"speedup={dt_o/dt_n:.2f}x")


if __name__ == "__main__":
    main()
