import os
import re
import unicodedata
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from pypdf import PdfReader
from reportlab.lib.colors import Color, HexColor, white
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas


BASE_DIR = Path(__file__).resolve().parent
GENERATED_DIR = BASE_DIR / "generated"

NAVY = HexColor("#08265A")
ORANGE = HexColor("#FF6A00")
TEAL = HexColor("#078C91")
LIGHT = HexColor("#F7F4ED")
PALE_ORANGE = HexColor("#FFF0E3")
PALE_TEAL = HexColor("#E5F6F4")
MID_GREY = HexColor("#7A8797")
LINE_GREY = HexColor("#B7C0C8")
CREAM = HexColor("#FFF9EE")
SOFT_NAVY = HexColor("#E9EEF4")

FONT_REGULAR = "FoxArial"
FONT_BOLD = "FoxArialBold"
_FONTS_READY = False


def register_pdf_fonts() -> None:
    global _FONTS_READY
    if _FONTS_READY:
        return
    candidates = [
        (
            Path("C:/Windows/Fonts/arial.ttf"),
            Path("C:/Windows/Fonts/arialbd.ttf"),
        ),
        (
            BASE_DIR / "assets" / "fonts" / "DejaVuSans.ttf",
            BASE_DIR / "assets" / "fonts" / "DejaVuSans-Bold.ttf",
        ),
    ]
    for regular, bold in candidates:
        if regular.is_file() and bold.is_file():
            pdfmetrics.registerFont(TTFont(FONT_REGULAR, str(regular)))
            pdfmetrics.registerFont(TTFont(FONT_BOLD, str(bold)))
            _FONTS_READY = True
            return
    raise FileNotFoundError("No bundled or system TrueType font with Cyrillic support")


def pdf_safe_text(value: Any) -> str:
    text = str(value or "")
    text = text.replace("—", "-").replace("–", "-").replace("‑", "-")
    text = text.replace("“", '"').replace("”", '"').replace("’", "'")
    text = text.replace("▶", "")
    text = text.replace("\ufe0f", "").replace("\u200d", "")
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", text)
    return " ".join(text.split()).strip()


def sanitize_filename_component(value: Any, fallback: str = "Game") -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = re.sub(r"[<>:\"/\\|?*\x00-\x1f]", " ", text)
    text = re.sub(r"\s+", "_", text).strip(" ._")
    text = re.sub(r"_+", "_", text)
    return (text[:70].rstrip(" ._") or fallback)


def unique_pdf_path(title: str, level: str, output_dir: Path | None = None) -> Path:
    target_dir = output_dir or GENERATED_DIR
    target_dir.mkdir(parents=True, exist_ok=True)
    base = f"FoxGameLab_{sanitize_filename_component(title)}_{sanitize_filename_component(level, 'Level')}"
    path = target_dir / f"{base}.pdf"
    if path.exists():
        suffix = datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + uuid4().hex[:4]
        path = target_dir / f"{base}_{suffix}.pdf"
    return path


def wrap_text(text: str, font_name: str, font_size: float, max_width: float) -> list[str]:
    text = pdf_safe_text(text)
    if not text:
        return [""]
    words = text.split()
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
            continue
        if current:
            lines.append(current)
        current = word
        while pdfmetrics.stringWidth(current, font_name, font_size) > max_width and len(current) > 1:
            split_at = max(1, int(len(current) * max_width / pdfmetrics.stringWidth(current, font_name, font_size)))
            lines.append(current[:split_at])
            current = current[split_at:]
    if current:
        lines.append(current)
    return lines


def draw_lines(
    pdf: canvas.Canvas,
    lines: list[str],
    x: float,
    y: float,
    width: float,
    font_name: str = FONT_REGULAR,
    font_size: float = 10,
    leading: float = 13,
    color: Color = NAVY,
) -> float:
    pdf.setFillColor(color)
    pdf.setFont(font_name, font_size)
    for raw_line in lines:
        if raw_line.strip().startswith(("☐", "□")):
            box_size = 8
            pdf.setStrokeColor(NAVY)
            pdf.rect(x, y - 1, box_size, box_size, stroke=1, fill=0)
            raw_line = raw_line.strip()[1:].strip()
            line_x = x + box_size + 6
            line_width = width - box_size - 6
        else:
            line_x = x
            line_width = width
        wrapped = wrap_text(raw_line, font_name, font_size, line_width)
        for line in wrapped:
            if line and set(line) == {"_"}:
                pdf.setStrokeColor(LINE_GREY)
                pdf.line(line_x, y + 2, line_x + min(line_width, 180), y + 2)
            else:
                pdf.drawString(line_x, y, line)
            y -= leading
    return y


def draw_page_background(pdf: canvas.Canvas) -> None:
    page_width, page_height = A4
    pdf.setFillColor(white)
    pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.8)
    pdf.roundRect(11, 10, page_width - 22, page_height - 20, 15, stroke=1, fill=0)
    pdf.setFillColor(ORANGE)
    pdf.circle(page_width + 3, page_height + 1, 48, stroke=0, fill=1)
    pdf.setFillColor(TEAL)
    pdf.circle(-7, -4, 39, stroke=0, fill=1)
    for row in range(4):
        for col in range(5):
            pdf.setFillColor(ORANGE)
            pdf.circle(29 + col * 14, page_height - 27 - row * 14, 1.7, stroke=0, fill=1)
            pdf.setFillColor(NAVY)
            pdf.circle(page_width - 31 - col * 12, 28 + row * 12, 1.5, stroke=0, fill=1)


def draw_fox_mascot(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    scale: float = 1.0,
    detective: bool = False,
) -> None:
    """Draw a tiny vector fox accent; x/y is the centre of the face."""
    pdf.saveState()
    ear = 11 * scale
    face = 13 * scale
    pdf.setFillColor(ORANGE)
    left_ear = pdf.beginPath()
    left_ear.moveTo(x - 10 * scale, y + 7 * scale)
    left_ear.lineTo(x - 13 * scale, y + 20 * scale)
    left_ear.lineTo(x - 2 * scale, y + 12 * scale)
    left_ear.close()
    pdf.drawPath(left_ear, stroke=0, fill=1)
    right_ear = pdf.beginPath()
    right_ear.moveTo(x + 10 * scale, y + 7 * scale)
    right_ear.lineTo(x + 13 * scale, y + 20 * scale)
    right_ear.lineTo(x + 2 * scale, y + 12 * scale)
    right_ear.close()
    pdf.drawPath(right_ear, stroke=0, fill=1)
    pdf.circle(x, y + 3 * scale, face, stroke=0, fill=1)
    pdf.setFillColor(CREAM)
    pdf.circle(x - 5 * scale, y + 1 * scale, 7 * scale, stroke=0, fill=1)
    pdf.circle(x + 5 * scale, y + 1 * scale, 7 * scale, stroke=0, fill=1)
    pdf.setFillColor(NAVY)
    pdf.circle(x - 4.5 * scale, y + 5 * scale, 1.1 * scale, stroke=0, fill=1)
    pdf.circle(x + 4.5 * scale, y + 5 * scale, 1.1 * scale, stroke=0, fill=1)
    pdf.circle(x, y - 3 * scale, 1.6 * scale, stroke=0, fill=1)
    if detective:
        pdf.setFillColor(NAVY)
        pdf.roundRect(x - 12 * scale, y + 13 * scale, 24 * scale, 4 * scale, 2 * scale, stroke=0, fill=1)
        pdf.wedge(x - 9 * scale, y + 12 * scale, x + 9 * scale, y + 25 * scale, 0, 180, stroke=0, fill=1)
        pdf.setStrokeColor(TEAL)
        pdf.setLineWidth(1.5 * scale)
        pdf.circle(x + 12 * scale, y - 2 * scale, 5 * scale, stroke=1, fill=0)
        pdf.line(x + 15.5 * scale, y - 6 * scale, x + 20 * scale, y - 11 * scale)
    pdf.restoreState()


