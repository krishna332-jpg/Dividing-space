"""
Spark Animation System
-----------------------
When a black puck gets close to (touches) a red pin,
a burst of spark particles is emitted at that contact point.

Sparks are rendered as short glowing lines that fade out over their lifetime.
"""

import math, random, time
import pygame
import config


class Spark:
    def __init__(self, x, y):
        angle    = random.uniform(0, 2 * math.pi)
        speed    = random.uniform(config.SPARK_SPEED * 0.4, config.SPARK_SPEED)
        self.x   = float(x)
        self.y   = float(y)
        self.vx  = math.cos(angle) * speed
        self.vy  = math.sin(angle) * speed
        self.born = time.perf_counter()
        self.life = config.SPARK_LIFETIME * random.uniform(0.6, 1.0)

    def alive(self):
        return (time.perf_counter() - self.born) < self.life

    def update(self, dt):
        self.x += self.vx * dt
        self.y += self.vy * dt
        # Gravity + drag
        self.vy += 200 * dt
        self.vx *= (1 - 2.5 * dt)
        self.vy *= (1 - 2.5 * dt)

    def draw(self, surface):
        t   = (time.perf_counter() - self.born) / self.life
        r1, g1, b1 = config.SPARK_COLOR_START
        r2, g2, b2 = config.SPARK_COLOR_END
        r   = int(r1 + (r2-r1)*t)
        g   = int(g1 + (g2-g1)*t)
        b   = int(b1 + (b2-b1)*t)
        a   = int(255 * (1 - t))
        spd = math.hypot(self.vx, self.vy)
        if spd < 1:
            return
        tail_len = min(spd * 0.05, 20)
        nx  = self.vx / spd
        ny  = self.vy / spd
        x1  = int(self.x - nx * tail_len)
        y1  = int(self.y - ny * tail_len)
        x2  = int(self.x)
        y2  = int(self.y)
        try:
            pygame.draw.line(surface, (r, g, b), (x1, y1), (x2, y2),
                             config.SPARK_WIDTH)
        except Exception:
            pass


class SparkSystem:
    def __init__(self):
        self._sparks   = []
        self._last_t   = time.perf_counter()
        self._triggered = set()   # set of red_pin indices we've already sparked

    def check_collisions(self, black_pucks_px, red_pins_px):
        """
        black_pucks_px : list of (px, py) in projection pixel coords
        red_pins_px    : list of (px, py) in projection pixel coords

        Triggers a spark when a black puck's actual position comes within
        config.SPARK_TOUCH_DIST of a red pin's actual position -- i.e. when
        the physical objects are touching/close, not when a Voronoi
        boundary line happens to pass nearby.
        """
        triggered_now = set()
        for pi, (rx, ry) in enumerate(red_pins_px):
            for bx, by in black_pucks_px:
                d = math.hypot(bx - rx, by - ry)
                if d < config.SPARK_TOUCH_DIST:
                    triggered_now.add(pi)
                    if pi not in self._triggered:
                        # Emit the spark at the point on the pin's edge
                        # facing the puck -- "the side the black touches".
                        if d > 1e-6:
                            nx, ny = (bx - rx) / d, (by - ry) / d
                        else:
                            nx, ny = 1.0, 0.0
                        ex = rx + nx * config.PIN_DOT_RADIUS
                        ey = ry + ny * config.PIN_DOT_RADIUS
                        self._emit(ex, ey)

        self._triggered = triggered_now

    def _emit(self, x, y):
        for _ in range(config.SPARK_COUNT):
            self._sparks.append(Spark(x, y))

    def update_and_draw(self, surface):
        now = time.perf_counter()
        dt  = now - self._last_t
        self._last_t = now
        dt  = min(dt, 0.05)   # cap at 50ms to avoid big jumps

        self._sparks = [s for s in self._sparks if s.alive()]
        for s in self._sparks:
            s.update(dt)
            s.draw(surface)