# GaussianVolume evidence index

Authoritative 2026-07-24 artifacts:

- `q3-120/metrics.json` — rejected Q3 24K@120 held-out evaluation and checkpoint hash.
- `memory-20260724-pool512/` — delayed warm-frame D3D12 logs for Q2 Gaussian, NanoVDB FpN, and UE SVT U8.
- `perf-20260724-pool512/` — matched 500-frame CSV captures for the 512K default pool and a 1M-pool CVar override; reported statistics use the last 300 valid frames.
- `perf-20260724-poolfree-multirate/` — full-resolution versus 0.5× R16F optical-depth pool-free 500-frame CSV captures, plus the 0.5× runtime RHI memory dump.

Earlier diagnostic captures:

- `memory-20260724-pool1m/` used editor worlds rather than Play; its Empty deltas are invalid and must not be cited.
- `memory-20260724-live-game/` is an incomplete first harness run.
- `memory-20260724-live-game-v2/` validates the real `-game` harness and Windows per-process counters with the 1M pool, but process-total deltas are dominated by UE heap reservation variance. Use it only as a diagnostic, not as the memory headline.

The signed fixed-Hero memory numbers are recorded in `../LOG.md` and `../SPEC.md`. Final matched-quality, continuous-camera, and 1/4/16-instance gates remain open.
