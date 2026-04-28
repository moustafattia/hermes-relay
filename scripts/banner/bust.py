"""Marble bust loading + chroma-key against the museum backdrop."""
from __future__ import annotations

import math

from PIL import Image, ImageFilter, ImageOps

from . import config


def _resize_to_target(src: Image.Image) -> Image.Image:
    """Resize to height = BUST_TARGET_H, preserving aspect ratio."""
    ratio = config.BUST_TARGET_H / src.height
    return src.resize(
        (int(src.width * ratio), config.BUST_TARGET_H),
        Image.LANCZOS,
    )


def _key_photo(src: Image.Image) -> Image.Image:
    """Chroma-key by distance from the corner-sampled background colour.

    Tuned for the Plato photograph (saturated blue museum backdrop).
    """
    px = src.load()
    samples = []
    for sx, sy in [(5, 5), (src.width - 6, 5),
                   (5, src.height - 6), (src.width - 6, src.height - 6)]:
        r, g, b, _ = px[sx, sy]
        samples.append((r, g, b))
    bg_r = sum(s[0] for s in samples) // len(samples)
    bg_g = sum(s[1] for s in samples) // len(samples)
    bg_b = sum(s[2] for s in samples) // len(samples)

    near, far = 55, 95
    for y in range(src.height):
        for x in range(src.width):
            r, g, b, _ = px[x, y]
            d = math.sqrt(
                (r - bg_r) ** 2 + (g - bg_g) ** 2 + (b - bg_b) ** 2
            )
            if d <= near:
                a = 0
            elif d >= far:
                a = 255
            else:
                a = int((d - near) / (far - near) * 255)
            r2 = min(255, int(r * 1.02 + 4))
            g2 = min(255, int(g * 1.01 + 2))
            b2 = min(255, int(b * 0.97))
            px[x, y] = (r2, g2, b2, a)
    return src


def _key_engraving(src: Image.Image) -> Image.Image:
    """Drop the near-white background of a B/W line engraving.

    Uses inverted luminance as alpha, so paper becomes transparent and
    ink stays opaque. Then tints the dark pixels toward INK so the
    engraving sits on the parchment in editorial ink colour rather
    than pure black.
    """
    grey = src.convert("L")
    g_px = grey.load()
    px = src.load()

    near = 215   # paper threshold — anything brighter is fully transparent
    far = 100    # ink threshold  — anything darker than this is fully opaque

    ink_r, ink_g, ink_b = config.INK
    for y in range(src.height):
        for x in range(src.width):
            v = g_px[x, y]
            if v >= near:
                a = 0
            elif v <= far:
                a = 255
            else:
                a = int((near - v) / (near - far) * 255)
            # Tint toward INK: dark pixels → ink, light pixels → ink with
            # less alpha (so they fade into parchment naturally).
            t = 1 - (v / 255)            # 0..1 darkness factor
            r2 = int(ink_r + (255 - ink_r) * (1 - t) * 0.8)
            g2 = int(ink_g + (255 - ink_g) * (1 - t) * 0.8)
            b2 = int(ink_b + (255 - ink_b) * (1 - t) * 0.8)
            px[x, y] = (r2, g2, b2, a)
    return src


def prepare_bust() -> Image.Image:
    """Load, crop, chroma-key, and tone-blend the right-side hero image."""
    src = Image.open(config.BUST_SRC).convert("RGBA")
    w0, h0 = src.size

    # Crop borders. The Plato photo has unwanted edge content; engravings
    # often have plate marks around the perimeter — same crop helps both.
    src = src.crop((int(w0 * 0.03), int(h0 * 0.02),
                    int(w0 * 0.97), int(h0 * 0.92)))

    src = _resize_to_target(src)

    if config.BUST_BG_KIND == "engraving":
        keyed = _key_engraving(src)
    else:
        keyed = _key_photo(src)
        # Photo path: slight desaturation toward parchment-grey.
        rgb = keyed.convert("RGB")
        grey = ImageOps.grayscale(rgb).convert("RGB")
        blended = Image.blend(rgb, grey, 0.30)
        blended.putalpha(keyed.split()[3])
        keyed = blended

    # Soften the alpha edge so chroma-key cuts don't show.
    alpha = keyed.split()[3].filter(ImageFilter.GaussianBlur(radius=1.2))
    keyed.putalpha(alpha)
    return keyed


def placement(bust: Image.Image) -> dict:
    """Return placement coordinates derived from the bust size."""
    bust_x = config.W - bust.width - config.BUST_RIGHT_MARGIN
    bust_y = config.H - bust.height + 10
    return {
        "x": bust_x,
        "y": bust_y,
        "eye_y": bust_y + int(bust.height * 0.28),
        "eye_x1": bust_x + int(bust.width * 0.20),
        "eye_x2": bust_x + int(bust.width * 0.78),
    }
