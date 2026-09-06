# Core reference

The current execution path and request fields are in [HOTPATH](../HOTPATH.md).

Use returned full object refPaths. Read unfamiliar arrays/structs before read-modify-write and
preserve nested fields. Stage array resizing separately where the native diff API requires it.
Declare exact save packages, including World Partition external Actor packages when relevant.
Before deletion/reparenting, inspect actual dependents; do not treat zero registry references as
complete proof. Asset save does not authorize level save. Do not manufacture a meaningless
mutation to obtain save permission. An uncertain task may have partial effects; inspect the
affected state before a new operation. Do not automatically save or revert unrelated work.

Targeted readback verifies the requested result, not every field of an asset. Shader/Blueprint/
Niagara changes require the corresponding compile result when relevant. Runtime/DI readback
must run after real frames and use current object identities. Structural evidence belongs to
the agent; visual/aesthetic decisions belong to the user.
