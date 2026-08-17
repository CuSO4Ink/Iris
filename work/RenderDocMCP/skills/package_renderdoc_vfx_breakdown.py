from __future__ import annotations

import zipfile
from pathlib import Path


SKILLS_ROOT = Path(__file__).resolve().parent
SKILL_NAME = "renderdoc-vfx-breakdown"
SOURCE = SKILLS_ROOT / SKILL_NAME
OUTPUT = SKILLS_ROOT / "dist" / f"{SKILL_NAME}.zip"

FORBIDDEN_SUFFIXES = {".rdc", ".pptx", ".pdf", ".fbx", ".obj"}
FORBIDDEN_PARTS = {"reference-delivery", "__pycache__"}


def collect_files() -> list[Path]:
    files = []
    for path in sorted(SOURCE.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(SOURCE)
        if any(part in FORBIDDEN_PARTS for part in relative.parts):
            raise SystemExit(f"Forbidden directory in skill: {relative}")
        if path.suffix.lower() in FORBIDDEN_SUFFIXES:
            raise SystemExit(f"Project artifact must not be bundled: {relative}")
        files.append(path)
    return files


def main() -> None:
    if not (SOURCE / "SKILL.md").is_file():
        raise SystemExit(f"Missing skill source: {SOURCE / 'SKILL.md'}")

    files = collect_files()
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(OUTPUT, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(SOURCE).as_posix()
            archive.write(path, f"{SKILL_NAME}/{relative}")

    with zipfile.ZipFile(OUTPUT) as archive:
        names = archive.namelist()
        required = f"{SKILL_NAME}/SKILL.md"
        if required not in names:
            raise SystemExit(f"Package verification failed: {required} is missing")
        if any("\\" in name for name in names):
            raise SystemExit("Package verification failed: non-portable path separator")

    print(f"Packaged {len(files)} files: {OUTPUT}")


if __name__ == "__main__":
    main()
