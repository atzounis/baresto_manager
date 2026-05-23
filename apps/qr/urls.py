from django.urls import path

from . import views

urlpatterns = [
    path("qr/menu/<uuid:menu_token>/", views.GuestMenuSharedView.as_view(), name="guest_menu_shared"),
    path("qr/<uuid:table_token>/", views.GuestMenuView.as_view(), name="guest_menu"),
]
