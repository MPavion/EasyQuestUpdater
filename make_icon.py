"""Generate icon.ico for EasyQuestUpdater — supersampled for smooth edges."""
from PIL import Image, ImageDraw

# Palette
BG_TOP  = (18, 24, 52, 255)    # top of background gradient
BG_BOT  = (8,  12, 32, 255)    # bottom of background gradient
VISOR   = (235, 242, 255, 255) # headset body — near-white with blue tint
LENS    = (10,  16, 38, 255)   # lens cutout — matches bg
STRAP   = (70, 100, 148, 255)  # side connectors — slate blue
CYAN    = (0,  200, 255, 255)  # download arrow
TRANSP  = (0, 0, 0, 0)

SCALE = 4   # supersampling — draw at 4x then downscale with LANCZOS


def _lerp(a, b, t):
    return tuple(int(a[i] + t * (b[i] - a[i])) for i in range(4))


def make_frame(size: int) -> Image.Image:
    s    = size * SCALE
    img  = Image.new("RGBA", (s, s), TRANSP)
    draw = ImageDraw.Draw(img)

    pad = max(SCALE, s // 16)
    r   = max(SCALE * 2, s // 5)

    # ── Gradient background ───────────────────────────────────────────────
    for y in range(s):
        t = y / s
        draw.line([(0, y), (s - 1, y)], fill=_lerp(BG_TOP, BG_BOT, t))

    # Mask gradient to rounded square
    mask = Image.new("L", (s, s), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [pad, pad, s - pad - 1, s - pad - 1], radius=r, fill=255
    )
    result = Image.new("RGBA", (s, s), TRANSP)
    result.paste(img, mask=mask)
    img  = result
    draw = ImageDraw.Draw(img)

    cx = s // 2
    cy = int(s * 0.42)

    # ── Headset visor body ────────────────────────────────────────────────
    vw  = int(s * 0.68)
    vh  = int(s * 0.30)
    vx0 = cx - vw // 2
    vx1 = cx + vw // 2
    vy0 = cy - vh // 2
    vy1 = cy + vh // 2
    draw.rounded_rectangle([vx0, vy0, vx1, vy1],
                           radius=max(SCALE, vh // 2), fill=VISOR)

    # ── Side strap connectors ─────────────────────────────────────────────
    sh  = max(SCALE, int(s * 0.065))
    sl  = max(SCALE * 2, int(s * 0.065))
    for x0, x1 in [(vx0 - sl, vx0), (vx1, vx1 + sl)]:
        if x0 >= pad and x1 <= s - pad:
            draw.rounded_rectangle(
                [x0, cy - sh // 2, x1, cy + sh // 2],
                radius=max(1, sh // 2), fill=STRAP,
            )

    # ── Lens cutouts ──────────────────────────────────────────────────────
    lp  = max(SCALE, int(s * 0.052))
    gap = max(SCALE, int(s * 0.036))
    ly0 = vy0 + lp
    ly1 = vy1 - lp
    lh  = ly1 - ly0
    lw  = (vw - 2 * lp - 2 * gap) // 2

    if lw > SCALE * 2 and lh > SCALE * 2:
        lr = max(SCALE, lh // 4)
        draw.rounded_rectangle([vx0 + lp,      ly0, vx0 + lp + lw, ly1],
                               radius=lr, fill=LENS)
        draw.rounded_rectangle([vx1 - lp - lw, ly0, vx1 - lp,      ly1],
                               radius=lr, fill=LENS)

    # ── Download arrow ────────────────────────────────────────────────────
    atop = vy1 + max(SCALE * 2, int(s * 0.06))
    amid = vy1 + max(SCALE * 3, int(s * 0.14))
    abot = vy1 + max(SCALE * 5, int(s * 0.22))
    aw   = max(SCALE * 3, int(s * 0.13))
    sw   = max(SCALE,     int(s * 0.048))

    if abot <= s - pad:
        draw.rectangle([cx - sw, atop, cx + sw, amid], fill=CYAN)
        draw.polygon([(cx, abot), (cx - aw, amid), (cx + aw, amid)], fill=CYAN)

    return img.resize((size, size), Image.LANCZOS)


sizes  = [16, 24, 32, 48, 64, 128, 256]
frames = [make_frame(s) for s in sizes]

out = r"c:\Users\micro\Documents\GitHub\Quest Updater\icon.ico"
frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes],
               append_images=frames[1:])
print(f"Saved {out}")
