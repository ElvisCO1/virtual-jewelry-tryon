"""Load the normalized ring views once, in a predictable browsing order."""

from dataclasses import dataclass
import json
from pathlib import Path

import numpy as np

from .config import PROJECT_ROOT
from .ring_overlay import load_ring


CATALOG_PATH = PROJECT_ROOT / "assets/rings/views_36_normalized"


@dataclass(frozen=True)
class RingView:
    filename: str
    azimuth: int
    elevation: int
    image: np.ndarray
    width_scale: float


def load_catalog(folder=CATALOG_PATH):
    """Return 36 cached PNGs: level, away, toward; each with increasing azimuth.

    Padding compensation preserves source pixel scale, not calibrated ring size.
    No angle estimation or sample recording is performed here.
    """
    folder = Path(folder)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    records = {item["filename"]: item for item in manifest["images"]}
    views = []
    for tag, elevation in (("000", 0), ("m30", -30), ("p30", 30)):
        for azimuth in range(0, 360, 30):
            name = f"ring_az{azimuth:03d}_el_{tag}.png"
            if name not in records:
                raise ValueError(f"Missing catalog metadata: {name}")
            image = load_ring(folder / name)
            source_width = records[name]["source_size"][0]
            if not isinstance(source_width, (int, float)) or source_width <= 0:
                raise ValueError(f"Invalid original width: {name}")
            if list(image.shape[1::-1]) != manifest["canvas_size"]:
                raise ValueError(f"Unexpected canvas size: {name}")
            image.setflags(write=False)
            views.append(RingView(name, azimuth, elevation, image, image.shape[1] / source_width))
    return tuple(views)
