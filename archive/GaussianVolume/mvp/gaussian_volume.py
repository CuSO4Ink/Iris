"""
GaussianVolume MVP — standalone CPU renderer
复现 "Don't Splat your Gaussians" 的最小工程结构：
  - Gaussian volume primitive 数据结构
  - ray-Gaussian 解析透射率（analytic optical depth，非固定步 raymarch）
  - brute-force traversal + candidate 统计
  - front-to-back 合成 + single scattering（含 fake ambient / powder）
  - debug view（optical depth / transmittance / candidate count）

纯 NumPy，离线出图。目的是回答 MVP 三问，不追最终精度。
"""
from __future__ import annotations
import numpy as np

SQRT_2PI = np.sqrt(2.0 * np.pi)


# ---------------------------------------------------------------------------
# Primitive 结构
# ---------------------------------------------------------------------------
class GaussianCloud:
    """一批 Gaussian volume primitives，列存以便向量化。

    属性（每个 primitive）：
      center   (3,)   椭球中心
      scale    (3,)   各轴标准差（局部坐标）
      quat     (4,)   旋转 (w,x,y,z)，把局部 -> 世界
      sigma_t  ()     峰值消光系数 density
      albedo   (3,)   single-scatter albedo
    """

    def __init__(self, center, scale, quat, sigma_t, albedo):
        self.center = np.asarray(center, np.float64)      # (N,3)
        self.scale = np.asarray(scale, np.float64)        # (N,3)
        self.quat = np.asarray(quat, np.float64)          # (N,4)
        self.sigma_t = np.asarray(sigma_t, np.float64)    # (N,)
        self.albedo = np.asarray(albedo, np.float64)      # (N,3)
        self.N = self.center.shape[0]
        self._R = _quat_to_matrix(self.quat)              # (N,3,3) 局部->世界
        # Sigma^{-1} = R S^{-2} R^T
        inv_s2 = 1.0 / (self.scale ** 2)                  # (N,3)
        Rt = np.transpose(self._R, (0, 2, 1))
        self._Sinv = np.einsum('nij,nj,njk->nik', self._R, inv_s2, Rt)  # (N,3,3)
        # bounding sphere 半径：3 sigma 的最大轴
        self.bound_r = 3.0 * self.scale.max(axis=1)       # (N,)


def _quat_to_matrix(q):
    q = q / np.linalg.norm(q, axis=1, keepdims=True)
    w, x, y, z = q[:, 0], q[:, 1], q[:, 2], q[:, 3]
    N = q.shape[0]
    R = np.empty((N, 3, 3), np.float64)
    R[:, 0, 0] = 1 - 2 * (y * y + z * z)
    R[:, 0, 1] = 2 * (x * y - w * z)
    R[:, 0, 2] = 2 * (x * z + w * y)
    R[:, 1, 0] = 2 * (x * y + w * z)
    R[:, 1, 1] = 1 - 2 * (x * x + z * z)
    R[:, 1, 2] = 2 * (y * z - w * x)
    R[:, 2, 0] = 2 * (x * z - w * y)
    R[:, 2, 1] = 2 * (y * z + w * x)
    R[:, 2, 2] = 1 - 2 * (x * x + y * y)
    return R


# ---------------------------------------------------------------------------
# Ray-Gaussian 解析透射率
# ---------------------------------------------------------------------------
def _erf(x):
    # 无 scipy 时的 erf 近似（Abramowitz & Stegun 7.1.26），误差 < 1.5e-7
    s = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def ray_gaussian_taus(cloud: GaussianCloud, o, d, idx, t0, t1):
    """沿 ray(o,d) 计算 idx 指定 primitives 在 [t0,t1] 的 optical depth。

    把 3D 各向异性高斯沿 ray 投影成 1D 高斯：
      令 m = o - c，二次型 q(t) = (m+td)^T Sinv (m+td) = A t^2 + 2B t + C
      density(t) = sigma_t * exp(-0.5 q(t))
      配方： -0.5 A (t - t*)^2 + peak，  t* = -B/A， 1D sigma = 1/sqrt(A)
      区间积分用 erf。返回每个 primitive 的 tau。
    """
    c = cloud.center[idx]            # (M,3)
    Sinv = cloud._Sinv[idx]          # (M,3,3)
    sigma_t = cloud.sigma_t[idx]     # (M,)
    m = o[None, :] - c               # (M,3)
    Sd = np.einsum('mij,j->mi', Sinv, d)        # (M,3)
    A = np.einsum('mi,i->m', Sd, d)             # d^T Sinv d
    B = np.einsum('mi,mi->m', m, Sd)            # m^T Sinv d
    Cq = np.einsum('mi,mij,mj->m', m, Sinv, m)  # m^T Sinv m
    A = np.maximum(A, 1e-12)
    t_star = -B / A
    peak = -0.5 * (Cq - B * B / A)              # 指数峰值（<=0）
    sig1d = 1.0 / np.sqrt(A)                     # 1D 标准差
    amp = sigma_t * np.exp(peak)                 # 峰值消光
    # ∫ exp(-0.5 (t-t*)^2 / sig^2) dt over [t0,t1]
    z0 = (t0 - t_star) / (np.sqrt(2.0) * sig1d)
    z1 = (t1 - t_star) / (np.sqrt(2.0) * sig1d)
    integral = sig1d * SQRT_2PI * 0.5 * (_erf(z1) - _erf(z0))
    tau = amp * integral
    return np.maximum(tau, 0.0)                  # (M,)


