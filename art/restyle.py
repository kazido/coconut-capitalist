"""Refresh the owner's own pixel art toward the shared look: richer colours, hue-shifted shadows, a plum outline and a white specular pixel.

The shape and the animation are untouched: every frame gets the same treatment, and the specular pixel is chosen once from frame 0 so it
does not jump around."""
import colorsys

from PIL import Image

from art.palette import outline_color


def _pixel(p, plum, sat=1.18, plum_mix=0.22):
    r, g, b, a = p
    h, s, v = colorsys.rgb_to_hsv(r / 255, g / 255, b / 255)
    s2 = min(1.0, s * sat + (0.04 if s > 0.1 else 0))
    if v < 0.45:  # shadows lean to violet with a touch of plum
        rgb = colorsys.hsv_to_rgb((h + 0.04) % 1.0, s2, v)
        out = [c * 255 * (1 - plum_mix) + t * plum_mix for c, t in zip(rgb, plum[:3], strict=True)]
    elif v > 0.8:  # lights go a little warmer and paler
        out = [c * 255 for c in colorsys.hsv_to_rgb((h - 0.015) % 1.0, s2 * 0.85, min(1.0, v * 1.04))]
    else:
        out = [c * 255 for c in colorsys.hsv_to_rgb(h, s2, min(1.0, v * 1.05))]
    return (round(out[0]), round(out[1]), round(out[2]), a)


def restyle_frames(frames: list[Image.Image], specular: bool = True) -> list[Image.Image]:
    plum = outline_color()
    n = frames[0].width
    spec = None
    if specular:
        f0 = frames[0]
        cands = [(x, y) for y in range(n) for x in range(n) if f0.getpixel((x, y))[3] and x + y < n + 1]
        if cands and not any(f0.getpixel(p)[:3] == (255, 255, 255) for p in cands):
            spec = max(cands, key=lambda q: (sum(f0.getpixel(q)[:3]), -(q[0] + q[1])))
    out = []
    for f in frames:
        im = Image.new("RGBA", f.size, (0, 0, 0, 0))
        for y in range(n):
            for x in range(n):
                p = f.getpixel((x, y))
                if p[3]:
                    im.putpixel((x, y), _pixel(p, plum))
        if spec and im.getpixel(spec)[3]:
            im.putpixel(spec, (255, 255, 255, 255))
        base = im.copy()
        for y in range(n):
            for x in range(n):
                if not base.getpixel((x, y))[3] and any(
                    0 <= x + dx < n and 0 <= y + dy < n and base.getpixel((x + dx, y + dy))[3] for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                ):
                    im.putpixel((x, y), plum)
        out.append(im)
    return out
