"""
DividingSpace — Main Exhibit Loop
===================================
Run this to start the exhibit:
    python main.py

HOW IT WORKS (end-to-end):
  1. Sensor (Kinect v2 / webcam / simulated) captures a camera frame
     looking down at the table.
  2. PuckDetector finds black pucks and red pins by color in that frame,
     maps them to normalized table coordinates [0..1].
  3. VoronoiEngine computes Voronoi cells from all seed positions and
     interpolates vertex positions smoothly toward the new geometry.
  4. SparkSystem checks if any black puck cell boundary is near a red pin
     and fires a burst of spark particles if so.
  5. Renderer draws: background → filled cells → glowing borders →
     puck dots → spark particles — onto a pygame surface.
  6. That surface is displayed fullscreen on the projector monitor.
  7. Repeat at 60 FPS.

CONTROLS (keyboard on any window):
    Q / ESC   quit
    D         toggle debug overlay (shows raw camera + detections)
    S         show/hide sensor debug window
    F         toggle FPS counter
    R         reset spark system
    SPACEBAR  save instant screen snapshot to file
"""

import sys, time, math
import pygame
import cv2
import numpy as np

sys.path.insert(0, ".")
import config
from sensors      import get_sensor
from detector     import PuckDetector, warp_frame_for_debug
from tracker      import PuckTracker
from voronoi_engine import VoronoiEngine
from sparks       import SparkSystem
from renderer     import draw_frame


def _get_monitor_pos(monitor_idx):
    """Return (x, y) top-left of the requested monitor for fullscreen placement."""
    try:
        from screeninfo import get_monitors
        monitors = get_monitors()
        if 0 <= monitor_idx < len(monitors):
            m = monitors[monitor_idx]
            return m.x, m.y, m.width, m.height
    except Exception as e:
        # screeninfo can fail for reasons other than being uninstalled
        # (no enumerator on this platform/session, no monitors detected,
        # running under a VM/headless test, etc). Any of these should
        # fall back to the hardcoded default below, not crash main().
        print(f"[WARN] screeninfo unavailable ({e}); using default monitor geometry.")
    if monitor_idx > 0:
        return 1920 * monitor_idx, 0, config.PROJ_W, config.PROJ_H
    return 0, 0, config.PROJ_W, config.PROJ_H


