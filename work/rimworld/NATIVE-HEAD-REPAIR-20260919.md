# Ratkin / Smelted Loong native head compatibility

User confirmed these are the two affected groups. Game closed at installation. Only IrisSessionRepairs.dll updated; no Workshop, save or active-list edits.

## Evidence

Current-save Ratkin pairs native RK_HeadType_Head7/3 with generic FA HeadPointy/HeadNormal. The two Loong pawns use native SmeltedLoongHeadGP and SmeltedLoongHeadMC_B, but both display generic HeadPointy. Original native texture files exist and were inspected. The installed Loong LoadFolders.xml includes its sbFA compatibility resources under v1.5, but does not enable those resources in v1.6. This is additional evidence against extending a universal empirical hair scale.

## Implemented behavior and tradeoff

- NativeHeadCompatibility suppresses both FA face-node creation and the FA hide-native-head / replace-hair-mesh decisions for Ratkin or a SmeltedLoongHead* native head when the chosen FA head is generic (HeadNormal, HeadPointy, HeadSquare, or not yet initialized).
- Dedicated FA head choices bypass this repair. All other races and ordinary Human heads retain their current behavior.
- Removed the previous HairFit class entirely: no +8% hair scale, +.015 offset or side-only empirical correction remains.
- The targeted generic-FA characters return to their original head artwork and hair rules. They lose generic FA blink/mouth animation; original ears, horns, tails, hair, genes, skills and saved face-controller data remain unchanged. Native head/eye appearance can visibly differ from generic FA, which is intentional.
- No new artwork, indiscriminate race scaling, or automatic rewriting of saved head/hair selections.

## Verification and limits

Build passes. Offline checks verify targeted Ratkin and Loong selection, exclusion of ordinary humans/other races, retention of dedicated FA heads, actual installed FA gate patch signatures and removal of old HairFit from the assembly. Existing lifecycle/draw-cache/skill edge harness also passes.

This restores the original rendering path rather than fabricating an animated compatibility face. It does not prove that every third-party hair asset fits every original head. Normal-game visual verification remains necessary, including both sides and portraits. No separate game launched.

Rollback DLL is in tmp/rimworld/native-head-repair-20260919/backup-*/. Restore while the game is closed. Current profile is synchronized separately with the installed DLL.
