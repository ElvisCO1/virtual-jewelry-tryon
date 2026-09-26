"""Lossless canvas alignment for the 36 approximate ring views.

This preprocessing step only translates the original RGBA pixels onto a common
transparent canvas. It does not resize, clean, rotate, or reconstruct the ring.
"""

import argparse
import hashlib
import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from .config import PROJECT_ROOT


EXPECTED_NAMES = {
    f"ring_az{azimuth:03d}_el_{elevation}.png"
    for azimuth in range(0, 360, 30)
    for elevation in ("m30", "000", "p30")
}


def estimate_anchor(image):
    """Approximate the ring center from the largest mostly opaque component.

    Ignore isolated alpha noise when estimating the anchor, but retain ALL source
    pixels in the output. Bounding-box center is only an initial alignment cue;
    it is not a calibrated finger axis or physical center of the ring.
    """
    alpha = np.asarray(image.getchannel("A"))
    count, _, stats, _ = cv2.connectedComponentsWithStats(
        (alpha >= 128).astype(np.uint8), connectivity=8
    )
    if count <= 1:
        raise ValueError("Image has no sufficiently opaque foreground.")
    x, y, width, height, _ = stats[1 + np.argmax(stats[1:, cv2.CC_STAT_AREA])]
    anchor = (round(float(x + (width - 1) / 2)), round(float(y + (height - 1) / 2)))
    return anchor, [int(x), int(y), int(width), int(height)]


def align_canvas(image, anchor, size):
    """Translate without resampling or alpha compositing, preserving RGBA bytes."""
    offset = (size // 2 - anchor[0], size // 2 - anchor[1])
    if min(offset) < 0 or offset[0] + image.width > size or offset[1] + image.height > size:
        raise ValueError("Canvas would clip source pixels.")
    canvas = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    # No mask: using the source alpha as a paste mask would apply transparency twice.
    canvas.paste(image, offset)
    return canvas, offset


def normalize_collection(source, destination):
    """Validate the complete collection before writing new, non-overwriting copies."""
    source, destination = Path(source).resolve(), Path(destination).resolve()
    if source == destination:
        raise ValueError("Source and destination must be different.")
    actual = {path.name for path in source.iterdir() if path.is_file()}
    missing, extra = EXPECTED_NAMES - actual, actual - EXPECTED_NAMES
    if missing or extra:
        raise ValueError(f"Unexpected collection: missing={sorted(missing)}, extra={sorted(extra)}")
    if destination.exists():
        raise FileExistsError(f"Destination already exists; choose a new directory: {destination}")

    prepared = []
    extent = 0
    for name in sorted(EXPECTED_NAMES):
        path = source / name
        with Image.open(path) as original:
            if original.mode != "RGBA":
                raise ValueError(f"Expected RGBA PNG: {name}")
            image = original.copy()
        anchor, bounds = estimate_anchor(image)
        extent = max(extent, *anchor, image.width - anchor[0], image.height - anchor[1])
        prepared.append((path, image, anchor, bounds))

    # One common square, with >=16 px padding and room for each FULL source canvas.
    size = ((2 * (extent + 16) + 31) // 32) * 32
    metadata = {
        "canvas_size": [size, size],
        "target_anchor": [size // 2, size // 2],
        "method": "integer translation; center of largest alpha>=128 component bounding box",
        "scale_factor": 1.0,
        "calibrated": False,
        "notes": [
            "Original RGBA pixels preserved, without resampling or cleanup.",
            "Shared pixel scale preserved; physical scale and perspective are not calibrated.",
            "Estimated anchors require manual visual validation.",
            "Existing clipped edges and halos are not repaired.",
        ],
        "images": [],
    }
    destination.mkdir(parents=True)
    for path, image, anchor, bounds in prepared:
        canvas, offset = align_canvas(image, anchor, size)
        target = destination / path.name
        canvas.save(target)
        alpha = np.asarray(image.getchannel("A"))
        metadata["images"].append({
            "filename": path.name,
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
            "source_size": list(image.size),
            "source_anchor": list(anchor),
            "foreground_bbox_xywh": bounds,
            "offset_xy": list(offset),
            "foreground_touches_source_edge": bool(any(
                np.any(edge >= 128) for edge in (alpha[0], alpha[-1], alpha[:, 0], alpha[:, -1])
            )),
        })
    (destination / "manifest.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=PROJECT_ROOT / "pack_image_36")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / "assets/rings/views_36_normalized")
    args = parser.parse_args()
    metadata = normalize_collection(args.source, args.output)
    print(f"Prepared {len(metadata['images'])} images on {metadata['canvas_size']} canvases.")
    print(f"Output: {args.output.resolve()}")


if __name__ == "__main__":
    main()
