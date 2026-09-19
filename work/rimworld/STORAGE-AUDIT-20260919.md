# Storage audit — 2026-09-19

Status: source/compiled repair STAGED ONLY. Game PID8432 running. Installed mod, live Defaults parameters, saved objects and remote Current profile unchanged this turn.

## Confirmed gaps

1. Steel is present in the live nonfood biological materials template and absent from all three pallet templates. Root code bug: Rules.Build unconditionally blacklisted race.meatDef for Humanlike/insect/etc races. Mechanical races can use Steel as their butcher material; that does not make Steel meat. Earlier explicit pallet whitelist was insufficient because Banned was checked before role classification. Corrected RegisterMeatProduct requires an actual meat definition; retained essential material role preservation.
2. BabyFood has only consuming appliances, no normal pantry/cabinet destination. Added baby food zone.
3. Fertilized eggs have only Hopper destination. Added incubating egg zone and comp-based hatchability classification; exclude from ordinary ingredients and appliance feed.
4. Luciferium, Ambrosia, Penoxycyline, GoJuice, WakeUp have no storage destination. Added special drug/consumable reserve zone. Storage permission does not permit consumption or change drug schedules.
5. Necro_Meat still allowed in Hopper/BiosculpterPod/GrowthVat/WRMC_WolfeinGrowthVat; Human meat likewise in multiple feeding pods. They were left untouched as special buildings. Now apply source exclusions and special ingredient exclusions to these template filters while preserving their functional building restrictions.
6. Pallets allow Silver/Gold/Jade at same priority as safe. Excluded valuables from bulk role.
7. Precision crates include MedicineHerbal/Industrial/Ultratech and broad manufactured resources. Excluded medical supplies, bulk materials, valuables and mortar shells from precision role.
8. Biocoded weapons/apparel and tainted apparel lacked dedicated storage outside consuming equipment. Added coded equipment and laundry zones with inverse existing special filters. No destruction/recycling bill enabled.
9. Nonfood biological zone formerly allowed only banned ingredient defs, not contaminated mixed meals. Added inverse clean-source special filter, allowing ingredient-recorded contaminated foods while rejecting normal food in that zone. Does not pretend to reconstruct unrecorded ingredients.

## Scope and validation

18 focused checks pass, including mechanical material blacklisting, steel, medical/precision separation, valuables, baby food/eggs/special drugs, new ordinary food, humanlike meat, Necro meat and mixed meals. Build clean. Native full DefDatabase startup and real filter UI still await next normal restart; offline tests do not replace runtime verification.

New templates are created when absent by the startup updater. Existing map storage, pawn diet policies and bills remain untouched. No queued repair is silently applied to the current save. Defaults templates remain managed by StorageRules.xml; manually changing those managed templates is overwritten at next startup, while map-specific filters remain independent.

Runtime errors from September18 (snowman blueprint54967, Quest21 null pawn, rendering/menu/invalid references) are separate unresolved work, not fixed by this classification update. No pawn deletion, broken-reference guessing, cache purge or log suppression performed.

After exit: back up installed DLL/Defs/manifest/Defaults configuration; deploy together, keep272active list; verify startup classification and special filters; then sync exported Current profile and parameter snapshots. Source DLL must not be exported as if already running.
