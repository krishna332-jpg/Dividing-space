"""
DividingSpace Configuration
-----------------------------
All tunable parameters in one place.
"""

# ── Camera / Sensor ───────────────────────────────────────────────────────────
SENSOR_BACKEND = "webcam"  # "kinect_v2" | "webcam" | "simulated"
WEBCAM_INDEX   = 0

# ── Table calibration ─────────────────────────────────────────────────────────
TABLE_CORNERS_CAM = [
    [1, 1],
    [635, 2],
    [637, 473],
    [0, 475],
]

# ── Projection output ─────────────────────────────────────────────────────────
PROJECTION_MONITOR = 1
PROJ_W = 1920
PROJ_H = 1080

# ── Puck detection (Black Puck / Red Pin, HSV space) ─────────────────────────
# Physical markers: a genuinely BLACK/dark puck and a RED pin. The black puck
# has no real hue/saturation of its own (measured H=0 S=0 V=24 off the actual
# marker) so it's detected by darkness (low Value) rather than hue, unlike
# the red pin which has a strong, distinct hue.

# Black puck: anything darker than this Value is considered a candidate.
# Measured actual puck V=24 -- leaving headroom above that for lighting
# variation while still staying well under typical tabletop/background V.
BLACK_PUCK_V_MAX  = 55

# Saturation ceiling for the black puck. A true matte-black object is
# near-neutral/colorless (low saturation) even though it's dark. Skin --
# even in shadow -- still reads noticeably more saturated than that. This
# cap is what lets the detector tell a resting hand apart from the puck
# instead of treating any sufficiently dark blob as "the puck."
# Measured real puck S=16 -- leaving headroom above that.
BLACK_PUCK_S_MAX  = 60

# Red pin HSV range (red wraps around 0/180 in OpenCV's Hue space, so we need
# two bands to cover it). Matches measured real pin: H=2 S=217 V=133.
RED_PIN_H_LOW1    = 0
RED_PIN_H_HIGH1   = 8
RED_PIN_H_LOW2    = 170
RED_PIN_H_HIGH2   = 180
RED_PIN_S_MIN     = 130    # Raised floor: rejects skin tones & neutral glare
RED_PIN_V_MIN     = 70

# Size thresholds
MIN_PUCK_AREA     = 700     # Raised: rejects small glare specks / fingertips
MAX_PUCK_AREA     = 35000   # raised further: camera is close enough that puck/pin blobs fill a large fraction of the 640x480 warped frame (~20-25k px measured) -- old ceiling was rejecting every real detection

# Shape filters
MIN_CIRCULARITY  = 0.35     # Rejects irregular blooms, hand/finger blobs
MIN_SOLIDITY     = 0.80     # Rejects hollow/ragged shapes

# Elongation filter: circularity/solidity alone can't reject an elongated
# finger/shadow blob that still happens to be fairly smooth-edged. The
# physical pucks/pins are round, so we also require the contour's
# minAreaRect aspect ratio (long/short side) to be near 1:1 -- this is what
# separates round pucks from stretched-out finger/shadow shapes.
MAX_ASPECT_RATIO = 2.0      # raised: tolerate mild elongation from motion blur while a puck is being moved

# ── New-track debounce ────────────────────────────────────────────────────────
# A hand sweeping across the table is only "sticker-shaped" for a few frames
# at most. Require a candidate detection to reappear near the same spot for
# several consecutive frames before it's promoted to a real tracked puck --
# this filters transient hand passes without adding lag to a resting sticker.
ENABLE_NEW_TRACK_DEBOUNCE = True   # set False to disable this filter entirely
NEW_TRACK_CONFIRM_FRAMES = 4     # consecutive frames required to confirm
NEW_TRACK_CONFIRM_DIST   = 0.05  # normalized-space match distance for candidates

# ── Table ROI masking ─────────────────────────────────────────────────────────
# After perspective-warping the frame to the calibrated table rectangle, we
# still inset the detection mask by a small margin. This absorbs small
# calibration drift/jitter in TABLE_CORNERS_CAM and kills the edge-of-table
# glare/vignetting that tends to hug the table boundary.
TABLE_MASK_MARGIN_PX = 12

# Optional list of extra polygons (in warped 640x480 space) to always exclude
# from detection -- e.g. a permanently glary spot, a mounted light, a UI
# control zone taped to the table. Empty by default.
TABLE_EXCLUSION_ZONES = []

# ── Puck tracking (Adjusted for stable tracking at lower framerates) ─────────
POSITION_SMOOTH_FRAMES = 8      
MAX_MISSING_FRAMES     = 45     # Keeps cells active during low FPS drops and longer detection gaps while moving
MAX_MATCH_DIST          = 0.20  # Keeps tracking intact during fast movements

LERP_SPEED         = 0.14   
VERTEX_MATCH_DIST  = 220    
TARGET_FPS         = 60

# ── Visual style ──────────────────────────────────────────────────────────────
BG_COLOR              = (245, 240, 230)   # warm cream
BLACK_PUCK_CELL_COLOR = (90, 165, 230)    # vivid blue
RED_PIN_CELL_COLOR    = (225, 120, 105)   # vivid coral-red
BORDER_COLOR          = (255, 255, 255)   # white dividing line
BORDER_OUTLINE_COLOR  = (20, 20, 20)      # thin black outline around the line
BORDER_WIDTH          = 4
BORDER_OUTLINE_WIDTH  = 2                 
PUCK_DOT_COLOR        = (25, 35, 45)      # dark charcoal
PUCK_DOT_RADIUS       = 18
PIN_DOT_COLOR         = (150, 25, 20)     # deep red
PIN_DOT_RADIUS        = 14

# Spark trigger distance -- how close (in projection pixel space) the
# tracked puck and pin centers need to get before a spark fires. This is
# INTENTIONALLY separate from PUCK_DOT_RADIUS/PIN_DOT_RADIUS (those are
# just cosmetic dot sizes, unrelated to how big the real physical objects
# are once mapped through your table calibration). If sparks still don't
# fire when the real objects touch, raise this; if they fire too early
# (before the objects visually touch), lower it. Tune by testing.
SPARK_TOUCH_DIST      = 100

# ── Spark animation ───────────────────────────────────────────────────────────
SPARK_COUNT        = 18
SPARK_LIFETIME     = 0.45
SPARK_SPEED        = 280
SPARK_COLOR_START  = (255, 240, 80)
SPARK_COLOR_END    = (255, 100, 20)
SPARK_WIDTH        = 3