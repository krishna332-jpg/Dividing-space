"""
Table Calibration Tool
-----------------------
Run this ONCE before running the main exhibit to tell the system
exactly where the table corners are in the camera's view.

HOW TO USE:
    python calibration.py

    1. A window opens showing the live camera feed.
    2. Click the FOUR corners of the table surface in this order:
           TOP-LEFT → TOP-RIGHT → BOTTOM-RIGHT → BOTTOM-LEFT
    3. After clicking all 4, the calibration is saved to config.py
       (TABLE_CORNERS_CAM is updated in place).
    4. Press Q or ESC to quit without saving.
    5. Press R to reset and re-click the corners.
"""

import sys, re
import cv2
import numpy as np
sys.path.insert(0, ".")
from sensors import get_sensor

WINDOW = "DividingSpace — Table Calibration"
CORNERS_NEEDED = 4

corners = []
sensor  = None
last_frame = None


def _mouse_cb(event, x, y, flags, param):
    global corners
    if event == cv2.EVENT_LBUTTONDOWN and len(corners) < CORNERS_NEEDED:
        corners.append([x, y])
        print(f"  Corner {len(corners)}: ({x}, {y})")
        if len(corners) == CORNERS_NEEDED:
            print("  All 4 corners captured. Press S to save, R to redo.")


def _save_to_config(pts):
    """Overwrite TABLE_CORNERS_CAM in config.py."""
    with open("config.py", "r") as f:
        text = f.read()
    new_val = (f"[\n"
               f"    {pts[0]},\n"
               f"    {pts[1]},\n"
               f"    {pts[2]},\n"
               f"    {pts[3]},\n"
               f"]")
    # Match the *whole* nested list: an outer [ ... ] that may contain
    # inner [ ... ] pairs. The old pattern ("\[.*?\]") stopped at the
    # first "]" it found -- which is the end of the FIRST corner pair,
    # not the end of the whole list -- leaving the rest of the old list
    # dangling in the file and breaking config.py's syntax.
    text = re.sub(
        r"TABLE_CORNERS_CAM\s*=\s*\[(?:[^\[\]]|\[[^\[\]]*\])*\]",
        f"TABLE_CORNERS_CAM = {new_val}",
        text, flags=re.DOTALL
    )
    with open("config.py", "w") as f:
        f.write(text)
    print(f"[Calibration] Saved to config.py: {pts}")


def run():
    global corners, sensor, last_frame

    sensor = get_sensor()
    sensor.start()

    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WINDOW, _mouse_cb)

    print("=" * 60)
    print("DividingSpace Table Calibration")
    print("Click the 4 table corners in order:")
    print("  1. Top-Left  2. Top-Right  3. Bottom-Right  4. Bottom-Left")
    print("Keys: S=save  R=reset  Q=quit")
    print("=" * 60)

    while True:
        frame = sensor.get_frame()
        if frame is not None:
            last_frame = frame.copy()

        if last_frame is None:
            continue

        display = last_frame.copy()

        # Draw already-clicked corners
        labels = ["TL", "TR", "BR", "BL"]
        for i, (cx, cy) in enumerate(corners):
            cv2.circle(display, (cx, cy), 8, (0, 255, 0), -1)
            cv2.putText(display, labels[i], (cx+10, cy-10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        # Draw lines between corners
        if len(corners) >= 2:
            for i in range(len(corners)-1):
                cv2.line(display, tuple(corners[i]), tuple(corners[i+1]),
                         (0, 200, 255), 2)
        if len(corners) == 4:
            cv2.line(display, tuple(corners[3]), tuple(corners[0]),
                     (0, 200, 255), 2)
            cv2.putText(display, "Press S to save, R to redo",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0,255,0), 2)
        else:
            remaining = CORNERS_NEEDED - len(corners)
            msg = f"Click {remaining} more corner(s) — {labels[len(corners)]} next"
            cv2.putText(display, msg, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0,200,255), 2)

        cv2.imshow(WINDOW, display)
        key = cv2.waitKey(1) & 0xFF

        if key != 255 and key != -1:
            print(f"[debug] key pressed: {key} ({chr(key) if 32 <= key < 127 else '?'})")

        if key in (ord("q"), ord("Q"), 27):
            break
        elif key in (ord("r"), ord("R")):
            corners = []
            print("[Calibration] Reset — click 4 corners again.")
        elif key in (ord("s"), ord("S")) and len(corners) == 4:
            _save_to_config(corners)
            print("[Calibration] Done. Run main.py to start the exhibit.")
            break
        elif key in (ord("s"), ord("S")) and len(corners) != 4:
            print(f"[Calibration] Need 4 corners first, you have {len(corners)}.")

    sensor.stop()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    run()