def draw_teacher_fox_detective(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    scale: float = 1.0,
) -> None:
    """Draw the full teacher-pack fox detective; x/y is the face centre."""
    pdf.saveState()
    pdf.setLineJoin(1)
    pdf.setLineCap(1)

    # Detective coat and crisp cream collar give the mascot a character silhouette.
    coat = pdf.beginPath()
    coat.moveTo(x - 26 * scale, y - 31 * scale)
    coat.curveTo(x - 23 * scale, y - 22 * scale, x - 14 * scale, y - 18 * scale, x, y - 18 * scale)
    coat.curveTo(x + 14 * scale, y - 18 * scale, x + 23 * scale, y - 22 * scale, x + 27 * scale, y - 31 * scale)
    coat.lineTo(x + 31 * scale, y - 40 * scale)
    coat.lineTo(x - 31 * scale, y - 40 * scale)
    coat.close()
    pdf.setFillColor(TEAL)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.7 * scale)
    pdf.drawPath(coat, stroke=1, fill=1)
    pdf.setFillColor(CREAM)
    left_collar = pdf.beginPath()
    left_collar.moveTo(x - 16 * scale, y - 23 * scale)
    left_collar.lineTo(x - 3 * scale, y - 37 * scale)
    left_collar.lineTo(x, y - 22 * scale)
    left_collar.close()
    pdf.drawPath(left_collar, stroke=0, fill=1)
    right_collar = pdf.beginPath()
    right_collar.moveTo(x + 16 * scale, y - 23 * scale)
    right_collar.lineTo(x + 3 * scale, y - 37 * scale)
    right_collar.lineTo(x, y - 22 * scale)
    right_collar.close()
    pdf.drawPath(right_collar, stroke=0, fill=1)

    # Pointed fox ears, with warm cream inner panels.
    pdf.setFillColor(ORANGE)
    pdf.setStrokeColor(NAVY)
    left_ear = pdf.beginPath()
    left_ear.moveTo(x - 20 * scale, y + 13 * scale)
    left_ear.lineTo(x - 26 * scale, y + 37 * scale)
    left_ear.lineTo(x - 7 * scale, y + 23 * scale)
    left_ear.close()
    pdf.drawPath(left_ear, stroke=1, fill=1)
    right_ear = pdf.beginPath()
    right_ear.moveTo(x + 20 * scale, y + 13 * scale)
    right_ear.lineTo(x + 26 * scale, y + 37 * scale)
    right_ear.lineTo(x + 7 * scale, y + 23 * scale)
    right_ear.close()
    pdf.drawPath(right_ear, stroke=1, fill=1)
    pdf.setFillColor(CREAM)
    for direction in (-1, 1):
        ear_inner = pdf.beginPath()
        ear_inner.moveTo(x + direction * 18 * scale, y + 19 * scale)
        ear_inner.lineTo(x + direction * 22 * scale, y + 31 * scale)
        ear_inner.lineTo(x + direction * 10 * scale, y + 23 * scale)
        ear_inner.close()
        pdf.drawPath(ear_inner, stroke=0, fill=1)

    # Orange head with a navy outline.
    pdf.setFillColor(ORANGE)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.6 * scale)
    pdf.ellipse(x - 25 * scale, y - 25 * scale, x + 25 * scale, y + 25 * scale, stroke=1, fill=1)

    # White cheek mask and tapered central blaze create the familiar fox face.
    pdf.setFillColor(white)
    pdf.ellipse(x - 22 * scale, y - 16 * scale, x + 1 * scale, y + 9 * scale, stroke=0, fill=1)
    pdf.ellipse(x - 1 * scale, y - 16 * scale, x + 22 * scale, y + 9 * scale, stroke=0, fill=1)
    blaze = pdf.beginPath()
    blaze.moveTo(x - 8 * scale, y + 22 * scale)
    blaze.curveTo(x - 5 * scale, y + 11 * scale, x - 4 * scale, y + 3 * scale, x, y - 4 * scale)
    blaze.curveTo(x + 4 * scale, y + 3 * scale, x + 5 * scale, y + 11 * scale, x + 8 * scale, y + 22 * scale)
    blaze.close()
    pdf.drawPath(blaze, stroke=0, fill=1)

    # Large expressive eyes, eyebrows and highlights keep the face lively at print size.
    for direction in (-1, 1):
        eye_x = x + direction * 9 * scale
        pdf.setFillColor(white)
        pdf.setStrokeColor(NAVY)
        pdf.setLineWidth(1.0 * scale)
        pdf.ellipse(eye_x - 4.7 * scale, y + 2 * scale, eye_x + 4.7 * scale, y + 12 * scale, stroke=1, fill=1)
        pdf.setFillColor(NAVY)
        pdf.circle(eye_x + direction * .5 * scale, y + 6.4 * scale, 2.4 * scale, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.circle(eye_x - .7 * scale, y + 7.5 * scale, .75 * scale, stroke=0, fill=1)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.35 * scale)
    pdf.line(x - 14 * scale, y + 14 * scale, x - 6 * scale, y + 15.5 * scale)
    pdf.line(x + 6 * scale, y + 15.5 * scale, x + 14 * scale, y + 14 * scale)

    # Nose, smile and tiny cheek marks.
    pdf.setFillColor(NAVY)
    pdf.circle(x, y - 6 * scale, 3.2 * scale, stroke=0, fill=1)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.15 * scale)
    pdf.line(x, y - 9 * scale, x, y - 12 * scale)
    pdf.arc(x - 8 * scale, y - 16 * scale, x, y - 9 * scale, 278, 82)
    pdf.arc(x, y - 16 * scale, x + 8 * scale, y - 9 * scale, 98, 164)
    for direction in (-1, 1):
        pdf.setStrokeColor(ORANGE)
        pdf.line(x + direction * 12 * scale, y - 6 * scale, x + direction * 18 * scale, y - 5 * scale)
        pdf.line(x + direction * 12 * scale, y - 9 * scale, x + direction * 18 * scale, y - 10 * scale)

    # Teal deerstalker hat with navy edging and orange check details.
    hat = pdf.beginPath()
    hat.moveTo(x - 19 * scale, y + 21 * scale)
    hat.curveTo(x - 16 * scale, y + 35 * scale, x - 4 * scale, y + 38 * scale, x, y + 37 * scale)
    hat.curveTo(x + 8 * scale, y + 38 * scale, x + 17 * scale, y + 32 * scale, x + 19 * scale, y + 21 * scale)
    hat.close()
    pdf.setFillColor(TEAL)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(1.7 * scale)
    pdf.drawPath(hat, stroke=1, fill=1)
    pdf.setFillColor(NAVY)
    pdf.roundRect(x - 23 * scale, y + 20 * scale, 46 * scale, 5 * scale, 2.5 * scale, stroke=0, fill=1)
    pdf.setStrokeColor(ORANGE)
    pdf.setLineWidth(1.1 * scale)
    pdf.line(x, y + 24 * scale, x, y + 36 * scale)
    pdf.line(x - 14 * scale, y + 28 * scale, x + 14 * scale, y + 28 * scale)
    pdf.setFillColor(ORANGE)
    pdf.circle(x, y + 38 * scale, 2.2 * scale, stroke=0, fill=1)

    # Prominent magnifying glass, held clear of the face and content below.
    lens_x, lens_y = x + 27 * scale, y - 5 * scale
    pdf.setFillColor(white)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(3.1 * scale)
    pdf.circle(lens_x, lens_y, 9.2 * scale, stroke=1, fill=1)
    pdf.setStrokeColor(TEAL)
    pdf.setLineWidth(1.4 * scale)
    pdf.circle(lens_x, lens_y, 6.8 * scale, stroke=1, fill=0)
    pdf.setStrokeColor(NAVY)
    pdf.setLineWidth(4.2 * scale)
    pdf.line(lens_x + 6.5 * scale, lens_y - 6.5 * scale, x + 42 * scale, y - 21 * scale)
    pdf.setStrokeColor(ORANGE)
    pdf.setLineWidth(1.6 * scale)
    pdf.line(lens_x + 7.8 * scale, lens_y - 7.8 * scale, x + 41 * scale, y - 21 * scale)
    pdf.restoreState()


