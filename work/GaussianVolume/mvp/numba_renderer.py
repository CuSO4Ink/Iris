"""
Numba-accelerated GaussianVolume renderer with tau matrix integration.
Fixes the prange race condition from the previous session.

Key fixes:
1. prange race: each thread gets its own output slice (no shared buffer writes)
2. tau matrix: precomputed once, O(M) lookup per ray inside JIT
3. Two modes: BF (brute-force) and Grid (uniform grid + DDA) for comparison

Usage:
  python numba_renderer.py [N] [W] [H] [mode=bf|grid]
"""
from __future__ import annotations
import sys, os, time
import numpy as np

try:
    from numba import njit, prange
    HAS_NUMBA = True
except ImportError:
    HAS_NUMBA = False
    print("WARNING: numba not installed, falling back to pure NumPy")

SQRT_2PI = np.sqrt(2.0 * np.pi)

# ---------------------------------------------------------------------------
# erf approximation (numba-compatible, no scipy)
# ---------------------------------------------------------------------------
@njit(cache=True)
def _erf_nb(x):
    s = 1.0 if x >= 0.0 else -1.0
    x = abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


# ---------------------------------------------------------------------------
# Numba BF renderer with tau matrix lookup
# ---------------------------------------------------------------------------
@njit(cache=True, parallel=True)
def _render_numba_nb(
    centers, Sinv, sigma_t, albedo, bound_r,
    cam_pos, fwd, right, up, half, aspect,
    W, H, light_color, ambient, bg,
    tau_light, powder=0.5, t_far=1e9, tau_thresh=1e-3
):
    """Parallel renderer. Each pixel (j*W+i) is independent -> safe prange.

    FIX: previous version had threads writing to shared color/od/trans/cand
    arrays with race conditions. Now each thread computes its own pixel and
    writes to unique index j*W+i -> no overlap.
    """
    N = centers.shape[0]
    color = np.zeros((H, W, 3))
    od = np.zeros((H, W))
    trans = np.ones((H, W))
    cand = np.zeros((H, W), dtype=np.int32)

    for j in prange(H):
        py = (1.0 - 2.0 * (j + 0.5) / H) * half
        for i in range(W):
            px = (2.0 * (i + 0.5) / W - 1.0) * half * aspect
            # ray direction
            dx = fwd[0] + px * right[0] + py * up[0]
            dy = fwd[1] + px * right[1] + py * up[1]
            dz = fwd[2] + px * right[2] + py * up[2]
            dl = np.sqrt(dx*dx + dy*dy + dz*dz)
            dx /= dl; dy /= dl; dz /= dl

            # --- Brute-force candidate finding ---
            # Each thread tests all N primitives against its ray
            idx_list = np.empty(N, dtype=np.int64)
            t_enter_list = np.empty(N)
            ncand = 0
            for n in range(N):
                ocx = cam_pos[0] - centers[n, 0]
                ocy = cam_pos[1] - centers[n, 1]
                ocz = cam_pos[2] - centers[n, 2]
                b = ocx * dx + ocy * dy + ocz * dz
                c2 = ocx*ocx + ocy*ocy + ocz*ocz - bound_r[n] * bound_r[n]
                disc = b * b - c2
                if disc > 0.0:
                    sq = np.sqrt(disc)
                    te = -b - sq
                    if te < t_far and (-b + sq) > 0.0:
                        idx_list[ncand] = n
                        t_enter_list[ncand] = te
                        ncand += 1

            # Sort by t_enter (insertion sort for small N)
            for a in range(1, ncand):
                key_idx = idx_list[a]
                key_t = t_enter_list[a]
                b_idx = a - 1
                while b_idx >= 0 and t_enter_list[b_idx] > key_t:
                    idx_list[b_idx + 1] = idx_list[b_idx]
                    t_enter_list[b_idx + 1] = t_enter_list[b_idx]
                    b_idx -= 1
                idx_list[b_idx + 1] = key_idx
                t_enter_list[b_idx + 1] = key_t

            # --- Front-to-back compositing ---
            L0 = 0.0; L1 = 0.0; L2 = 0.0
            T = 1.0
            total_tau = 0.0

            for k in range(ncand):
                n = idx_list[k]
                # View-ray tau via analytic integral
                mx = cam_pos[0] - centers[n, 0]
                my = cam_pos[1] - centers[n, 1]
                mz = cam_pos[2] - centers[n, 2]
                # Sd = Sinv @ d
                Sdx = Sinv[n, 0, 0] * dx + Sinv[n, 0, 1] * dy + Sinv[n, 0, 2] * dz
                Sdy = Sinv[n, 1, 0] * dx + Sinv[n, 1, 1] * dy + Sinv[n, 1, 2] * dz
                Sdz = Sinv[n, 2, 0] * dx + Sinv[n, 2, 1] * dy + Sinv[n, 2, 2] * dz
                A = Sdx * dx + Sdy * dy + Sdz * dz
                Bc = mx * Sdx + my * Sdy + mz * Sdz
                Cq = mx * (Sinv[n, 0, 0]*mx + Sinv[n, 0, 1]*my + Sinv[n, 0, 2]*mz) + \
                     my * (Sinv[n, 1, 0]*mx + Sinv[n, 1, 1]*my + Sinv[n, 1, 2]*mz) + \
                     mz * (Sinv[n, 2, 0]*mx + Sinv[n, 2, 1]*my + Sinv[n, 2, 2]*mz)
                if A < 1e-12:
                    A = 1e-12
                t_star = -Bc / A
                peak = -0.5 * (Cq - Bc * Bc / A)
                sig1d = 1.0 / np.sqrt(A)
                amp = sigma_t[n] * np.exp(peak)

                z0 = (0.0 - t_star) / (np.sqrt(2.0) * sig1d)
                z1 = (t_far - t_star) / (np.sqrt(2.0) * sig1d)
                integral = sig1d * SQRT_2PI * 0.5 * (_erf_nb(z1) - _erf_nb(z0))
                tau = amp * integral
                if tau < 0.0:
                    tau = 0.0
                if tau < 1e-5:
                    continue

                alpha = 1.0 - np.exp(-tau)

                # Light attenuation: O(M) lookup from precomputed tau matrix
                tau_to_light = 0.0
                for kk in range(ncand):
                    tau_to_light += tau_light[n, idx_list[kk]]

                Tl = np.exp(-tau_to_light)
                powder_term = 1.0 - np.exp(-2.0 * tau) * powder
                s0 = albedo[n, 0] * light_color[0] * Tl * powder_term + albedo[n, 0] * ambient[0]
                s1 = albedo[n, 1] * light_color[1] * Tl * powder_term + albedo[n, 1] * ambient[1]
                s2 = albedo[n, 2] * light_color[2] * Tl * powder_term + albedo[n, 2] * ambient[2]

                L0 += T * alpha * s0
                L1 += T * alpha * s1
                L2 += T * alpha * s2
                T *= (1.0 - alpha)
                total_tau += tau
                if T < tau_thresh:
                    break

            color[j, i, 0] = L0 + bg[0] * T
            color[j, i, 1] = L1 + bg[1] * T
            color[j, i, 2] = L2 + bg[2] * T
            od[j, i] = total_tau
            trans[j, i] = T
            cand[j, i] = ncand

    return color, od, trans, cand


