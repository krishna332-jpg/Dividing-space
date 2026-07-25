"""
Puck & Pin Detector - Color Tracking Edition
--------------------------------------------------
Tracks pucks by color/darkness: a genuinely BLACK/dark puck (detected by
low Value, since it has no distinct hue of its own) and a RED pin (detected
by hue, since red is a strong distinct color) -- no sticker required on top
of either marker.

Detection pipeline (in order):
  1. Perspective warp to the calibrated table rectangle.
  2. Table ROI mask: crop out everything outside the calibrated table
     surface (inset margin + optional exclusion zones), so glare/objects
     off the table can never generate detections.
  3. Thresholding: low-Value mask for the black puck, HSV hue-band mask
     for the red pin (red wraps 0/180 so it needs two sub-ranges).
  4. Morphological open (kill isolated glare specks) then close
     (fill in genuine marker blobs).
  5. Contour filtering on area, circularity, and solidity to reject
     shadows, reflections, and other dark/red fragments.
"""

import cv2
import math
import numpy as np
import config

# Module-level homography (kept for any external code that wants the
# raw table->unit-square mapping; not used directly in the hot path).
_src = np.array(config.TABLE_CORNERS_CAM, dtype=np.float32)
_dst = np.array([[0, 0], [1, 0], [1, 1], [0, 1]], dtype=np.float32)
_H, _ = cv2.findHomography(_src, _dst)

# Warped canvas size used throughout the detector.
_WARP_W, _WARP_H = 640, 480


def _warp_frame(frame):
    """Perspective-correct the raw camera frame onto a fixed-size canvas
    where the calibrated table corners map exactly to the canvas corners."""
    dst = np.array(
        [[0, 0], [_WARP_W, 0], [_WARP_W, _WARP_H], [0, _WARP_H]], dtype=np.float32
    )
    src = np.array(config.TABLE_CORNERS_CAM, dtype=np.float32)
    M, _ = cv2.findHomography(src, dst)
    return cv2.warpPerspective(frame, M, (_WARP_W, _WARP_H))


def warp_frame_for_debug(frame):
    return _warp_frame(frame)


def _build_table_roi_mask(shape):
    """Build a binary ROI mask (255 = valid detection area) for the warped
    canvas. Insets from the canvas edge to absorb calibration jitter/edge
    glare, and blacks out any configured exclusion zones (e.g. a glary
    fixed spot, a control zone taped to the table).

    Because the warp itself maps TABLE_CORNERS_CAM exactly onto the canvas
    rectangle, the whole warped canvas *is* the table by construction --
    this ROI mask exists to guard against calibration drift and edge
    artifacts, not to redo the perspective crop.
    """
    h, w = shape
    roi = np.full((h, w), 255, dtype=np.uint8)

    margin = max(0, int(config.TABLE_MASK_MARGIN_PX))
    if margin > 0:
        # Zero out a border strip of `margin` px on all sides.
        roi[:margin, :] = 0
        roi[h - margin:, :] = 0
        roi[:, :margin] = 0
        roi[:, w - margin:] = 0

    for zone in getattr(config, "TABLE_EXCLUSION_ZONES", []):
        pts = np.array(zone, dtype=np.int32).reshape((-1, 1, 2))
        cv2.fillPoly(roi, [pts], 0)

    return roi


def _black_puck_mask(hsv, roi_mask):
    """Threshold for the black puck: dark (low Value) AND low-saturation
    (near-neutral/colorless), which is what separates a true matte black
    puck from a hand -- a hand is dark in shadow too, but still reads
    noticeably more saturated (skin-colored) than a colorless black
    object."""
    lower = np.array([0, 0, 0])
    upper = np.array([180, config.BLACK_PUCK_S_MAX, config.BLACK_PUCK_V_MAX])
    mask = cv2.inRange(hsv, lower, upper)
    return cv2.bitwise_and(mask, roi_mask)


