# local-delta - provenance

These three bundles capture each project's VibeUE working tree against its own
HEAD, taken 2026-09-07.

Provenance, corrected after inspection: the content is **not hand edits**. It is
the pre-pull packaged state - `work/UEAgent/patches/vibeue-reliable-kernel.patch`
as of commit `45e55bb`, which carried the protocol 2.0.0 kernel (SHA-256 payload
identity via PlatformCrypto, journaling, richer receipt/snapshot/ack machinery).
Upstream commit `f5d2858` ("protocol 3.0 execution and engine fixes") replaced
that patch with a reduced 1253-line kernel at protocol 3.0.0 that contains none
of those features. The three live editors were built against the pre-pull
patches, so they still report 2.0.0.

Consequences:

- The state is fully reconstructible from Iris git history (`45e55bb` patch plus
  each project's VibeUE HEAD); these bundles are a convenience backup, not the
  only copy.
- The three bundles differ only because each project's VibeUE HEAD is a
  different merge commit; the working trees are byte-identical for the
  deviating files.
- They are absent from every apply list on purpose. They are input to the
  decision of whether the 2.0.0 reliability features get carried forward onto
  the 3.0 kernel, or accepted as removed by upstream.
