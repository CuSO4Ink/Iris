# Cross-race head / hair inspection

Read-only follow-up to the user's report that misalignment affects more than Ratkin. No game process present during inspection; no additional runtime changes or broad scaling applied.

## What is established

- FA CreateSlaveNode gives its face nodes parentTagDef Head and overrideMeshSize from GraphicHelper.GetHeadMeshSet(pawn).
- With IgnoreHairMeshParams enabled (the inspected setting's default, not overridden in the local FA settings), FA also replaces the humanlike hair mesh result with the same GetHeadMeshSet size for pawns it draws. This deliberately overrides the original headType.hairMeshSize and HAR scale factors at this entry point.
- HAR supplies separate map/portrait size factors. Pawn Texture Offset Adjuster changes the shared Head parent, so its head scale alone is not evidence of a relative head/hair mismatch. FA and hair normally inherit that parent transform.
- Matching mesh dimensions do not imply matching artwork contours. A generic FA scalp and a race-native hairstyle can expose scalp even when both use the same mesh size.
- Local texture-budget source resamples the whole image canvas. This inspection found no crop/anchor adjustment that by itself explains a consistent geometrical head offset. This is not a full cache/asset integrity audit.

## Current-save combinations

| Race / group | Saved head / hair | Interpretation |
|---|---|---|
| Ratkin | HeadNormal + RK_Middle2; HeadPointy + RK_Mai | Generic FA heads paired with Ratkin hair. No dedicated Ratkin FaceAdjustmentDef found in the inspected loaded-definition roots. Priority for contour and native-hair convention checks. |
| Smelted Loong characters represented as Human | HeadPointy + NY_SmeltedLoongHair01 / 05 | Another generic FA head / specialized hair combination. Race-only filters would incorrectly lump these in with all Human pawns; use actual head/hair/genes as needed. |
| Kiiro | Kiiro_Head + Kiiro_Null | Dedicated age-based FA sizing (adult 1.5) and specialized head content; not equivalent to generic hair-on-head composition. |
| Milira | Milira_Head + Milira_Null | Dedicated FA size 1.5. Separate hairstyle replacement packages still need per-character inspection if reported. |
| Wolfein | Wolfein_Head + Wolfein_HairNull | Dedicated age-based sizing, adult 1.125, corresponding to native adult head factor .75 × 1.5. Do not globally multiply it by generic race factors again. |
| Mugirl | Mugirl_HeadNormal5 + Mugirl_GloomHair6 | Dedicated head artwork exists even without a separate FaceAdjustmentDef. Absence of that def does not prove missing support. Native declared head factor 1.09 alone is insufficient to choose a correction. |
| Mincho | No saved HeadControllerComp face type; native Mincho_Hair_Large styles | No evidence this character follows the same FA head-replacement route. Native declared body 1.2 / head .9; requires native rendering path inspection if affected. |
| Miho | No saved FA head; Bald | Not evidence of the reported hair mismatch. Native head factor .75 is not a diagnosis. |

Axolotl's inspected dedicated adjustment specifies 1.38. Its settings do not justify applying Ratkin's empirical 8% correction elsewhere.

## Limits and next action

The XML inventory approximates active load folders/conditions; it does not materialize the fully patched runtime DefDatabase. An additional broad assembly scan was incomplete as a complete patch inventory and is not used to claim that no other renderer hooks exist.

The earlier RK_Mai +8% / +.015 side-view fit remains a provisional single-combination correction, not a general repair. The user's report broadens the diagnosis; do not propagate that constant to all races. Requested names of other affected races/characters to route the next check. Confirm actual actor, head/hair source, effective mesh/node transforms, portrait versus map and facing before choosing a common compatibility patch versus an asset-specific adjustment.
