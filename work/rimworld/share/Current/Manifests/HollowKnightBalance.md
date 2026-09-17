# Hollow Knight balance revision 1

Conservative targeted XML overlay for the installed 1.6 version. Changes23 existing fields, no new mod or global cap. Does not edit Workshop files, existing original IrisBalance patch, skills, raid points or Boss stage logic. Affects any pawn using the corresponding definitions, including NPCs.

| Effect | Before | After |
|---|---|---|
| Quick Slash melee cooldown | x0.5 | x0.8 |
| Quick Slash ranged cooldown/aim time | x0.5 each | x1 each |
| Fragile Strength melee damage / AP offset | x2 / +0.25 | x1.25 / +0.05 |
| Unbreakable Strength melee damage / AP offset | x2 / +0.5 | x1.35 / +0.05 |
| Steady Body / Broken Vessel reward cooldown offsets | -0.1 each melee/ranged | -0.05 each |
| Pure Vessel reward incoming damage / consciousness offset | x0.5 / +0.5 | x0.85 / +0.05 |
| Pale King trait damage / incoming / ranged cooldown | x2 / x0.25 / x0.25 | x1.35 / x0.7 / x0.8 |
| Pale King trait melee hit/dodge factors | x2 each | x1.15 each |
| Pale King AP offset | +1 | +0.05 |
| Quirrel trait incoming damage | x0.5 | x0.85 |
| Quirrel AP / hit / dodge offsets | +1 / +20 / +20 | +0.05 each |

Previous Void Heart x1.75 and armor/weapon patches retained. Timed invulnerability, dash, Boss protection windows, spells, lifeblood/shield/recovery, acquisition research and costs not changed in this revision. Therefore not a claim that every possible cross-mod build is balanced.

Verification: each XPath uniquely resolves against current installed XML; all23 fields exist; none overlaps earlier Hollow Knight patch paths. XML parsed; installed and export files compared byte-for-byte. Active ModsConfig unchanged. No DLL change required; no game launched. Actual combat tuning awaits normal play. Existing pawn stats should resolve updated Def values after restart; not editing saved pawn states.

Evidence and original patch/list backups: tmp/rimworld/hollow-balance-20260917/. Remove only HollowKnightProgression.xml while the game is closed to revert this revision.
