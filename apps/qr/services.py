import base64
import io

import qrcode
from django.conf import settings
from django.core.files.base import ContentFile


def build_table_qr_url(table):
    return f"{settings.SITE_BASE_URL}/qr/{table.qr_token}/"


def build_shared_menu_qr_url(restaurant):
    return f"{settings.SITE_BASE_URL}/qr/menu/{restaurant.menu_qr_token}/"


def qr_png_bytes(url, *, box_size=10, border=2):
    img = qrcode.make(url, box_size=box_size, border=border)
    buffer = io.BytesIO()
    img.save(buffer, format="PNG")
    return buffer.getvalue()


def qr_png_data_uri(url, **kwargs):
    raw = qr_png_bytes(url, **kwargs)
    encoded = base64.b64encode(raw).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def generate_table_qr(table, save=True):
    url = build_table_qr_url(table)
    raw = qr_png_bytes(url)
    filename = f"table_{table.pk}_{table.qr_token}.png"
    table.qr_code.save(filename, ContentFile(raw), save=save)
    return table


# Backwards compatibility
build_qr_url = build_table_qr_url
