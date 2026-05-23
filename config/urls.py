from django.conf import settings
from django.conf.urls.static import static
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

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    try:
        import debug_toolbar

        urlpatterns = [path("__debug__/", include(debug_toolbar.urls))] + urlpatterns
    except ImportError:
        pass