def draw_line_icon(
    pdf: canvas.Canvas,
    kind: str,
    x: float,
    y: float,
    size: float = 11,
    color: Color = white,
) -> None:
    """Small vector pictograms used throughout the printable pack."""
    k = kind.lower()
    r = size / 2
    pdf.saveState()
    pdf.setStrokeColor(color)
    pdf.setFillColor(color)
    pdf.setLineWidth(max(1, size * 0.11))
    if k == "lock":
        pdf.roundRect(x - r * .55, y - r * .52, r * 1.1, r * .85, r * .15, stroke=1, fill=0)
        pdf.arc(x - r * .42, y - r * .05, x + r * .42, y + r * .85, 0, 180)
        pdf.circle(x, y - r * .12, r * .10, stroke=0, fill=1)
    elif k in {"search", "magnifier"}:
        pdf.circle(x - r * .15, y + r * .12, r * .48, stroke=1, fill=0)
        pdf.line(x + r * .20, y - r * .25, x + r * .63, y - r * .68)
    elif k == "eye":
        pdf.ellipse(x - r * .78, y - r * .36, x + r * .78, y + r * .36, stroke=1, fill=0)
        pdf.circle(x, y, r * .17, stroke=0, fill=1)
    elif k in {"speech", "say"}:
        pdf.roundRect(x - r * .72, y - r * .42, r * 1.44, r * .92, r * .20, stroke=1, fill=0)
        pdf.line(x - r * .22, y - r * .42, x - r * .42, y - r * .68)
        pdf.line(x - r * .42, y - r * .68, x + r * .02, y - r * .42)
    elif k == "ear":
        pdf.arc(x - r * .56, y - r * .72, x + r * .56, y + r * .72, 295, 225)
        pdf.arc(x - r * .25, y - r * .38, x + r * .25, y + r * .38, 285, 210)
        pdf.circle(x + r * .20, y - r * .42, r * .08, stroke=0, fill=1)
    elif k == "play":
        path = pdf.beginPath()
        path.moveTo(x - r * .35, y - r * .58)
        path.lineTo(x + r * .60, y)
        path.lineTo(x - r * .35, y + r * .58)
        path.close()
        pdf.drawPath(path, stroke=0, fill=1)
    elif k == "check":
        pdf.line(x - r * .58, y, x - r * .12, y - r * .42)
        pdf.line(x - r * .12, y - r * .42, x + r * .62, y + r * .50)
    elif k == "lightning":
        path = pdf.beginPath()
        path.moveTo(x + r * .10, y + r * .78)
        path.lineTo(x - r * .54, y - r * .03)
        path.lineTo(x - r * .06, y - r * .03)
        path.lineTo(x - r * .26, y - r * .78)
        path.lineTo(x + r * .58, y + r * .10)
        path.lineTo(x + r * .12, y + r * .10)
        path.close()
        pdf.drawPath(path, stroke=0, fill=1)
    elif k == "pencil":
        pdf.line(x - r * .58, y - r * .45, x + r * .48, y + r * .60)
        pdf.line(x - r * .42, y - r * .60, x + r * .63, y + r * .45)
        pdf.line(x - r * .58, y - r * .45, x - r * .68, y - r * .70)
    elif k == "question":
        pdf.setFont(FONT_BOLD, size * .95)
        pdf.drawCentredString(x, y - size * .32, "?")
    elif k == "twist":
        pdf.arc(x - r * .65, y - r * .65, x + r * .40, y + r * .52, 25, 235)
        pdf.line(x + r * .34, y + r * .45, x + r * .66, y + r * .30)
        pdf.line(x + r * .34, y + r * .45, x + r * .28, y + r * .76)
    elif k == "book":
        pdf.line(x, y - r * .62, x, y + r * .55)
        pdf.roundRect(x - r * .78, y - r * .62, r * .76, r * 1.18, r * .08, stroke=1, fill=0)
        pdf.roundRect(x + r * .02, y - r * .62, r * .76, r * 1.18, r * .08, stroke=1, fill=0)
        pdf.line(x - r * .60, y + r * .26, x - r * .18, y + r * .18)
        pdf.line(x + r * .18, y + r * .18, x + r * .60, y + r * .26)
    elif k in {"notebook", "clipboard"}:
        pdf.roundRect(x - r * .62, y - r * .70, r * 1.24, r * 1.35, r * .10, stroke=1, fill=0)
        pdf.roundRect(x - r * .22, y + r * .48, r * .44, r * .25, r * .08, stroke=1, fill=0)
        for offset in (.24, -.05, -.34):
            pdf.line(x - r * .34, y + r * offset, x + r * .35, y + r * offset)
    elif k == "fingerprint":
        pdf.arc(x - r * .65, y - r * .72, x + r * .65, y + r * .72, 18, 315)
        pdf.arc(x - r * .48, y - r * .55, x + r * .48, y + r * .55, 30, 290)
        pdf.arc(x - r * .30, y - r * .38, x + r * .30, y + r * .38, 50, 250)
        pdf.line(x - r * .62, y - r * .15, x - r * .54, y - r * .58)
    elif k == "hat":
        pdf.line(x - r * .80, y - r * .35, x + r * .80, y - r * .35)
        path = pdf.beginPath()
        path.moveTo(x - r * .54, y - r * .28)
        path.lineTo(x - r * .35, y + r * .55)
        path.lineTo(x + r * .38, y + r * .55)
        path.lineTo(x + r * .55, y - r * .28)
        path.close()
        pdf.drawPath(path, stroke=1, fill=0)
        pdf.line(x - r * .46, y, x + r * .46, y)
    elif k == "heart":
        path = pdf.beginPath()
        path.moveTo(x, y - r * .65)
        path.curveTo(x - r * 1.0, y, x - r * .65, y + r * .70, x, y + r * .22)
        path.curveTo(x + r * .65, y + r * .70, x + r * 1.0, y, x, y - r * .65)
        pdf.drawPath(path, stroke=1, fill=0)
    elif k == "clock":
        pdf.circle(x, y, r * .72, stroke=1, fill=0)
        pdf.line(x, y, x, y + r * .42)
        pdf.line(x, y, x + r * .34, y - r * .20)
    elif k == "trophy":
        pdf.roundRect(x - r * .42, y + r * .02, r * .84, r * .58, r * .10, stroke=1, fill=0)
        pdf.arc(x - r * .76, y + r * .08, x - r * .26, y + r * .52, 80, 210)
        pdf.arc(x + r * .26, y + r * .08, x + r * .76, y + r * .52, 250, 210)
        pdf.line(x, y + r * .02, x, y - r * .46)
        pdf.line(x - r * .35, y - r * .58, x + r * .35, y - r * .58)
    elif k == "group":
        pdf.circle(x, y + r * .28, r * .25, stroke=1, fill=0)
        pdf.circle(x - r * .48, y + r * .10, r * .20, stroke=1, fill=0)
        pdf.circle(x + r * .48, y + r * .10, r * .20, stroke=1, fill=0)
        pdf.arc(x - r * .42, y - r * .62, x + r * .42, y + r * .05, 0, 180)
        pdf.arc(x - r * .78, y - r * .52, x - r * .12, y - r * .02, 0, 180)
        pdf.arc(x + r * .12, y - r * .52, x + r * .78, y - r * .02, 0, 180)
    else:
        pdf.circle(x, y, r * .55, stroke=1, fill=0)
        pdf.circle(x, y, r * .16, stroke=0, fill=1)
    pdf.restoreState()


def draw_icon_badge(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    kind: str,
    fill_color: Color = ORANGE,
    radius: float = 9,
) -> None:
    pdf.setFillColor(fill_color)
    pdf.circle(x, y, radius, stroke=0, fill=1)
    draw_line_icon(pdf, kind, x, y, radius * 1.25)


def icon_for_text(value: str) -> str:
    text = pdf_safe_text(value).lower()
    if any(word in text for word in ("secret", "hide", "role")):
        return "lock"
    if any(word in text for word in ("listen", "hear")):
        return "ear"
    if any(word in text for word in ("find", "clue", "guess", "detect")):
        return "search"
    if any(word in text for word in ("watch", "look", "notice")):
        return "eye"
    if any(word in text for word in ("ask", "question")):
        return "question"
    if any(word in text for word in ("say", "answer", "speak", "tell")):
        return "speech"
    if any(word in text for word in ("change", "twist")):
        return "twist"
    if any(word in text for word in ("check", "choose", "match")):
        return "check"
    return "pencil"


def draw_brand_footer(pdf: canvas.Canvas, page_number: int) -> None:
    page_width, _ = A4
    pdf.setStrokeColor(TEAL)
    pdf.setLineWidth(.7)
    pdf.line(122, 27, page_width - 122, 27)
    pdf.setFont(FONT_BOLD, 7.5)
    pdf.setFillColor(NAVY)
    pdf.drawString(34, 16, "FOX GAME LAB")
    pdf.setFont(FONT_REGULAR, 7.5)
    pdf.setFillColor(MID_GREY)
    pdf.drawRightString(page_width - 34, 16, str(page_number))
    pdf.setFillColor(ORANGE)
    pdf.circle(119, 17, 2.1, stroke=0, fill=1)
    pdf.setFillColor(TEAL)
    pdf.circle(127, 17, 2.1, stroke=0, fill=1)


