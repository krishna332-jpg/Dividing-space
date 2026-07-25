"""
Voronoi Engine
---------------
Takes a list of seed points (black pucks + red pins) and computes
Voronoi cells clipped to the table rectangle.

Key feature: INTERPOLATED VERTICES
    Each Voronoi vertex is not snapped immediately to its computed position.
    Instead it glides from its old position toward the new one at LERP_SPEED
    per frame. This creates the organic, liquid-like animation seen in the
    Exploratorium exhibit.

Returns a list of cells, each being:
    {
        "polygon"  : [(x,y), ...] in projection pixel coords,
        "color"    : (R,G,B),
        "seed_idx" : int,           # which seed this cell belongs to
        "seed_type": "black"|"red", # puck type
    }
"""

import numpy as np
from scipy.spatial import Voronoi, cKDTree
import config

# Table bounding box in projection coords
TABLE_RECT = np.array([
    [0,           0          ],
    [config.PROJ_W, 0        ],
    [config.PROJ_W, config.PROJ_H],
    [0,           config.PROJ_H],
], dtype=np.float64)

# Mirror points outside the table to clip Voronoi to table bounds
# (standard technique -- add 4 far-away ghost points)
_GHOSTS = [
    (-config.PROJ_W * 3, config.PROJ_H / 2),
    (config.PROJ_W * 4,  config.PROJ_H / 2),
    (config.PROJ_W / 2,  -config.PROJ_H * 3),
    (config.PROJ_W / 2,  config.PROJ_H * 4),
]


def _lerp(a, b, t):
    return a + (b - a) * t


def _clip_polygon_to_rect(polygon, rect_w, rect_h):
    """Sutherland-Hodgman algorithm -- clips a polygon to the [0,0,W,H] rectangle."""
    def inside(p, edge):
        ex1, ey1, ex2, ey2 = edge
        return (ex2-ex1)*(p[1]-ey1) - (ey2-ey1)*(p[0]-ex1) >= 0

    def intersection(p1, p2, edge):
        ex1, ey1, ex2, ey2 = edge
        dx1, dy1 = p2[0]-p1[0], p2[1]-p1[1]
        dx2, dy2 = ex2-ex1, ey2-ey1
        denom = dx1*dy2 - dy1*dx2
        if abs(denom) < 1e-10:
            return p1
        t = ((ex1-p1[0])*dy2 - (ey1-p1[1])*dx2) / denom
        return (p1[0]+t*dx1, p1[1]+t*dy1)

    edges = [
        (0, 0, rect_w, 0),
        (rect_w, 0, rect_w, rect_h),
        (rect_w, rect_h, 0, rect_h),
        (0, rect_h, 0, 0),
    ]
    output = list(polygon)
    for edge in edges:
        if not output:
            return []
        inp = output
        output = []
        for i in range(len(inp)):
            curr = inp[i]
            prev = inp[i-1]
            if inside(curr, edge):
                if not inside(prev, edge):
                    output.append(intersection(prev, curr, edge))
                output.append(curr)
            elif inside(prev, edge):
                output.append(intersection(prev, curr, edge))
    return output


