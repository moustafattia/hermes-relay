#!/usr/bin/env python3
"""Generate the animated banner GIF for the README.

Theme: a thread (Theseus's clew) being drawn through the Labyrinth — nodes
light up as the thread visits them, then the DAEDALUS wordmark fades in.
Palette matches the wordmark SVG (#0B0F14 / #22D3EE).

Re-run with::

    /usr/bin/python3 scripts/build_banner_gif.py

Writes assets/daedalus-banner.gif.
"""
from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageFilter

OUT_PATH = Path(__file__).resolve().parents[1] / "assets" / "daedalus-banner.gif"

W, H = 1000, 300
BG = (11, 15, 20)            # #0B0F14
PANEL = (17, 22, 29)          # #11161D
CYAN = (34, 211, 238)         # #22D3EE
CYAN_DIM = (34, 211, 238, 70)
CYAN_GHOST = (34, 211, 238, 28)
WHITE = (235, 245, 250)
SUBTLE = (90, 110, 125)

# Labyrinth node coordinates — picked so the thread traces a maze-like path.
NODES = [
    (110, 215),   # 0 entry
    (110, 110),   # 1
    (210, 110),   # 2
    (210, 195),   # 3
    (310, 195),   # 4
    (310, 95),    # 5
    (410, 95),    # 6
    (410, 215),   # 7
    (510, 215),   # 8
    (510, 110),   # 9 — center pivot
]
LABEL_NODES = {
    0: "shadow",
    3: "preflight",
    5: "dispatch",
    7: "review",
    9: "merge",
}

FRAMES = 42          # ~2.5s @ ~17fps
DURATION_MS = 60      # ~17 fps


def ease(t: float) -> float:
    """Smooth in-out easing on [0, 1]."""
    return 0.5 - 0.5 * math.cos(math.pi * max(0.0, min(1.0, t)))


def load_font(size: int) -> ImageFont.ImageFont:
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        "/usr/share/fonts/TTF/DejaVuSans-Bold.ttf",
    ]
    for c in candidates:
        if Path(c).exists():
            return ImageFont.truetype(c, size)
    return ImageFont.load_default()


FONT_TITLE = load_font(60)
FONT_SUB = load_font(18)
FONT_TAG = load_font(14)


def draw_grid(d: ImageDraw.ImageDraw) -> None:
    """Faint dot grid suggesting the labyrinth floor."""
    for y in range(40, H - 30, 28):
        for x in range(40, W - 30, 28):
            d.point((x, y), fill=(28, 36, 46))


def draw_panel_chrome(im: Image.Image) -> None:
    """Outer rounded border like the wordmark SVG."""
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((12, 12, W - 12, H - 12), radius=24,
                        outline=(22, 29, 38), width=4)
    d.rounded_rectangle((24, 24, W - 24, H - 24), radius=18,
                        outline=(17, 22, 29), width=2)


def thread_progress(frame: int) -> float:
    """Return 0..1 progress along the polyline for this frame."""
    # First 70% of frames draw the thread; last 30% hold + reveal text.
    return ease(min(1.0, frame / (FRAMES * 0.55)))


def text_progress(frame: int) -> float:
    """Wordmark/subtitle fade-in progress on [0, 1]."""
    start = FRAMES * 0.35
    end = FRAMES * 0.85
    if frame < start:
        return 0.0
    if frame > end:
        return 1.0
    return ease((frame - start) / (end - start))


def polyline_length(pts: list[tuple[int, int]]) -> float:
    total = 0.0
    for a, b in zip(pts, pts[1:]):
        total += math.hypot(b[0] - a[0], b[1] - a[1])
    return total


def point_on_polyline(pts: list[tuple[int, int]], dist: float) -> tuple[float, float]:
    """Return (x, y) at arc-length `dist` along the polyline."""
    travelled = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if travelled + seg >= dist:
            t = (dist - travelled) / seg if seg > 0 else 0
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
        travelled += seg
    return pts[-1]


def visible_polyline(pts: list[tuple[int, int]], total_len: float, progress: float):
    """Slice of the polyline that's currently drawn."""
    target = total_len * progress
    out = [pts[0]]
    travelled = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        if travelled + seg <= target:
            out.append(b)
            travelled += seg
        else:
            t = (target - travelled) / seg if seg > 0 else 0
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
            break
    return out