def draw_section_header(pdf: canvas.Canvas, title: str, subtitle: str, page_number: int) -> float:
    page_width, page_height = A4
    draw_page_background(pdf)
    draw_fox_mascot(pdf, page_width / 2, page_height - 37, .62, detective=True)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 10.5)
    pdf.drawCentredString(page_width / 2, page_height - 63, "FOX GAME LAB")
    pdf.setFont(FONT_BOLD, 19)
    pdf.drawCentredString(page_width / 2, page_height - 80, pdf_safe_text(title))
    if subtitle:
        pill_width = min(230, max(120, pdfmetrics.stringWidth(pdf_safe_text(subtitle), FONT_BOLD, 10) + 44))
        pdf.setFillColor(NAVY)
        pdf.roundRect((page_width - pill_width) / 2, page_height - 115, pill_width, 19, 9, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont(FONT_BOLD, 10)
        pdf.drawCentredString(page_width / 2, page_height - 108, pdf_safe_text(subtitle))
    draw_brand_footer(pdf, page_number)
    return page_height - 135


def worksheet_block_height(title: str, lines: list[str], width: float) -> float:
    clean_title = re.sub(r"^TASK\s+\d+\s*[-:|]+\s*", "", pdf_safe_text(title), flags=re.I)
    title_count = max(1, len(wrap_text(clean_title, FONT_BOLD, 9.2, width - 50)))
    line_count = 0
    for line in lines:
        available = width - 28 - (14 if line.strip().startswith(("☐", "□")) else 0)
        line_count += max(1, len(wrap_text(line, FONT_REGULAR, 8.4, available)))
    return max(48, 25 + title_count * 11 + line_count * 10.5)


def paginate_worksheet_blocks(
    blocks: list[tuple[str, list[str]]],
    column_width: float,
    top: float,
    bottom: float,
    height_function=None,
) -> list[list[tuple[int, float, str, list[str]]]]:
    height_function = height_function or worksheet_block_height
    measured = [
        (title, lines, height_function(title, lines, column_width))
        for title, lines in blocks
    ]
    capacity = top - bottom
    pages: list[list[tuple[int, float, str, list[str]]]] = []
    start = 0
    while start < len(measured):
        chosen_end = start + 1
        chosen_split = 1
        chosen_balance = float("inf")
        for end in range(start + 1, len(measured) + 1):
            chunk = measured[start:end]
            best_for_chunk: tuple[float, int] | None = None
            for split in range(1, len(chunk) + 1):
                left = sum(item[2] for item in chunk[:split]) + 8 * max(0, split - 1)
                right_count = len(chunk) - split
                right = sum(item[2] for item in chunk[split:]) + 8 * max(0, right_count - 1)
                if left <= capacity and right <= capacity:
                    balance = abs(left - right)
                    if best_for_chunk is None or balance < best_for_chunk[0]:
                        best_for_chunk = (balance, split)
            if best_for_chunk is None:
                break
            chosen_end = end
            chosen_balance, chosen_split = best_for_chunk

        chunk = measured[start:chosen_end]
        page_blocks: list[tuple[int, float, str, list[str]]] = []
        for column, column_items in enumerate((chunk[:chosen_split], chunk[chosen_split:])):
            y = top
            for title, lines, height in column_items:
                page_blocks.append((column, y, title, lines))
                y -= height + 8
        pages.append(page_blocks)
        start = chosen_end
    return pages


def draw_compact_worksheet_header(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    page_number: int,
    worksheet_page: int,
    worksheet_page_count: int,
) -> float:
    page_width, page_height = A4
    draw_page_background(pdf)
    heading = "PLAYER WORKSHEET"
    if worksheet_page_count > 1:
        heading += f" {worksheet_page}"
    draw_fox_mascot(pdf, page_width / 2, page_height - 35, .5, detective=True)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 9.5)
    pdf.drawCentredString(page_width / 2, page_height - 55, "FOX GAME LAB")
    pdf.setFont(FONT_BOLD, 16)
    pdf.drawCentredString(page_width / 2, page_height - 77, heading)
    game_title = pdf_safe_text(game.get("title", "Game"))
    pdf.setFillColor(NAVY)
    pdf.roundRect(page_width / 2 - 74, page_height - 104, 148, 19, 9, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont(FONT_BOLD, 10)
    pdf.drawCentredString(page_width / 2, page_height - 97, game_title[:40])
    labels = [("GRAMMAR", state.get("topic")), ("LEVEL", state.get("level")), ("AGE", state.get("age")), ("SKILL", state.get("skill")), ("TIME", state.get("duration"))]
    info_y = page_height - 137
    info_w = (page_width - 72 - 4 * 6) / 5
    for index, (label, value) in enumerate(labels):
        x = 36 + index * (info_w + 6)
        pdf.setFillColor(PALE_ORANGE if index % 2 == 0 else PALE_TEAL)
        pdf.setStrokeColor(ORANGE if index % 2 == 0 else TEAL)
        pdf.roundRect(x, info_y, info_w, 27, 6, stroke=1, fill=1)
        pdf.setFillColor(MID_GREY)
        pdf.setFont(FONT_BOLD, 5.8)
        pdf.drawString(x + 7, info_y + 17, label)
        pdf.setFillColor(NAVY)
        pdf.setFont(FONT_BOLD, 8.2)
        pdf.drawString(x + 7, info_y + 6, pdf_safe_text(value or "-")[:16])
    draw_brand_footer(pdf, page_number)
    return page_height - 151


def draw_worksheet_panel(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    title: str,
    lines: list[str],
    height_override: float | None = None,
) -> float:
    natural_height = worksheet_block_height(title, lines, width)
    height = max(natural_height, height_override or 0)
    safe_title = pdf_safe_text(title)
    task_match = re.match(r"^TASK\s+(\d+)\s*[-:|]+\s*(.*)$", safe_title, re.I)
    is_challenge = "FOX CHALLENGE" in safe_title.upper()
    fill_color = PALE_ORANGE if is_challenge else white
    pdf.setFillColor(fill_color)
    pdf.setStrokeColor(TEAL if is_challenge else LINE_GREY)
    if is_challenge:
        pdf.saveState()
        pdf.setDash(4, 2)
    pdf.roundRect(x, y_top - height, width, height, 7, stroke=1, fill=1)
    if is_challenge:
        pdf.restoreState()

    if not is_challenge:
        pdf.setFillColor(PALE_TEAL)
        pdf.roundRect(x + 1, y_top - 28, width - 2, 27, 6, stroke=0, fill=1)

    title_x = x + 12
    display_title = safe_title
    if task_match:
        number, display_title = task_match.groups()
        display_title = f"TASK {number} - {display_title}"
        pdf.setFillColor(ORANGE)
        pdf.circle(x + 17, y_top - 17, 9, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont(FONT_BOLD, 7.5)
        pdf.drawCentredString(x + 17, y_top - 19.5, number)
        title_x = x + 32
    elif is_challenge:
        display_title = "FOX CHALLENGE"
        draw_fox_mascot(pdf, x + 18, y_top - 21, .42)
        title_x = x + 37

    if not is_challenge:
        draw_icon_badge(
            pdf,
            x + width - 17,
            y_top - 15,
            icon_for_text(display_title),
            TEAL,
            7,
        )

    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 9.2)
    title_lines = wrap_text(display_title, FONT_BOLD, 9.2, width - (title_x - x) - 12)
    title_y = y_top - 19
    for line in title_lines[:2]:
        pdf.drawString(title_x, title_y, line)
        title_y -= 11
    body_y = min(y_top - 35, title_y - 4)
    draw_lines(
        pdf,
        lines,
        x + 12,
        body_y,
        width - 24,
        font_size=8.4,
        leading=10.5,
    )
    if height - natural_height >= 18:
        pdf.setStrokeColor(Color(LINE_GREY.red, LINE_GREY.green, LINE_GREY.blue, alpha=0.55))
        line_y = y_top - height + 13
        pdf.line(x + 12, line_y, x + width - 12, line_y)
        if height - natural_height >= 36:
            pdf.line(x + 12, line_y + 16, x + width - 12, line_y + 16)
    return height


def draw_worksheet_pages(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    body: str,
    page_number: int,
) -> int:
    blocks = parse_material_blocks(body)
    page_width, page_height = A4
    margin = 32
    gap = 10
    column_width = (page_width - margin * 2 - gap) / 2
    top = page_height - 151
    pages = paginate_worksheet_blocks(blocks, column_width, top, 42)
    for worksheet_index, page_blocks in enumerate(pages, 1):
        draw_compact_worksheet_header(
            pdf,
            game,
            state,
            page_number,
            worksheet_index,
            len(pages),
        )
        for column in (0, 1):
            column_blocks = [
                (title, lines)
                for block_column, _, title, lines in page_blocks
                if block_column == column
            ]
            if not column_blocks:
                continue
            natural_total = sum(
                worksheet_block_height(title, lines, column_width)
                for title, lines in column_blocks
            ) + 8 * max(0, len(column_blocks) - 1)
            capacity = top - 42
            extra_each = max(0, (capacity - natural_total) / len(column_blocks))
            x = margin + column * (column_width + gap)
            y_top = top
            for title, lines in column_blocks:
                natural_height = worksheet_block_height(title, lines, column_width)
                used = draw_worksheet_panel(
                    pdf,
                    x,
                    y_top,
                    column_width,
                    title,
                    lines,
                    height_override=natural_height + extra_each,
                )
                y_top -= used + 8
        pdf.showPage()
        page_number += 1
    return page_number


def parse_material_blocks(text: str) -> list[tuple[str, list[str]]]:
    chunks = [chunk.strip() for chunk in re.split(r"\n\s*\n", text.strip()) if chunk.strip()]
    blocks: list[tuple[str, list[str]]] = []
    for chunk in chunks:
        lines = [line.strip() for line in chunk.splitlines() if line.strip()]
        if lines:
            blocks.append((lines[0], lines[1:]))
    return blocks


def parse_cards(text: str) -> tuple[int | None, list[tuple[str, list[str]]]]:
    set_match = re.search(r"SET:\s*(\d+)\s+CARDS?", text, re.IGNORECASE)
    announced_count = int(set_match.group(1)) if set_match else None
    cards: list[tuple[str, list[str]]] = []
    for title, lines in parse_material_blocks(text):
        if title.upper().startswith("SET:"):
            continue
        if re.match(r"^\d+\s+\w+\s*[•|]", title):
            continue
        copies = 1
        kept_lines = []
        for line in lines:
            copy_match = re.search(r"PRINT\s+(\d+)\s+COPIES", line, re.IGNORECASE)
            if copy_match:
                copies = max(1, min(12, int(copy_match.group(1))))
            else:
                kept_lines.append(line)
        for _ in range(copies):
            cards.append((title, list(kept_lines)))
    return announced_count, cards


def draw_cover(pdf: canvas.Canvas, game: dict[str, Any], state: dict[str, Any], page_number: int) -> None:
    page_width, page_height = A4
    pdf.setFillColor(LIGHT)
    pdf.rect(0, 0, page_width, page_height, stroke=0, fill=1)
    pdf.setFillColor(NAVY)
    pdf.roundRect(38, page_height - 186, page_width - 76, 120, 18, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.circle(page_width - 79, page_height - 95, 22, stroke=0, fill=1)
    draw_fox_mascot(pdf, page_width - 79, page_height - 98, .82)
    pdf.setFillColor(ORANGE)
    pdf.circle(page_width - 113, page_height - 75, 5, stroke=0, fill=1)
    pdf.setFillColor(white)
    pdf.setFont(FONT_BOLD, 12)
    pdf.drawString(58, page_height - 98, "FOX GAME LAB")
    pdf.setFont(FONT_BOLD, 29)
    pdf.drawString(58, page_height - 141, "GAME PACK")

    title_lines = wrap_text(game.get("title", "Game"), FONT_BOLD, 25, page_width - 100)
    y = page_height - 245
    pdf.setFillColor(NAVY)
    for line in title_lines[:3]:
        pdf.setFont(FONT_BOLD, 25)
        pdf.drawString(50, y, line)
        y -= 31

    details = [
        ("TOPIC", state.get("topic")),
        ("LEVEL", state.get("level")),
        ("AGE", state.get("age")),
        ("SKILL", state.get("skill")),
        ("TIME", state.get("duration")),
    ]
    box_y = y - 30
    box_w = (page_width - 116) / 2
    for index, (label, value) in enumerate(details):
        col = index % 2
        row = index // 2
        x = 50 + col * (box_w + 16)
        current_y = box_y - row * 57
        pdf.setFillColor(PALE_TEAL if index % 2 else PALE_ORANGE)
        pdf.roundRect(x, current_y - 36, box_w, 43, 8, stroke=0, fill=1)
        pdf.setFillColor(MID_GREY)
        pdf.setFont(FONT_BOLD, 7.5)
        pdf.drawString(x + 11, current_y - 8, label)
        pdf.setFillColor(NAVY)
        pdf.setFont(FONT_BOLD, 11)
        pdf.drawString(x + 11, current_y - 25, pdf_safe_text(value or "-"))

    mission_y = box_y - 3 * 57 - 26
    pdf.setFillColor(white)
    pdf.setStrokeColor(TEAL)
    pdf.setLineWidth(1.4)
    pdf.roundRect(50, mission_y - 104, page_width - 100, 110, 12, stroke=1, fill=1)
    pdf.setFillColor(TEAL)
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawString(64, mission_y - 19, "MISSION")
    mission_lines = wrap_text(game.get("mission", ""), FONT_REGULAR, 11, page_width - 130)
    draw_lines(pdf, mission_lines[:4], 64, mission_y - 42, page_width - 130, font_size=11, leading=15)

    pdf.setFillColor(ORANGE)
    pdf.setFont(FONT_BOLD, 13)
    pdf.drawString(50, 58, "Ready to play.")
    draw_brand_footer(pdf, page_number)
    pdf.showPage()


def draw_card(pdf: canvas.Canvas, x: float, y: float, width: float, height: float, title: str, lines: list[str]) -> None:
    safe_title = pdf_safe_text(title)
    upper_title = safe_title.upper()
    role_color = TEAL if upper_title.startswith(("STUDENT ", "PLAYER ")) else NAVY
    pdf.saveState()
    pdf.setDash(5, 3)
    pdf.setStrokeColor(NAVY)
    pdf.rect(x - 4, y - 4, width + 8, height + 8, stroke=1, fill=0)
    pdf.restoreState()
    pdf.setFillColor(white)
    pdf.setStrokeColor(role_color)
    pdf.setLineWidth(1.4)
    pdf.roundRect(x, y, width, height, 12, stroke=1, fill=1)
    pdf.setFillColor(PALE_ORANGE if role_color == NAVY else PALE_TEAL)
    pdf.roundRect(x + 10, y + height - 48, width - 20, 37, 10, stroke=0, fill=1)
    draw_icon_badge(
        pdf,
        x + 29,
        y + height - 29,
        "lock" if role_color == NAVY else "speech",
        ORANGE,
        9,
    )
    title_lines = wrap_text(safe_title, FONT_BOLD, 11.5, width - 54)
    pdf.setFillColor(role_color)
    pdf.setFont(FONT_BOLD, 12)
    title_y = y + height - 27
    for line in title_lines[:2]:
        pdf.drawString(x + 48, title_y, line)
        title_y -= 14

    body_y = y + height - 59
    action_lines = lines[:3]
    target_row_height = min(44, max(32, (height - 76) / max(1, len(action_lines))))
    for line in action_lines:
        wrapped = wrap_text(line, FONT_REGULAR, 9.4, width - 58)
        row_height = max(target_row_height, 10.2 * len(wrapped) + 11)
        if body_y - row_height < y + 10:
            break
        pdf.setFillColor(white)
        pdf.setStrokeColor(Color(role_color.red, role_color.green, role_color.blue, alpha=.18))
        pdf.roundRect(x + 12, body_y - row_height + 7, width - 24, row_height - 3, 7, stroke=1, fill=1)
        draw_icon_badge(
            pdf,
            x + 27,
            body_y - row_height / 2 + 5,
            icon_for_text(line),
            role_color,
            7,
        )
        draw_lines(
            pdf,
            wrapped,
            x + 42,
            body_y - 11,
            width - 58,
            font_size=9.4,
            leading=10.8,
        )
        body_y -= row_height


def draw_cards_pages(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    cards_text: str,
    page_number: int,
) -> int:
    announced_count, cards = parse_cards(cards_text)
    if not cards:
        cards = [("GAME CARD", ["Use this card during the game."])]
    subtitle = (
        f"{state.get('level') or '-'} | {state.get('age') or '-'} years | "
        f"{state.get('topic') or '-'} | {announced_count or len(cards)} cards"
    )
    page_width, page_height = A4
    margin_x = 34
    gap = 14
    card_width = (page_width - 2 * margin_x - gap) / 2
    for start in range(0, len(cards), 6):
        y_top = draw_section_header(pdf, "GAME CARDS", game.get("title", ""), page_number)
        pdf.setFillColor(MID_GREY)
        pdf.setFont(FONT_REGULAR, 7.5)
        pdf.drawCentredString(page_width / 2, page_height - 127, pdf_safe_text(subtitle))
        rows = 3
        row_gap = 10
        card_height = (y_top - 43 - row_gap * (rows - 1)) / rows
        batch = cards[start : start + 6]
        for index, (title, lines) in enumerate(batch):
            col = index % 2
            row = index // 2
            x = margin_x + col * (card_width + gap)
            y = y_top - (row + 1) * card_height - row * row_gap
            draw_card(pdf, x, y, card_width, card_height, title, lines)
        pdf.showPage()
        page_number += 1
    return page_number


def estimated_panel_height(title: str, lines: list[str], width: float) -> float:
    count = len(wrap_text(title, FONT_BOLD, 10.5, width - 28))
    for line in lines:
        count += max(1, len(wrap_text(line, FONT_REGULAR, 9.5, width - 28)))
    return max(58, min(190, 28 + count * 13))


def draw_panel(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    title: str,
    lines: list[str],
    fill_color: Color,
) -> float:
    height = estimated_panel_height(title, lines, width)
    pdf.setFillColor(fill_color)
    pdf.setStrokeColor(Color(NAVY.red, NAVY.green, NAVY.blue, alpha=0.16))
    pdf.roundRect(x, y_top - height, width, height, 9, stroke=1, fill=1)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 10.5)
    title_lines = wrap_text(title, FONT_BOLD, 10.5, width - 28)
    title_y = y_top - 20
    for line in title_lines[:2]:
        pdf.drawString(x + 14, title_y, line)
        title_y -= 13
    body_y = title_y - 5
    draw_lines(pdf, lines, x + 14, body_y, width - 28, font_size=9.5, leading=13)
    return height


def draw_panel_section_pages(
    pdf: canvas.Canvas,
    title: str,
    game_title: str,
    body: str,
    page_number: int,
    teacher: bool = False,
) -> int:
    blocks = parse_material_blocks(body)
    page_width, _ = A4
    panel_width = page_width - 68
    y = draw_section_header(pdf, title, game_title, page_number)
    fill_cycle = [PALE_TEAL, PALE_ORANGE] if teacher else [white, PALE_TEAL]
    for index, (block_title, lines) in enumerate(blocks):
        height = estimated_panel_height(block_title, lines, panel_width)
        if y - height < 43:
            pdf.showPage()
            page_number += 1
            y = draw_section_header(pdf, f"{title} (CONT.)", game_title, page_number)
        used = draw_panel(pdf, 34, y, panel_width, block_title, lines, fill_cycle[index % 2])
        y -= used + 10
    pdf.showPage()
    return page_number + 1


def draw_compact_teacher_header(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    page_number: int,
    teacher_page: int,
    teacher_page_count: int,
) -> float:
    page_width, page_height = A4
    draw_page_background(pdf)
    game_title = pdf_safe_text(game.get("title", "Game"))[:28]
    heading = f"TEACHER MINI PACK  /  {game_title}"
    if teacher_page_count > 1:
        heading += f" {teacher_page}"
    draw_fox_mascot(pdf, page_width / 2, page_height - 36, .56, detective=True)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 9.5)
    pdf.drawCentredString(page_width / 2, page_height - 58, "FOX GAME LAB")
    pdf.setFont(FONT_BOLD, 17)
    pdf.drawCentredString(page_width / 2, page_height - 82, heading)
    details = " • ".join(
        pdf_safe_text(value) or "-"
        for value in (state.get("level"), state.get("age"), state.get("topic"), state.get("duration"))
    )
    pdf.setFillColor(MID_GREY)
    pdf.setFont(FONT_REGULAR, 7.8)
    pill_width = min(270, pdfmetrics.stringWidth(details, FONT_REGULAR, 7.8) + 28)
    pdf.setFillColor(PALE_TEAL)
    pdf.roundRect((page_width - pill_width) / 2, page_height - 111, pill_width, 18, 8, stroke=0, fill=1)
    pdf.setFillColor(NAVY)
    pdf.drawCentredString(page_width / 2, page_height - 104, details)
    draw_brand_footer(pdf, page_number)
    return page_height - 126


