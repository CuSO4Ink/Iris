# Reflect Cache read model

Sidecars describe saved assets, never dirty Editor state. Supported formats cover Material,
Material Function, Material Instance, Blueprint and Niagara System. Normal save-hook generation
uses a temporary file and replacement, skips autosave/cook/procedural saves and checks writes.

Source path, format, mtime and size determine applicability. Use summary/refs/detail/full views
according to the question; content generation omits graph/HLSL/file hashes. Historic sidecars may
still contain old summary keys until regenerated. No hash is an execution or save authorization.

The offline reconciler reports stale/missing/orphan metadata without checksum scanning, automatic
rename inference, manifest generation or file migration. Rebuild missing caches on demand. Keep
unresolved user-owned files; cache maintenance is not authorization to change UE assets.
