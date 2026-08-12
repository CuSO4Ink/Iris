# Q2 pool-free optical-depth raster evidence

Environment: UE 5.8, D3D12, RTX 5060, 1920×1080, Q2 9,944 primitives, `-game`, offscreen, no VSync. Statistics use the last 300 rows of each 500-frame CSV capture.

| Internal scale | GPU total P50/P95 | `GPU/GaussianVolumePoolFree` P50/P95 |
|---|---:|---:|
| 1.0 | 6.8625 / 7.5071 ms | 1.9661 / 2.1377 ms |
| 0.5 | 5.4609 / 5.5104 ms | 0.5996 / 0.6007 ms |

At 0.5× the runtime RHI dump contains only:

- `GaussianVolumePoolFree.Tau`: `1.1875 MiB`, transient R16F render target;
- `GaussianVolumePoolFree.GaussianBuffer`: `0.3125 MiB`;
- total named GaussianVolume resources: `1.50 MiB`.

There is no candidate pool, tile buffer, LightTau buffer, or `GaussianVolumePoolFree.Output` in the runtime dump. The full-resolution output is only an editor/non-UAV fallback.

This camera is the standard runtime view, not the user-reported `50+ ms` close-up worst case. Do not use it to claim the close-up Gate has passed.
