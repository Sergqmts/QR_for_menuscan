import io
import os
import boto3
from botocore.config import Config
import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from PIL import Image

from app.core.config import settings

_FONTS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "fonts")
_RL_FONTS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..", "..", "..",
    # reportlab ships Vera fonts inside the package
)

def _register_fonts() -> tuple[str, str]:
    """Return (regular_font, bold_font) names, registering TTF if needed."""
    try:
        import reportlab
        rl_fonts = os.path.join(os.path.dirname(reportlab.__file__), "fonts")
        pdfmetrics.registerFont(TTFont("_Vera", os.path.join(rl_fonts, "Vera.ttf")))
        pdfmetrics.registerFont(TTFont("_VeraBd", os.path.join(rl_fonts, "VeraBd.ttf")))
        return "_Vera", "_VeraBd"
    except Exception:
        return "Helvetica", "Helvetica-Bold"


_FONT_REG, _FONT_BOLD = _register_fonts()


def generate_qr_image_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(version=None, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_qr_pdf(venue_name: str, qr_entries: list[dict]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    page_width, page_height = A4
    cols, rows = 2, 2
    per_page = cols * rows
    qr_size = 7 * cm
    cell_w = page_width / cols
    cell_h = (page_height - 3 * cm) / rows

    for page_start in range(0, max(len(qr_entries), 1), per_page):
        page_entries = qr_entries[page_start:page_start + per_page]
        c.setFont(_FONT_BOLD, 14)
        c.drawCentredString(page_width / 2, page_height - 1.5 * cm, venue_name)

        for idx, entry in enumerate(page_entries):
            col = idx % cols
            row = idx // cols
            x = col * cell_w + (cell_w - qr_size) / 2
            y = page_height - 3 * cm - (row + 1) * cell_h + (cell_h - qr_size) / 2
            qr_img = Image.open(io.BytesIO(generate_qr_image_bytes(entry["url"])))
            c.drawImage(ImageReader(qr_img), x, y, width=qr_size, height=qr_size)
            c.setFont(_FONT_BOLD, 12)
            c.drawCentredString(col * cell_w + cell_w / 2, y - 0.6 * cm, f"Стол {entry['table_number']}")

        c.showPage()

    c.save()
    return buf.getvalue()


def _get_s3_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint_url,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        config=Config(signature_version="s3v4"),
    )


def ensure_bucket_exists() -> None:
    s3 = _get_s3_client()
    try:
        s3.head_bucket(Bucket=settings.s3_bucket_name)
    except Exception:
        s3.create_bucket(Bucket=settings.s3_bucket_name)
        s3.put_bucket_policy(
            Bucket=settings.s3_bucket_name,
            Policy=(
                '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":"*",'
                '"Action":"s3:GetObject","Resource":"arn:aws:s3:::' + settings.s3_bucket_name + '/*"}]}'
            )
        )


def upload_pdf_to_s3(pdf_bytes: bytes, key: str) -> str:
    ensure_bucket_exists()
    _get_s3_client().put_object(
        Bucket=settings.s3_bucket_name, Key=key, Body=pdf_bytes, ContentType="application/pdf"
    )
    return f"{settings.s3_public_url}/{key}"


def get_presigned_upload_url(key: str) -> tuple[str, str]:
    s3 = _get_s3_client()
    upload_url = s3.generate_presigned_url(
        "put_object",
        Params={"Bucket": settings.s3_bucket_name, "Key": key, "ContentType": "image/jpeg"},
        ExpiresIn=300,
    )
    image_url = f"{settings.s3_public_url}/{key}"
    return upload_url, image_url
