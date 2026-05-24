"""Serve uploaded media in local dev when DEBUG is False."""

from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404


def serve_media_dev(request, path):
    media_root = Path(settings.MEDIA_ROOT).resolve()
    file_path = (media_root / path).resolve()
    if not str(file_path).startswith(str(media_root)) or not file_path.is_file():
        raise Http404
    return FileResponse(file_path.open("rb"))
