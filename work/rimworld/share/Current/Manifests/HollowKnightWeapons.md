# Hollow Knight weapon balance revision

Targeted follow-up to passive-effect rebalance. 13 existing fields and one new projectile Def; no DLL changes.

- Player-craftable Grimm staff: burst9->6, range48->36,warmup1->1.2s,cooldown1.2->1.8s,burst interval3->5ticks. Uses new Iris_HK_PlayerGrimmFire projectile (18damage,0.9AP), copied from original bullet definition. Original shared bullet30damage/6AP is untouched, preserving other weapons/summons using it. Nominal direct-damage cycle rate103.85->31.61 per second before accuracy, armor, quality, pawn modifiers and fire effects; not measured effective DPS.
- Pure Nail: first attack cooldown0.8->1.1s;second36damage/1.2s->32damage/1.4s;additional Stun amount12->4. Retains sharpness,60%explicit first-tool AP and link identity. Tool damage/cooldown ratios27.27 and22.86 are NOT complete DPS; custom melee verb also spawns additional projectiles.
- Giant Nail:64damage/4s->45damage/3.2s. Retains heavy-hit identity with less single-hit destruction.
- Champion hammer:48damage->36,2s cooldown retained.
- Early nail tiers, existing Aspid/armor adjustments, spells and Boss stage mechanics not changed. Changes apply to any wielder of these particular weapon definitions, not just colonists.

Validation: all13 replacement paths unique in installed XML; no overlap with existing IrisBalance patch paths; cloned projectile does not modify shared bullet. No game launch, actual combat tuning pending. Installed/export bytes checked;272active list unchanged. Roll back while closed by removing HollowKnightWeapons.xml, preferably before saving in-flight projectiles from the new definition. Previous saves are not edited.