def draw_teacher_panel(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    title: str,
    lines: list[str],
    fill_color: Color,
    height_override: float | None = None,
) -> float:
    natural_height = teacher_block_height(title, lines, width)
    height = max(natural_height, height_override or 0)
    safe_title = pdf_safe_text(title)
    normal_lines: list[str] = []
    tip_lines: list[str] = []
    for line in lines:
        if re.match(r"^Teacher\s+(Note|Tip)\s*:", pdf_safe_text(line), re.I):
            tip_lines.append(line)
        else:
            normal_lines.append(line)

    pdf.setFillColor(fill_color)
    pdf.setStrokeColor(Color(NAVY.red, NAVY.green, NAVY.blue, alpha=0.18))
    pdf.roundRect(x, y_top - height, width, height, 7, stroke=1, fill=1)
    pdf.setFillColor(NAVY)
    pdf.roundRect(x + 1, y_top - 30, width - 2, 29, 6, stroke=0, fill=1)
    title_icon_map = {
        "START": "play",
        "SAY THIS": "speech",
        "ENGLISH SUPPORT": "question",
        "TEACHER TIPS": "check",
        "FOX TWIST": "twist",
        "IF TOO EASY": "lightning",
        "IF TOO HARD": "ear",
        "AFTER THE GAME": "speech",
        "QUICK CHECK": "check",
    }
    icon_kind = title_icon_map.get(safe_title.upper(), icon_for_text(safe_title))
    draw_icon_badge(pdf, x + 17, y_top - 15, icon_kind, ORANGE, 8)
    pdf.setFillColor(white)
    title_text = safe_title[:38]
    title_size = 9.2
    while title_size > 6.3 and pdfmetrics.stringWidth(title_text, FONT_BOLD, title_size) > width - 42:
        title_size -= .3
    pdf.setFont(FONT_BOLD, title_size)
    pdf.drawString(x + 31, y_top - 18.5, title_text)
    body_y = y_top - 46
    body_y = draw_lines(
        pdf,
        normal_lines,
        x + 12,
        body_y,
        width - 24,
        font_size=8.7,
        leading=11.2,
    )
    if tip_lines:
        tip_text = " ".join(pdf_safe_text(line) for line in tip_lines)
        tip_wrapped = wrap_text(tip_text, FONT_REGULAR, 7.7, width - 46)
        tip_height = max(28, len(tip_wrapped) * 9 + 10)
        tip_y = max(y_top - height + 9, body_y - tip_height + 2)
        pdf.saveState()
        pdf.setDash(3, 2)
        pdf.setStrokeColor(ORANGE)
        pdf.setFillColor(CREAM)
        pdf.roundRect(x + 10, tip_y, width - 20, tip_height, 5, stroke=1, fill=1)
        pdf.restoreState()
        draw_icon_badge(pdf, x + 22, tip_y + tip_height - 13, "check", TEAL, 6)
        draw_lines(
            pdf,
            tip_wrapped,
            x + 33,
            tip_y + tip_height - 16,
            width - 46,
            font_size=7.7,
            leading=9,
        )
    return height