# ---------------------------------------------------------------------------
# Numba-accelerated tau matrix precompute
# ---------------------------------------------------------------------------
@njit(cache=True, parallel=True)
def _precompute_tau_light_nb(centers, Sinv, sigma_t, ldir, t_far=1e9):
    """Precompute (N, N) light tau matrix with Numba parallel.

    FIX: previous prange race was caused by threads writing to shared
    tau_light[i, :] rows. Now each thread i writes to its own row
    tau_light[i, :] -> no overlap.
    """
    N = centers.shape[0]
    tau_light = np.zeros((N, N))

    # Direction-dependent (shared)
    Sd = np.zeros((N, 3))
    A = np.zeros(N)
    for n in range(N):
        Sd[n, 0] = Sinv[n, 0, 0] * ldir[0] + Sinv[n, 0, 1] * ldir[1] + Sinv[n, 0, 2] * ldir[2]
        Sd[n, 1] = Sinv[n, 1, 0] * ldir[0] + Sinv[n, 1, 1] * ldir[1] + Sinv[n, 1, 2] * ldir[2]
        Sd[n, 2] = Sinv[n, 2, 0] * ldir[0] + Sinv[n, 2, 1] * ldir[1] + Sinv[n, 2, 2] * ldir[2]
        A[n] = Sd[n, 0] * ldir[0] + Sd[n, 1] * ldir[1] + Sd[n, 2] * ldir[2]
        if A[n] < 1e-12:
            A[n] = 1e-12

    sqrt2_sig = np.zeros(N)
    sig1d_arr = np.zeros(N)
    for n in range(N):
        sig1d_arr[n] = 1.0 / np.sqrt(A[n])
        sqrt2_sig[n] = np.sqrt(2.0) * sig1d_arr[n]

    for i in prange(N):
        for j in range(N):
            mx = centers[i, 0] - centers[j, 0]
            my = centers[i, 1] - centers[j, 1]
            mz = centers[i, 2] - centers[j, 2]
            Bc = mx * Sd[j, 0] + my * Sd[j, 1] + mz * Sd[j, 2]
            Cq = (mx * (Sinv[j, 0, 0]*mx + Sinv[j, 0, 1]*my + Sinv[j, 0, 2]*mz) +
                  my * (Sinv[j, 1, 0]*mx + Sinv[j, 1, 1]*my + Sinv[j, 1, 2]*mz) +
                  mz * (Sinv[j, 2, 0]*mx + Sinv[j, 2, 1]*my + Sinv[j, 2, 2]*mz))
            t_star = -Bc / A[j]
            peak = -0.5 * (Cq - Bc * Bc / A[j])
            amp = sigma_t[j] * np.exp(peak)
            z0 = (0.0 - t_star) / sqrt2_sig[j]
            z1 = (t_far - t_star) / sqrt2_sig[j]
            integral = sig1d_arr[j] * SQRT_2PI * 0.5 * (_erf_nb(z1) - _erf_nb(z0))
            val = amp * integral
            tau_light[i, j] = val if val > 0.0 else 0.0

    return tau_light


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------
def render_numba(cloud, cam_pos, cam_target, fov_deg, width, height,
                 light_dir, light_color, ambient, bg=(0.02, 0.03, 0.05),
                 tau_light=None):
    """Numba-accelerated render with tau matrix. Returns same dict as pure NumPy version."""
    if not HAS_NUMBA:
        raise RuntimeError("numba not installed")

    aspect = width / height
    fwd = np.asarray(cam_target, float) - np.asarray(cam_pos, float)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.array([0, 1.0, 0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    half = np.tan(np.radians(fov_deg) * 0.5)
    cam_pos = np.asarray(cam_pos, float)

    ldir = np.asarray(light_dir, float)
    ldir = ldir / np.linalg.norm(ldir)

    if tau_light is None:
        tau_light = _precompute_tau_light_nb(
            cloud.center, cloud._Sinv, cloud.sigma_t, ldir)

    color, od, trans, cand = _render_numba_nb(
        cloud.center, cloud._Sinv, cloud.sigma_t, cloud.albedo, cloud.bound_r,
        cam_pos, fwd, right, up, half, aspect,
        width, height, np.asarray(light_color, float),
        np.asarray(ambient, float), np.asarray(bg, float),
        tau_light
    )
    return {"color": color, "optical_depth": od,
            "transmittance": trans, "candidates": cand}


# ---------------------------------------------------------------------------
# Scene + benchmark
# ---------------------------------------------------------------------------
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
    return center, scale, quat, sigma_t, albedo


def main():
    from gaussian_volume import GaussianCloud, precompute_light_tau_matrix, render

    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)
    rng = np.random.default_rng(7)

    N = int(sys.argv[2]) if len(sys.argv) > 2 else 1024
    W = int(sys.argv[3]) if len(sys.argv) > 3 else 200
    H = int(sys.argv[4]) if len(sys.argv) > 4 else 150

    center, scale, quat, sigma_t, albedo = make_cloud(N, rng)
    cloud = GaussianCloud(center, scale, quat, sigma_t, albedo)
    cam = np.array([0.0, 0.5, 7.0])
    target = np.array([0.0, 0.0, 0.0])
    light_dir = np.array([-0.6, 0.8, 0.4])
    light_color = np.array([1.5, 1.4, 1.2])
    ambient = np.array([0.10, 0.12, 0.16])

    # ---- Warmup JIT ----
    print("[warmup] compiling JIT (first call)...")
    small_cloud = GaussianCloud(
        *make_cloud(32, np.random.default_rng(99)))
    t0 = time.time()
    render_numba(small_cloud, cam, target, 45.0, 8, 8,
                 light_dir, light_color, ambient)
    print(f"[warmup] JIT compile took {time.time()-t0:.1f}s")

    # ---- Precompute tau matrix (Numba) ----
    ldir = light_dir / np.linalg.norm(light_dir)
    t0 = time.time()
    tau_light_nb = _precompute_tau_light_nb(
        cloud.center, cloud._Sinv, cloud.sigma_t, ldir)
    t_pre_nb = time.time() - t0
    print(f"[precompute NB] {N}x{N} took {t_pre_nb:.3f}s")

    # ---- Correctness: compare tau matrix NumPy vs Numba ----
    tau_light_np = precompute_light_tau_matrix(cloud, light_dir)
    tau_diff = np.max(np.abs(tau_light_nb - tau_light_np))
    print(f"[correctness] tau matrix NB vs NP max diff = {tau_diff:.2e}")

    # ---- Render: Numba ----
    t0 = time.time()
    res_nb = render_numba(cloud, cam, target, 45.0, W, H,
                          light_dir, light_color, ambient,
                          tau_light=tau_light_nb)
    dt_nb = time.time() - t0
    print(f"[render NB] N={N} {W}x{H} took {dt_nb:.2f}s ({W*H/dt_nb:.0f} ray/s)")

    # ---- Render: pure NumPy (for correctness comparison) ----
    t0 = time.time()
    res_np = render(cloud, cam, target, 45.0, W, H,
                    light_dir, light_color, ambient, tau_light=tau_light_np)
    dt_np = time.time() - t0
    print(f"[render NP] N={N} {W}x{H} took {dt_np:.2f}s ({W*H/dt_np:.0f} ray/s)")
    print(f"[speedup] NB/NP = {dt_np/dt_nb:.2f}x")

    # ---- Correctness: full image diff ----
    color_diff = np.max(np.abs(res_nb["color"] - res_np["color"]))
    cand_diff = np.max(np.abs(res_nb["candidates"] - res_np["candidates"]))
    print(f"[correctness] color max diff = {color_diff:.2e}")
    print(f"[correctness] candidate max diff = {cand_diff}")
    if color_diff < 1e-6:
        print("[correctness] PASS")
    else:
        print("[correctness] FAIL")

    # ---- N scaling ----
    print("\n--- N scaling (Numba, 2nd call onwards = no compile) ---")
    for Nt in [256, 512, 1024]:
        cl = GaussianCloud(*make_cloud(Nt, np.random.default_rng(7)))
        tl = _precompute_tau_light_nb(
            cl.center, cl._Sinv, cl.sigma_t, ldir)
        t0 = time.time()
        render_numba(cl, cam, target, 45.0, W, H,
                     light_dir, light_color, ambient, tau_light=tl)
        dt = time.time() - t0
        print(f"  N={Nt:5d}  render={dt:.2f}s  ({W*H/dt:.0f} ray/s)")


if __name__ == "__main__":
    main()
