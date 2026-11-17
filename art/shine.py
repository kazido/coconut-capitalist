"""A gentle shine for the top rarities: a pale diagonal band sweeps across the sprite (never the cell), then it rests for a moment."""
from PIL import Image

HOLD_MS = 1800   # the still frame, so a list of these is calm
STEP_MS = 70
FRAMES = 10
WIDTH_BOOST = (0.55, 0.28)  # lerp to white at the band's centre / its edge pixels


def shine_frames(frame: Image.Image) -> tuple[list[Image.Image], list[int]]:
    n = frame.width
    out = [frame.copy()]
    for k in range(FRAMES):
        centre = k * ((2 * n) / FRAMES) - 2
        im = frame.copy()
        for y in range(n):
            for x in range(n):
                p = frame.getpixel((x, y))
                d = abs((x + y) - centre)
                if p[3] and d <= 1:
                    t = WIDTH_BOOST[0] if d < 0.5 else WIDTH_BOOST[1]
                    im.putpixel((x, y), tuple(round(c + (255 - c) * t) for c in p[:3]) + (p[3],))
        out.append(im)
    return out, [HOLD_MS] + [STEP_MS] * FRAMES
