from __future__ import annotations

import argparse
import shutil
from datetime import datetime
from pathlib import Path


SKILL_NAME = "renderdoc-vfx-breakdown"
SOURCE = Path(__file__).resolve().parent / SKILL_NAME


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install the RenderDoc VFX Breakdown skill into an AI platform skills root."
    )
    parser.add_argument(
        "--target-root",
        required=True,
        type=Path,
        help="AI platform skills root; the skill folder is created beneath it.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Back up an existing installation before replacing it.",
    )
    return parser.parse_args()


def validate_source() -> None:
    required = [
        SOURCE / "SKILL.md",
        SOURCE / "agents" / "openai.yaml",
        SOURCE / "references" / "workflow.md",
        SOURCE / "references" / "evidence-standard.md",
        SOURCE / "references" / "quality-gates.md",
    ]
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise SystemExit("Skill source is incomplete:\n" + "\n".join(missing))


def main() -> None:
    args = parse_args()
    validate_source()

    target_root = args.target_root.expanduser().resolve()
    target_root.mkdir(parents=True, exist_ok=True)
    destination = (target_root / SKILL_NAME).resolve()

    if destination.parent != target_root:
        raise SystemExit("Resolved destination escaped the requested target root.")

    if destination.exists():
        if not args.replace:
            raise SystemExit(
                f"Destination already exists: {destination}\n"
                "Run again with --replace to create a backup and install the new version."
            )
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        backup = (target_root / f"{SKILL_NAME}.backup-{stamp}").resolve()
        if backup.parent != target_root:
            raise SystemExit("Resolved backup escaped the requested target root.")
        destination.rename(backup)
        print(f"Backed up existing skill to: {backup}")

    shutil.copytree(SOURCE, destination)
    print(f"Installed skill to: {destination}")


if __name__ == "__main__":
    main()
