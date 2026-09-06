# UEAgent backlog

Only unresolved work lives here. Completed decisions belong in `LOG.md`.

## P0 — finish the Abyss target

- [ ] Restore the exact VRM4U dependency for `E:/work/engine_work/ue/abyss/Abyss.uproject`,
      cold-start Abyss, then run Doctor and one task-relevant representative asset check.
      The engine installation and disposable UEAgentProbe passed; this does not prove Abyss.
- [ ] If the recorded complex-Blueprint parent/save or inherited-component dirty loop recurs,
      reproduce on an isolated copy of that exact asset. The plain Actor-to-Pawn/CDO probes
      passed and do not establish a fix for every Blueprint subclass.

## P1 — first installation on another machine

- [ ] Run the documented installer/bootstrap/Doctor flow on the next clean UE 5.8.1 workstation.
      Strict source replay and the installed local engine passed; a second machine was not tested.

External Niagara-script caches and additional client adapters require a real consumer task before
implementation. They are not prerequisites for the current stack.
