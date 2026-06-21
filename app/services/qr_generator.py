"""QR code image generation service.

Generates clean, high-error-correction PNG images using the ``qrcode``
library and Pillow.  All heavy work happens in-memory (no temp files).

Usage:
    png_bytes = generate_qr_image("https://example.com/scan/abc123")
    # Optionally add a human-readable label beneath the code:
    png_bytes = generate_qr_image(
        "https://example.com/scan/abc123",
        label="Summer Campaign #42",
    )
"""

from __future__ import annotations

import io
from typing import Optional

import qrcode
from PIL import Image, ImageDraw, ImageFont
from qrcode.constants import ERROR_CORRECT_H
from qrcode.image.pil import PilImage


def generate_qr_image(
    data: str,
    size: int = 10,
    border: int = 2,
    label: Optional[str] = None,
) -> bytes:
    """Generate a QR code PNG and return it as raw bytes.

    Parameters
    ----------
    data:
        The string to encode (typically a URL).
    size:
        Box size in pixels for each QR module.  Larger values produce
        higher-resolution images.  Default ``10``.
    border:
        Width of the quiet zone (white border) in modules.  The QR spec
        recommends at least 4, but ``2`` is fine for on-screen use.
    label:
        Optional text rendered below the QR code.  Useful for printing
        so humans can identify the code without scanning.

    Returns
    -------
    bytes
        PNG-encoded image data.
    """
    # Build the QR matrix with the highest error-correction level so the
    # code remains scannable even if ~30 % of it is obscured.
    qr = qrcode.QRCode(
        version=None,  # auto-detect smallest version that fits
        error_correction=ERROR_CORRECT_H,
        box_size=size,
        border=border,
    )
    qr.add_data(data)
    qr.make(fit=True)

    # Render to a Pillow image (white background, black modules).
    qr_image: Image.Image = qr.make_image(
        image_factory=PilImage,
        fill_color="black",
        back_color="white",
    ).get_image()

    # If a label was requested, composite the QR image onto a taller
    # canvas that has room for text beneath the code.
    if label:
        qr_image = _add_label(qr_image, label, box_size=size)

    # Serialise to PNG bytes in memory.
    buf = io.BytesIO()
    qr_image.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _add_label(
    qr_img: Image.Image,
    text: str,
    box_size: int,
) -> Image.Image:
    """Return a new image with *text* rendered below *qr_img*.

    Uses Pillow's built-in default font (no external font files needed)
    scaled relative to the QR image width so the label looks proportional
    regardless of the chosen ``box_size``.
    """
    # Calculate label area height (roughly 1.5x the font size + padding).
    font_size = max(12, box_size * 2)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", font_size)
    except (OSError, IOError):
        # Fallback to Pillow's built-in bitmap font when DejaVu isn't
        # available (e.g. minimal Docker images).
        font = ImageFont.load_default()

    padding = font_size // 2
    label_height = font_size + padding * 2

    # Create a new canvas tall enough for QR + label.
    qr_w, qr_h = qr_img.size
    canvas = Image.new("RGB", (qr_w, qr_h + label_height), "white")
    canvas.paste(qr_img, (0, 0))

    # Draw the label text, centered horizontally.
    draw = ImageDraw.Draw(canvas)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_x = (qr_w - text_w) // 2
    text_y = qr_h + padding

    draw.text((text_x, text_y), text, fill="black", font=font)

    return canvas