def main():
    # ── Init sensor FIRST, before opening any window ─────────────────────
    print("Opening camera...")
    sensor = get_sensor()
    sensor.start()

    # ── Init pygame ───────────────────────────────────────────────────────
    pygame.init()
    mx, my, mw, mh = _get_monitor_pos(config.PROJECTION_MONITOR)

    # Move window to projector monitor before setting fullscreen
    import os
    os.environ["SDL_VIDEO_WINDOW_POS"] = f"{mx},{my}"

    screen = pygame.display.set_mode(
        (config.PROJ_W, config.PROJ_H),
        pygame.FULLSCREEN | pygame.NOFRAME
    )
    pygame.display.set_caption("DividingSpace")
    clock = pygame.time.Clock()

    # ── Init remaining subsystems ────────────────────────────────────────
    detector = PuckDetector()
    tracker  = PuckTracker()
    voronoi  = VoronoiEngine()
    sparks   = SparkSystem()

    show_debug = False
    show_fps   = True
    font       = pygame.font.SysFont("Segoe UI", 28)

    print("=" * 60)
    print("DividingSpace — Running")
    print(f"Sensor  : {config.SENSOR_BACKEND}")
    print(f"Monitor : {config.PROJECTION_MONITOR}  ({config.PROJ_W}×{config.PROJ_H})")
    print("Controls: Q=quit  D=debug  F=fps  R=reset sparks  SPACE=screenshot")
    print("=" * 60)

    running     = True
    last_frame  = None
    frame_count = 0
    fps_display = 0
    fps_timer   = time.perf_counter()

    while running:
        # ── Events ───────────────────────────────────────────────────────
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key in (pygame.K_q, pygame.K_ESCAPE):
                    running = False
                elif event.key == pygame.K_d:
                    show_debug = not show_debug
                    print(f"[INFO] Debug overlay: {'ON' if show_debug else 'OFF'}")
                elif event.key == pygame.K_f:
                    show_fps = not show_fps
                elif event.key == pygame.K_r:
                    sparks = SparkSystem()
                    print("[INFO] Spark system reset.")
                
                # ── Screenshot hotkey: save a timestamped snapshot to Desktop ──
                elif event.key == pygame.K_SPACE:
                    import os
                    fname = f"dividingspace_snapshot_{time.strftime('%Y%m%d_%H%M%S')}.png"
                    desktop_path = os.path.join(os.path.expanduser("~"), "Desktop", fname)
                    pygame.image.save(screen, desktop_path)
                    print(f"[INFO] Snapshot saved to Desktop as '{fname}'")

        # ── Capture frame ─────────────────────────────────────────────────
        cam_frame = sensor.get_frame()
        if cam_frame is not None:
            last_frame = cam_frame

        if last_frame is None:
            screen.fill(config.BG_COLOR)
            txt = font.render("Waiting for camera…", True, (100, 100, 100))
            screen.blit(txt, (config.PROJ_W//2 - txt.get_width()//2,
                               config.PROJ_H//2))
            pygame.display.flip()
            clock.tick(config.TARGET_FPS)
            continue

        # ── Detect pucks (raw, per-frame) ───────────────────────────────────
        black_raw, red_raw = detector.detect(last_frame, debug=show_debug)

        # ── Track pucks (persistent identity, smoothing, missing-frame grace) ──
        black_tracked, red_tracked = tracker.update(black_raw, red_raw)
        black_norm = [t.pos for t in black_tracked]
        red_norm   = [t.pos for t in red_tracked]

        # Convert normalized [0..1] -> projection pixel coords
        black_px = [(nx * config.PROJ_W, ny * config.PROJ_H)
                    for nx, ny in black_norm]
        red_px   = [(nx * config.PROJ_W, ny * config.PROJ_H)
                    for nx, ny in red_norm]

        # ── Voronoi update ────────────────────────────────────────────────
        cells = voronoi.update(black_norm, red_norm)

        # ── Spark collision check ─────────────────────────────────────────
        sparks.check_collisions(black_px, red_px)

        # ── Render ────────────────────────────────────────────────────────
        draw_frame(screen, cells, black_px, red_px, sparks)

        # ── FPS counter ───────────────────────────────────────────────────
        frame_count += 1
        now = time.perf_counter()
        if now - fps_timer >= 1.0:
            fps_display = frame_count
            frame_count = 0
            fps_timer   = now

        if show_fps:
            fps_txt = font.render(f"{fps_display} fps", True, (80, 80, 80))
            screen.blit(fps_txt, (10, 10))

        # ── Debug overlay ─────────────────────────────────────────────────
        if show_debug and last_frame is not None:
            warped = warp_frame_for_debug(last_frame)   # 640x480, table-cropped
            dbg = cv2.resize(warped, (320, 240))
            dbg = cv2.cvtColor(dbg, cv2.COLOR_BGR2RGB)
            dbg_surf = pygame.surfarray.make_surface(dbg.transpose(1, 0, 2))
            screen.blit(dbg_surf, (config.PROJ_W - 330, 10))

            pygame.draw.rect(screen, (0, 200, 255),
                              (config.PROJ_W - 330, 10, 320, 240), 2)

            for nx, ny in black_norm:
                bx = int(nx * 320) + config.PROJ_W - 330
                by = int(ny * 240) + 10
                pygame.draw.circle(screen, config.PUCK_DOT_COLOR, (bx, by), 6)
            for nx, ny in red_norm:
                bx = int(nx * 320) + config.PROJ_W - 330
                by = int(ny * 240) + 10
                pygame.draw.circle(screen, config.PIN_DOT_COLOR, (bx, by), 6)

            dbg_info = font.render(
                f"Black pucks: {len(black_norm)}   Red pins: {len(red_norm)}",
                True, (200, 200, 200))
            screen.blit(dbg_info, (config.PROJ_W - 330, 260))

        pygame.display.flip()
        clock.tick(config.TARGET_FPS)

    # ── Cleanup ───────────────────────────────────────────────────────────
    sensor.stop()
    pygame.quit()
    print("[INFO] DividingSpace stopped.")


if __name__ == "__main__":
    main()