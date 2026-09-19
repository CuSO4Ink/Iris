# Follow-up repairs installed — 2026-09-19

Supersedes the three open correctness findings in LOGIC-AUDIT-20260919.md. User authorized aggressive follow-up. Game closed throughout deployment; no Workshop edits, saved-pawn rewrites, active-list changes or independent game launch.

## Changes

- **Food filters:** both special filters now attach to Root, not Foods. Existing workers still determine food/ingredient eligibility. Normal drinks/drugs outside Foods are rejected by the disposal filter, and forbidden ingredient checks can cover custom categories. This does not discover ingredients a mod never records.
- **Talent:** explicit PawnKind per-skill ranges are excluded from shaping. Kinds with an explicit extraSkillLevels bonus are left unchanged. Unconstrained skills retain the progression distribution. Only future generated pawns change; old lost skill levels cannot be reconstructed from absent original data.
- **Insect spawners:** replaced the previous skip-only repair. A thread-local, nested damage context records the relevant building's map before damage and releases it in a finalizer. The original damage callback reads this map after destruction, retaining its own activation conditions and map-wide effects. No duplicate independent spawning implementation.
- **Drawing:** patch the installed repair helpers, preserving their existing prefix/finalizer state pairing and native-array cleanup. Full cleanup runs on list-version changes, registration/despawn dirtiness, and every 120 frames as a safety sweep. It uses linear RemoveAll compaction. Reference-identity membership caching avoids linear duplicate checks across normal bulk registration; caches are weak-keyed to the existing draw lists, not global retained maps. Installed Unity Mono mscorlib List._version field was verified.
- **RI wanderer:** the installed WhoXiuXian quest still overrides legacy GeneratePawn only. A narrowly scoped bridge from GeneratePawn_NewTemp invokes that existing override, preventing new null-pawn quest generation through this path.
- **Old quest references:** population/look-target helpers ignore absent pawn references without deleting survivors or rewriting quests. Already missing characters are not recreated and malformed old quests are not declared restored.
- **Invalid construction blueprints:** exact Blueprint_Build instances lacking a target frame cannot repeatedly acquire construction work; a retained in-flight job ends incompletable. Blueprints/materials are not deleted. The player can cancel a retained malformed blueprint. Valid frames and specialized blueprint classes keep existing behavior.
- **Hair:** retained the narrowly scoped RK_Mai side-view calibration. Added one-time per-pawn/direction/portrait managed-property diagnostics, using weak lifetime tracking and no Unity Mesh/Texture calls from parallel render workers. Both-side/head-turn/portrait visual acceptance remains outstanding; no additional blind enlargement applied.

## Verification

Both DLL builds: zero warnings/errors. Offline harness covered actual installed Harmony targets, nested damage map lifetimes, null-map paths, nested draw finalizer state, reference-identity duplicate checks, same-count list mutation invalidation, periodic sweep boundaries, valid versus invalid blueprint handling, quest list filtering and explicit skill constraints.

Stable-list scheduling model: 5 full sweeps per 600 frames instead of 600. Synthetic 30,000-item / 50%-null list compaction measured approximately 19 ms for backwards RemoveAt versus 0.2 ms for linear compaction in one harness run. These are bounded algorithm checks, not actual game FPS/TPS measurements. High-churn maps still trigger immediate sweeps; periodic fallback may discover unsupported lifecycle mutations later than the former per-frame scan.

The category-filter reproduction changed from failed rejection under Foods to successful rejection under Root, using actual classifier, worker and category predicate. Full ThingFilter integration and visual output still require normal gameplay.

## Deployment

Updated only IrisSessionRepairs.dll, IrisTalentProgression.dll and IrisStorageDefaults/Defs/Filters.xml. Original main IrisFixes.dll and the undeployed profiler remain untouched. Backups are under tmp/rimworld/followup-repair-20260919/backup-*/. ModsConfig byte comparison confirmed unchanged.

Next normal-session checks: absence of installation errors, recurrence of Titan/wander/spawner errors, placement/hauling classification, blue-haired Ratkin both side views and actual FPS/TPS under comparable load. These pending observations prevent a claim of universal correctness or measured whole-game speedup.
