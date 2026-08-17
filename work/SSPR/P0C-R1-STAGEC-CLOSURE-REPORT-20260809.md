# P0c R1 Stage C Closure Report — 2026-08-09

## Outcome

Gate R1 **PASS**. The isolated candidate now contains one ordered, P1-gated Stage C named `SSPR Resolve Continuous Field`, one scratch module named `SSPR_ResolveContinuousField`, and two system-owned private Field RT parameters:

- `User.SSPR_FieldMainRT`
- `User.SSPR_FieldAuxRT`

Both Field RTs are 2048² RGBA16F, bilinear, no inherited external settings. Together with the existing Raw Main/Aux, the live candidate owns four distinct current-frame RT DIs. Formal M3 and `/Game/NewNiagaraSystem.NewNiagaraSystem` were not mutated.

## Recovery points

Pre-R1 exact binary backup:

- `D:/Work/Company/Advance/Fluid/precisefluid/Saved/CodexBackups/P0_StageC_PreR1_20260809-145211/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1.uasset`
- bytes: `1,194,088`
- SHA-256: `A2436A9BE5792D07F29C125345ABF4ED09DE5D49296417D32803AA17D2A43E6C`

R1-pass exact binary backup:

- `D:/Work/Company/Advance/Fluid/precisefluid/Saved/CodexBackups/P0_StageC_R1_Pass_20260809-153000/NS_SSPR_V4Dev_P0_Gather_RawMoments_V1.uasset`
- bytes: `1,322,287`
- SHA-256: `6517FDA40CE6715AC587A0B0F79578ACA8EE2041365B2485A0FD2E945E2CB4C0`

Each copy was checked byte-for-byte by length and SHA-256 before later mutation.

## Structural closure

- Stage order: Stage A `SSPR Rasterize Trails` → Stage B `SSPR Resolve Grid To Material` → Stage C `SSPR Resolve Continuous Field`.
- Stage C iteration source: `User.SSPR_TrajectoryGrid`.
- Stage C `EnabledBinding` export text is identical to Stage B's `P1_IsLastSubstep` binding.
- `bDisablePartialParticleUpdate=true`.
- R1 marker performs same-frame integer point loads from Raw Main/Aux and writes Field Main/Aux; it contains no History or ping-pong state.
- R1 marker HLSL node: `72955175476105439BC8A2B4D2769A34`.
- R1 marker HLSL SHA-256: `8ffebdc5aaf6c1392302339c57eaac5af6d2ee7ead0f9cfc449c653800898e0f`.
- All three Simulation Stage scripts are `UpToDate`; the full Niagara system reports 0 errors and 0 warnings. The two existing upgrade notes remain informational only.

## Runtime ownership and cold-start proof

A fresh `StartPIE(bSimulate=true)` session used the historical Gate C camera and the scene overrides `rate=40,000`, `K=64`, `DensityPerParticle=0.03`. Component user-variable readback resolved four distinct DIs, one for each Raw/Field role. The active world inventory contained exactly four 2048² RGBA16F TextureRTs associated with those active DIs.

The first aggregate reader incorrectly assumed that a TextureRT numeric suffix was the same thing as its DI role suffix and therefore printed `pass:false`. That was a role-assignment error in the reader, not a Stage C failure. Its raw statistics already exposed two exact numerical pairs. A corrected object-pair probe superseded that result:

- Aux pair: 1,048,576 pixels × 4 channels, maximum absolute difference `0`, exact mismatches `[0,0,0,0]`.
- Main pair: 1,048,576 pixels × 4 channels, maximum absolute difference `0`, exact mismatches `[0,0,0,0]`.
- Total exact comparison: 2,097,152 pixels / 8,388,608 channel values.
- Both pairs are finite and non-empty.

Because the probe followed save, component reinitialization and a fresh SIE start, it proves a cold-start, same-frame Raw→Field pass-through rather than stale texture contents.

## Provisional cost observation

One ProfileGPU capture reported Stage A ≈`0.05 ms`, NeighborQuery sort ≈`0.19 ms`, Stage B ≈`1.01 ms`, and the R1 point-copy marker Stage C ≈`0.51 ms`. The full frame was contaminated by fixed-tick catch-up after a long Python readback and by the reference Niagara Fluids system, so these values are attribution-only and do not constitute R1.5 or the final complete-chain performance Gate.

## Safety discipline

All 2048² aggregation stayed inside UE and returned scalar summaries only. Every gateway PowerShell process used a 1 GiB private-memory guard. Asset mutation/apply, component reinitialization, SIE start, runtime readback and profiling were issued as separate requests with engine frames between them.

## Next Gate

R1.5 is now active. It must cover the approved resolution/tap/input/sampling/output/support dimensions and select the first production sampling budget from measured Stage C cost. The temporary microbenchmark HLSL is not a product implementation and must be replaced by the canonical Pilot + shared Main continuous-field resolve before R1.6.
