# virtual-jewelry-tryon

An incremental Python replication of the core functionality described in
"Enhancing the Virtual Jewelry Try-On Experience with Computer Vision".

## Try the included ring images

Two transparent test assets are included: `assets/rings/demo/ring_front.png` (diamond/decorative
face) and `assets/rings/demo/ring_back.png` (plain gold band). Run the following, or use the existing
VS Code **Webcam - entorno .venv** launch configuration with F5:

```powershell
.\.venv\Scripts\python.exe main.py
```

The default run loads both images automatically. Show the back of your hand to
see the decorative face; turn your palm toward the camera to see the plain band.
Uncertain/edge-on views hide the ring. Use `--geometry-only` for measurements
without images. Press **q** to quit.

These are generated demonstration assets based on the original ring sheet.
Generation method and exact prompts: [ring asset notes](ring_assets.md).

## Phase 1 - Baseline Replication

Completed: the webcam baseline works, as confirmed by the user. It opens the
default camera, displays live video, exits on **q**, and handles camera failures.

## Phase 2 - Hand Landmark Detection

Completed: hand landmark detection works, as confirmed by the user.

The existing camera loop now detects up to two hands and draws their 21 landmarks
and connections in real time. Focus the video window and press **d** to print a
coordinate snapshot to the terminal, or **q** to quit. No jewelry images, ring
placement, or ring overlays are implemented.

Detection uses the MediaPipe Tasks Hand Landmarker API in synchronous VIDEO mode,
with increasing timestamps, so results match the displayed frame. Performance
depends on the computer and camera. The detector converts OpenCV's BGR frames to
RGB internally and owns no camera or display window.

### Project structure

The current layout and entry point are documented in the [project README](../README.md).
The following sections preserve the phase-by-phase implementation notes.

### Setup and run (Windows PowerShell)

Use your working desktop Python environment. Run these commands from the
repository root. If `.venv` already exists, skip its creation:

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip uninstall -y opencv-python opencv-python-headless opencv-contrib-python-headless
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

The commands use the virtual environment directly, so activation is unnecessary.
If `py` cannot find Python, create the environment using the full path to your
installed interpreter, for example:

```powershell
& "$env:LOCALAPPDATA\Programs\Python\Python312\python.exe" -m venv .venv
```

In VS Code, open this repository folder and choose **Python: Select Interpreter**
from the command palette, then select `.venv\Scripts\python.exe`. If a different
interpreter was previously selected, change it explicitly. For debugging, select
**Webcam - entorno .venv** in Run and Debug and press **F5**; this configuration
explicitly uses the project's isolated environment. `.venv` is excluded from Git.

`opencv-contrib-python` provides the same `cv2` camera and drawing functions and
is also required by MediaPipe. Remove the previous OpenCV package before installing
to avoid overlapping `cv2` installations. Pip installs transitive dependencies.

Download the official model once (skip if `models/hand_landmarker.task` exists):

```powershell
New-Item -ItemType Directory -Force models | Out-Null
Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task" -OutFile "models/hand_landmarker.task"
```

The model is stored locally and excluded from Git, so fresh clones need this step.
The application resolves its model path relative to the source file and reports
a helpful error if it is missing. After setup, run:

```powershell
.\.venv\Scripts\python.exe main.py
```

### Landmark coordinates

`HandDetector.detect(frame)` returns a MediaPipe result. Access an individual
point with `result.hand_landmarks[hand_index][landmark_index]`, then read its
`.x`, `.y`, and `.z` attributes. No hands produces an empty `hand_landmarks` list.

- `x` and `y` are normalized image coordinates, normally from 0 to 1. The origin
  is the top-left; x increases rightward and y increases downward.
- Pixel positions are `int(x * frame_width)` and `int(y * frame_height)`.
- `z` is relative depth with the wrist as zero. Smaller values are closer to
  the camera; its scale is roughly that of x. It is not a distance in meters.
- `result.hand_world_landmarks` separately exposes estimated 3D coordinates in
  meters, centered on the hand. These are not used for drawing.
- `result.handedness` contains the predicted left/right label and confidence.
  Hand list indices are per-frame positions, not persistent tracking IDs.

The video is displayed without mirroring. Debug output includes every point's
index and name, normalized x/y/z, and pixel x/y. Landmark indices are:

