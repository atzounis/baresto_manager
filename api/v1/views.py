from django.shortcuts import get_object_or_404
from rest_framework import generics, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.common.permissions import get_employee_role, role_has_permission
from apps.menus.models import Menu, MenuItem
from apps.orders.models import Order, OrderItem
from apps.orders.services import confirm_order, create_bill, update_item_status
from apps.restaurants.models import Table, TableSession

from .serializers import (
    BillSerializer,
    MenuItemSerializer,
    MenuSerializer,
    OrderCreateSerializer,
    OrderItemCreateSerializer,
    OrderItemSerializer,
    OrderSerializer,
    TableSerializer,
    TableSessionSerializer,
)


class RestaurantScopedMixin:
    def get_restaurant(self):
        return self.request.user.employee_profile.restaurant

    def filter_by_restaurant(self, qs):
        return qs.filter(restaurant=self.get_restaurant())


class MenuViewSet(RestaurantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = MenuSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Menu.objects.filter(restaurant=self.get_restaurant(), is_active=True)
            .prefetch_related("categories__items__modifier_groups__options")
        )


class MenuItemViewSet(RestaurantScopedMixin, viewsets.GenericViewSet):
    serializer_class = MenuItemSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return MenuItem.objects.filter(category__menu__restaurant=self.get_restaurant())

    @action(detail=True, methods=["post"])
    def toggle_availability(self, request, pk=None):
        if not role_has_permission(get_employee_role(request.user), "edit_menu"):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        item = self.get_object()
        item.is_available = not item.is_available
        item.save(update_fields=["is_available", "updated_at"])
        return Response(self.get_serializer(item).data)


class TableViewSet(RestaurantScopedMixin, viewsets.ReadOnlyModelViewSet):
    serializer_class = TableSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return (
            Table.objects.filter(floor__branch__restaurant=self.get_restaurant())
            .select_related("floor__branch", "assigned_to__user")
        )


class TableSessionViewSet(RestaurantScopedMixin, viewsets.ModelViewSet):
    serializer_class = TableSessionSerializer
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post"]

    def get_queryset(self):
        return TableSession.objects.filter(
            table__floor__branch__restaurant=self.get_restaurant(),
            is_active=True,
        ).select_related("table")


class OrderViewSet(RestaurantScopedMixin, viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated]
    http_method_names = ["get", "post", "patch"]

    def get_queryset(self):
        return (
            Order.objects.filter(session__table__floor__branch__restaurant=self.get_restaurant())
            .select_related("session__table", "waiter__user")
            .prefetch_related("items__menu_item", "items__modifiers")
        )

    def get_serializer_class(self):
        if self.action == "create":
            return OrderCreateSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        if not role_has_permission(get_employee_role(request.user), "take_order"):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        serializer = OrderCreateSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        order = self.get_object()
        confirm_order(order, request.user, request)
        return Response(OrderSerializer(order).data)

    @action(detail=True, methods=["post"], url_path="items")
    def add_item(self, request, pk=None):
        order = self.get_object()
        serializer = OrderItemCreateSerializer(data=request.data, context={"order": order})
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(OrderItemSerializer(item).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["post"])
    def bill(self, request, pk=None):
        if not role_has_permission(get_employee_role(request.user), "close_bill"):
            return Response({"detail": "Forbidden"}, status=status.HTTP_403_FORBIDDEN)
        order = self.get_object()
        bill = create_bill(order)
        return Response(BillSerializer(bill).data)


class OrderItemStatusView(generics.GenericAPIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        item = get_object_or_404(
            OrderItem.objects.select_related("order__session__table__floor__branch"),
            pk=pk,
            order__session__table__floor__branch__restaurant=request.user.employee_profile.restaurant,
        )
        new_status = request.data.get("status")
        if new_status not in dict(OrderItem.STATUS_CHOICES):
            return Response({"detail": "Invalid status"}, status=status.HTTP_400_BAD_REQUEST)
        update_item_status(item, new_status, request.user, request)
        return Response(OrderItemSerializer(item).data)
