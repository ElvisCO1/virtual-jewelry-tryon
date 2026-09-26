"""Render ring-finger measurements without covering the camera image with text."""

import cv2

from .geometry import FINGER_INDICES


def draw_geometry(frame, geometries, labels, orientation_lines=None, show_references=True,
                  finger="ring", placement_centers=None, widths=None, manual_widths=None):
    """Return a video frame with highlights and a measurement panel on the right."""
    height, width = frame.shape[:2]
    indices = FINGER_INDICES[finger]
    segment = f"{indices[0]}->{indices[1]}"
    # Each detected hand gets its own panel block; the original image is unscaled.
    block_height = 310 if orientation_lines is not None else 240
    if manual_widths is not None:
        block_height += 21
    panel_height = max(height, 70 + block_height * len(geometries))
    output = cv2.copyMakeBorder(
        frame, 0, panel_height - height, 0, 390, cv2.BORDER_CONSTANT, value=(25, 25, 25)
    )

    def text(message, position, color=(240, 240, 240)):
        cv2.putText(output, message, position, cv2.FONT_HERSHEY_SIMPLEX,
                    0.48, color, 1, cv2.LINE_AA)

    text(f"Finger: {finger} | units: pixels", (width + 12, 24))
    text("q: quit | d: print landmarks", (width + 12, 46))
    if not geometries:
        text("No hands detected", (width + 12, 85))

    colors = ((0, 255, 255), (255, 180, 80))  # BGR: yellow, blue
    for hand_index, (geometry, label) in enumerate(zip(geometries, labels)):
        center = placement_centers[hand_index] if placement_centers is not None else geometry.midpoint
        color = colors[hand_index % len(colors)]
        if show_references:
            # Round only for drawing; calculations retain floating-point precision.
            points = [(round(x), round(y)) for x, y in geometry.points]
            for start, end in zip(points, points[1:]):
                cv2.line(output, start, end, color, 3, cv2.LINE_AA)
            for landmark_id, point in zip(indices, points):
                cv2.circle(output, point, 6, color, -1, cv2.LINE_AA)
                text(str(landmark_id), (point[0] + 8, point[1] - 8), color)

            if center is not None:
                marker = tuple(round(value) for value in center)
                cv2.drawMarker(output, marker, (255, 255, 255), cv2.MARKER_CROSS, 16, 2)
            text(f"H{hand_index}", (points[0][0] + 8, points[0][1] + 20), color)

        angle = "undefined" if geometry.angle_deg is None else f"{geometry.angle_deg:.1f} deg"
        lines = [f"H{hand_index} {label} | base segment {segment}"]
        for landmark_id, name, (x, y) in zip(
            indices, (("MCP", "IP", "TIP") if finger == "thumb" else ("MCP", "PIP", "DIP", "TIP")), geometry.points
        ):
            lines.append(f"{landmark_id} {name}: x={x:.1f}  y={y:.1f}")
        lines.extend([
            f"Placement: ({center[0]:.1f}, {center[1]:.1f})" if center is not None else "Placement: unavailable",
            f"Distance {segment}: {geometry.distance_px:.1f} px",
            f"Angle {segment}: {angle}",
            "0=right, +90=down, -90=up",
        ])
        if orientation_lines is not None:
            lines.extend(orientation_lines[hand_index])
        if manual_widths is not None:
            reference = manual_widths[hand_index]
            lines.append(f"Ancho manual: {reference['width_px']:.1f} px" if reference else "Ancho manual: sin referencia")
        if widths is not None:
            measurement = widths[hand_index]
            if measurement is None:
                lines.append("Ancho: no fiable | mm: sin calibrar")
            else:
                mm = measurement['width_mm']
                units = f"{mm:.1f} mm (aprox.)" if mm is not None else "mm: sin calibrar"
                lines.append(f"Ancho: {measurement['width_px']:.1f} px | {units}")
                if show_references:
                    a, b = [tuple(round(v) for v in p) for p in measurement['endpoints']]
                    cv2.line(output, a, b, (255, 255, 0), 2, cv2.LINE_AA)
                    for endpoint in (a, b):
                        cv2.circle(output, endpoint, 4, (255, 255, 0), -1)
        for line_index, line in enumerate(lines):
            text(line, (width + 12, 76 + hand_index * block_height + line_index * 21), color)

    return output
