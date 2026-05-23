from django.urls import path

from . import views

urlpatterns = [
    path("waiter/alerts/", views.WaiterAlertsPollView.as_view(), name="waiter_alerts_poll"),
    path("orders/items/<int:pk>/served/", views.WaiterItemServedView.as_view(), name="waiter_item_served"),
    path("orders/", views.OrderHistoryListView.as_view(), name="order_history"),
    path("orders/new/<int:session_id>/", views.OrderCreateView.as_view(), name="order_new"),
    path("sessions/<int:session_id>/close/", views.CloseTableView.as_view(), name="close_table"),
    path("orders/<int:pk>/receipt/", views.OrderReceiptView.as_view(), name="order_receipt"),
    path("orders/<int:pk>/receipt/print/", views.OrderReceiptPrintView.as_view(), name="order_receipt_print"),
    path("orders/<int:pk>/receipt/print-now/", views.OrderReceiptQuickPrintView.as_view(), name="order_receipt_print_now"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order_detail"),
    path("orders/<int:pk>/confirm/", views.OrderConfirmView.as_view(), name="order_confirm"),
    path("orders/<int:pk>/status/", views.OrderStatusUpdateView.as_view(), name="order_status"),
]
