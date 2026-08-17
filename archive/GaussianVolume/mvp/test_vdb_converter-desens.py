"""
VDB → Gaussian 转换器测试

用程序化生成的 density volume 模拟 VDB grid，测试转换器的：
  1. 基本转换（各向同性）
  2. 各向异性模式（gradient-based）
  3. max_primitives 限制
  4. 渲染验证（转换后的 GaussianCloud 渲染效果）
  5. 统计输出
"""
import sys, os, time
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from vdb_converter import vdb_to_gaussians, read_numpy_grid, conversion_stats
from gaussian_volume import render, precompute_light_tau_matrix
from scene_mvp import to_srgb


def make_synthetic_vdb(shape=(48, 48, 48), voxel_size=0.1):
    """生成一个程序化的体积云 density volume。

    使用多个球状密度团叠加，模拟自然云形态。
    """
    D = np.zeros(shape, dtype=np.float64)
    # 网格坐标
    xs = np.linspace(-1, 1, shape[0])
    ys = np.linspace(-1, 1, shape[1])
    zs = np.linspace(-1, 1, shape[2])
    X, Y, Z = np.meshgrid(xs, ys, zs, indexing="ij")

    # 3 个密度团叠加
    for cx, cy, cz, r, amp in [
        (0.0, 0.1, 0.0, 0.5, 2.0),
        (-0.3, -0.2, 0.2, 0.35, 1.5),
        (0.3, 0.0, -0.2, 0.4, 1.8),
    ]:
        dist2 = (X - cx)**2 + (Y - cy)**2 + (Z - cz)**2
        D += amp * np.exp(-dist2 / (2 * r**2))

    # 加一点噪声
    rng = np.random.default_rng(42)
    D += rng.normal(0, 0.05, shape)
    D = np.maximum(D, 0)

    return D, voxel_size, np.array([-2.4, -2.4, -2.4])  # origin


