from django.urls import path

from . import views

urlpatterns = [
    path("qr/menu/<uuid:menu_token>/", views.GuestMenuSharedView.as_view(), name="guest_menu_shared"),
    path(
        "qr/menu/<uuid:menu_token>/call-waiter/",
        views.GuestCallWaiterSharedView.as_view(),
        name="guest_call_waiter_shared",
    ),
    path("qr/<uuid:table_token>/", views.GuestMenuView.as_view(), name="guest_menu"),
    path(
        "qr/<uuid:table_token>/call-waiter/",
        views.GuestCallWaiterTableView.as_view(),
        name="guest_call_waiter",
    ),
]