| Indices | Points (in order) |
| --- | --- |
| 0 | Wrist |
| 1-4 | Thumb CMC, MCP, IP, tip |
| 5-8 | Index MCP, PIP, DIP, tip |
| 9-12 | Middle MCP, PIP, DIP, tip |
| 13-16 | Ring MCP, PIP, DIP, tip |
| 17-20 | Pinky MCP, PIP, DIP, tip |

MCP is the knuckle at the finger base; PIP and DIP are the middle and outer finger
joints. The thumb has CMC (base), MCP, and IP joints.

See the official [MediaPipe Python guide](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker/python)
for API and coordinate definitions, and the [model overview](https://ai.google.dev/edge/mediapipe/solutions/vision/hand_landmarker)
for the model source.

### Manual verification

1. Run the script. With no hands visible, confirm that live video continues;
   press **d** and check for "No hands detected in this frame."
2. Show one hand, then two, in good light. Confirm joints and connections follow
   each hand. Remove your hands and confirm the markings disappear.
3. Focus the video window and press **d**. Check that the terminal prints 21
   labeled coordinate rows for each detected hand.
4. Press lowercase **q**. Confirm the window closes, then rerun to verify that
   the camera was released.
5. If practical, disconnect the webcam (with no other camera available) and run
   again. Confirm an explanatory error appears and the script exits.

If the camera cannot open, check its connection, Windows camera permissions for
desktop apps, and whether another application is using it.

The isolated `.venv` was created with Python 3.12.10. Dependency checks, imports,
and model inference on a blank frame passed with MediaPipe 1.0.1 and OpenCV 5.0.0.

## Phase 3 - Ring Finger Geometry

Run the same `main.py` command. Each hand's ring finger is highlighted in a
distinct color, with indices **13 (MCP), 14 (PIP), 15 (DIP), 16 (tip)** beside the
points. A white cross marks the midpoint of the base segment, **13 -> 14**.
The panel beside the video displays all four x/y pixel coordinates, the midpoint,
the base segment length in pixels, and its angle in degrees. H0/H1 link each hand
to its panel; these labels are per-frame indices and can switch between hands.

### Mathematics and reusable output

`geometry.ring_finger_geometry(landmarks, width, height)` accepts a hand's
normalized landmarks and returns a `RingFingerGeometry` with `points` (13-16),
`midpoint`, `distance_px`, and `angle_deg`. It has no camera or rendering dependency.
For pixel endpoints A=(x1,y1) at MCP and B=(x2,y2) at PIP:

```text
x = normalized_x * original_frame_width
y = normalized_y * original_frame_height
midpoint = ((x1+x2)/2, (y1+y2)/2)
dx = x2-x1, dy = y2-y1
distance = sqrt(dx*dx + dy*dy)
angle = degrees(atan2(dy, dx))
```

Calculations retain floating-point precision and use the original camera frame's
dimensions, excluding the added panel. The origin is top-left, so the directed
MCP-to-PIP angle is **0 degrees right, +90 down, -90 up**, and +/-180 left.
Angles wrap at +/-180. Coincident endpoints produce an undefined angle (`None`)
rather than an invented orientation.

The midpoint is a candidate position for geometry validation. The measured length
is along the finger, **not finger width or ring size**. These are 2D projected
measurements: bending, occlusion, and pointing toward the camera can affect them.
They do not determine a physical ring fit or a full 3D orientation. No jewelry
images or ring overlays are included.

### Validate geometry

1. Show an open hand and check that only its ring finger has the larger colored
   points labeled 13-16, with a white midpoint cross between 13 and 14.
2. Point the base segment upward: the angle should be near -90 degrees. Rotate
   toward the right: it should approach 0 degrees.
3. Move the hand across the frame: coordinates and midpoint should move with it.
   Move closer to the camera: the projected base-segment length should increase
   if the hand's orientation stays the same.
4. Show two hands and check both panel blocks. Remove them and check that the
   values clear and "No hands detected" appears.
5. Press **d** for the original landmark dump or **q** to exit.

Run the mathematical checks with no webcam required:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

The geometry-only mode remains available by running with `--geometry-only`.

## Ring orientation and temporal smoothing

The camera loop now supports a transparent ring PNG centered on the MCP-PIP
midpoint, resized proportionally, and rotated using the existing finger angle.
No new detection models, bracelets, or earrings are added.

The default run uses the included `assets/rings/demo/ring_front.png` and `assets/rings/demo/ring_back.png` test assets.
To use a different individual transparent ring PNG in single-image mode:

```powershell
# Replace the quoted path with your individual ring PNG.
.\.venv\Scripts\python.exe main.py --ring "C:\path\to\ring.png"
```

The PNG must be 8-bit RGBA, tightly framed around one ring, with its intended
placement anchor at the image center. By default it should be designed for a
finger pointing upward, with the band across the finger. If your original asset
uses a different orientation, set `--asset-angle` to that finger direction in
screen degrees (e.g. `0` for a right-pointing finger). Do not use the band's
crosswise direction for this value. In VS Code, add the corresponding `--ring`
and path strings to an `args` array in the webcam launch configuration.

### Rotation and scale mathematics

Let `theta = atan2(y14-y13, x14-x13)` in degrees, and let `theta_asset` be the
finger direction represented by the unrotated PNG (default -90 degrees).
The required clockwise image rotation is `delta = theta - theta_asset`.
Because OpenCV uses counterclockwise-positive angles, the code passes
`theta_asset - theta` to `getRotationMatrix2D`.

For an image point relative to the PNG center, screen-coordinate rotation is:

```text
x' = s * (cos(delta)*x - sin(delta)*y)
y' = s * (sin(delta)*x + cos(delta)*y)
target_width = width_ratio * distance(MCP, PIP)
s = target_width / PNG_width
```

The same scale `s` applies to both axes. The rotation canvas expands to preserve
corners, then its center is placed on the smoothed midpoint. Transparent edges
are interpolated using premultiplied alpha to avoid dark fringes. Only pixels
inside the camera frame are blended. See [OpenCV's affine transformation guide](https://docs.opencv.org/4.12.0/d4/d61/tutorial_warp_affine.html).

The default `--width-ratio 0.8` is an adjustable visual proportion, not a measured
finger width or physical ring size. Extreme output sizes are capped for safety.

### Smoothing

`smoothing.py` applies a time-based exponential moving average independently to
the center, width, and angle. With elapsed frame time `dt` and time constant `tau`:

```text
alpha = 1 - exp(-dt / tau)
smoothed = previous + alpha * (current - previous)
angle_difference = (current_angle - previous_angle + 180) % 360 - 180
smoothed_angle = previous_angle + alpha * angle_difference
```

The shortest angular difference prevents a full spin when crossing +/-180 degrees.
The default `--smoothing 0.12` reduces small fluctuations with a slight response
delay. Higher values smooth more but lag more; `--smoothing 0` disables smoothing
for comparison. The time-based weight makes the response similar across frame rates.

Each left/right label has its own history, so reordering the detector's result list
does not swap smoothing state. Missing or invalid detections clear their history
and hide the ring immediately. Long gaps and large position jumps reset the filter.
Duplicate handedness labels bypass smoothing to avoid mixing histories; label
misclassification or crossing hands can still cause discontinuities. This is a
simple two-hand baseline, not persistent multi-person tracking.

The geometry panel continues to show **raw measurements**; only the ring pose is
smoothed. Very short projected base segments (under 2 pixels) hide the ring because
their orientation is unreliable. The overlay remains 2D, without occlusion or
perspective correction.

### Validate orientation

1. Start with your ring PNG. An upright finger should leave an upright asset
   unrotated; turn the finger right and check that the ring follows it.
2. Move closer/farther at a fixed hand orientation and check proportional sizing.
3. Hold still, then compare the default smoothing with `--smoothing 0`.
4. Rotate through the leftward direction (+/-180 degrees) and check for continuity.
5. Show two hands, remove one, and bring it back; verify no ring remains after loss.
6. Move near the frame edges and check that clipping is clean. Press **q** to exit.

Run `python -m unittest discover -s tests -v` using the project's `.venv` interpreter.
Synthetic tests cover scaling, rotation direction, alpha blending, edge clipping,
angle wraparound, frame-rate independence, and hand-history resets. Validation
with the actual ring asset and webcam remains pending.

## Hand orientation and ring-view selection

The video panel now shows **Left/Right**, handedness confidence, and **Palm / Back /
Unknown** for each detected hand. `estimate` is the current heuristic result;
`Side` is the result after three consecutive matching estimates. The selected ring
view is shown separately. Press **d** for orientation and landmark debug output.
No additional model or training is used.

Run orientation detection without images using `--geometry-only`. The normal
webcam command loads the included pair. To specify an alternative pair explicitly:

```powershell
.\.venv\Scripts\python.exe main.py --ring-front "assets/rings/demo/ring_front.png" --ring-back "assets/rings/demo/ring_back.png"
```

Explicit paths are relative to the working directory; full paths also work.
The bundled defaults are resolved relative to the project. `assets/references/pack_anillos.png`
is the original reference sheet and is not used directly. Both assets should use the same
finger direction, centered anchor, and comparable transparent margins so switching
does not shift the ring. Existing rotation, proportional sizing, and pose smoothing
apply to whichever image is selected.

| Visible hand surface | Default image | Meaning |
| --- | --- | --- |
| Back of hand | `assets/rings/demo/ring_front.png` | Decorative face / gemstone |
| Palm | `assets/rings/demo/ring_back.png` | Underside / band |
| Unknown or initially unconfirmed | None | Hide the two-view overlay |

Use `--swap-ring-views` if your assets use the opposite naming convention. The
existing `--ring` mode remains supported and always draws its single image;
it does not use surface selection. It cannot be combined with the two-image mode.

### Explainable heuristic

`hand_orientation.py` uses the existing MediaPipe Tasks handedness category and
three image landmarks: **0 (wrist), 5 (index MCP), 17 (pinky MCP)**. In pixel units:

```text
u = index_MCP - wrist
v = pinky_MCP - wrist
c = (u.x*v.y - u.y*v.x) / (length(u)*length(v))
```

The numerator is twice the signed area of the projected palm triangle. Its sign
describes the order of the landmarks, and normalization makes the threshold
independent of image scale. This is more robust to in-plane rotation than comparing
thumb and pinky x coordinates alone. For the unmirrored image convention used here:

| Anatomical hand | Palm visible | Back visible |
| --- | --- | --- |
| Right | c < 0 | c > 0 |
| Left | c > 0 | c < 0 |

The heuristic reports `Unknown` when handedness confidence is below **0.60**,
either palm vector is shorter than **2 pixels**, or **abs(c) < 0.15** (nearly
collinear / edge-on). These are empirical baseline cutoffs, not learned values.
The displayed confidence belongs to left/right classification, not palm/back.

Three consecutive confident estimates confirm a side or switch the selected view.
During a pending switch the previous image remains; the panel shows the differing
raw estimate. Unknown views, lost hands, and duplicate left/right labels clear
that hand's state and hide its two-view overlay immediately. Each hand has separate
state keyed by handedness, so result-list reordering does not exchange views.

### Mirroring and limitations

The app processes and displays the original camera frame without flipping it.
This implementation uses the current **MediaPipe Tasks Hand Landmarker** convention;
do not apply legacy `mp.solutions.hands` mirror rules blindly. The convention was
checked with the installed model and MediaPipe's official `right_hands.jpg` test
image, including a horizontally mirrored copy. The current
[Tasks handedness label mapping](https://github.com/google-ai-edge/mediapipe/blob/master/mediapipe/tasks/cc/vision/hand_landmarker/hand_landmarks_detector_graph.cc)
is the relevant implementation reference.

If your camera driver already supplies mirrored frames, add `--input-mirrored`.
This corrects both the left/right label and triangle sign; it does not flip the
video. Confirm that your actual right hand is labeled Right during setup.

This is a 2D heuristic approximating the baseline idea of orientation-dependent
image choice, not a full 3D pose estimator or an exact reproduction of a specified
paper algorithm. Strong perspective, folded hands, occlusion, bad landmarks, and
handedness errors can produce an incorrect side. Edge-on transitions may hide the
ring. Duplicate labels are treated conservatively; multi-person tracking is not
implemented.

### Manual verification

1. Show your right palm, then its back; expect Right/Palm, then Right/Back. Repeat
   with the left hand. Rotate each hand within the image; the side should persist.
2. Turn slowly edge-on; check for Unknown rather than a forced side classification.
3. With both PNGs loaded, check that the decorative image appears on the back and
   the band image on the palm after three matching estimates.
4. Show one left and one right hand. Verify independent labels and image choices.
5. Remove and reintroduce a hand; confirm that an old image choice is not retained.
6. If the capture is mirrored by the driver, repeat with `--input-mirrored`.

Run the existing unittest command for automated heuristic and selection checks.
Live palm/back behavior and switching with your actual PNGs still need webcam
validation; the reference-image check does not replace it.
