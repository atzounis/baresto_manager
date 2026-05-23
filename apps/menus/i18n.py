"""Helpers for modeltranslation-backed menu labels."""

from django.utils.translation import get_language


def localized_name(obj, *, base: str = "name") -> str:
    """Return name for the active UI language, with fallback to the other language."""
    if obj is None:
        return ""
    lang = (get_language() or "el")[:2]
    el = (getattr(obj, f"{base}_el", None) or "").strip()
    en = (getattr(obj, f"{base}_en", None) or "").strip()
    legacy = (getattr(obj, base, None) or "").strip()
    if lang == "en":
        return en or el or legacy
    return el or en or legacy


def has_localized_name(obj, *, base: str = "name") -> bool:
    return bool(localized_name(obj, base=base))
