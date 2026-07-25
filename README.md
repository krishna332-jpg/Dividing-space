# DividingSpace

An interactive projector exhibit. A camera watches a table from above,
tracks **black pucks** and **red pins** placed on it, and a projector draws
colored regions (Voronoi cells) around each one — one region per object.
Move a puck and its region follows smoothly, in real time. Bring a black
puck close to a red pin, and sparks fly.

---

## Table of Contents
1. [How It Works](#how-it-works)
2. [Project Structure](#project-structure)
3. [Hardware](#hardware)
4. [Installation](#installation)
5. [Quick Start (the short version)](#quick-start-the-short-version)
6. [Step-by-Step Usage](#step-by-step-usage)
   - [Step 1 — Choose your camera backend](#step-1--choose-your-camera-backend)
   - [Step 2 — Calibrate the table](#step-2--calibrate-the-table)
   - [Step 3 — (Optional) Tune color detection with the HSV picker](#step-3--optional-tune-color-detection-with-the-hsv-picker)
   - [Step 4 — Run the exhibit](#step-4--run-the-exhibit)
7. [Controls (while main.py is running)](#controls-while-mainpy-is-running)
8. [Switching Cameras](#switching-cameras)
9. [Configuration Reference (config.py)](#configuration-reference-configpy)
10. [Troubleshooting](#troubleshooting)
11. [Typical First-Time Setup Order](#typical-first-time-setup-order)

---

## How It Works

Every frame (target: 60 times per second), the pipeline does this:

1. **Sensor** (`sensors/`) — grabs a raw camera frame looking down at the
   table. Backend is one of `kinect_v2`, `webcam`, or `simulated`.
2. **Detector** (`detector.py`) — perspective-warps the frame to the
   calibrated table rectangle, then finds black pucks and red pins by HSV
   color thresholding, filters out noise (hands, glare, shadows) using
   size/shape/circularity checks, and converts surviving blobs into
   normalized `[0..1]` table coordinates.
3. **Tracker** (`tracker.py`) — gives each detected blob a persistent
   identity across frames, smooths its position, and tolerates a few
   missing frames so a track doesn't disappear the instant detection blips.
4. **Voronoi Engine** (`voronoi_engine.py`) — takes all tracked
   pucks/pins as seed points and computes a Voronoi diagram, clipped to the
   table bounds. Vertices glide (interpolate) toward their new positions
   each frame instead of snapping, which is what makes the region
   boundaries move fluidly instead of jumping.
5. **Sparks** (`sparks.py`) — checks whether any black puck has gotten
   close enough to a red pin and, if so, fires a burst of spark particles.
6. **Renderer** (`renderer.py`) — draws the filled Voronoi cells, glowing
   borders, puck/pin dots, and spark particles onto a `pygame` surface.
7. That surface is displayed fullscreen on the projector's monitor, and the
   loop repeats.

`main.py` is the orchestrator that wires all of the above together and
runs the live loop.

## Project Structure

```
DividingSpace/
├── main.py             # Run this to start the actual exhibit
├── calibration.py       # Run this first — maps table corners in the camera view
├── hsv_picker.py         # Optional helper — sample HSV values off your real puck/pin
├── config.py             # All tunable settings (camera, colors, sizes, visuals, physics)
├── detector.py           # Perspective warp + color/shape based puck & pin detection
├── tracker.py             # Frame-to-frame identity, smoothing, missing-frame handling
├── voronoi_engine.py       # Computes & animates the Voronoi regions
├── sparks.py                # Spark particle system (black puck ↔ red pin collisions)
├── renderer.py                # Draws everything to the pygame screen
└── sensors/
    ├── __init__.py             # get_sensor() factory — reads config.SENSOR_BACKEND
    ├── base.py                  # Abstract sensor interface (start / get_frame / stop)
    ├── kinect_v2.py               # Kinect v2 backend
    ├── webcam.py                   # Any USB webcam backend (via OpenCV)
    └── simulated.py                  # Fake camera feed — no hardware needed, for testing
```

## Hardware

- A projector, mounted overhead, facing straight down at a white/light
  matte table.
- A camera facing the same table from above: either a **Kinect v2** or a
  regular **USB webcam**.
- Physical **black pucks** and **red pins** to place on the table surface.

You don't strictly need any of this to try the software — set
`SENSOR_BACKEND = "simulated"` in `config.py` and it'll run against a fake
generated camera feed so you can confirm everything works first.

## Installation

```bash
pip install pygame opencv-python numpy scipy screeninfo pykinect2
```

`pykinect2` and the Kinect for Windows SDK 2.0 are only required if you're
using `SENSOR_BACKEND = "kinect_v2"`. If you're only using a webcam or the
simulated backend, you can skip installing `pykinect2` and the SDK.

## Quick Start (the short version)

If you just want the commands, in order:

```bash
# 1. Set SENSOR_BACKEND in config.py to your real camera ("webcam" or "kinect_v2")

# 2. Calibrate the table corners (once, or whenever the camera/table moves)
python calibration.py

# 3. Run the exhibit
python main.py
```

That's really it — `calibration.py` first, then `python main.py`. Everything
below explains each of those steps in more detail and covers the optional
tuning tools.

## Step-by-Step Usage

### Step 1 — Choose your camera backend

Open `config.py` and set:

```python
SENSOR_BACKEND = "webcam"   # or "kinect_v2" or "simulated"
```

- `"simulated"` — no hardware needed, generates a fake test frame. Good for
  a first sanity check that the software itself runs correctly.
- `"webcam"` — any USB webcam, opened via OpenCV. Set `WEBCAM_INDEX` if you
  have more than one camera attached (0 is usually the default/built-in one).
- `"kinect_v2"` — requires the Kinect for Windows SDK 2.0 and `pykinect2`
  installed.

### Step 2 — Calibrate the table

This tells the software exactly where the table's four corners sit in the
camera's raw view, so it can perspective-warp the feed into a clean
top-down rectangle. **Do this once per camera/table setup, and again any
time the camera or table physically moves.**

```bash
python calibration.py
```

1. A window opens showing the live camera feed.
2. Click the four table corners **in this exact order**:
   `Top-Left → Top-Right → Bottom-Right → Bottom-Left`.
3. Once all 4 are placed, press **S** to save — this writes the corner
   coordinates straight into `TABLE_CORNERS_CAM` in `config.py`.
4. Press **R** at any point to reset and re-click the corners.
5. Press **Q** or **Esc** to quit without saving.

> ⚠️ **Important:** make sure `SENSOR_BACKEND` is set to your *real* camera
> (`"webcam"` or `"kinect_v2"`) **before** calibrating. Calibrating while
> set to `"simulated"` will overwrite your saved corners with corners
> measured from the fake test frame, which won't line up with anything real.

### Step 3 — (Optional) Tune color detection with the HSV picker

If pucks/pins aren't being detected reliably (different lighting, different
physical markers, etc.), use the HSV picker to read the exact color values
of your real objects instead of guessing:

```bash
python hsv_picker.py
```

1. A window opens showing the same warped, top-down table view the
   detector uses.
2. Click directly on the puck or pin in the image.
3. The exact `H`, `S`, `V` values under your click print to the console.
4. Click several spots (center, edge, under different lighting) to see the
   real range those values vary across.
5. Press **Q** or **Esc** to quit.

Use those readings to adjust the thresholds in `config.py`:
- `BLACK_PUCK_V_MAX` / `BLACK_PUCK_S_MAX` — the black puck is detected by
  darkness (low Value), not hue.
- `RED_PIN_H_LOW1/HIGH1/LOW2/HIGH2`, `RED_PIN_S_MIN`, `RED_PIN_V_MIN` — the
  red pin's hue range (split into two bands since red wraps around 0°/180°
  in OpenCV's hue space).

This step is optional — the shipped defaults are already tuned to a
measured real black puck and red pin, so start with Step 4 and only come
back here if detection is unreliable.

### Step 4 — Run the exhibit

```bash
python main.py
```

This opens a fullscreen window on the configured projector monitor
(`PROJECTION_MONITOR` in `config.py`) and starts the live loop: capture →
detect → track → compute Voronoi cells → check for spark collisions →
render, at up to `TARGET_FPS` (default 60) frames per second.

## Controls (while main.py is running)

| Key         | Action                                                |
|-------------|--------------------------------------------------------|
| `Q` / `Esc` | Quit                                                    |
| `D`         | Toggle debug overlay (raw camera feed + detected dots)  |
| `F`         | Toggle FPS counter                                      |
| `R`         | Reset the spark system                                  |
| `Space`     | Save an instant screenshot of the projected output      |

Screenshots are saved to your Desktop as
`dividingspace_snapshot_YYYYMMDD_HHMMSS.png`.

## Switching Cameras

Change one line in `config.py`:

```python
SENSOR_BACKEND = "simulated"   # test without any hardware
SENSOR_BACKEND = "webcam"      # any USB webcam
SENSOR_BACKEND = "kinect_v2"   # Kinect v2
```

`calibration.py` and `hsv_picker.py` both calibrate/sample whichever
backend `SENSOR_BACKEND` is currently set to (they use the same
`get_sensor()` factory `main.py` uses) — so always double-check that
setting before running either tool.

## Configuration Reference (config.py)

All tunable values live in one file. The main groups:

| Section | What it controls |
|---|---|
| Camera / Sensor | `SENSOR_BACKEND`, `WEBCAM_INDEX` |
| Table calibration | `TABLE_CORNERS_CAM` (written automatically by `calibration.py`) |
| Projection output | `PROJECTION_MONITOR`, `PROJ_W`, `PROJ_H` |
| Puck/pin detection | HSV thresholds, size (`MIN_PUCK_AREA`/`MAX_PUCK_AREA`), shape filters (`MIN_CIRCULARITY`, `MIN_SOLIDITY`, `MAX_ASPECT_RATIO`) |
| New-track debounce | `NEW_TRACK_CONFIRM_FRAMES`, `NEW_TRACK_CONFIRM_DIST` — stops a passing hand from being mistaken for a new puck |
| Table ROI masking | `TABLE_MASK_MARGIN_PX`, `TABLE_EXCLUSION_ZONES` |
| Tracking smoothness | `POSITION_SMOOTH_FRAMES`, `MAX_MISSING_FRAMES`, `MAX_MATCH_DIST` |
| Voronoi animation | `LERP_SPEED`, `VERTEX_MATCH_DIST`, `TARGET_FPS` |
| Visual style | Colors, border widths, dot sizes (`BG_COLOR`, `BLACK_PUCK_CELL_COLOR`, `RED_PIN_CELL_COLOR`, etc.) |
| Sparks | `SPARK_TOUCH_DIST` (trigger distance), plus particle count/lifetime/speed/color |

The two you'll touch most often when tuning behavior after setup:
- **`LERP_SPEED`** — how fast region boundaries glide to their new shape.
  Lower = smoother/slower, higher = snappier/more jittery.
- **`SPARK_TOUCH_DIST`** — how close a black puck and red pin need to get
  (in projected pixel space) before sparks fire.

## Troubleshooting

- **No pucks detected at all:** First switch to `SENSOR_BACKEND =
  "simulated"` and run `main.py` to confirm the software itself works.
  Then switch back to your real camera and press **D** while running to
  see exactly what the camera sees and where (if anywhere) it thinks
  objects are.
- **Detected regions don't line up with the real pucks/pins on the
  table:** Re-run `python calibration.py` with `SENSOR_BACKEND` set to your
  real camera. Don't move the camera after calibrating — if you do, you
  need to recalibrate.
- **Detection is flaky / picks up hands or shadows as pucks:** Run
  `python hsv_picker.py`, sample your real markers, and tighten the HSV
  ranges and size/shape filters in `config.py` accordingly.
- **Too jittery, or too slow to respond to movement:** Adjust
  `LERP_SPEED` and `POSITION_SMOOTH_FRAMES` in `config.py`.
- **Sparks fire too early or too late:** Adjust `SPARK_TOUCH_DIST` in
  `config.py`.
- **Wrong monitor / wrong resolution:** Check `PROJECTION_MONITOR`,
  `PROJ_W`, and `PROJ_H` in `config.py` match your projector setup.

## Typical First-Time Setup Order

For a brand-new setup, this is the order things are meant to be done in:

1. `pip install` the dependencies.
2. Set `SENSOR_BACKEND = "simulated"` and run `python main.py` just to
   confirm the software runs end-to-end with no hardware involved.
3. Plug in your real camera, set `SENSOR_BACKEND` to `"webcam"` or
   `"kinect_v2"`.
4. Run `python calibration.py` and click the 4 table corners, then press
   **S** to save.
5. *(Optional)* Run `python hsv_picker.py` if you need to tune detection
   colors for your specific pucks/pins/lighting.
6. Run `python main.py` — the exhibit is now live.
7. If anything drifts (camera bumped, table moved, lighting changed a lot),
   go back to step 4 (or step 5 for color issues).
