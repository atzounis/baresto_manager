#!/usr/bin/env python
import os
import sys


def _inject_runserver_port(argv):
    """Use DJANGO_PORT (default 8765) when runserver has no addr:port."""
    if len(argv) < 2 or argv[1] != "runserver":
        return argv
    if any(not arg.startswith("-") for arg in argv[2:]):
        return argv
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    import django

    django.setup()
    from django.conf import settings

    port = getattr(settings, "DJANGO_PORT", 8765)
    return [*argv, f"127.0.0.1:{port}"]


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable?"
        ) from exc
    execute_from_command_line(_inject_runserver_port(sys.argv))


if __name__ == "__main__":
    main()
