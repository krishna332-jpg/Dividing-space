"""
Simulated sensor — generates a fake camera frame with colored circles
representing pucks, so the full pipeline can be tested without hardware.
Pucks drift slowly to test live Voronoi animation.
"""
import math, time
import numpy as np
import cv2

W, H = 640, 480

class SimulatedSensor:
    def __init__(self):
        self._t0 = time.perf_counter()

    def start(self):
        print("[Simulated] Started — fake pucks moving on 640x480 frame.")

    def get_frame(self):
        t  = time.perf_counter() - self._t0
        frame = np.full((H, W, 3), (230, 235, 240), dtype=np.uint8)

        # Three black pucks (dark circles with black outline)
        black_pucks = [
            (int(W*0.25 + 60*math.sin(t*0.4)),   int(H*0.35 + 40*math.cos(t*0.3))),
            (int(W*0.65 + 50*math.cos(t*0.35)),  int(H*0.25 + 30*math.sin(t*0.5))),
            (int(W*0.5  + 40*math.sin(t*0.25)),  int(H*0.70 + 35*math.cos(t*0.45))),
        ]
        for cx, cy in black_pucks:
            cv2.circle(frame, (cx, cy), 28, (20, 20, 20), -1)       # black ring
            cv2.circle(frame, (cx, cy), 18, (230, 230, 230), -1)    # white top

        # Two red pins (fixed-ish, slow drift to simulate replacement)
        red_pins = [
            (int(W*0.40 + 15*math.sin(t*0.08)), int(H*0.55 + 10*math.cos(t*0.06))),
            (int(W*0.72 + 12*math.cos(t*0.07)), int(H*0.65 + 8 *math.sin(t*0.09))),
        ]
        for cx, cy in red_pins:
            cv2.circle(frame, (cx, cy), 22, (30, 30, 200), -1)      # red ring (BGR)
            cv2.circle(frame, (cx, cy), 14, (230, 230, 230), -1)    # white top

        return frame

    def stop(self):
        print("[Simulated] Stopped.")