def teacher_block_height(title: str, lines: list[str], width: float) -> float:
    normal_lines = [
        line for line in lines
        if not re.match(r"^Teacher\s+(Note|Tip)\s*:", pdf_safe_text(line), re.I)
    ]
    tip_lines = [line for line in lines if line not in normal_lines]
    line_count = sum(
        max(1, len(wrap_text(line, FONT_REGULAR, 8.7, width - 24)))
        for line in normal_lines
    )
    tip_count = sum(
        max(1, len(wrap_text(line, FONT_REGULAR, 7.7, width - 46)))
        for line in tip_lines
    )
    tip_height = (max(28, tip_count * 9 + 10) + 6) if tip_lines else 0
    return max(66, 44 + line_count * 11.2 + tip_height)


def draw_teacher_pack_pages(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    body: str,
    page_number: int,
) -> int:
    blocks = parse_material_blocks(body)
    page_width, page_height = A4
    margin = 32
    gap = 8
    column_width = (page_width - margin * 2 - gap * 2) / 3
    top = page_height - 126
    fill_cycle = [PALE_TEAL, PALE_ORANGE]
    pages = [blocks[index:index + 9] for index in range(0, len(blocks), 9)] or [[]]
    for teacher_index, page_blocks in enumerate(pages, 1):
        draw_compact_teacher_header(
            pdf,
            game,
            state,
            page_number,
            teacher_index,
            len(pages),
        )
        row_count = max(1, (len(page_blocks) + 2) // 3)
        row_gap = 8
        row_height = (top - 42 - row_gap * (row_count - 1)) / row_count
        for index, (title, lines) in enumerate(page_blocks):
            row, column = divmod(index, 3)
            x = margin + column * (column_width + gap)
            y_top = top - row * (row_height + row_gap)
            draw_teacher_panel(
                pdf,
                x,
                y_top,
                column_width,
                title,
                lines,
                fill_cycle[index % 2],
                height_override=row_height,
            )
        pdf.showPage()
        page_number += 1
    return page_number


def draw_paw(pdf: canvas.Canvas, x: float, y: float, scale: float = 1.0, color: Color = TEAL) -> None:
    """Small solid paw used as a recurring premium-printable motif."""
    pdf.saveState()
    pdf.setFillColor(color)
    pdf.ellipse(x - 5 * scale, y - 4 * scale, x + 5 * scale, y + 4 * scale, stroke=0, fill=1)
    for dx, dy, radius in ((-6, 5, 2.4), (-2, 8, 2.5), (3, 8, 2.5), (7, 4, 2.3)):
        pdf.circle(x + dx * scale, y + dy * scale, radius * scale, stroke=0, fill=1)
    pdf.restoreState()


def draw_premium_title(
    pdf: canvas.Canvas,
    heading: str,
    game_title: str,
    page_number: int,
    heading_size: float = 25,
) -> float:
    """Reference-led title treatment shared by the three Spy Hunt sheets."""
    page_width, page_height = A4
    draw_page_background(pdf)
    draw_fox_mascot(pdf, page_width / 2, page_height - 37, .70, detective=True)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 10.5)
    pdf.drawCentredString(page_width / 2, page_height - 67, "FOX GAME LAB")
    pdf.setStrokeColor(ORANGE)
    pdf.setLineWidth(1.2)
    pdf.line(page_width / 2 - 92, page_height - 79, page_width / 2 - 18, page_height - 79)
    pdf.line(page_width / 2 + 18, page_height - 79, page_width / 2 + 92, page_height - 79)
    pdf.setFillColor(ORANGE)
    pdf.circle(page_width / 2, page_height - 79, 3.8, stroke=0, fill=1)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, heading_size)
    pdf.drawCentredString(page_width / 2, page_height - 111, pdf_safe_text(heading))
    pill_width = max(155, min(235, pdfmetrics.stringWidth(pdf_safe_text(game_title), FONT_BOLD, 11) + 72))
    pdf.setFillColor(NAVY)
    pdf.roundRect((page_width - pill_width) / 2, page_height - 141, pill_width, 22, 11, stroke=0, fill=1)
    draw_line_icon(pdf, "search", page_width / 2 - pill_width / 2 + 20, page_height - 130, 13, TEAL)
    pdf.setFillColor(white)
    pdf.setFont(FONT_BOLD, 11)
    pdf.drawCentredString(page_width / 2, page_height - 134, pdf_safe_text(game_title))
    draw_paw(pdf, page_width / 2 + pill_width / 2 - 19, page_height - 134, .58, TEAL)
    draw_brand_footer(pdf, page_number)
    return page_height - 152


def draw_premium_card(
    pdf: canvas.Canvas,
    x: float,
    y: float,
    width: float,
    height: float,
    title: str,
    lines: list[str],
) -> None:
    safe_title = pdf_safe_text(title)
    spy = safe_title.upper().startswith("SPY")
    role_color = NAVY if spy else TEAL
    pdf.saveState()
    pdf.setDash(4, 3)
    pdf.setStrokeColor(Color(NAVY.red, NAVY.green, NAVY.blue, alpha=.72))
    pdf.rect(x - 4, y - 4, width + 8, height + 8, stroke=1, fill=0)
    pdf.restoreState()
    pdf.setFillColor(CREAM if spy else white)
    pdf.setStrokeColor(role_color)
    pdf.setLineWidth(1.55 if spy else 1.25)
    pdf.roundRect(x, y, width, height, 11, stroke=1, fill=1)
    if spy:
        pdf.setFillColor(ORANGE)
        pdf.roundRect(x + 1, y + 11, 5, height - 22, 2, stroke=0, fill=1)
        pdf.setFillColor(PALE_ORANGE)
        pdf.circle(x + width - 25, y + 25, 23, stroke=0, fill=1)
    else:
        pdf.setFillColor(PALE_TEAL)
        pdf.wedge(x + width - 52, y, x + width, y + 52, 0, 90, stroke=0, fill=1)
    draw_icon_badge(pdf, x + 30, y + height - 28, "hat" if spy else "group", role_color, 15.5)
    pdf.setFillColor(role_color)
    pdf.roundRect(x + 52, y + height - 43, width - 92, 31, 8, stroke=0, fill=1)
    pdf.setFillColor(white)
    title_size = 13.2
    while title_size > 9 and pdfmetrics.stringWidth(safe_title, FONT_BOLD, title_size) > width - 110:
        title_size -= .4
    pdf.setFont(FONT_BOLD, title_size)
    pdf.drawCentredString(x + 52 + (width - 92) / 2, y + height - 34, safe_title)
    draw_paw(pdf, x + width - 24, y + height - 32, .82, ORANGE if not spy else NAVY)
    draw_fox_mascot(pdf, x + width - 26, y + 23, .50, detective=spy)
    content_top = y + height - 57
    available = height - 70
    row_h = available / max(1, len(lines[:4]))
    for index, line in enumerate(lines[:4]):
        row_y = content_top - index * row_h
        icon_color = TEAL if index % 2 == 0 else ORANGE
        draw_icon_badge(pdf, x + 23, row_y - row_h / 2 + 5, icon_for_text(line), icon_color, 7.7)
        wrapped = wrap_text(line, FONT_REGULAR, 9.1, width - 82)
        text_y = row_y - 6
        for wrapped_line in wrapped[:2]:
            pdf.setFillColor(NAVY)
            pdf.setFont(FONT_REGULAR, 9.1)
            pdf.drawString(x + 40, text_y, wrapped_line)
            text_y -= 10.1
        if index < len(lines[:4]) - 1:
            pdf.setStrokeColor(Color(TEAL.red, TEAL.green, TEAL.blue, alpha=.22))
            line_end = x + width - (50 if index == len(lines[:4]) - 2 else 14)
            pdf.line(x + 40, row_y - row_h + 5, line_end, row_y - row_h + 5)


def draw_premium_cards_page(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    cards_text: str,
    page_number: int,
) -> int:
    announced_count, cards = parse_cards(cards_text)
    top = draw_premium_title(pdf, "GAME CARDS", game.get("title", "Spy Hunt"), page_number, 29)
    page_width, page_height = A4
    draw_fox_mascot(pdf, page_width - 74, page_height - 104, 2.25, detective=True)
    details = f"{state.get('level')}   •   age {state.get('age')}   •   {state.get('topic')}   •   {state.get('skill')}"
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 8.3)
    pdf.drawCentredString(page_width / 2, top - 7, pdf_safe_text(details))
    margin_x, gap_x, gap_y = 34, 12, 8
    grid_top, grid_bottom = top - 22, 46
    card_width = (page_width - 2 * margin_x - gap_x) / 2
    card_height = (grid_top - grid_bottom - 2 * gap_y) / 3
    for index, (title, lines) in enumerate(cards[:6]):
        col, row = index % 2, index // 2
        x = margin_x + col * (card_width + gap_x)
        y = grid_top - (row + 1) * card_height - row * gap_y
        draw_premium_card(pdf, x, y, card_width, card_height, title, lines)
    pdf.setFillColor(ORANGE)
    pdf.setFont(FONT_BOLD, 8.5)
    pdf.drawCentredString(page_width / 2, 34, "CUT • SHARE • ASK • LISTEN • FIND")
    pdf.showPage()
    return page_number + 1


