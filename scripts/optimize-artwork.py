"""Create optimized runtime PNG copies for BayouFinds Windows Cleanup GUI."""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Pillow is required to optimize artwork. Install it with: python -m pip install Pillow")
    sys.exit(1)


ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT / "assets"
OPTIMIZED_DIR = ASSETS_DIR / "optimized"


@dataclass(frozen=True)
class ArtworkTarget:
    filename: str
    max_width: int | None = None
    max_height: int | None = None


TARGETS = (
    ArtworkTarget("header_banner.png", max_width=900),
    ArtworkTarget("cleanup_mascot.png", max_height=340),
    ArtworkTarget("splash.png", max_width=720),
)


def resize_preserving_aspect(image: Image.Image, target: ArtworkTarget) -> Image.Image:
    width, height = image.size
    scale = 1.0

    if target.max_width and width > target.max_width:
        scale = min(scale, target.max_width / width)

    if target.max_height and height > target.max_height:
        scale = min(scale, target.max_height / height)

    if scale >= 1.0:
        return image.copy()

    new_size = (max(1, round(width * scale)), max(1, round(height * scale)))
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    return image.resize(new_size, resample)


def optimize_png(target: ArtworkTarget) -> bool:
    source = ASSETS_DIR / target.filename
    destination = OPTIMIZED_DIR / target.filename

    if not source.exists():
        print(f"Skipping missing source: {source.relative_to(ROOT)}")
        return False

    with Image.open(source) as image:
        optimized = resize_preserving_aspect(image.convert("RGBA"), target)
        destination.parent.mkdir(parents=True, exist_ok=True)
        optimized.save(destination, format="PNG", optimize=True, compress_level=9)

    source_size = source.stat().st_size
    destination_size = destination.stat().st_size
    reduction = 0
    if source_size:
        reduction = round((1 - (destination_size / source_size)) * 100)

    print(
        f"Optimized {target.filename}: "
        f"{source_size:,} bytes -> {destination_size:,} bytes ({reduction}% reduction)"
    )
    return True


def main() -> int:
    optimized_count = 0

    for target in TARGETS:
        if optimize_png(target):
            optimized_count += 1

    if optimized_count == 0:
        print("No artwork files were optimized. Add PNG originals to assets/ and run again.")
    else:
        print(f"Optimized artwork written to: {OPTIMIZED_DIR.relative_to(ROOT)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
