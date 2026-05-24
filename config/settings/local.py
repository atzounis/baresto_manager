import socket

from .base import *  # noqa: F403

DEBUG = True

# Local dev never requires a Redis daemon. (Production uses Redis via config/settings/production.py.)
CACHES = {  # noqa: F405
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "baresto-local",
    }
}

INSTALLED_APPS += ["debug_toolbar"]  # noqa: F405

MIDDLEWARE.insert(0, "debug_toolbar.middleware.DebugToolbarMiddleware")  # noqa: F405

INTERNAL_IPS = ["127.0.0.1", "localhost"]

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"


def _detect_lan_ip():
    """Primary LAN IPv4 (for phone/tablet access on the same Wi‑Fi)."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(0.1)
        sock.connect(("10.255.255.255", 1))
        ip = sock.getsockname()[0]
        sock.close()
        return ip
    except OSError:
        return None


# Extend .env ALLOWED_HOSTS with this machine's LAN IP in local dev.
ALLOWED_HOSTS = list(ALLOWED_HOSTS)  # noqa: F405
_lan_ip = _detect_lan_ip()
LAN_IP = _lan_ip
if _lan_ip and _lan_ip not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_lan_ip)
    if _lan_ip not in INTERNAL_IPS:
        INTERNAL_IPS.append(_lan_ip)

# QR codes / guest menu links: use LAN IP when SITE_BASE_URL still points at localhost.
if _lan_ip and env.bool("SITE_BASE_URL_AUTO_LAN", default=True):  # noqa: F405
    from urllib.parse import urlparse

    _site = urlparse(SITE_BASE_URL)  # noqa: F405
    if (_site.hostname or "") in ("127.0.0.1", "localhost", "[::1]"):
        _port = _site.port or DJANGO_PORT  # noqa: F405
        _scheme = _site.scheme or "http"
        SITE_BASE_URL = f"{_scheme}://{_lan_ip}:{_port}"  # noqa: F405

# Optional extra hosts (e.g. ALLOWED_HOSTS_EXTRA=192.168.1.50,myhost.local)
ALLOWED_HOSTS.extend(env.list("ALLOWED_HOSTS_EXTRA", default=[]))  # noqa: F405

# Required for login/forms when opening the app via http://<LAN-IP>:8765 on a phone.
_csrf_origins = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405
for host in ALLOWED_HOSTS:
    if host in ("localhost", "127.0.0.1", "[::1]"):
        _csrf_origins.append(f"http://{host}:{DJANGO_PORT}")  # noqa: F405
        _csrf_origins.append(f"https://{host}:{DJANGO_PORT}")  # noqa: F405
    elif host and host != "*":
        _csrf_origins.append(f"http://{host}:{DJANGO_PORT}")  # noqa: F405
CSRF_TRUSTED_ORIGINS = list(dict.fromkeys(_csrf_origins))
