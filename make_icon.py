"""Generate icon.ico for EasyQuestUpdater – VR headset design."""
import io
import struct
from PIL import Image, ImageDraw

TRANSP   = (0,   0,   0,   0)
BG       = (13,  18,  38,  255)   # #0d1226  dark navy
WHITE    = (255, 255, 255, 255)
LENS_COL = (13,  18,  38,  255)   # same as BG – dark cutout
STRAP    = (80,  110, 150, 255)   # #506e96  blue-gray
CYAN     = (0,   195, 255, 255)   # #00c3ff


def make_frame(size: int) -> Image.Image:
    img  = Image.new("RGBA", (size, size), TRANSP)
    draw = ImageDraw.Draw(img)

    # ── background rounded square ─────────────────────────────────────────
    pad = max(1, size // 16)
    r   = max(2, size // 6)
    draw.rounded_rectangle(
        [pad, pad, size - pad - 1, size - pad - 1],
        radius=r, fill=BG,
    )

    cx = size // 2
    cy = size // 2

    # ── visor (white pill) ────────────────────────────────────────────────
    # wide pill sitting slightly above centre
    visor_w  = max(6, int(size * 0.70))
    visor_h  = max(3, int(size * 0.28))
    visor_y0 = cy - visor_h - max(1, size // 16)   # top edge (above centre)
    visor_y1 = visor_y0 + visor_h
    visor_x0 = cx - visor_w // 2
    visor_x1 = visor_x0 + visor_w
    visor_r  = max(1, visor_h // 2)                 # pill shape
    draw.rounded_rectangle(
        [visor_x0, visor_y0, visor_x1, visor_y1],
        radius=visor_r, fill=WHITE,
    )

    # ── lens cutouts (two dark rounded rectangles inside the visor) ───────
    lens_margin_v = max(1, int(visor_h * 0.20))
    lens_margin_h = max(1, int(visor_w * 0.06))
    gap           = max(2, int(visor_w * 0.08))     # gap between the two lenses

    lh = visor_h - 2 * lens_margin_v
    lw = (visor_w - 2 * lens_margin_h - gap) // 2

    if lw > 2 and lh > 2:
        lr = max(1, min(lw, lh) // 4)
        # left lens
        ll_x0 = visor_x0 + lens_margin_h
        ll_x1 = ll_x0 + lw
        ll_y0 = visor_y0 + lens_margin_v
        ll_y1 = ll_y0 + lh
        draw.rounded_rectangle([ll_x0, ll_y0, ll_x1, ll_y1], radius=lr, fill=LENS_COL)
        # right lens
        rl_x0 = ll_x1 + gap
        rl_x1 = rl_x0 + lw
        draw.rounded_rectangle([rl_x0, ll_y0, rl_x1, ll_y1], radius=lr, fill=LENS_COL)

    # ── side strap connectors (short blue-gray bars from each side) ───────
    strap_w  = max(1, int(size * 0.07))
    strap_h  = max(1, int(visor_h * 0.45))
    strap_y0 = visor_y0 + (visor_h - strap_h) // 2
    strap_y1 = strap_y0 + strap_h
    strap_r  = max(1, strap_w // 3)

    # left strap
    ls_x1 = visor_x0 - 1
    ls_x0 = ls_x1 - strap_w
    if ls_x0 >= pad:
        draw.rounded_rectangle([ls_x0, strap_y0, ls_x1, strap_y1], radius=strap_r, fill=STRAP)

    # right strap
    rs_x0 = visor_x1 + 1
    rs_x1 = rs_x0 + strap_w
    if rs_x1 <= size - pad - 1:
        draw.rounded_rectangle([rs_x0, strap_y0, rs_x1, strap_y1], radius=strap_r, fill=STRAP)

    # ── cyan downward arrow below the visor ──────────────────────────────
    arrow_gap    = max(1, size // 20)           # gap between visor bottom and arrow top
    stem_w       = max(1, int(size * 0.09))
    stem_y0      = visor_y1 + arrow_gap
    stem_h       = max(1, int(size * 0.13))
    stem_y1      = stem_y0 + stem_h

    head_w       = max(3, int(size * 0.26))
    head_h       = max(2, int(size * 0.11))
    head_y0      = stem_y1
    head_y1      = head_y0 + head_h

    # only draw if everything fits inside the background
    if head_y1 < size - pad:
        # stem
        draw.rectangle(
            [cx - stem_w // 2, stem_y0, cx + stem_w // 2, stem_y1],
            fill=CYAN,
        )
        # arrowhead (pointing down)
        draw.polygon(
            [
                (cx,                head_y1),   # tip
                (cx - head_w // 2,  head_y0),   # top-left
                (cx + head_w // 2,  head_y0),   # top-right
            ],
            fill=CYAN,
        )

    return img


def save_ico(path: str, frames: list) -> None:
    """Write a proper multi-size ICO file from a list of RGBA PIL Images."""
    # Encode each frame as raw 32-bit RGBA BMP (BITMAPINFOHEADER + pixels)
    raw_images = []
    for img in frames:
        w, h = img.size
        buf = io.BytesIO()
        # BITMAPINFOHEADER (40 bytes)
        pixels = img.tobytes("raw", "BGRA")
        info_size     = 40
        bpp           = 32
        planes        = 1
        compression   = 0  # BI_RGB
        size_image    = len(pixels)
        x_pels        = 0
        y_pels        = 0
        clr_used      = 0
        clr_important = 0
        buf.write(struct.pack('<IiiHHIIiiII',
            info_size, w, -h,       # negative height = top-down
            planes, bpp, compression, size_image,
            x_pels, y_pels, clr_used, clr_important,
        ))
        buf.write(pixels)
        raw_images.append(buf.getvalue())

    n = len(frames)
    # ICO header: 6 bytes
    # Directory entries: 16 bytes each
    # Image data follows
    header_size = 6 + 16 * n
    offsets = []
    offset = header_size
    for data in raw_images:
        offsets.append(offset)
        offset += len(data)

    with open(path, 'wb') as f:
        # ICO header
        f.write(struct.pack('<HHH', 0, 1, n))
        # Directory entries
        for i, img in enumerate(frames):
            w, h = img.size
            wbyte = 0 if w == 256 else w
            hbyte = 0 if h == 256 else h
            data_size = len(raw_images[i])
            f.write(struct.pack('<BBBBHHII',
                wbyte, hbyte,
                0,      # color count (0 = no palette)
                0,      # reserved
                1,      # planes
                32,     # bpp
                data_size,
                offsets[i],
            ))
        # Image data
        for data in raw_images:
            f.write(data)


sizes  = [16, 24, 32, 48, 64, 128, 256]
frames = [make_frame(s) for s in sizes]

out = r"c:\Users\micro\Documents\GitHub\Quest Updater\icon.ico"
save_ico(out, frames)
print(f"Saved {out}")
