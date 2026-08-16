"""
VDB → Gaussian Primitive 转换器

将 VDB 体积云的 voxel density grid 转换为 Gaussian volume primitives，
作为 VDB 中远景 LOD / proxy / compression 方案。

设计思路（参考交叉阅读笔记）：
  1. 每个 active voxel → 一个 isotropic Gaussian（scale = voxel_size / 2）
  2. sigma_t = voxel_density * density_scale（线性映射，可调）
  3. 可选：邻域密度梯度估计各向异性方向（类似 VoGE normal-based anisotropy）
  4. 可选：合并相邻低密度 voxel 为一个更大 Gaussian（减少 primitive 数）

支持两种输入：
  A. pyopenvdb.Grid（如果安装了 pyopenvdb）
  B. NumPy dense array + voxel_size（用于测试，模拟 VDB 读取结果）

输出：GaussianCloud（与 mvp/gaussian_volume.py 兼容）

参考：
  - VoGE Converter: neighbor-based sigma estimation, percentage 参数
  - Vol3DGS: analytic alpha 验证 Gaussian volume 用于体积介质的物理正确性
  - 3DGEER: PBF 启发——per-Gaussian closed-form computation, 避免 BVH
"""
from __future__ import annotations
import numpy as np

# 尝试导入 pyopenvdb（可选依赖）
try:
    import pyopenvdb as vdb
    HAS_PYOPENVDB = True
except ImportError:
    HAS_PYOPENVDB = False

# 复用 MVP 的 GaussianCloud
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gaussian_volume import GaussianCloud


# ---------------------------------------------------------------------------
# VDB 读取层
# ---------------------------------------------------------------------------

def read_vdb_grid(vdb_path: str, grid_name: str = "density"):
    """从 .vdb 文件读取 density grid，返回 (dense_array, voxel_size, origin)。

    需要 pyopenvdb。如果未安装，抛出 ImportError 并提示安装方法。
    """
    if not HAS_PYOPENVDB:
        raise ImportError(
            "pyopenvdb not installed. Install via:\n"
            "  conda install -c conda-forge openvdb\n"
            "Or use read_numpy_grid() for testing with NumPy arrays."
        )
    grid = vdb.read(vdb_path, grids=[grid_name])[0]
    # 获取 dense array
    bbox = grid.evalActiveVoxelBoundingBox()
    dim = (bbox[1][0] - bbox[0][0] + 1,
           bbox[1][1] - bbox[0][1] + 1,
           bbox[1][2] - bbox[0][2] + 1)
    # accessor → dense numpy
    dense = np.zeros(dim, dtype=np.float32)
    accessor = grid.getConstAccessor()
    i0, j0, k0 = bbox[0]
    for i in range(dim[0]):
        for j in range(dim[1]):
            for k in range(dim[2]):
                dense[i, j, k] = accessor.getValue((i + i0, j + j0, k + k0))
    # voxel size
    transform = grid.transform
    voxel_size = transform.voxelSize()[0]  # assume uniform
    # world origin of voxel (i0, j0, k0)
    origin = np.array(transform.indexToWorld((i0, j0, k0)))
    return dense, voxel_size, origin


def read_numpy_grid(dense: np.ndarray, voxel_size: float = 1.0,
                    origin: np.ndarray = None):
    """从 NumPy dense array 模拟 VDB 读取。用于测试。

    dense: (Dx, Dy, Dz) density volume
    voxel_size: world-space voxel edge length
    origin: world-space position of voxel (0,0,0)
    """
    if origin is None:
        origin = np.zeros(3)
    return np.asarray(dense, np.float64), float(voxel_size), np.asarray(origin, np.float64)


# ---------------------------------------------------------------------------
# 转换核心
# ---------------------------------------------------------------------------

