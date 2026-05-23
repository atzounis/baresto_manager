from django.apps import AppConfig


class MenusConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.menus"

    def ready(self):
        from . import translation  # noqa: F401
