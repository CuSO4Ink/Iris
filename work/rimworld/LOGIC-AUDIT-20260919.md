# Targeted interaction audit — 2026-09-19

This is a review, not a game simulation or an exhaustive audit of 272 mods. No runtime files, configuration, enabled list or saves changed in this turn. No independent game launched.

## Evidence

Installed IrisBalance, IrisTalentProgression, IrisRitualRecruitment and IrisStorageDefaults DLLs match their inspected build artifacts byte-for-byte. Inspected installed main IrisFixes drawing code separately; its staged profiler is not installed. Reviewed generation/ritual scope, skill shaping, cooldown state, storage special filters, medical recipe changes, post-destruction callbacks and drawing lifecycle. Original-game control flow inspected from the locally decompiled assembly.

Current talent policy rebuilt and executed for 60,000 deterministic cases (20,000 each at development 0, .5, 1). Level limits, shaped-skill budgets and passion-count constraints passed. Mean shaped totals: 10.34 / 19.02 / 28.24; mean best shaped skill: 3.31 / 5.32 / 7.52. These are algorithm outputs, not full generated-pawn statistics after protected skills and other mods.

Necro cooldown boundary, extension, disabled-duration and quest/forced exemption checks passed, as did actual Harmony target installation in the offline harness.

## Confirmed gaps

### 1. Storage special filters only apply inside Foods

Both Iris special filters declare parentCategory Foods. ThingFilter.Allows(Thing) calls a special worker but rejects an item only when its definition belongs to that category (unless the entire filter is special-only). Rules.Matches("bio", d) accepts ingestibles irrespective of category.

Concrete example: Core Beer inherits Drugs -> Manufactured -> Root and has Fluid/Processed/Liquor food flags. The installed classifier admits it to bio; CleanFoodSourceFilter matches it, but the game's category predicate is false, so that filter cannot reject it. Thus normal drinks/drugs can enter the non-food disposal template. Conversely, a mod ingestible outside Foods with forbidden recorded ingredients can evade the ingredient special filter when otherwise allowed.

Offline executed the actual classifier, worker and category predicate: admitted=True, worker=True, effective rejection=False; moving the same definition under Foods gives rejection=True. Full ThingFilter.Allows could not execute in the standalone harness because ModsConfig initializes Unity-native paths; no claim of in-game reproduction.

Repair direction: widen the special filters' category scope appropriately while retaining worker eligibility, and test actual item filtering for clean drugs, ordinary meals and contaminated custom-category products. Do not just remove every drink from storage.

### 2. Talent shaping does not preserve PawnKindDef.skills ranges

AfterSkills protects declared backstory/trait gains and skips minTotalSkillLevels/minBestSkillLevel, but does not check per-skill PawnKindDef.skills or extraSkillLevels. Vanilla applies those ranges before the postfix. A qualifying unprotected skill can therefore be overwritten below its declared minimum; the later validation inspected checks disabled work, not that numerical range.

Installed mods contain real per-skill declarations (e.g. VPE Warlord Shooting/Melee 11~16). Non-player fighter combat preservation often protects those examples, so do not claim every such pawn is currently affected. The gap remains for other eligible skills/kinds or when combat preservation is disabled.

Repair direction: preserve explicit per-skill constraints in shaping, and define how extraSkillLevels should interact with the intended low-skill distribution. The current total budget also deliberately excludes protected background/trait skills; it is not a cap on the pawn's total ability.

### 3. Previous spawner guard omits an intended side effect

The last-turn SpawnerDamage prefix rejects an already-destroyed parent with no map. It prevents the observed null access and retains the original Destroy-prefix release from that building. However, PostPostApplyDamage also normally activates other armed building spawners on the map. Skipping it loses that map-wide notification for fatal hits. This is a confirmed semantic limitation of our new patch, not proof of an upstream-only defect.

Repair direction: preserve the pre-damage map context and perform the original notification once, including fatal damage. Account for nested damage and avoid retaining maps indefinitely or double-spawning insects.

## Remaining validation / cost candidates

- RK_Mai/Facial Animation side-view fit is empirical. Both side directions, head turns, portraits and other scales still need visual verification. It is not a general head-transform fix.
- Installed StaleDrawRepair scans all dynamic things every DrawDynamicThings call and linearly checks duplicates on registration. This adds O(N) per draw and potentially O(N²) work across bulk registrations. Actual time share is unmeasured; replace only after profiling, preserving required draw-array consistency.
- Ritual whitelist depth is restored by a finalizer; generation occurs synchronously within the inspected base ritual call. No specific depth leak found. The whitelist chooses races, not xenotypes or sex, and cannot certify unrelated mods' generated-pawn constraints.
- Necro quest/forced exemptions intentionally allow events during cooldown. Existing incident spawners are outside this cooldown. Neither implies a cooldown bug by itself.
- The inspected surgery patch removes the brain target and uses Recipe_AddHediff. This review did not simulate every third-party surgery/hediff callback or resurrection path.
- Earlier invalid snowman blueprints and RI null-pawn quests were not repaired by the latest session guards. They remain distinct historical issues; do not describe them as resolved or mutate current save IDs based on an old colony.

## Priority

First fix the filter category hole and explicit skill-range protection; then preserve the destroyed-spawner notification. Keep visual fit verification and measured rendering optimization separate from correctness fixes. Audit scope does not justify a claim that all major mods are bug-free.
