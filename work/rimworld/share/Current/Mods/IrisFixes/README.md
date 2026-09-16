# IrisFixes

Local XML and runtime compatibility repairs for the current RimWorld 1.6 mod set.

## Runtime repairs

- HAR thought registration: repeated identical mappings are idempotent. Conflicting mappings keep the first existing mapping and report race/thought names, rather than throwing and abandoning remaining registrations.
- ZombieGirl: bypass the obsolete child-reset transpiler only when its incoming instructions contain no Child body-type field reference, indicating that branch is already absent. If the reference remains, the upstream transpiler still runs and can report a genuine mismatch.
- LegacySounds.xml substitutes existing vanilla sounds for five missing sound names (generic building punch, and MythSword pickup/hit/miss sounds). No damage values change; sound character can differ from the unavailable original.
- Optional tech implants: exclude nonpositive or nonfinite market-value candidates before vanilla's weighted draw. An all-zero candidate set previously returned null and aborted faction-leader generation. Positive candidates keep their weights; required implants are unchanged. Each rejected definition is logged once for diagnosis.
- Static texture atlases: cap each atlas dimension at 4096; the game's existing pixel-budget batching creates more, smaller atlases. This reduces temporary allocation peaks without resampling source files. More atlas switches may increase rendering overhead. The full-resolution atlas path exhausted memory during isolated verification.
- Show Me Your Hands: measure unconfigured weapon silhouettes at at most 512 pixels per dimension. The original artwork remains unchanged. Read raw RGBA bytes to avoid Image Opt's additional full-resolution readback, and release the temporary texture immediately. Hand placement can differ slightly for very large source textures.
- Eoral Ratkin Gene Expanded: skip only `SYSPatch_ReplaceSYSDrawPrefix` when its old SYS drawing target is absent. Other patches and gene definitions remain enabled. This cannot restore that obsolete integration's visual behavior.

Requires Harmony. Source is in `Source/`; build with `dotnet build Source/IrisFixes.csproj -c Release`. Reference paths currently point to this machine's game and Workshop directories. Intermediate build output belongs under the repository's `tmp/rimworld/irisfixes-build/`.

## Simplified Chinese world-generation naming

`Languages/ChineseSimplified/DefInjected/RulePackDef/IrisWorldgenNaming.xml` retains the game's translated deity and generic leader rule lists and appends the fallback branches already present in the XML patches. Translation replaces these entire lists after patching, so the XML-only fallbacks were lost. Observed failure: unresolved `memeConcept`/`memeGod`, then an untranslated RulePack null reference aborting `WorldGenStep_Factions`. The translated fix requires restarting and generating a new world; it does not populate an already partially generated world. Original translated entries and deployment equality were checked; full world generation with this addition remains unverified.

The runtime DLL does not modify saves, raid difficulty, or texture files. See the project's crash repair report for separate settings and Workshop XML repairs.

## Latest maintenance

- QuestCompatibility safely compares BPC assignment links, avoiding null Pawn/def dereferences during guest-status changes. It does not change valid assignment policies or replay old quests. Kiiro's legacy-only wanderer generator is bridged into the new map-aware base entry point for that exact task type.
- ZombieGirl's old child-body IL rewrite is superseded by scoped load-state preservation for valid active ZombieGeneDef child body types. No global child-stage rules are removed.
- SmallTextureBypass.txt lists 28 observed failing PNGs. Headers are checked again; only shortest-edge-below-4 files bypass ImageOpt compression via its original-image loader. The source files are untouched.
- OptionalWorkshopTargets handles four exact missing XPath targets before the original operation errors. The two previously edited Workshop files were restored. Do not install archived WorkshopRepairs copies.
- LogWindowCompatibility snapshots messages under the original logger lock, removes only the exact repetitive harvest trace, and resets grammar tracing on startup. Errors remain visible. Prefs verbose logging was separately turned off on this machine.
- GenerationDiagnostics records the first rejected required-work combination per PawnKind. The Tribal_ChiefMelee disabled-work generation issue is not yet fixed; instrumentation is not claimed as a fix.

Runtime verification remains pending user play; no independent game session was launched.

Follow-up: required combat work is propagated to generation requests; incompatible random backgrounds are reselected within their original categories without weakening required work. The log viewer now renders only visible fixed-height rows, with bounded plain previews; full message details and file logs remain available. These changes are compiled and installed but not live-tested in an independent game.
