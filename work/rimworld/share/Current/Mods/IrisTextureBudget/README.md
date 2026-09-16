# Iris Texture Budget

Local RimWorld 1.6 texture-memory and startup-reliability limiter for the `rimworld` project.

The mod patches the base DDS and `Graphics Settings+` loading paths before game content is retained. It does not edit Workshop content or save files.

Default balanced budget:

- UI, storyteller, gizmo, and icon paths: 1024 px
- Pawn, body, head, hair, apparel, race, face, tattoo, and gene paths: 256 px
- Other paths: 512 px

Existing DDS mipmaps are loaded directly from the first safe lower level, without creating the discarded top levels. Other oversized images are resampled once, compressed, and stored in a versioned cache under the RimWorld save-data folder. Cache entries invalidate when source length, modification time, or the selected cap changes.

Do not enable this together with `Image Opt` (`dev.soeur.imageopt`), because both replace the texture-loading pipeline.

## Validation

- RimWorld `1.6.4871 rev591`, isolated 344-item test order.
- The active set exposed about 42,074 textures with an estimated 13.416 GiB of retained GPU data.
- Without a budget, isolated startup exceeded 18.3 GiB private memory before completing.
- First enhanced-cache run: 15,821 direct DDS mip loads, 2,265 resamples/cache writes, about 8.14 GiB of discarded top-level data avoided; startup and compatible-save load completed in 925.2 seconds.
- Hot-cache run: 15,723 direct DDS mip loads, 2,265 cache hits, zero resamples, about 5.94 GiB avoided; completed in 911.0 seconds.
- Persistent cache shortened total startup by about 14.2 seconds (1.5%). Its main value is avoiding repeated CPU resampling, not solving Def/Harmony initialization time.
- Observed startup peaks varied from 17.6–18.2 GiB private and 7.8–8.6 GiB working set. A 16 GB system still relies on paging and should close heavy background applications.
- Eight unusual DDS effect sheets safely fell back to the original loader. No Iris texture failure reached the save.
- Full map, portrait, UI, and effect visual QA remains required before enabling the mod in the real configuration.

Build with:

```powershell
dotnet build Source/IrisTextureBudget.csproj -c Release
```

The DLL is emitted to `1.6/Assemblies`.