# ---------------------------------------------------------------------------
# Traversal: bounding-sphere brute force
# ---------------------------------------------------------------------------
def candidates_along_ray(cloud, o, d, t_near=0.0, t_far=1e9):
    """返回与 ray bounding sphere 相交的 primitive 索引，按进入 t 排序。"""
    oc = o[None, :] - cloud.center            # (N,3)
    b = np.einsum('ni,i->n', oc, d)
    c2 = np.einsum('ni,ni->n', oc, oc) - cloud.bound_r ** 2
    disc = b * b - c2
    hit = disc > 0.0
    sq = np.sqrt(np.maximum(disc, 0.0))
    t_enter = -b - sq
    hit &= (t_enter < t_far) & (-b + sq > t_near)
    idx = np.nonzero(hit)[0]
    order = np.argsort(t_enter[idx])
    return idx[order], t_enter[idx][order]


# ---------------------------------------------------------------------------
# Single-scattering integrator (front-to-back)
# ---------------------------------------------------------------------------
def shade_ray(cloud, o, d, light_dir, light_color, ambient, t_far=1e9,
              powder=0.5):
    """返回 (radiance(3,), optical_depth, transmittance, candidate_count)。"""
    idx, _ = candidates_along_ray(cloud, o, d, 0.0, t_far)
    L = np.zeros(3)
    T = 1.0                       # 透射率累积（front-to-back）
    total_tau = 0.0
    if idx.size == 0:
        return L, 0.0, 1.0, 0
    # 各 candidate 沿 view ray 的 tau（整段）
    tau_view = ray_gaussian_taus(cloud, o, d, idx, 0.0, t_far)   # (M,)
    centers = cloud.center[idx]
    albedo = cloud.albedo[idx]
    ldir = light_dir / np.linalg.norm(light_dir)
    for k in range(idx.size):
        tau = tau_view[k]
        if tau < 1e-5:
            continue
        alpha = 1.0 - np.exp(-tau)
        # single scattering: 从该 primitive 中心朝光源的解析透射率
        single = np.array([k])
        tau_to_light = ray_gaussian_taus(
            cloud, centers[k], ldir, idx, 0.0, t_far).sum()
        Tl = np.exp(-tau_to_light)
        powder_term = 1.0 - np.exp(-2.0 * tau) * powder
        scat = albedo[k] * light_color * Tl * powder_term
        scat = scat + albedo[k] * ambient        # fake ambient
        L += T * alpha * scat
        T *= (1.0 - alpha)
        total_tau += tau
        if T < 1e-3:
            break
    return L, total_tau, T, int(idx.size)


def render(cloud, cam_pos, cam_target, fov_deg, width, height,
           light_dir, light_color, ambient, bg=(0.02, 0.03, 0.05)):
    """全画面渲染，返回 dict：color / optical_depth / transmittance / candidates。"""
    aspect = width / height
    fwd = np.asarray(cam_target, float) - np.asarray(cam_pos, float)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.array([0, 1.0, 0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    half = np.tan(np.radians(fov_deg) * 0.5)
    cam_pos = np.asarray(cam_pos, float)

    color = np.zeros((height, width, 3))
    od = np.zeros((height, width))
    trans = np.ones((height, width))
    cand = np.zeros((height, width), np.int32)
    bg = np.asarray(bg, float)

    for j in range(height):
        py = (1.0 - 2.0 * (j + 0.5) / height) * half
        for i in range(width):
            px = (2.0 * (i + 0.5) / width - 1.0) * half * aspect
            d = fwd + px * right + py * up
            d /= np.linalg.norm(d)
            L, tau, T, n = shade_ray(cloud, cam_pos, d, light_dir,
                                     light_color, ambient)
            color[j, i] = L + bg * T          # 背景透过残余透射
            od[j, i] = tau
            trans[j, i] = T
            cand[j, i] = n
    return {"color": color, "optical_depth": od,
            "transmittance": trans, "candidates": cand}