def vdb_to_gaussians(
    dense, voxel_size, origin,
    density_threshold: float = 0.01,
    density_scale: float = 1.0,
    sigma_max_scale: float = 2.0,
    anisotropy_mode: str = "none",
    anisotropy_ratio: float = 0.3,
    merge_threshold: float = 0.0,
    max_primitives: int = None,
):
    """将 dense voxel density grid 转换为 Gaussian volume primitives。

    Parameters
    ----------
    dense : (Dx, Dy, Dz) array
        Voxel density values.
    voxel_size : float
        World-space voxel edge length.
    origin : (3,) array
        World-space position of voxel (0,0,0).
    density_threshold : float
        低于此值的 voxel 被跳过（视为空）。
    density_scale : float
        密度 → sigma_t 的线性缩放因子。sigma_t = density * density_scale。
    sigma_max_scale : float
        Gaussian 的 scale = voxel_size * sigma_max_scale / 2。
        sigma_max_scale=2 → scale ≈ voxel_size（覆盖 ±1σ = 0.5 voxel）。
        sigma_max_scale=3 → scale ≈ 1.5*voxel_size（更宽，overlap 多）。
    anisotropy_mode : str
        "none" - 各向同性
        "gradient" - 沿密度梯度方向压缩（类似 VoGE normal-based）
    anisotropy_ratio : float
        各向异性模式下，沿梯度方向的 scale 压缩比（0~1，越小越扁）。
    merge_threshold : float
        > 0 时，合并密度差小于此值的相邻 voxel 为一个 Gaussian。
        0 = 不合并。实验性，暂未实现。
    max_primitives : int or None
        限制最大 primitive 数。超过时按密度降序保留 top-K。

    Returns
    -------
    GaussianCloud
    """
    dense = np.asarray(dense, np.float64)
    Dx, Dy, Dz = dense.shape

    # 1. 找 active voxels（密度 > threshold）
    active_mask = dense > density_threshold
    active_indices = np.argwhere(active_mask)  # (M, 3) int indices
    M = len(active_indices)

    if M == 0:
        raise ValueError(f"No active voxels above threshold {density_threshold}")

    # 2. 提取密度
    densities = dense[active_mask]  # (M,)

    # 3. 限制 primitive 数
    if max_primitives is not None and M > max_primitives:
        top_k_idx = np.argsort(densities)[::-1][:max_primitives]
        active_indices = active_indices[top_k_idx]
        densities = densities[top_k_idx]
        M = max_primitives

    # 4. 世界坐标 center
    centers = origin[None, :] + active_indices.astype(np.float64) * voxel_size  # (M, 3)

    # 5. sigma_t
    sigma_t = densities * density_scale  # (M,)

    # 6. scale
    base_scale = voxel_size * sigma_max_scale / 2.0  # isotropic default

    if anisotropy_mode == "gradient":
        # 计算密度梯度方向（有限差分）
        grad = _compute_density_gradients(dense, active_indices)  # (M, 3)
        # 构造各向异性 scale：沿梯度方向压缩，垂直方向不变
        scales, quats = _anisotropic_scales_from_gradient(
            grad, base_scale, anisotropy_ratio)
    else:
        # 各向同性
        scales = np.tile([base_scale, base_scale, base_scale], (M, 1))
        quats = np.tile([1.0, 0.0, 0.0, 0.0], (M, 1))  # identity rotation

    # 7. albedo（统一白色，可后续按需求调整）
    albedo = np.tile(np.array([0.92, 0.94, 1.0]), (M, 1))

    return GaussianCloud(
        center=centers,
        scale=scales,
        quat=quats,
        sigma_t=sigma_t,
        albedo=albedo,
    )


# ---------------------------------------------------------------------------
# 各向异性辅助
# ---------------------------------------------------------------------------

