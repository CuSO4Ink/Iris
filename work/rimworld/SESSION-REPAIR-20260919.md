# Session repair — 2026-09-19

## Evidence and scope

Read-only snapshot: `tmp/rimworld/repair-20260919/Player.log`. Game was closed before deployment. No independent game launch, save rewrite, Workshop edit, or active-mod-list change.

- `A34CE07D`: 20 wait/auto-attack exceptions for `RH_DF_Titan162566`; job recovery itself entered repeated failures. The patched method's reported offset is not an original vanilla IL offset, so the particular contributing mod is not proven.
- `E907F6E6`: 11 wander-root exceptions. Actual installed assembly offset 0x003f is `GenGrid.InBounds(cell, pawn.Map)`, confirming an invalid map context.
- `FDBFB5E9`: one VFE Insectoids building damage callback dereferences `parent.Map.listerThings` after damage/destruction. The mod already releases that building's insects in its Destroy prefix.
- `A78F62A1`: four historical Human pawn references resolve by numeric ID to clothing/meals, causing invalid casts. These exact pawn references are absent from the newest saved colony (`绮罗百合邦9`). No ID-based pawn reconstruction, deletions or save surgery performed.

## Installed

Added `IrisFixes/Assemblies/IrisSessionRepairs.dll`, built separately from the existing IrisFixes DLL. The existing main DLL and unfinished profiler source were not redeployed.

- Reject off-map wandering before job creation; return an invalid destination for off-map wander-root requests.
- Reject off-map wait auto-attack entry. Within the original wait implementation, make the bounds query and native beat-fire call tolerate removal during callbacks. Preserve all other original instructions and other mods' patches.
- Skip VFE Insectoids post-damage callbacks whose parent has no map. Normal live-building activation is unchanged; a destroyed building no longer attempts its late map-wide notification. Its existing own-insect release remains intact.
- If auto-attack still fails, preserve the error and add one context diagnostic (spawn state, map, native verbs, stance/melee trackers and job). This is not proof that every Titan failure cause is fixed.

## Ratkin visual adjustment

The blue-haired matching saved pawn is `Ratkin69599` (金缕梅茶), with `RK_Mai`, `RK_HeadType_Head7`, and Facial Animation `HeadPointy`. The on-screen animated head therefore is not simply the native Ratkin head texture. Inspection did not establish a missing texture or show that the resolution upgrade overrides Head7.

A provisional fit adjustment is installed only for Ratkin + RK_Mai + horizontal facing while Facial Animation actually draws the pawn: hair x/z scale ×1.08 and local z offset +0.015. No raster assets changed. Other hairstyles, north/south views, the head and ears retain their existing rules. This is an empirical fit candidate, not a proven general transform-system fix. It requires normal-game visual verification, including both side directions and head-turn animations. If it fails, revise/remove this narrow adjustment rather than scaling all Ratkin.

## Previously prepared storage repair deployed

Installed the verified `IrisStorageDefaults` DLL, rules and filter defs together. Mechanical butcher outputs such as Steel no longer enter the meat blacklist; the additional storage classification changes are described in `STORAGE-AUDIT-20260919.md`. Existing placed storage and saved bills are not rewritten; use Defaults to apply templates to existing buildings.

## Verification and rollback

- Builds: zero warnings/errors.
- 14 targeted runtime-repair checks: real installed Harmony targets accepted, actual patched wander method safely handles an off-map pawn, only two calls replaced in wait IL, FA API and narrowly scoped hair predicates verified.
- 18 storage classification checks passed.
- Installed files compared byte-for-byte to their build inputs; ModsConfig unchanged.
- Backup: `tmp/rimworld/repair-20260919/backup-111753/`. Remove only the added `IrisSessionRepairs.dll` to undo these session/visual patches; restore backed-up storage files to undo the storage deployment.
- No live visual or normal-session error-free claim yet. Next normal play should verify the blue-haired Ratkin side profile and whether the named exception references recur.