def draw_premium_info_row(pdf: canvas.Canvas, state: dict[str, Any], y: float) -> None:
    page_width, _ = A4
    items = [
        ("TOPIC", state.get("topic"), "pencil"),
        ("LEVEL", state.get("level"), "check"),
        ("AGE", state.get("age"), "speech"),
        ("SKILL", state.get("skill"), "speech"),
        ("TIME", "5 minutes", "twist"),
    ]
    gap = 6
    width = (page_width - 64 - gap * 4) / 5
    for index, (label, value, icon) in enumerate(items):
        x = 32 + index * (width + gap)
        accent = ORANGE if index % 2 == 0 else TEAL
        pdf.setFillColor(CREAM)
        pdf.setStrokeColor(Color(accent.red, accent.green, accent.blue, alpha=.55))
        pdf.roundRect(x, y, width, 33, 6, stroke=1, fill=1)
        draw_icon_badge(pdf, x + 13, y + 17, icon, accent, 8)
        pdf.setFillColor(MID_GREY)
        pdf.setFont(FONT_BOLD, 5.7)
        pdf.drawString(x + 25, y + 21, label)
        pdf.setFillColor(NAVY)
        pdf.setFont(FONT_BOLD, 8)
        pdf.drawString(x + 25, y + 8, pdf_safe_text(value or "-")[:14])


def draw_premium_task(
    pdf: canvas.Canvas,
    x: float,
    y_top: float,
    width: float,
    height: float,
    title: str,
    lines: list[str],
    accent: Color = TEAL,
) -> None:
    safe_title = pdf_safe_text(title)
    match = re.match(r"TASK\s+(\d+)\s*[-:|]+\s*(.*)", safe_title, re.I)
    is_special = safe_title.upper() in {"FOX CHALLENGE", "HELPER BOX"}
    task_number = int(match.group(1)) if match else 0
    task_icons = {
        1: "book", 2: "question", 3: "pencil", 4: "notebook",
        5: "fingerprint", 6: "search", 7: "hat", 8: "speech",
    }
    fills = {1: white, 2: CREAM, 3: PALE_TEAL, 4: white, 5: PALE_ORANGE, 6: white, 7: PALE_TEAL, 8: CREAM}
    fill = PALE_ORANGE if safe_title.upper() == "FOX CHALLENGE" else (CREAM if safe_title.upper() == "HELPER BOX" else fills.get(task_number, white))
    pdf.setFillColor(fill)
    border_color = ORANGE if task_number in {2, 5, 8} or is_special else TEAL
    pdf.setStrokeColor(border_color)
    pdf.setLineWidth(1.15 if task_number in {1, 4, 6} or is_special else .8)
    radius = 11 if task_number in {1, 5, 8} or is_special else 6
    pdf.roundRect(x, y_top - height, width, height, radius, stroke=1, fill=1)
    if task_number in {1, 4, 7}:
        pdf.setFillColor(border_color)
        pdf.roundRect(x + 1, y_top - height + 7, 5, height - 14, 2, stroke=0, fill=1)
    if task_number in {3, 6}:
        pdf.setFillColor(Color(TEAL.red, TEAL.green, TEAL.blue, alpha=.13))
        pdf.wedge(x + width - 42, y_top - 42, x + width, y_top, 90, 90, stroke=0, fill=1)
    if task_number not in {2, 6, 7} or is_special:
        band_color = NAVY if safe_title.upper() == "FOX CHALLENGE" else Color(border_color.red, border_color.green, border_color.blue, alpha=.14)
        pdf.setFillColor(band_color)
        pdf.roundRect(x + 1, y_top - 26, width - 2, 25, radius - 1, stroke=0, fill=1)
    if match:
        number, label = match.groups()
        badge_color = ORANGE if task_number in {1, 4, 5, 8} else TEAL
        pdf.setFillColor(badge_color)
        if task_number in {2, 6, 7}:
            pdf.roundRect(x + 8, y_top - 25, 24, 24, 6, stroke=0, fill=1)
        else:
            pdf.circle(x + 16, y_top - 13.5, 10, stroke=0, fill=1)
        pdf.setFillColor(white)
        pdf.setFont(FONT_BOLD, 8.4)
        pdf.drawCentredString(x + 20 if task_number in {2, 6, 7} else x + 16, y_top - 16.5, number)
        title_x, display = x + 38, label
    else:
        icon_kind = "lightning" if "CHALLENGE" in safe_title.upper() else "book"
        icon_fill = ORANGE if safe_title.upper() == "HELPER BOX" else accent
        draw_icon_badge(pdf, x + 17, y_top - 13.5, icon_kind, icon_fill, 9.5)
        title_x, display = x + 34, safe_title
    title_color = white if safe_title.upper() == "FOX CHALLENGE" else (ORANGE if safe_title.upper() == "HELPER BOX" else NAVY)
    pdf.setFillColor(title_color)
    title_size = 9.2
    while title_size > 6.8 and pdfmetrics.stringWidth(display, FONT_BOLD, title_size) > width - 44:
        title_size -= .3
    pdf.setFont(FONT_BOLD, title_size)
    pdf.drawString(title_x, y_top - 17, display)
    if task_number:
        icon_kind = task_icons[task_number]
        icon_color = ORANGE if task_number % 2 else TEAL
        draw_icon_badge(pdf, x + width - 17, y_top - 14, icon_kind, icon_color, 9.3)
    body_y = y_top - 38
    line_size = 8.45 if len(lines) >= 5 else 8.7
    leading = 10.35
    body_width = width - 24
    for raw in lines:
        wrapped = wrap_text(raw, FONT_REGULAR, line_size, body_width)
        for line in wrapped:
            if body_y < y_top - height + 8:
                break
            pdf.setFillColor(NAVY)
            pdf.setFont(FONT_REGULAR, line_size)
            pdf.drawString(x + 13, body_y, line)
            body_y -= leading
    if task_number in {1, 5, 7}:
        watermark = task_icons[task_number]
        draw_line_icon(pdf, watermark, x + width - 24, y_top - height + 23, 24, Color(TEAL.red, TEAL.green, TEAL.blue, alpha=.45))


def draw_premium_worksheet_page(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    body: str,
    page_number: int,
) -> int:
    blocks = parse_material_blocks(body)
    block_map = {re.sub(r"^TASK\s+\d+\s*[-:|]+\s*", "", pdf_safe_text(title), flags=re.I).upper(): (title, lines) for title, lines in blocks}
    by_task = {int(m.group(1)): (title, lines) for title, lines in blocks if (m := re.match(r"TASK\s+(\d+)", pdf_safe_text(title), re.I))}
    specials = {pdf_safe_text(title).upper(): (title, lines) for title, lines in blocks if not re.match(r"TASK\s+\d+", pdf_safe_text(title), re.I)}
    top = draw_premium_title(pdf, "PLAYER WORKSHEET", game.get("title", "Spy Hunt"), page_number, 22)
    page_width, _ = A4
    draw_premium_info_row(pdf, state, top - 37)
    mission_y = top - 47
    hero_h = 58
    pdf.setFillColor(PALE_TEAL)
    pdf.setStrokeColor(TEAL)
    pdf.setLineWidth(1.25)
    pdf.roundRect(32, mission_y - hero_h, page_width - 64, hero_h - 4, 10, stroke=1, fill=1)
    pdf.setFillColor(TEAL)
    hero_path = pdf.beginPath()
    hero_path.moveTo(33, mission_y - 4)
    hero_path.lineTo(75, mission_y - 4)
    hero_path.lineTo(69, mission_y - hero_h + 4)
    hero_path.lineTo(52, mission_y - hero_h + 14)
    hero_path.lineTo(34, mission_y - hero_h + 4)
    hero_path.close()
    pdf.drawPath(hero_path, stroke=0, fill=1)
    draw_line_icon(pdf, "search", 53, mission_y - 24, 18, white)
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_BOLD, 10.4)
    pdf.drawString(86, mission_y - 19, "MISSION")
    pdf.setFillColor(NAVY)
    pdf.setFont(FONT_REGULAR, 8.7)
    pdf.drawString(86, mission_y - 36, "Use am, is and are. Ask, record clues, and find the two spies.")
    draw_fox_mascot(pdf, page_width - 77, mission_y - 31, 1.25, detective=True)
    draw_paw(pdf, page_width - 132, mission_y - 40, .55, ORANGE)
    draw_paw(pdf, page_width - 150, mission_y - 24, .42, TEAL)
    x1, gap = 32, 9
    col_w = (page_width - 64 - gap) / 2
    x2 = x1 + col_w + gap
    grid_top = mission_y - hero_h - 7
    left_specs = [(1, 78), (2, 80), (3, 102), (4, 94)]
    right_specs = [(5, 72), (6, 84), (7, 64), (8, 72)]
    y = grid_top
    for number, height in left_specs:
        title, lines = by_task[number]
        draw_premium_task(pdf, x1, y, col_w, height, title, lines)
        y -= height + 6
    y = grid_top
    for number, height in right_specs:
        title, lines = by_task[number]
        draw_premium_task(pdf, x2, y, col_w, height, title, lines)
        y -= height + 6
    helper_title, helper_lines = specials["HELPER BOX"]
    draw_premium_task(pdf, x2, y, col_w, 72, helper_title, helper_lines, ORANGE)
    challenge_title, challenge_lines = specials["FOX CHALLENGE"]
    draw_premium_task(pdf, 32, 197, page_width - 64, 110, challenge_title, challenge_lines, ORANGE)
    pdf.setStrokeColor(ORANGE)
    pdf.setLineWidth(1)
    pdf.line(49, 112, page_width - 126, 112)
    pdf.line(49, 99, page_width - 126, 99)
    draw_icon_badge(pdf, page_width - 116, 111, "speech", TEAL, 8)
    draw_fox_mascot(pdf, page_width - 85, 120, 2.00, detective=True)
    draw_paw(pdf, page_width - 35, 94, .68, ORANGE)
    pdf.showPage()
    return page_number + 1


