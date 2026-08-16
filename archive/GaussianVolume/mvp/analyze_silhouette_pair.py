from __future__ import annotations

import argparse
from collections import deque

import numpy as np
from PIL import Image, ImageDraw, ImageFilter


def parse_crop(text: str) -> tuple[int, int, int, int]:
    values = tuple(map(int, text.split(",")))
    if len(values) != 4:
        raise argparse.ArgumentTypeError("crop must be x0,y0,x1,y1")
    return values


def center_component(score: np.ndarray, threshold: float) -> np.ndarray:
    mask = score > threshold
    h, w = mask.shape
    seeds = np.argwhere(mask[h // 3 : 2 * h // 3, w // 3 : 2 * w // 3])
    if not len(seeds):
        raise ValueError(f"no center component at threshold {threshold}")
    sy, sx = seeds[len(seeds) // 2] + (h // 3, w // 3)
    out = np.zeros_like(mask)
    out[sy, sx] = True
    queue = deque([(int(sy), int(sx))])
    while queue:
        y, x = queue.popleft()
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                ny, nx = y + dy, x + dx
                if (
                    0 <= ny < h
                    and 0 <= nx < w
                    and mask[ny, nx]
                    and not out[ny, nx]
                ):
                    out[ny, nx] = True
                    queue.append((ny, nx))
    return out


def perimeter(mask: np.ndarray) -> int:
    interior = mask.copy()
    interior[1:, :] &= mask[:-1, :]
    interior[:-1, :] &= mask[1:, :]
    interior[:, 1:] &= mask[:, :-1]
    interior[:, :-1] &= mask[:, 1:]
    return int(np.count_nonzero(mask & ~interior))


def fill_holes(mask: np.ndarray) -> np.ndarray:
    h, w = mask.shape
    image = Image.fromarray(mask.astype(np.uint8) * 255).copy()
    for y, x in (
        *((0, x) for x in range(w)),
        *((h - 1, x) for x in range(w)),
        *((y, 0) for y in range(1, h - 1)),
        *((y, w - 1) for y in range(1, h - 1)),
    ):
        if image.getpixel((x, y)) == 0:
            ImageDraw.floodfill(image, (x, y), 128)
    return np.asarray(image) != 128


def metrics(score: np.ndarray) -> dict[str, float]:
    masks = {t: fill_holes(center_component(score, t)) for t in (5.0, 15.0, 25.0)}
    base = masks[15.0]
    area = int(np.count_nonzero(base))
    edge = perimeter(base)
    blurred = np.asarray(
        Image.fromarray(base.astype(np.uint8) * 255)
        .filter(ImageFilter.GaussianBlur(6.0))
    ) > 127
    smooth_edge = perimeter(blurred)
    return {
        "area_px": float(area),
        "perimeter_px": float(edge),
        "roughness": edge / np.sqrt(max(area, 1)),
        "small_scale_excess": (edge - smooth_edge) / max(smooth_edge, 1),
        "soft_tail_px": (
            np.count_nonzero(masks[5.0]) - np.count_nonzero(masks[25.0])
        )
        / max(edge, 1),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--left", type=parse_crop, required=True)
    parser.add_argument("--right", type=parse_crop, required=True)
    args = parser.parse_args()
    image = np.asarray(Image.open(args.image).convert("RGB"), dtype=np.float32)
    for name, (x0, y0, x1, y1) in (("SVT", args.left), ("GS", args.right)):
        crop = image[y0:y1, x0:x1]
        result = metrics(crop[..., 0] - crop[..., 2])
        print(name, " ".join(f"{key}={value:.6f}" for key, value in result.items()))


if __name__ == "__main__":
    check = np.ones((3, 3), dtype=bool)
    check[1, 1] = False
    assert fill_holes(check).all()
    main()
