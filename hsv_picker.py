"""
HSV Picker — Calibration Helper
--------------------------------
Standalone tool: shows the live, perspective-warped camera feed (same warp
detector.py uses) and prints the exact HSV value under your cursor when you
click. Use this to find the real H/S/V range for your physical black puck
and red pin, instead of guessing config.py thresholds blind.

USAGE:
    python hsv_picker.py

    1. A window opens showing the warped (640x480) table view.
    2. Click directly on the puck/pin in the window.
    3. The exact H, S, V at that pixel prints to the console.
    4. Click several spots across the marker (center, edge, under the
       projector's ambient light) to see the real range it varies over.
    5. Press Q or ESC to quit.

Then update config.py's BLACK_PUCK_V_MAX (the puck is detected by darkness,
so only V matters) and/or RED_PIN_H_LOW1/HIGH1/LOW2/HIGH2/S_MIN/V_MIN to
comfortably bracket the values you see (leave a little margin on each side
for lighting flicker).
"""

import sys
import cv2
import numpy as np

sys.path.insert(0, ".")
from sensors import get_sensor
from detector import _warp_frame  # reuse the exact same warp the detector uses

WINDOW = "HSV Picker — click the marker"
_last_frame_hsv = None


def _mouse_cb(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN and _last_frame_hsv is not None:
        h, s, v = _last_frame_hsv[y, x]
        print(f"[HSV PICK] x={x} y={y}  ->  H={h}  S={s}  V={v}")


def run():
    global _last_frame_hsv

    sensor = get_sensor()
    sensor.start()

    cv2.namedWindow(WINDOW)
    cv2.setMouseCallback(WINDOW, _mouse_cb)

    print("=" * 60)
    print("HSV Picker")
    print("Click on the puck/pin to print its exact HSV value.")
    print("Sample several spots (center, edge) to see the real range.")
    print("Press Q or ESC to quit.")
    print("=" * 60)

    while True:
        frame = sensor.get_frame()
        if frame is None:
            continue

        warped = _warp_frame(frame)
        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)
        _last_frame_hsv = hsv

        cv2.imshow(WINDOW, warped)
        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), ord("Q"), 27):
            break

    sensor.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()