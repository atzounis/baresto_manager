from django.urls import path

from apps.qr.views import GuestMenuHubView, GuestMenuPrintView

from . import views

urlpatterns = [
    path("menu/", views.MenuManageView.as_view(), name="menu_manage"),
    path("menu/guest/", GuestMenuHubView.as_view(), name="guest_menu_hub"),
    path("menu/guest/print/", GuestMenuPrintView.as_view(), name="guest_menu_qr_print"),
    path("menu/items/new/", views.MenuItemCreateView.as_view(), name="menu_item_create"),
    path("menu/items/<int:pk>/edit/", views.MenuItemUpdateView.as_view(), name="menu_item_edit"),
    path("menu/items/<int:pk>/delete/", views.MenuItemDeleteView.as_view(), name="menu_item_delete"),
    path("menu/items/<int:pk>/toggle/", views.MenuItemToggleView.as_view(), name="menu_item_toggle"),
    path("menu/categories/new/", views.MenuCategoryCreateView.as_view(), name="menu_category_create"),
    path(
        "menu/categories/<int:pk>/delete/",
        views.MenuCategoryDeleteView.as_view(),
        name="menu_category_delete",
    ),
]
