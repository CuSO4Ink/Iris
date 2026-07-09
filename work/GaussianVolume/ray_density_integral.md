# Anisotropic Gaussian Ray Density Integral

> Mathematical derivation for the analytic optical depth used in GaussianVolume MVP.
> This documents the core formula: projecting a 3D anisotropic Gaussian density
> field along a ray and integrating it analytically via erf.

## 1. Gaussian Volume Primitive

Each primitive is an anisotropic Gaussian ellipsoid in 3D:

```
density(x) = sigma_t * exp(-0.5 * (x - c)^T Sigma^{-1} (x - c))
```

where:
- `c` is the center (3,)
- `Sigma = R * diag(scale^2) * R^T` is the covariance matrix
- `Sigma^{-1} = R * diag(1/scale^2) * R^T` (precomputed as `_Sinv`)
- `R` is the rotation matrix from quaternion
- `scale` is the per-axis standard deviation (local frame)
- `sigma_t` is the peak extinction coefficient

## 2. Ray Definition

A ray is parameterized as:

```
x(t) = o + t * d,  t in [t0, t1]
```

where `o` is the ray origin and `d` is the unit direction.

## 3. Density Along the Ray

Substitute `x(t)` into the density function:

```
density(t) = sigma_t * exp(-0.5 * q(t))
```

where the quadratic form is:

```
q(t) = (o + t*d - c)^T Sigma^{-1} (o + t*d - c)
```

Let `m = o - c`:

```
q(t) = (m + t*d)^T Sigma^{-1} (m + t*d)
     = m^T Sinv m + 2t * m^T Sinv d + t^2 * d^T Sinv d
     = C + 2B*t + A*t^2
```

with:
- `A = d^T Sinv d`  (scalar, always > 0 for positive-definite Sigma)
- `B = m^T Sinv d`  (scalar)
- `C = m^T Sinv m`  (scalar, always >= 0)

## 4. Completing the Square

Rewrite `q(t)` by completing the square:

```
q(t) = A*(t - t*)^2 + (C - B^2/A)
```

where:

```
t* = -B / A          # ray parameter at peak density
```

The peak value of the exponent:

```
peak = -0.5 * (C - B^2/A)    # <= 0 since C >= B^2/A (Cauchy-Schwarz)
```

So:

```
density(t) = sigma_t * exp(peak) * exp(-0.5 * A * (t - t*)^2)
           = amp * exp(-0.5 * (t - t*)^2 / sig1d^2)
```

where:
- `amp = sigma_t * exp(peak)`  (peak extinction along this ray)
- `sig1d = 1 / sqrt(A)`       (1D standard deviation of projected Gaussian)

**Key insight**: The 3D anisotropic Gaussian, when sampled along a ray,
reduces exactly to a 1D Gaussian in `t`. This is what makes analytic
integration possible.

## 5. Optical Depth (Analytic Integral)

The optical depth (optical thickness) along [t0, t1] is:

```
tau = integral_{t0}^{t1} density(t) dt
    = amp * integral_{t0}^{t1} exp(-0.5 * (t - t*)^2 / sig1d^2) dt
```

This is a standard Gaussian integral. Using the error function (erf):

```
tau = amp * sig1d * sqrt(2*pi) * 0.5 * [erf(z1) - erf(z0)]
```

where:

```
z0 = (t0 - t*) / (sqrt(2) * sig1d)
z1 = (t1 - t*) / (sqrt(2) * sig1d)
```

### Physical Interpretation

- `tau` is the optical depth = integrated extinction along the ray segment
- `transmittance T = exp(-tau)` = fraction of light passing through
- `alpha = 1 - exp(-tau)` = opacity for front-to-back compositing
- When `t*` is outside `[t0, t1]`, the erf difference captures only the tail

### Special Cases

- **t0=0, t1=inf** (full ray): `z0 -> -inf, z1 -> +inf`, so `erf(z1)-erf(z0) -> 2`,
  giving `tau = amp * sig1d * sqrt(2*pi)` = peak * width of the 1D Gaussian.
- **Ray misses bounding sphere**: `tau` will be negligibly small (tail only).

## 6. Implementation (NumPy)

The vectorized implementation in `gaussian_volume.py`:

```python
Sd = Sinv @ d                    # (M,3) = Sinv contracted with d
A = d^T Sinv d = dot(Sd, d)      # (M,)
B = m^T Sinv d = dot(m, Sd)      # (M,)
C = m^T Sinv m                   # (M,)

t_star = -B / A
peak = -0.5 * (C - B^2 / A)
sig1d = 1 / sqrt(A)
amp = sigma_t * exp(peak)

z0 = (t0 - t_star) / (sqrt(2) * sig1d)
z1 = (t1 - t_star) / (sqrt(2) * sig1d)
integral = sig1d * sqrt(2*pi) * 0.5 * (erf(z1) - erf(z0))
tau = amp * integral
```

All operations are element-wise on arrays of shape `(M,)` where M = candidate count,
making it fully vectorizable.

## 7. Precomputed Light-Direction Tau Matrix

When the light direction `ldir` is fixed for a frame, we precompute a
`(N, N)` matrix where:

```
tau_light[i, j] = tau of primitive j along ray(center[i], ldir)
```

This is the same formula with `o = center[i]`, `d = ldir`, `idx = j`.

The precompute is O(N^2) once per frame. In `shade_ray`, the per-candidate
light attenuation `tau_to_light = sum(tau_light[idx[k], idx])` becomes O(M)
table lookup instead of O(M^2) repeated `ray_gaussian_taus` calls.

### Chunked Computation

For N=1024, the full `(N, N, 3)` intermediate arrays would be ~24MB. The
implementation chunks over origin batches (chunk_size=256) to keep peak
memory at `(256, N, 3)` ~ 6MB.

## 8. erf Approximation

Without scipy, we use Abramowitz & Stegun 7.1.26 (error < 1.5e-7):

```
erf(x) = sign(x) * [1 - (a1*t + a2*t^2 + a3*t^3 + a4*t^4 + a5*t^5) * exp(-x^2)]
where t = 1 / (1 + p*x), p = 0.3275911
a1=0.254829592, a2=-0.284496736, a3=1.421413741, a4=-1.453152027, a5=1.061405429
```

This is numba-compatible (no external calls).

## 9. Performance Summary

| Configuration                    | ray/s @ N=1024 | Speedup |
|----------------------------------|----------------|---------|
| Pure Python BF (original)        | 355            | 1x      |
| NumPy BF + tau matrix            | 3,675          | 10.4x   |
| Numba BF + tau matrix (parallel) | 763,485        | 2,151x  |

The Numba version achieves real-time rates for 200x150 resolution.