def _red_pin_mask(hsv, roi_mask):
    """Threshold for the red pin's hue band. Red wraps around 0/180 in
    OpenCV's Hue space, so two sub-ranges are combined."""
    lower1 = np.array([config.RED_PIN_H_LOW1, config.RED_PIN_S_MIN, config.RED_PIN_V_MIN])
    upper1 = np.array([config.RED_PIN_H_HIGH1, 255, 255])
    lower2 = np.array([config.RED_PIN_H_LOW2, config.RED_PIN_S_MIN, config.RED_PIN_V_MIN])
    upper2 = np.array([config.RED_PIN_H_HIGH2, 255, 255])

    mask1 = cv2.inRange(hsv, lower1, upper1)
    mask2 = cv2.inRange(hsv, lower2, upper2)
    mask = cv2.bitwise_or(mask1, mask2)
    return cv2.bitwise_and(mask, roi_mask)


def _clean_mask(mask):
    """MORPH_OPEN to strip isolated glare/noise specks, then MORPH_CLOSE
    to fill in and solidify genuine target blobs."""
    open_kernel = np.ones((3, 3), np.uint8)
    close_kernel = np.ones((7, 7), np.uint8)

    mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, open_kernel)
    mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, close_kernel)
    return mask


class PuckDetector:
    def detect(self, frame, debug=False):
        warped = _warp_frame(frame)
        hsv = cv2.cvtColor(warped, cv2.COLOR_BGR2HSV)

        if debug:
            h, s, v = cv2.split(hsv)
            print(f"[HSV RANGE] S: min={s.min()} max={s.max()} | V: min={v.min()} max={v.max()}")

        roi_mask = _build_table_roi_mask(warped.shape[:2])

        # Black puck mask (low-Value/dark) and red pin mask (hue-based),
        # each independently ROI-limited
        black_mask = _clean_mask(_black_puck_mask(hsv, roi_mask))
        red_mask   = _clean_mask(_red_pin_mask(hsv, roi_mask))

        if debug:
            cv2.imshow("DividingSpace | ROI mask", roi_mask)
            cv2.imshow("DividingSpace | black puck mask", black_mask)
            cv2.imshow("DividingSpace | red pin mask", red_mask)

        black_pucks = _find_centroids(black_mask, warped.shape[:2], "BLACK_PUCK", debug)
        red_pins    = _find_centroids(red_mask, warped.shape[:2], "RED_PIN", debug)

        return black_pucks, red_pins


def _find_centroids(mask, frame_shape, label="", debug=False):
    """Find contours in `mask` and keep only ones that pass strict area,
    circularity, solidity, and elongation filters -- rejecting color blooms,
    hands, and shadow fragments that survive thresholding."""
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    fh, fw = frame_shape
    points = []

    for cnt in contours:
        area = cv2.contourArea(cnt)

        # Cheap reject before the more expensive perimeter/hull math.
        if area < config.MIN_PUCK_AREA:
            continue

        area_ok = config.MIN_PUCK_AREA <= area <= config.MAX_PUCK_AREA
        if not area_ok:
            continue

        perimeter = cv2.arcLength(cnt, True)
        if perimeter == 0:
            continue
        circularity = 4 * math.pi * area / (perimeter * perimeter)
        if circularity < config.MIN_CIRCULARITY:
            continue

        hull = cv2.convexHull(cnt)
        hull_area = cv2.contourArea(hull)
        if hull_area == 0:
            continue
        solidity = area / hull_area
        if solidity < config.MIN_SOLIDITY:
            continue

        # Elongation filter: reject elongated finger/shadow blobs that pass
        # circularity+solidity but aren't round-ish like the physical pucks.
        (_, (rw, rh), _) = cv2.minAreaRect(cnt)
        short_side, long_side = sorted((rw, rh))
        if short_side == 0:
            continue
        aspect_ratio = long_side / short_side
        if aspect_ratio > config.MAX_ASPECT_RATIO:
            continue

        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        cx = M["m10"] / M["m00"] / fw
        cy = M["m01"] / M["m00"] / fh
        points.append((cx, cy))

        if debug:
            print(
                f"[{label}] area={area:.0f} circ={circularity:.2f} "
                f"solidity={solidity:.2f} aspect={aspect_ratio:.2f} -> accepted"
            )

    return points