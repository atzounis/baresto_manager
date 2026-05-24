from django.urls import path

from . import views

urlpatterns = [
    path("kitchen/", views.KitchenDisplayView.as_view(), name="kitchen"),
    path("kitchen/alerts/", views.KitchenAlertsPollView.as_view(), name="kitchen_alerts_poll"),
    path("kitchen/items/<int:pk>/status/", views.KitchenItemStatusView.as_view(), name="kitchen_item_status"),
]
