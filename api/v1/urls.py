from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from . import views

router = DefaultRouter()
router.register("menus", views.MenuViewSet, basename="menu")
router.register("menu-items", views.MenuItemViewSet, basename="menu-item")
router.register("tables", views.TableViewSet, basename="table")
router.register("sessions", views.TableSessionViewSet, basename="session")
router.register("orders", views.OrderViewSet, basename="order")

urlpatterns = [
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("order-items/<int:pk>/status/", views.OrderItemStatusView.as_view(), name="order-item-status"),
    path("", include(router.urls)),
]
