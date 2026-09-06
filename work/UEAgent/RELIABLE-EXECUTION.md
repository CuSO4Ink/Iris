# UEAgent execution protocol 3.0

The user approved the five-boundary simplification on 2026-09-06. The execution card is
[HOTPATH](skills/ue-mcp-workflows/HOTPATH.md). Version 2 snapshot/OCC/token request fields are
retired; do not silently send them to version 3. Schema discovery supplies current fields.

K1 binds expected_project and editor_epoch at dispatch. K2 keeps one active mutation until its
underlying callback finishes; caller-declared reads can overlap. K3 stores the canonical actual
request once before execution and one terminal result; write failure prevents acceptance or
reports uncertainty. Same ID/different request is rejected by direct string comparison.
K4 dispatches one caller-specified typed readback and matches its expected result. K5 saves only
the dirty declared packages of a verified task, with explicit handling of pre-existing dirty
state. Save uses command_id, a checked started record and terminal save receipt; previous-epoch
tasks cannot authorize saving. Native save completion and clean packages are verified.

No general-purpose snapshot diff, HMAC capability, payload/file checksum, automatic rollback or
out-of-scope event monitoring remains. Package save generations catch intervening saves but
cannot detect all manual unsaved edits. Public snapshots are explicit diagnostics only. The
normal path is one Gateway request, local queue/poll/readback/save, one compact terminal result.
Direct native tools remain trusted local capabilities; this is not a hostile-client sandbox.

Historic v2 journals and receipts remain on disk as evidence; they are not new save authority.
Performance monitoring uses the normal StartMonitor/ReadMonitor/StopMonitor tools; it does not
freeze unrelated reads. Warmup/sample sizes are measurement parameters.
