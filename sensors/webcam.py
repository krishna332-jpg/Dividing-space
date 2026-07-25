"""Webcam sensor backend."""
import sys
import cv2

class WebcamSensor:
    def __init__(self, index=0):
        self._idx = index
        self._cap = None

    def start(self):
        # On Windows, cv2.VideoCapture(index) with the default backend (MSMF)
        # can take several seconds to open -- during which nothing pumps the
        # OS message queue for any already-created window, making it look
        # frozen/black ("Not Responding"). CAP_DSHOW opens near-instantly.
        if sys.platform == "win32":
            self._cap = cv2.VideoCapture(self._idx, cv2.CAP_DSHOW)
        else:
            self._cap = cv2.VideoCapture(self._idx)
            
        if not self._cap.isOpened():
            raise RuntimeError(f"Could not open webcam {self._idx}")

        # ── EXPOSURE & WHITE BALANCE CALIBRATION ──────────────────────────────
        # 1. Turn off Auto Exposure (1 typically forces manual mode in OpenCV)
        self._cap.set(cv2.CAP_PROP_AUTO_EXPOSURE, 1) 
        
        # 2. Lock Exposure level 
        # Note: -6 is a standard starting point for many webcams under museum lighting.
        # If the camera feed becomes completely black, change this to -5 or -4.
        self._cap.set(cv2.CAP_PROP_EXPOSURE, -6) 
        
        # 3. Disable Auto White Balance to lock down target HSV colors permanently
        self._cap.set(cv2.CAP_PROP_AUTO_WB, 0)
        # ──────────────────────────────────────────────────────────────────────

        print(f"[Webcam] Started (index {self._idx}) with Locked Manual Settings.")

    def get_frame(self):
        if self._cap:
            ret, frame = self._cap.read()
            if ret: return frame
        return None

    def stop(self):
        if self._cap: self._cap.release()
        print("[Webcam] Stopped.")