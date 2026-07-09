"""
GaussianVolume MVP - standalone CPU renderer
Reproduce "Don't Splat your Gaussians" minimal engineering structure:
  - Gaussian volume primitive data structure
  - ray-Gaussian analytic transmittance (erf interval integral)
  - brute-force traversal + candidate stats
  - front-to-back compositing + single scattering (fake ambient / powder)
  - precomputed light-direction tau matrix (O(N^2) once/frame -> O(M) lookup/ray)
  - debug view (optical depth / transmittance / candidate count)

Pure NumPy, offline rendering. Goal: answer MVP three questions, not final accuracy.
"""
from __future__ import annotations
import numpy as np

SQRT_2PI = np.sqrt(2.0 * np.pi)


# ---------------------------------------------------------------------------
# Primitive structure
# ---------------------------------------------------------------------------
class GaussianCloud:
    """Batch of Gaussian volume primitives, column-stored for vectorization.

    Attributes (per primitive):
      center   (3,)   ellipsoid center
      scale    (3,)   per-axis std dev (local coords)
      quat     (4,)   rotation (w,x,y,z), local -> world
      sigma_t  ()     peak extinction coefficient (density)
      albedo   (3,)   single-scatter albedo
    """

    def __init__(self, center, scale, quat, sigma_t, albedo):
        self.center = np.asarray(center, np.float64)      # (N,3)
        self.scale = np.asarray(scale, np.float64)        # (N,3)
        self.quat = np.asarray(quat, np.float64)          # (N,4)
        self.sigma_t = np.asarray(sigma_t, np.float64)    # (N,)
        self.albedo = np.asarray(albedo, np.float64)      # (N,3)
        self.N = self.center.shape[0]
        self._R = _quat_to_matrix(self.quat)              # (N,3,3) local->world
        # Sigma^{-1} = R S^{-2} R^T
        inv_s2 = 1.0 / (self.scale ** 2)                  # (N,3)
        Rt = np.transpose(self._R, (0, 2, 1))
        self._Sinv = np.einsum('nij,nj,njk->nik', self._R, inv_s2, Rt)  # (N,3,3)
        # bounding sphere radius: 3 sigma max axis
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
# Ray-Gaussian analytic transmittance
# ---------------------------------------------------------------------------
def _erf(x):
    # erf approximation without scipy (Abramowitz & Stegun 7.1.26), error < 1.5e-7
    s = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1.0 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t
                - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def ray_gaussian_taus(cloud: GaussianCloud, o, d, idx, t0, t1):
    """Compute optical depth along ray(o,d) for primitives idx in [t0,t1].

    Project 3D anisotropic Gaussian along ray into 1D Gaussian:
      Let m = o - c, quadratic q(t) = (m+td)^T Sinv (m+td) = A t^2 + 2B t + C
      density(t) = sigma_t * exp(-0.5 q(t))
      Complete square: -0.5 A (t - t*)^2 + peak,  t* = -B/A, 1D sigma = 1/sqrt(A)
      Interval integral via erf. Returns tau per primitive.
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
    peak = -0.5 * (Cq - B * B / A)              # exponential peak (<=0)
    sig1d = 1.0 / np.sqrt(A)                     # 1D std dev
    amp = sigma_t * np.exp(peak)                 # peak extinction
    # integral of exp(-0.5 (t-t*)^2 / sig^2) dt over [t0,t1]
    z0 = (t0 - t_star) / (np.sqrt(2.0) * sig1d)
    z1 = (t1 - t_star) / (np.sqrt(2.0) * sig1d)
    integral = sig1d * SQRT_2PI * 0.5 * (_erf(z1) - _erf(z0))
    tau = amp * integral
    return np.maximum(tau, 0.0)                  # (M,)


# ---------------------------------------------------------------------------
# Precompute light-direction tau matrix
# ---------------------------------------------------------------------------
def precompute_light_tau_matrix(cloud, ldir, t_far=1e9, chunk_size=256):
    """Precompute (N, N) light-direction optical depth matrix.

    tau_light[i, j] = tau of primitive j along ray(origin=center[i], dir=ldir).
    Once per frame (light direction fixed), replaces O(M^2) per-candidate
    light attenuation in shade_ray with O(M) table lookup.

    Chunked to avoid (N, N, 3) intermediate arrays.
    """
    N = cloud.N
    ldir = np.asarray(ldir, float)
    ldir = ldir / np.linalg.norm(ldir)
    tau_light = np.zeros((N, N), dtype=np.float64)

    # Direction-dependent quantities shared by all origins
    Sd = np.einsum('nkl,l->nk', cloud._Sinv, ldir)  # (N,3) Sinv @ d
    A = np.einsum('nk,k->n', Sd, ldir)               # (N,) d^T Sinv d
    A = np.maximum(A, 1e-12)
    sig1d = 1.0 / np.sqrt(A)                          # (N,)
    sigma_t = cloud.sigma_t                           # (N,)
    sqrt2_sig = np.sqrt(2.0) * sig1d                  # (N,)

    for i0 in range(0, N, chunk_size):
        i1 = min(i0 + chunk_size, N)
        o_batch = cloud.center[i0:i1]                 # (B,3)
        m = o_batch[:, None, :] - cloud.center[None, :, :]  # (B,N,3)
        B_coef = np.einsum('bnk,nk->bn', m, Sd)       # (B,N) m^T Sinv d
        Sinv_m = np.einsum('nkl,bnl->bnk', cloud._Sinv, m)  # (B,N,3)
        Cq = np.einsum('bnk,bnk->bn', m, Sinv_m)      # (B,N) m^T Sinv m

        t_star = -B_coef / A[None, :]                  # (B,N)
        peak = -0.5 * (Cq - B_coef**2 / A[None, :])    # (B,N)
        amp = sigma_t[None, :] * np.exp(peak)          # (B,N)

        z0 = (0.0 - t_star) / sqrt2_sig[None, :]       # (B,N)
        z1 = (t_far - t_star) / sqrt2_sig[None, :]     # (B,N)
        integral = sig1d[None, :] * SQRT_2PI * 0.5 * (_erf(z1) - _erf(z0))
        tau_light[i0:i1] = np.maximum(amp * integral, 0.0)

    return tau_light


# ---------------------------------------------------------------------------
# Traversal: bounding-sphere brute force
# ---------------------------------------------------------------------------
def candidates_along_ray(cloud, o, d, t_near=0.0, t_far=1e9):
    """Return primitive indices intersecting ray bounding sphere, sorted by entry t."""
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
              powder=0.5, tau_light=None):
    """Return (radiance(3,), optical_depth, transmittance, candidate_count).

    tau_light: precomputed light-direction (N,N) tau matrix. When provided,
    uses O(M) table lookup instead of O(M^2) per-candidate ray_gaussian_taus.
    """
    idx, _ = candidates_along_ray(cloud, o, d, 0.0, t_far)
    L = np.zeros(3)
    T = 1.0                       # accumulated transmittance (front-to-back)
    total_tau = 0.0
    if idx.size == 0:
        return L, 0.0, 1.0, 0
    # Per-candidate view-ray tau (full interval)
    tau_view = ray_gaussian_taus(cloud, o, d, idx, 0.0, t_far)   # (M,)
    centers = cloud.center[idx]
    albedo = cloud.albedo[idx]
    ldir = light_dir / np.linalg.norm(light_dir)
    for k in range(idx.size):
        tau = tau_view[k]
        if tau < 1e-5:
            continue
        alpha = 1.0 - np.exp(-tau)
        # single scattering: analytic transmittance from primitive center toward light
        if tau_light is not None:
            tau_to_light = tau_light[idx[k], idx].sum()
        else:
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
           light_dir, light_color, ambient, bg=(0.02, 0.03, 0.05),
           tau_light=None):
    """Full-frame render. Returns dict: color / optical_depth / transmittance / candidates.

    tau_light: precomputed light-direction tau matrix. If None, auto-precomputes.
    Pass tau_light='disable' to force old per-candidate path (for benchmarking).
    """
    aspect = width / height
    fwd = np.asarray(cam_target, float) - np.asarray(cam_pos, float)
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, np.array([0, 1.0, 0]))
    right /= np.linalg.norm(right)
    up = np.cross(right, fwd)
    half = np.tan(np.radians(fov_deg) * 0.5)
    cam_pos = np.asarray(cam_pos, float)

    # Resolve tau_light mode
    force_old = (isinstance(tau_light, str) and tau_light == "disable")
    if tau_light is None:
        tau_light = precompute_light_tau_matrix(cloud, light_dir)
    elif force_old:
        tau_light = None

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
                                     light_color, ambient,
                                     tau_light=tau_light)
            color[j, i] = L + bg * T          # background through residual transmittance
            od[j, i] = tau
            trans[j, i] = T
            cand[j, i] = n
    return {"color": color, "optical_depth": od,
            "transmittance": trans, "candidates": cand}
