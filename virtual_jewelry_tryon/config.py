"""Central project paths and immutable runtime options."""

from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = PROJECT_ROOT / "models" / "hand_landmarker.task"
DEMO_ASSETS = PROJECT_ROOT / "assets" / "rings" / "demo"
DEFAULT_RING_FRONT = DEMO_ASSETS / "ring_front.png"
DEFAULT_RING_BACK = DEMO_ASSETS / "ring_back.png"


@dataclass(frozen=True)
class AppConfig:
    ring: str | Path | None = None
    ring_front: str | Path | None = None
    ring_back: str | Path | None = None
    geometry_only: bool = False
    swap_ring_views: bool = False
    input_mirrored: bool = False
    width_ratio: float = 0.8
    asset_angle: float = -90.0
    smoothing: float = 0.12
    opencv_preview: bool = False
