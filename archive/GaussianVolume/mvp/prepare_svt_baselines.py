"""Create density-only VDBs that UE imports as R8 and R16F SVTs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pyopenvdb as vdb


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    grids, metadata = vdb.readAll(str(args.source.resolve()))
    matches = [grid for grid in grids if grid.name == "density"]
    if len(matches) != 1:
        raise ValueError(f"expected one density grid, found {len(matches)}")
    source = matches[0]
    expected = {
        "active_voxels": source.activeVoxelCount(),
        "active_bbox": source.evalActiveVoxelBoundingBox(),
        "value_type": source.valueTypeName,
        "transform": source.transform.info(),
    }

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {}
    for suffix, grid_name in (("u8", "density"), ("f16", "density_f16")):
        output = args.output_dir / f"{args.source.stem}_density_{suffix}.vdb"
        grid = source.deepCopy()
        grid.name = grid_name
        vdb.write(str(output), [grid], metadata)

        written, _ = vdb.readAll(str(output))
        if len(written) != 1:
            raise RuntimeError(f"{output} contains {len(written)} grids")
        check = written[0]
        actual = {
            "active_voxels": check.activeVoxelCount(),
            "active_bbox": check.evalActiveVoxelBoundingBox(),
            "value_type": check.valueTypeName,
            "transform": check.transform.info(),
        }
        if check.name != grid_name or actual != expected:
            raise RuntimeError(f"verification failed for {output}")
        outputs[suffix] = {"path": str(output.resolve()), "grid": grid_name}

    print(json.dumps({"source": str(args.source.resolve()), "outputs": outputs}, indent=2))


if __name__ == "__main__":
    main()