def render_frame(frame: int) -> Image.Image:
    im = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(im, "RGBA")

    draw_grid(d)
    draw_panel_chrome(im)

    # Subtle wing arc behind everything — Daedalus's wings, distant.
    wing_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    wd = ImageDraw.Draw(wing_layer)
    for i, alpha in enumerate((22, 14, 8)):
        wd.arc(
            (-160 + i * 30, 60 + i * 20, 380 + i * 30, 480 + i * 20),
            start=300, end=60, fill=(34, 211, 238, alpha), width=3,
        )
        wd.arc(
            (820 - i * 30, 60 + i * 20, 1360 - i * 30, 480 + i * 20),
            start=120, end=240, fill=(34, 211, 238, alpha), width=3,
        )
    wing_layer = wing_layer.filter(ImageFilter.GaussianBlur(radius=2))
    im.paste(wing_layer, (0, 0), wing_layer)
    d = ImageDraw.Draw(im, "RGBA")

    total = polyline_length(NODES)
    p = thread_progress(frame)
    visible = visible_polyline(NODES, total, p)

    # Ghost full path — always visible, very faint.
    d.line(NODES, fill=CYAN_GHOST, width=2, joint="curve")

    # The drawn thread (Theseus's clew) — bold cyan.
    if len(visible) >= 2:
        # Glow halo
        glow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gd.line(visible, fill=(34, 211, 238, 90), width=10, joint="curve")
        glow = glow.filter(ImageFilter.GaussianBlur(radius=4))
        im.paste(glow, (0, 0), glow)
        d = ImageDraw.Draw(im, "RGBA")
        d.line(visible, fill=CYAN, width=4, joint="curve")

    # Nodes — dim until the thread reaches them.
    travelled_target = total * p
    cumulative = 0.0
    reached = [False] * len(NODES)
    reached[0] = True
    for idx, (a, b) in enumerate(zip(NODES, NODES[1:])):
        seg = math.hypot(b[0] - a[0], b[1] - a[1])
        cumulative += seg
        if cumulative <= travelled_target + 4:
            reached[idx + 1] = True

    for i, (x, y) in enumerate(NODES):
        if reached[i]:
            # Lit node — solid + halo.
            d.ellipse((x - 14, y - 14, x + 14, y + 14),
                      fill=(34, 211, 238, 60))
            d.ellipse((x - 7, y - 7, x + 7, y + 7), fill=CYAN)
            label = LABEL_NODES.get(i)
            if label:
                d.text((x - 28, y + 14), label, font=FONT_TAG, fill=(150, 200, 215))
        else:
            d.ellipse((x - 6, y - 6, x + 6, y + 6),
                      outline=(34, 211, 238, 80), width=2)

    # Comet head at the tip of the thread.
    if 0 < p < 1:
        hx, hy = point_on_polyline(NODES, total * p)
        head_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        hd = ImageDraw.Draw(head_layer)
        hd.ellipse((hx - 16, hy - 16, hx + 16, hy + 16), fill=(34, 211, 238, 130))
        head_layer = head_layer.filter(ImageFilter.GaussianBlur(radius=3))
        im.paste(head_layer, (0, 0), head_layer)
        d = ImageDraw.Draw(im, "RGBA")
        d.ellipse((hx - 5, hy - 5, hx + 5, hy + 5), fill=(245, 252, 255))

    # Wordmark + subtitle on the right side.
    tp = text_progress(frame)
    if tp > 0:
        alpha = int(255 * tp)
        title_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
        td = ImageDraw.Draw(title_layer)
        td.text((620, 90), "DAEDALUS", font=FONT_TITLE,
                fill=(34, 211, 238, alpha))
        ux2 = 620 + int(300 * tp)
        td.line((620, 165, ux2, 165), fill=(34, 211, 238, alpha), width=3)
        td.text((620, 178), "the durable thread for agent workflows",
                font=FONT_SUB, fill=(180, 210, 220, alpha))
        td.text((620, 208), "leases · hot-reload · stalls · shadow → active",
                font=FONT_TAG, fill=(110, 145, 160, alpha))
        im.paste(title_layer, (0, 0), title_layer)

    return im


def main() -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    frames = [render_frame(i) for i in range(FRAMES)]
    # Quantize to a small palette so the GIF stays small.
    quantized = [
        f.convert("P", palette=Image.Palette.ADAPTIVE, colors=32, dither=Image.Dither.NONE)
        for f in frames
    ]
    quantized[0].save(
        OUT_PATH,
        save_all=True,
        append_images=quantized[1:],
        duration=DURATION_MS,
        loop=0,
        optimize=True,
        disposal=2,
    )
    size_kb = OUT_PATH.stat().st_size / 1024
    print(f"wrote {OUT_PATH} ({size_kb:.1f} KiB, {len(frames)} frames)")


if __name__ == "__main__":
    main()
