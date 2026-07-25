"""
Kinect v2 sensor backend for DividingSpace.
Returns BGR color frames for puck detection.
Reuses the same pykinect2 fixes from APCS (time.perf_counter, struct assert).
"""
import time
import numpy as np

COLOR_W = 1920
COLOR_H = 1080


class KinectV2Sensor:
    def __init__(self):
        self._kinect = None

    def start(self):
        try:
            from pykinect2 import PyKinectV2, PyKinectRuntime
        except ImportError:
            raise RuntimeError(
                "pykinect2 not installed. Run: pip install pykinect2\n"
                "Then apply the two patches from the APCS setup:\n"
                "  1. Comment out: from comtypes import _check_version; _check_version('')\n"
                "  2. Replace: time.clock() -> time.perf_counter()"
            )
        self._kinect = PyKinectRuntime.PyKinectRuntime(
            PyKinectV2.FrameSourceTypes_Color
        )
        print("[KinectV2] Started.")

    def get_frame(self):
        """Returns latest BGR color frame as numpy array (1080x1920x3), or None."""
        if self._kinect and self._kinect.has_new_color_frame():
            raw = self._kinect.get_last_color_frame()
            if raw is not None:
                bgra = raw.reshape((COLOR_H, COLOR_W, 4))
                return bgra[:, :, :3].copy()
        return None

    def stop(self):
        if self._kinect:
            self._kinect.close()
        print("[KinectV2] Stopped.")
