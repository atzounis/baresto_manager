from django.urls import path

from . import views

urlpatterns = [
    path("orders/new/<int:session_id>/", views.OrderCreateView.as_view(), name="order_new"),
    path("sessions/<int:session_id>/close/", views.CloseTableView.as_view(), name="close_table"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/confirm/", views.OrderConfirmView.as_view(), name="order_confirm"),
    path("orders/<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="order_status"),
]
