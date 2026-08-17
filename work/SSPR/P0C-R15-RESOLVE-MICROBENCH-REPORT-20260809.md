# P0c R1.5 Resolve Microbenchmark Report — 2026-08-09

> Gate result: **PASS FOR FIRST PRODUCTION BUDGET**. This Gate selects the first Stage C budget; it is not the final whole-system performance acceptance.

## Scope and isolation

- Candidate: `/Game/SSPR_Validation/M3/Performance/P0_Gather_RawMoments_V1/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1`.
- Only the candidate Niagara component was ticking during the captures. The Niagara Fluids gold reference and every other PIE Niagara component were deactivated.
- Runtime audits, not only asset defaults, proved the active candidate used exactly four private RGBA16F RenderTarget2D DIs and one Grid2DCollection at each requested resolution: `512²`, `1024²`, and `2048²`.
- The validation contract remains one active system instance. At `2048²`, `2 Raw + 2 Field` is a persistent lower-bound allocation of `128 MiB` per instance, excluding Grid, transient UAV/RDG state, and driver overhead.
- Every live request used the UEAgent route and a PowerShell private-memory guard of `1024 MiB`; no full RT pixel array crossed MCP/PowerShell.

## Measured matrix

All Stage values below are the ProfileGPU event `Stage(SSPR Resolve Continuous Field)`. Point variants use explicit integer `Load`; every logical tap reads the selected Raw input set and writes the selected Field UAV set.

| Resolution | Logical taps | Inputs | Sampling | Outputs | Support | Stage GPU | Custom-HLSL SHA-256 |
|---|---:|---:|---|---:|---|---:|---|
| 2048² | 16 | 2 RT | Point | 2 UAV | full | 0.84 ms | `7f11518252e4e627d0df7906f68c8262cbb3700fc780a6b5e85812591997c540` |
| 2048² | 24 | 2 RT | Point | 2 UAV | full | 1.03 ms | `461d44d82e2dcd31ab9b00b92c55fb11fba7e5d7a29d874a51edfb96825e19f6` |
| 2048² | 32 | 2 RT | Point | 2 UAV | full | 1.42–1.47 ms | `3032adca5dc35f58766e5bb457e30d04f5598dacdbb6e109766c5f4621f694d4` |
| 2048² | 48 | 2 RT | Point | 2 UAV | full | 2.74 ms | `5e38fc1e8e01ebcc38785bd84ca083a4bb6aeebda8b247e778e3e90eb6b0f6e4` |
| 512² | 32 | 2 RT | Point | 2 UAV | full | 0.11 ms | `36fadd82b0ed44f570d68ba850de5b23d9dd1fcae65867302a3b87a5d309a520` |
| 1024² | 32 | 2 RT | Point | 2 UAV | full | 0.64 ms | `b286549e3c1dfd4a202c7f448e3f203c03d4aa286d31ddd0f8a2c7571153708c` |
| 2048² | 32 | 1 RT | Point | 2 UAV | full | 0.88 ms | `2046b0cba9b31ebfff9f7e4da9d27fcbdbf3346c22521891941b9d77bb3f5a` |
| 2048² | 32 | 2 RT | Point | 1 UAV | full | 1.50 ms | `9a5f1818da0504991f5c6d67be296075c58b574fcf6375ee81817c06706b8001` |
| 2048² | 32 logical / 256 physical loads | 2 RT | manual bilinear equivalent | 2 UAV | full | 30.87 ms | `61fc9c36373f2a8255950d65ec3c78b7d42d4d9d4983f4cac018d0389dd8ecf0` |
| 2048² | 32 | 2 RT | Point | 2 UAV | 25% checkerboard | 1.36 ms | `d1c34cf3dacdeb87879f7cb0f98ea96f79139350c02f09f2271bbc5e4cb892b5` |
| 2048² | 32 | 2 RT | Point | 2 UAV | real sparse-density early-out | 1.04 ms | `b08b286b3f51f812bd9e0c7299c5a1c8971de9c9dde87c9b414923b643cf6501` |

The manual-bilinear row deliberately exposes the physical-load multiplication and is rejected, not a production candidate. The 25% checkerboard row shows that merely masking output does not remove most dispatch/read cost; the density-driven Pilot early-out is the only accepted sparse path.

## Whole-frame caveat

The editor was background-throttled to `8 Hz` (`DeltaSeconds=0.125`) despite throttle cvar attempts. Several captures therefore contain multiple fixed-tick catch-up substeps. Observed frame values ranged roughly from `33–50 ms`, with contaminated outliers around `95–96 ms`; they are retained in the raw log but are not comparable whole-frame measurements and are not used to pass this Gate. Final Gate A/B still requires a representative foreground window, fixed viewport/state, warmup, sampling window, median/P95, and the complete gold-reference chain.

Niagara authoring exposed the exact Custom HLSL and its hashes above, compile state, runtime dispatch dimensions, and ProfileGPU stage event. Generated shader assembly was not exposed by the available authoring interface, so this report records it as unavailable rather than inferring it. No RDG implementation is authorized by this result.

## Decision

The first production Stage C budget is frozen as:

```text
9-tap isotropic Pilot
+ 24-tap shared nested Main
= 33 total logical taps
2 Raw Point/Load inputs
2 Field UAV outputs
Pilot-support early-out
```

This is the closest production topology to the measured 32-tap envelope. `48` taps and Bilinear are rejected for the first candidate. The actual guidance/depth arithmetic must be profiled again after production HLSL installation; this Gate does not allow hiding extra taps or claiming the synthetic `1.42–1.47 ms` as the final Stage C cost.

