# Iris Storage Defaults

Maintains the user's approved Defaults templates. Requires 1trickPwnyta's Defaults, RimWorld 1.6.

- Runs once during startup after explicitly completing DefaultsModInitializer. No game-tick hooks, no pawn scanning, no workshop modifications.
- StorageRules.xml names the managed building/zone roles. These managed template filters are regenerated at each startup using resolved definitions and building fixed storage restrictions. Manual edits to managed template filters are overwritten next startup; edit/remove a role in the manifest to stop managing it.
- Ordinary new meal definitions enter the default policy named 正食配置; other policies retain their food selection apart from forbidden-source exclusions. Ordinary new raw ingredients enter existing culinary templates only where the recipe allows them. No production bills are created automatically.
- Humanlike, insect and Anomaly flesh sources, specified abnormal meat families, Necro_Meat, and race butcher-products which are meat are excluded. This also covers Insect Girls sharing Human meat.
- Iris_ForbiddenFoodSources filters completed items by recorded CompIngredients. It does not infer concealed ingredients from mod code. Unmarked/custom definitions can require additional rules.
- Fertile eggs, drugs and named special materials (healing, resurrection, soul/blood resources etc.) are excluded from automatic ordinary food additions. The classifier is not a universal guarantee against every custom food effect.
- Existing map storage, saved pawn food policies and existing workbench bills are NOT rewritten. Apply the updated defaults to existing objects through Defaults when desired. Global ingredient radius, product destination and production counts are preserved.
- Local settings were edited offline before activation; startup classification uses the fully resolved runtime defs (including patches) to refine those templates. No independent game launch was performed.

Verification: build succeeds; actual classification helpers tested for human/new humanlike/Necro meat, ordinary meat/new vegetables/meals, raw-versus-meal separation, fertile eggs, resurrection material exclusion and mixed-meal ingredients. Full DefDatabase/startup integration requires normal game play; offline Unity DefOf initialization is unavailable.

2026-09-19: mechanical race meatDef fields are accepted into the blacklist only when they actually identify meat, preserving Steel storage. Added baby food, fertile egg, reserved consumable, biocoded equipment and tainted apparel zone templates. Bio disposal also accepts meals with recorded forbidden ingredients; valuables and mortar shells no longer compete with bulk/precision storage. 18 focused classification checks passed; DLL, rules and filter defs deployed together.