def main():
    out_dir = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out_dir, exist_ok=True)

    # 1. 生成 synthetic VDB-like density volume
    print("=" * 60)
    print("VDB → Gaussian Converter Test")
    print("=" * 60)
    dense, voxel_size, origin = make_synthetic_vdb(shape=(48, 48, 48), voxel_size=0.1)
    print(f"[input] grid shape={dense.shape}, voxel_size={voxel_size}")
    print(f"        active voxels={np.sum(dense > 0.01)} / {dense.size}")
    print(f"        density range=[{dense.min():.3f}, {dense.max():.3f}]")

    # 2. 各向同性转换
    print("\n--- Test 1: Isotropic conversion ---")
    cloud_iso = vdb_to_gaussians(
        dense, voxel_size, origin,
        density_threshold=0.05,
        density_scale=2.0,
        sigma_max_scale=2.0,
        anisotropy_mode="none",
    )
    stats_iso = conversion_stats(dense, cloud_iso)
    print(f"  primitives: {stats_iso['n_primitives']}")
    print(f"  compression: {stats_iso['compression_ratio']:.1f}x "
          f"({stats_iso['active_voxels']} voxels → {stats_iso['n_primitives']} Gaussians)")
    print(f"  sigma_t: [{stats_iso['density_min']:.3f}, {stats_iso['density_max']:.3f}]")
    print(f"  scale: {stats_iso['scale_mean']:.3f} (mean)")

    # 3. 各向异性转换
    print("\n--- Test 2: Anisotropic (gradient-based) ---")
    cloud_aniso = vdb_to_gaussians(
        dense, voxel_size, origin,
        density_threshold=0.05,
        density_scale=2.0,
        sigma_max_scale=2.0,
        anisotropy_mode="gradient",
        anisotropy_ratio=0.3,
    )
    stats_aniso = conversion_stats(dense, cloud_aniso)
    print(f"  primitives: {stats_aniso['n_primitives']}")
    print(f"  compression: {stats_aniso['compression_ratio']:.1f}x")
    print(f"  scale range: [{cloud_aniso.scale.min():.4f}, {cloud_aniso.scale.max():.4f}]")

    # 4. max_primitives 限制
    print("\n--- Test 3: max_primitives=512 ---")
    cloud_limited = vdb_to_gaussians(
        dense, voxel_size, origin,
        density_threshold=0.05,
        density_scale=2.0,
        sigma_max_scale=2.0,
        max_primitives=512,
    )
    print(f"  primitives: {cloud_limited.N} (limited to 512)")
    print(f"  sigma_t: [{cloud_limited.sigma_t.min():.3f}, {cloud_limited.sigma_t.max():.3f}]")

    # 5. 渲染对比
    print("\n--- Test 4: Render comparison ---")
    cam = np.array([0.0, 1.0, 6.0])
    target = np.array([0.0, 0.0, 0.0])
    light_dir = np.array([-0.6, 0.8, 0.4])
    light_color = np.array([1.5, 1.4, 1.2])
    ambient = np.array([0.10, 0.12, 0.16])
    W, H = 200, 150

    # 渲染各向同性版
    t0 = time.time()
    tau_light = precompute_light_tau_matrix(cloud_iso, light_dir)
    res_iso = render(cloud_iso, cam, target, 45.0, W, H,
                     light_dir, light_color, ambient, tau_light=tau_light)
    dt_iso = time.time() - t0
    print(f"  [isotropic] N={cloud_iso.N} {W}x{H} took {dt_iso:.2f}s ({W*H/dt_iso:.0f} ray/s)")

    # 渲染各向异性版
    t0 = time.time()
    tau_light_a = precompute_light_tau_matrix(cloud_aniso, light_dir)
    res_aniso = render(cloud_aniso, cam, target, 45.0, W, H,
                       light_dir, light_color, ambient, tau_light=tau_light_a)
    dt_aniso = time.time() - t0
    print(f"  [anisotropic] N={cloud_aniso.N} {W}x{H} took {dt_aniso:.2f}s ({W*H/dt_aniso:.0f} ray/s)")

    # 颜色差异
    color_diff = np.abs(res_iso["color"] - res_aniso["color"]).mean()
    print(f"  color diff (iso vs aniso): {color_diff:.6f}")

    # 6. 可视化
    fig, axes = plt.subplots(2, 3, figsize=(15, 10))

    # Row 0: 渲染结果
    axes[0, 0].imshow(to_srgb(res_iso["color"]))
    axes[0, 0].set_title(f"Isotropic (N={cloud_iso.N})")
    axes[0, 0].axis("off")

    axes[0, 1].imshow(to_srgb(res_aniso["color"]))
    axes[0, 1].set_title(f"Anisotropic (N={cloud_aniso.N})")
    axes[0, 1].axis("off")

    axes[0, 2].imshow(to_srgb(np.abs(res_iso["color"] - res_aniso["color"])))
    axes[0, 2].set_title(f"Diff (mean={color_diff:.4f})")
    axes[0, 2].axis("off")

    # Row 1: debug views
    im0 = axes[1, 0].imshow(res_iso["optical_depth"], cmap="magma")
    axes[1, 0].set_title("Optical depth (iso)")
    axes[1, 0].axis("off")
    fig.colorbar(im0, ax=axes[1, 0], fraction=0.046)

    im1 = axes[1, 1].imshow(res_iso["transmittance"], cmap="viridis")
    axes[1, 1].set_title("Transmittance (iso)")
    axes[1, 1].axis("off")
    fig.colorbar(im1, ax=axes[1, 1], fraction=0.046)

    im2 = axes[1, 2].imshow(res_iso["candidates"], cmap="cividis")
    axes[1, 2].set_title(f"Candidates (max={res_iso['candidates'].max()})")
    axes[1, 2].axis("off")
    fig.colorbar(im2, ax=axes[1, 2], fraction=0.046)

    plt.suptitle("VDB → Gaussian Converter: Render Validation", fontsize=14)
    plt.tight_layout()
    out_png = os.path.join(out_dir, "vdb_converter_test.png")
    plt.savefig(out_png, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"\n[output] {out_png}")

    # 7. 原始 VDB slice 可视化
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    mid = dense.shape[2] // 2
    axes[0].imshow(dense[:, :, mid], cmap="magma", origin="lower")
    axes[0].set_title(f"VDB density slice z={mid}")
    axes[0].axis("off")

    # Gaussian center 投影到 z=mid 平面附近
    centers_near = cloud_iso.center[np.abs(cloud_iso.center[:, 2] - origin[2] - mid * voxel_size) < voxel_size * 2]
    if len(centers_near) > 0:
        axes[1].scatter(centers_near[:, 0], centers_near[:, 1], s=2, alpha=0.5, c="cyan")
        axes[1].set_xlim(origin[0], origin[0] + dense.shape[0] * voxel_size)
        axes[1].set_ylim(origin[1], origin[1] + dense.shape[1] * voxel_size)
    axes[1].set_title("Gaussian centers (z≈mid slice)")
    axes[1].set_aspect("equal")

    # 密度直方图
    axes[2].hist(cloud_iso.sigma_t, bins=50, color="steelblue", alpha=0.7)
    axes[2].set_title("sigma_t distribution")
    axes[2].set_xlabel("sigma_t")
    axes[2].set_ylabel("count")

    plt.tight_layout()
    slice_png = os.path.join(out_dir, "vdb_converter_slices.png")
    plt.savefig(slice_png, dpi=130, bbox_inches="tight")
    plt.close()
    print(f"[output] {slice_png}")

    print("\nDone.")


if __name__ == "__main__":
    main()