class VoronoiEngine:
    """
    Maintains the current Voronoi state with smooth vertex interpolation.
    Call update() every frame with new seed positions.
    """

    def __init__(self):
        # Positions of last frame's *interpolated* vertices (not scipy indices --
        # those are unstable across separate Voronoi() calls and cannot be used
        # as a persistent identity for a vertex). Matched spatially each frame.
        self._prev_vertex_pts  = np.empty((0, 2))
        self._prev_seeds       = []
        self._cells            = []   # last computed cells
        self._last_valid       = {}   # seed_idx -> last good cell dict (avoids flicker)

    def update(self, black_pucks, red_pins):
        """
        black_pucks: list of (nx, ny) normalized [0..1]
        red_pins:    list of (nx, ny) normalized [0..1]

        Returns list of cell dicts ready for rendering.
        """
        # Convert normalized coords -> projection pixel coords
        all_seeds      = []
        all_seed_types = []

        for nx, ny in black_pucks:
            all_seeds.append([nx * config.PROJ_W, ny * config.PROJ_H])
            all_seed_types.append("black")

        for nx, ny in red_pins:
            all_seeds.append([nx * config.PROJ_W, ny * config.PROJ_H])
            all_seed_types.append("red")

        if len(all_seeds) == 0:
            # No objects at all -- nothing to show but background.
            self._cells = []
            self._prev_vertex_pts = np.empty((0, 2))
            return self._cells

        if len(all_seeds) == 1:
            # Only one seed (either genuinely one object on the table, or
            # the other puck's track momentarily dropped out, e.g. while
            # being moved quickly). Voronoi needs >=2 points to divide
            # anything, so rather than flashing the whole table blank,
            # that single object owns the whole table -- matches the
            # physical reality (nothing else is claiming any space) and
            # avoids the jarring blank-screen flicker during fast moves.
            color = (config.BLACK_PUCK_CELL_COLOR if all_seed_types[0] == "black"
                     else config.RED_PIN_CELL_COLOR)
            cell = {
                "polygon":   [(0, 0), (config.PROJ_W, 0),
                              (config.PROJ_W, config.PROJ_H), (0, config.PROJ_H)],
                "color":     color,
                "seed_idx":  0,
                "seed_type": all_seed_types[0],
                "seed_px":   tuple(all_seeds[0]),
            }
            self._cells = [cell]
            self._prev_vertex_pts = np.empty((0, 2))
            self._last_valid = {0: cell}
            return self._cells

        # Add ghost points to bound the Voronoi
        seeds_with_ghosts = all_seeds + _GHOSTS
        n_real = len(all_seeds)

        try:
            vor = Voronoi(seeds_with_ghosts)
        except Exception:
            return self._cells

        # scipy assigns a fresh internal index to every vertex each time
        # Voronoi() is called -- that index is *not* a stable identity for
        # the same geometric vertex between frames (it depends on qhull's
        # internal ordering, which can shift even for a tiny point move).
        # So instead of trusting vertex index, we match each new vertex to
        # the closest vertex position from last frame's rendered output and
        # lerp from there. That's what actually makes the animation smooth,
        # and it's what was causing the white flicker before: mismatched
        # vertices were being lerped together, producing a warped/degenerate
        # polygon for a frame, which then fell back to a stale cached shape
        # that didn't line up with its neighbors -- leaving a gap that
        # showed the (near-white) background color through.
        prev_pts  = self._prev_vertex_pts
        prev_tree = cKDTree(prev_pts) if len(prev_pts) else None

        # Memoize per-frame so a vertex shared between adjacent cells is
        # resolved identically for both, keeping edges seamless.
        resolved = {}

        def resolve_vertex(vi):
            if vi in resolved:
                return resolved[vi]
            target = vor.vertices[vi]
            pos = (target[0], target[1])
            if prev_tree is not None:
                dist, idx = prev_tree.query(target)
                if dist <= config.VERTEX_MATCH_DIST:
                    old = prev_pts[idx]
                    pos = (
                        _lerp(old[0], target[0], config.LERP_SPEED),
                        _lerp(old[1], target[1], config.LERP_SPEED),
                    )
            resolved[vi] = pos
            return pos

        # Build cells from Voronoi regions
        cells = []
        for seed_idx in range(n_real):
            region_idx = vor.point_region[seed_idx]
            region     = vor.regions[region_idx]

            if not region or -1 in region:
                # Unbounded/degenerate this frame -- reuse last good shape for
                # this seed instead of skipping, so it never flashes blank.
                if seed_idx in self._last_valid:
                    cells.append(self._last_valid[seed_idx])
                continue

            poly_px = [resolve_vertex(vi) for vi in region]

            # Clip to table bounds
            clipped = _clip_polygon_to_rect(poly_px, config.PROJ_W, config.PROJ_H)
            if len(clipped) < 3:
                # Clipping collapsed the shape this frame -- reuse last good
                # shape rather than leaving a blank gap.
                if seed_idx in self._last_valid:
                    cells.append(self._last_valid[seed_idx])
                continue

            seed_type = all_seed_types[seed_idx]
            if seed_type == "black":
                color = config.BLACK_PUCK_CELL_COLOR
            else:
                # Each red pin gets its own distinct shade of pink/rose/salmon
                RED_SHADES = [
                    (235, 200, 195),   # soft pink
                    (225, 185, 185),   # dusty rose
                    (240, 210, 200),   # peach pink
                    (220, 175, 175),   # muted rose
                    (245, 205, 190),   # salmon pink
                    (230, 190, 195),   # mauve pink
                    (238, 200, 180),   # warm peach
                    (215, 180, 185),   # antique rose
                ]
                # Use the red pin's index within the red pins list
                red_idx = seed_idx - len([t for t in all_seed_types[:seed_idx] if t == "black"])
                color = RED_SHADES[red_idx % len(RED_SHADES)]

            cell = {
                "polygon":   clipped,
                "color":     color,
                "seed_idx":  seed_idx,
                "seed_type": seed_type,
                "seed_px":   tuple(all_seeds[seed_idx]),
            }
            cells.append(cell)
            self._last_valid[seed_idx] = cell

        # Drop cached shapes for seeds that no longer exist (puck removed)
        self._last_valid = {
            k: v for k, v in self._last_valid.items() if k < n_real
        }

        # Remember this frame's interpolated vertex positions so next frame
        # can match against them spatially.
        if resolved:
            self._prev_vertex_pts = np.array(list(resolved.values()))
        else:
            self._prev_vertex_pts = np.empty((0, 2))

        self._cells = cells
        return cells