"""
Puck Tracker
-------------
Maintains persistent identities for detected pucks across frames.
Applies temporal smoothing (rolling average) to positions.
Handles pucks appearing and disappearing gracefully -- a puck that fails
to detect for a few frames (noise, motion blur, momentary occlusion) is
NOT dropped immediately; it holds its last known position for up to
MAX_MISSING_FRAMES before being removed. This is what prevents the
"flickering" / "changes automatically" symptom where cells would pop in
and out or jump every time a single frame's detection was noisy.

Matching new detections to existing tracked pucks is done by nearest
distance in normalized table space (not by relying on detector output
order, which is NOT stable frame-to-frame -- OpenCV's findContours does
not guarantee consistent ordering).
"""

import math
from collections import deque
import config


class TrackedPuck:
    _counter = 0

    def __init__(self, x, y, puck_type):
        TrackedPuck._counter += 1
        self.id        = TrackedPuck._counter
        self.puck_type = puck_type        # "black" or "red"
        self.missing   = 0
        self._history  = deque(maxlen=config.POSITION_SMOOTH_FRAMES)
        self._history.append((x, y))
        self.x, self.y = x, y

    def update(self, x, y):
        self.missing = 0
        self._history.append((x, y))
        self.x = sum(p[0] for p in self._history) / len(self._history)
        self.y = sum(p[1] for p in self._history) / len(self._history)

    def mark_missing(self):
        self.missing += 1

    @property
    def pos(self):
        return (self.x, self.y)

    @property
    def alive(self):
        return self.missing <= config.MAX_MISSING_FRAMES


class _Candidate:
    """A not-yet-confirmed detection. Must be re-seen near the same spot for
    NEW_TRACK_CONFIRM_FRAMES consecutive frames before becoming a real
    TrackedPuck. Any missed frame resets it -- this is what filters out a
    hand sweeping through, since it rarely holds still that long, while a
    resting sticker confirms in a few frames without adding real UX lag."""

    def __init__(self, x, y):
        self.x, self.y = x, y
        self.count = 1


class PuckTracker:
    """
    Call update(black_pts, red_pts) once per frame with the RAW (unsmoothed)
    detections from PuckDetector. Returns (black_tracked, red_tracked) --
    lists of TrackedPuck with stable .id across frames and smoothed .pos.
    """

    def __init__(self):
        self._black = []   # list of TrackedPuck
        self._red   = []
        self._black_candidates = []   # list of _Candidate, not yet confirmed
        self._red_candidates   = []

    def update(self, black_pts, red_pts):
        self._black = self._match(self._black, black_pts, "black", "_black_candidates")
        self._red   = self._match(self._red,   red_pts,   "red",   "_red_candidates")
        return self._black, self._red

    def _match(self, existing, new_pts, puck_type, candidates_attr):
        matched_existing = set()
        matched_new      = set()

        # Nearest-neighbor matching: for each new detection, find the
        # closest still-unmatched existing tracked puck within MAX_MATCH_DIST.
        for ni, (nx, ny) in enumerate(new_pts):
            best_i, best_d = None, float("inf")
            for ei, ep in enumerate(existing):
                if ei in matched_existing:
                    continue
                d = math.hypot(nx - ep.x, ny - ep.y)
                if d < best_d:
                    best_d, best_i = d, ei
            if best_i is not None and best_d < config.MAX_MATCH_DIST:
                existing[best_i].update(nx, ny)
                matched_existing.add(best_i)
                matched_new.add(ni)

        # Age out unmatched existing pucks (don't kill immediately --
        # give them MAX_MISSING_FRAMES grace period, holding last position)
        for ei, ep in enumerate(existing):
            if ei not in matched_existing:
                ep.mark_missing()

        # Unmatched new detections go through the candidate debounce buffer
        # instead of instantly becoming a tracked puck (unless disabled).
        if not config.ENABLE_NEW_TRACK_DEBOUNCE:
            for ni, (nx, ny) in enumerate(new_pts):
                if ni not in matched_new:
                    existing.append(TrackedPuck(nx, ny, puck_type))
            return [ep for ep in existing if ep.alive]

        candidates = getattr(self, candidates_attr)
        matched_candidates = set()
        new_candidates = []

        for ni, (nx, ny) in enumerate(new_pts):
            if ni in matched_new:
                continue

            best_ci, best_cd = None, float("inf")
            for ci, cand in enumerate(candidates):
                if ci in matched_candidates:
                    continue
                d = math.hypot(nx - cand.x, ny - cand.y)
                if d < best_cd:
                    best_cd, best_ci = d, ci

            if best_ci is not None and best_cd < config.NEW_TRACK_CONFIRM_DIST:
                cand = candidates[best_ci]
                cand.x, cand.y = nx, ny
                cand.count += 1
                matched_candidates.add(best_ci)
                if cand.count >= config.NEW_TRACK_CONFIRM_FRAMES:
                    # Confirmed: promote to a real tracked puck.
                    existing.append(TrackedPuck(nx, ny, puck_type))
                else:
                    new_candidates.append(cand)
            else:
                new_candidates.append(_Candidate(nx, ny))

        # Any candidate not re-matched this frame is dropped (strict reset --
        # this is the actual debounce; a hand rarely holds still long enough
        # to survive it, a resting sticker does).
        setattr(self, candidates_attr, new_candidates)

        # Drop tracks that have been missing too long
        return [ep for ep in existing if ep.alive]