from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("i18n/", include("django.conf.urls.i18n")),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("", include("apps.accounts.urls")),
    path("", include("apps.restaurants.urls")),
    path("", include("apps.orders.urls")),
    path("", include("apps.kitchen.urls")),
    path("", include("apps.analytics.urls")),
    path("", include("apps.menus.urls")),
    path("", include("apps.qr.urls")),
]

if settings.DEBUG or getattr(settings, "SERVE_STATIC_IN_DEV", False):
    from django.contrib.staticfiles.views import serve as staticfiles_serve
    from django.urls import re_path

    from config.dev_media import serve_media_dev

    urlpatterns += [
        re_path(r"^static/(?P<path>.*)$", staticfiles_serve, kwargs={"insecure": True}),
        re_path(r"^media/(?P<path>.*)$", serve_media_dev),
    ]

if settings.DEBUG:
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