def draw_premium_teacher_page(
    pdf: canvas.Canvas,
    game: dict[str, Any],
    state: dict[str, Any],
    body: str,
    page_number: int,
) -> int:
    blocks = parse_material_blocks(body)[:9]
    top = draw_premium_title(pdf, "TEACHER MINI PACK", game.get("title", "Spy Hunt"), page_number, 25)
    page_width, _ = A4
    details = f"{state.get('level')}  •  age {state.get('age')}  •  {state.get('topic')}  •  {state.get('skill')}  •  5 minutes"
    pdf.setFillColor(TEAL)
    pdf.setFont(FONT_BOLD, 8)
    pdf.drawCentredString(page_width / 2, top - 8, pdf_safe_text(details))
    draw_teacher_fox_detective(pdf, page_width - 76, top + 28, 1.12)
    draw_paw(pdf, page_width - 112, top + 14, .52, ORANGE)
    draw_paw(pdf, page_width - 129, top + 26, .38, TEAL)
    margin, gap = 28, 7
    grid_top, grid_bottom = top - 22, 45
    col_w = (page_width - margin * 2 - gap * 2) / 3
    row_heights = [205, 198, 195]
    title_icons = ["play", "speech", "book", "heart", "hat", "clock", "ear", "trophy", "clipboard"]
    note_texts = [
        "MODEL FIRST • KEEP ROLES HIDDEN",
        "USE ENERGY • BUILD EXCITEMENT",
        "KEEP THIS LANGUAGE VISIBLE",
        "PRAISE CLEAR SPEAKING",
        "NEW DETAILS = NEW CLUES",
        "MORE CHALLENGE • MORE THINKING",
        "LOWER THE BARRIER, NOT THE GOAL",
        "REFLECT • REPORT • CELEBRATE",
        "READY MATERIALS = SMOOTH GAME",
    ]
    row_tops = [grid_top, grid_top - row_heights[0] - gap, grid_top - row_heights[0] - row_heights[1] - gap * 2]
    for index, (title, lines) in enumerate(blocks):
        row, col = divmod(index, 3)
        x = margin + col * (col_w + gap)
        y_top = row_tops[row]
        row_h = row_heights[row]
        fill_cycle = [PALE_TEAL, PALE_ORANGE, white, white, PALE_TEAL, CREAM, CREAM, white, PALE_TEAL]
        fill = fill_cycle[index]
        pdf.setFillColor(fill)
        border = TEAL if index in {0, 1, 2, 4} else ORANGE
        pdf.setStrokeColor(Color(border.red, border.green, border.blue, alpha=.65))
        pdf.setLineWidth(1.25 if index < 3 else .85)
        radius = 12 if index in {0, 2, 4, 7} else 7
        pdf.roundRect(x, y_top - row_h, col_w, row_h, radius, stroke=1, fill=1)
        if index in {3, 4}:
            pdf.setFillColor(Color(ORANGE.red, ORANGE.green, ORANGE.blue, alpha=.12))
            pdf.wedge(x + col_w - 48, y_top - 48, x + col_w, y_top, 90, 90, stroke=0, fill=1)
        if index in {5, 6, 7}:
            pdf.setFillColor(border)
            pdf.roundRect(x + 1, y_top - row_h + 8, 5, row_h - 16, 2, stroke=0, fill=1)
        pdf.setFillColor(NAVY)
        header_width = col_w - (18 if index < 3 else 31)
        pdf.roundRect(x + 12, y_top - 29, header_width, 25, 8, stroke=0, fill=1)
        icon_fill = ORANGE if index in {3, 4, 7} else TEAL
        draw_icon_badge(pdf, x + 15, y_top - 16, title_icons[index], icon_fill, 14 if index < 3 else 12.5)
        clean_title = pdf_safe_text(title)
        if index == 8:
            clean_title = "QUICK CHECK"
        title_size = 8.0 if index < 3 else 7.7
        while title_size > 5.8 and pdfmetrics.stringWidth(clean_title, FONT_BOLD, title_size) > col_w - 43:
            title_size -= .25
        pdf.setFillColor(white)
        pdf.setFont(FONT_BOLD, title_size)
        pdf.drawString(x + 33, y_top - 19, clean_title)
        body_y = y_top - 44
        body_lines = lines
        for line_index, raw in enumerate(body_lines):
            clean = pdf_safe_text(raw).lstrip("• ")
            body_size = 7.85 if index < 3 else 7.75
            wrapped = wrap_text(clean, FONT_REGULAR, body_size, col_w - 31)
            bullet_kind = "check" if index in {2, 8} else ("speech" if index in {1, 7} else "pencil")
            draw_icon_badge(pdf, x + 11.5, body_y + 1, bullet_kind, ORANGE if line_index % 2 == 0 else TEAL, 4.6)
            for wrapped_line in wrapped[:3]:
                if body_y < y_top - row_h + 40:
                    break
                pdf.setFillColor(NAVY)
                pdf.setFont(FONT_REGULAR, body_size)
                pdf.drawString(x + 19, body_y - 1.5, wrapped_line)
                body_y -= 9.15
            body_y -= 3.3
        note_y = y_top - row_h + 12
        note_size = 5.7
        note_text = note_texts[index]
        while note_size > 4.5 and pdfmetrics.stringWidth(note_text, FONT_BOLD, note_size) > col_w - 48:
            note_size -= .2
        if index in {0, 1, 8}:
            pdf.saveState()
            pdf.setDash(3, 2)
            pdf.setStrokeColor(TEAL)
            pdf.setFillColor(white)
            pdf.roundRect(x + 10, note_y, col_w - 20, 27, 6, stroke=1, fill=1)
            pdf.restoreState()
            draw_icon_badge(pdf, x + 21, note_y + 13.5, "clipboard" if index in {0, 8} else "speech", TEAL, 6.5)
            note_center_y = note_y + 10.5
        else:
            pdf.setFillColor(Color(TEAL.red, TEAL.green, TEAL.blue, alpha=.12))
            pdf.roundRect(x + 12, note_y + 3, col_w - 24, 21, 10, stroke=0, fill=1)
            accent_icon = ["heart", "hat", "clock", "book", "trophy"][index - 3]
            draw_icon_badge(pdf, x + 22, note_y + 13.5, accent_icon, icon_fill, 6)
            note_center_y = note_y + 10.5
        pdf.setFillColor(NAVY)
        pdf.setFont(FONT_BOLD, note_size)
        pdf.drawCentredString(x + col_w / 2 + 8, note_center_y, note_text)
        if index in {0, 4, 7}:
            draw_fox_mascot(pdf, x + col_w - 18, y_top - row_h + 54, .40, detective=index != 0)
        else:
            accent_kind = title_icons[index]
            draw_line_icon(pdf, accent_kind, x + col_w - 19, y_top - row_h + 51, 17, Color(TEAL.red, TEAL.green, TEAL.blue, alpha=.55))
    pdf.setFillColor(ORANGE)
    pdf.setFont(FONT_BOLD, 9)
    pdf.drawCentredString(page_width / 2, 32, "READY TO TEACH • READY TO PLAY")
    pdf.showPage()
    return page_number + 1


def create_printable_pack(
    game: dict[str, Any],
    state: dict[str, Any],
    cards_text: str,
    worksheet_text: str,
    mini_pack_text: str,
    output_dir: Path | None = None,
    output_path: Path | None = None,
    include_cover: bool = True,
) -> tuple[Path, int]:
    register_pdf_fonts()
    output_path = output_path or unique_pdf_path(game.get("title", "Game"), str(state.get("level") or "Level"), output_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = output_path.with_name(f".{output_path.stem}.{uuid4().hex}.tmp.pdf")
    try:
        pdf = canvas.Canvas(str(temp_path), pagesize=A4, pageCompression=1)
        pdf.setTitle(pdf_safe_text(f"Fox Game Lab - {game.get('title', 'Game')}"))
        pdf.setAuthor("Fox Game Lab")
        page_number = 1
        premium_spy_hunt = (
            pdf_safe_text(game.get("title", "")).lower() == "spy hunt"
            and pdf_safe_text(state.get("level", "")).upper() == "A1"
            and pdf_safe_text(state.get("topic", "")).lower() == "to be"
            and pdf_safe_text(state.get("age", "")) == "9"
        )
        if premium_spy_hunt and not include_cover:
            page_number = draw_premium_cards_page(pdf, game, state, cards_text, page_number)
            page_number = draw_premium_worksheet_page(pdf, game, state, worksheet_text, page_number)
            page_number = draw_premium_teacher_page(pdf, game, state, mini_pack_text, page_number)
        elif include_cover:
            draw_cover(pdf, game, state, page_number)
            page_number += 1
            page_number = draw_cards_pages(pdf, game, state, cards_text, page_number)
            page_number = draw_worksheet_pages(
                pdf,
                game,
                state,
                worksheet_text,
                page_number,
            )
            page_number = draw_teacher_pack_pages(
                pdf,
                game,
                state,
                mini_pack_text,
                page_number,
            )
        else:
            page_number = draw_cards_pages(pdf, game, state, cards_text, page_number)
            page_number = draw_worksheet_pages(
                pdf,
                game,
                state,
                worksheet_text,
                page_number,
            )
            page_number = draw_teacher_pack_pages(
                pdf,
                game,
                state,
                mini_pack_text,
                page_number,
            )
        pdf.save()
        os.replace(temp_path, output_path)
        reader = PdfReader(str(output_path))
        if not reader.pages or output_path.stat().st_size <= 0:
            raise ValueError("Created PDF is empty")
        return output_path, len(reader.pages)
    finally:
        if temp_path.exists():
            temp_path.unlink()
