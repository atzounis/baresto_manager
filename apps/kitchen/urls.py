from django.urls import path

from . import views

urlpatterns = [
    path("kitchen/", views.KitchenDisplayView.as_view(), name="kitchen"),
    path("kitchen/items/<int:pk>/status/", views.KitchenItemStatusView.as_view(), name="kitchen_item_status"),
]