def _compute_density_gradients(dense, active_indices):
    """计算 active voxels 处的密度梯度（有限差分）。

    梯度方向 = 密度变化最快的方向 = 云边界法线方向。
    """
    Dx, Dy, Dz = dense.shape
    M = len(active_indices)
    grads = np.zeros((M, 3), dtype=np.float64)

    for i in range(M):
        ix, iy, iz = active_indices[i]
        # 中心差分，边界用前向/后向差分
        gx = _central_diff(dense, ix, iy, iz, axis=0, Dmax=Dx)
        gy = _central_diff(dense, ix, iy, iz, axis=1, Dmax=Dy)
        gz = _central_diff(dense, ix, iy, iz, axis=2, Dmax=Dz)
        grads[i] = [gx, gy, gz]

    # 归一化梯度方向（零梯度 → 默认 [0,1,0]）
    norms = np.linalg.norm(grads, axis=1, keepdims=True)
    norms = np.maximum(norms, 1e-10)
    grads = grads / norms

    return grads


def _central_diff(dense, ix, iy, iz, axis, Dmax):
    """沿指定轴的中心差分。"""
    idx = [ix, iy, iz]
    lo = list(idx); lo[axis] = max(0, idx[axis] - 1)
    hi = list(idx); hi[axis] = min(Dmax - 1, idx[axis] + 1)
    return (dense[tuple(hi)] - dense[tuple(lo)]) / 2.0


def _anisotropic_scales_from_gradient(grad, base_scale, ratio):
    """根据梯度方向构造各向异性 scale 和 rotation。

    梯度方向 = 云表面法线 → 沿法线方向 scale 压缩为 ratio * base_scale
    垂直方向保持 base_scale。

    类似 VoGE 的 normal-based anisotropy:
      isigma_base = ...
      base = diag(1, 1, shape_ratio) * isigma_base
      iSigma = R @ base @ R^T  (R = look_at_rotation(-normal))
    """
    M = grad.shape[0]
    scales = np.empty((M, 3), dtype=np.float64)

    # 沿梯度方向（法线）的 scale 压缩
    normal_scale = base_scale * ratio
    tangent_scale = base_scale

    # scale = [tangent, tangent, normal] in local frame (z-axis = normal)
    scales[:] = [tangent_scale, tangent_scale, normal_scale]

    # 构造 rotation：local z-axis → gradient direction
    # quaternion from [0,0,1] to grad
    quats = np.empty((M, 4), dtype=np.float64)
    forward = np.array([0.0, 0.0, 1.0])

    for i in range(M):
        n = grad[i]
        # quaternion rotating forward → n
        # q = (1 + dot(f,n), cross(f,n)) normalized
        dot = np.dot(forward, n)
        if dot > 0.9999:
            quats[i] = [1.0, 0.0, 0.0, 0.0]  # identity
        elif dot < -0.9999:
            quats[i] = [0.0, 1.0, 0.0, 0.0]  # 180° around x
        else:
            cross = np.cross(forward, n)
            q = np.array([1.0 + dot, cross[0], cross[1], cross[2]])
            q = q / np.linalg.norm(q)
            quats[i] = q

    return scales, quats


# ---------------------------------------------------------------------------
# 统计 / 诊断
# ---------------------------------------------------------------------------

def conversion_stats(dense, cloud):
    """返回转换统计：压缩比、密度分布等。"""
    Dx, Dy, Dz = dense.shape
    total_voxels = Dx * Dy * Dz
    active_voxels = int(np.sum(dense > 0.01))
    n_primitives = cloud.N
    return {
        "grid_shape": (Dx, Dy, Dz),
        "total_voxels": total_voxels,
        "active_voxels": active_voxels,
        "n_primitives": n_primitives,
        "compression_ratio": active_voxels / max(n_primitives, 1),
        "density_mean": float(np.mean(cloud.sigma_t)),
        "density_max": float(np.max(cloud.sigma_t)),
        "density_min": float(np.min(cloud.sigma_t)),
        "scale_mean": float(np.mean(cloud.scale)),
        "scale_max": float(np.max(cloud.scale)),
    }
