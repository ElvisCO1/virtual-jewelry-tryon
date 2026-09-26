"""Command-line parsing and process exit handling."""

import argparse
import math
import sys

from .config import AppConfig, DEFAULT_RING_FRONT, DEFAULT_RING_BACK


def parse_args(argv=None):
    """Validate options without opening a camera or loading a model."""
    parser = argparse.ArgumentParser(description="Virtual jewelry try-on: webcam, hand geometry and ring views.")
    parser.add_argument("--opencv-preview", action="store_true", help="Use the original OpenCV window instead of the interface")
    parser.add_argument("--ring", help="Use a single PNG instead of the bundled front/back pair")
    parser.add_argument("--geometry-only", action="store_true", help="Show measurements without ring images")
    parser.add_argument("--ring-front", help="Path to ring_front.png (decorative view)")
    parser.add_argument("--ring-back", help="Path to ring_back.png (band view)")
    parser.add_argument("--swap-ring-views", action="store_true", help="Reverse palm/back asset mapping")
    parser.add_argument("--input-mirrored", action="store_true",
                        help="Set only if the camera driver already mirrors captured frames")
    parser.add_argument("--width-ratio", type=float, default=0.8,
                        help="Ring image width / MCP-PIP distance (default: 0.8)")
    parser.add_argument("--asset-angle", type=float, default=-90,
                        help="Finger direction in the original PNG, in screen degrees")
    parser.add_argument("--smoothing", type=float, default=0.12,
                        help="Smoothing time constant in seconds; 0 disables smoothing")
    args = parser.parse_args(argv)
    if bool(args.ring_front) != bool(args.ring_back):
        parser.error("provide both --ring-front and --ring-back")
    if args.ring and args.ring_front:
        parser.error("use either --ring or the --ring-front/--ring-back pair")
    if args.geometry_only and (args.ring or args.ring_front):
        parser.error("--geometry-only cannot be combined with ring image paths")
    if not (args.ring or args.ring_front or args.geometry_only):
        args.ring_front = DEFAULT_RING_FRONT
        args.ring_back = DEFAULT_RING_BACK
    if not math.isfinite(args.width_ratio) or args.width_ratio <= 0:
        parser.error("--width-ratio must be finite and positive")
    if not math.isfinite(args.asset_angle):
        parser.error("--asset-angle must be finite")
    if not math.isfinite(args.smoothing) or args.smoothing < 0:
        parser.error("--smoothing must be finite and nonnegative")
    return AppConfig(**vars(args))


def main(argv=None):
    """Application entry point; argv can be supplied by tests or another caller."""
    config = parse_args(argv)
    # Defer native dependencies so --help works without camera/model initialization.
    from .app import run
    import cv2

    try:
        if config.opencv_preview:
            return run(config)
        from .gui import run_gui
        return run_gui(config)
    except KeyboardInterrupt:
        return 0
    except (OSError, ValueError, RuntimeError, cv2.error) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
