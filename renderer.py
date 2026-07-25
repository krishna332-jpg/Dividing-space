"""
Renderer
---------
Draws the Voronoi cells, borders, puck dots, and spark effects
onto a pygame surface for projection output.
"""

import pygame
import config


def draw_frame(surface, cells, black_pucks_px, red_pins_px, spark_system):
    """
    surface       : pygame.Surface (projection output)
    cells         : list of cell dicts from VoronoiEngine.update()
    black_pucks_px: list of (px, py) in projection pixel coords
    red_pins_px   : list of (px, py) in projection pixel coords
    spark_system  : SparkSystem instance
    """
    # Background
    surface.fill(config.BG_COLOR)

    # Draw filled cells
    for cell in cells:
        poly = [(int(x), int(y)) for x, y in cell["polygon"]]
        if len(poly) >= 3:
            pygame.draw.polygon(surface, cell["color"], poly)

    # Draw cell borders: white line with a thin black outline for contrast,
    # matching the reference photo.
    for cell in cells:
        poly = [(int(x), int(y)) for x, y in cell["polygon"]]
        if len(poly) >= 2:
            # Black outline (wider, drawn first / underneath)
            pygame.draw.polygon(surface, config.BORDER_OUTLINE_COLOR, poly,
                                config.BORDER_WIDTH + config.BORDER_OUTLINE_WIDTH)
            # White line (narrower, drawn on top)
            pygame.draw.polygon(surface, config.BORDER_COLOR, poly,
                                config.BORDER_WIDTH)

    # Draw black puck dots
    for px, py in black_pucks_px:
        ix, iy = int(px), int(py)
        # Outer glow ring
        pygame.draw.circle(surface, (150, 205, 245),
                           (ix, iy), config.PUCK_DOT_RADIUS + 6)
        # Main dot
        pygame.draw.circle(surface, config.PUCK_DOT_COLOR,
                           (ix, iy), config.PUCK_DOT_RADIUS)
        # White center
        pygame.draw.circle(surface, (240, 248, 255),
                           (ix, iy), config.PUCK_DOT_RADIUS // 2)

    # Draw red pin dots
    for px, py in red_pins_px:
        ix, iy = int(px), int(py)
        # Outer glow ring
        pygame.draw.circle(surface, (255, 175, 150),
                           (ix, iy), config.PIN_DOT_RADIUS + 5)
        # Main dot
        pygame.draw.circle(surface, config.PIN_DOT_COLOR,
                           (ix, iy), config.PIN_DOT_RADIUS)
        # White center
        pygame.draw.circle(surface, (255, 240, 240),
                           (ix, iy), config.PIN_DOT_RADIUS // 2)

    # Sparks on top of everything
    spark_system.update_and_draw(surface)
