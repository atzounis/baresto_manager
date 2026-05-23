from rest_framework import serializers

from apps.accounts.models import EmployeeProfile
from apps.menus.models import Allergen, Menu, MenuCategory, MenuItem, ModifierGroup, ModifierOption
from apps.orders.models import Bill, Order, OrderItem
from apps.orders.services import add_item_to_order, confirm_order, create_order
from apps.restaurants.models import Branch, Restaurant, Table, TableSession


class RestaurantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Restaurant
        fields = ["id", "name", "primary_color", "default_language", "is_active"]


class BranchSerializer(serializers.ModelSerializer):
    class Meta:
        model = Branch
        fields = ["id", "name", "address", "phone", "timezone", "is_active"]


class TableSerializer(serializers.ModelSerializer):
    class Meta:
        model = Table
        fields = ["id", "number", "label", "capacity", "status", "qr_token"]


class TableSessionSerializer(serializers.ModelSerializer):
    table = TableSerializer(read_only=True)

    class Meta:
        model = TableSession
        fields = ["id", "table", "cover_count", "is_active", "opened_at"]


class ModifierOptionSerializer(serializers.ModelSerializer):
    class Meta:
        model = ModifierOption
        fields = ["id", "name", "price_delta"]


class ModifierGroupSerializer(serializers.ModelSerializer):
    options = ModifierOptionSerializer(many=True, read_only=True)

    class Meta:
        model = ModifierGroup
        fields = ["id", "name", "is_required", "min_select", "max_select", "options"]


class AllergenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Allergen
        fields = ["id", "name", "icon"]


class MenuItemSerializer(serializers.ModelSerializer):
    modifier_groups = ModifierGroupSerializer(many=True, read_only=True)
    allergens = AllergenSerializer(many=True, read_only=True)

    class Meta:
        model = MenuItem
        fields = [
            "id",
            "name",
            "description",
            "image",
            "price",
            "happy_hour_price",
            "preparation_time",
            "is_available",
            "is_featured",
            "is_vegetarian",
            "is_vegan",
            "calories",
            "protein_g",
            "carbohydrates_g",
            "fat_g",
            "fiber_g",
            "salt_g",
            "allergens",
            "modifier_groups",
        ]


class MenuCategorySerializer(serializers.ModelSerializer):
    items = MenuItemSerializer(many=True, read_only=True)

    class Meta:
        model = MenuCategory
        fields = ["id", "name", "description", "sort_order", "items"]


class MenuSerializer(serializers.ModelSerializer):
    categories = MenuCategorySerializer(many=True, read_only=True)

    class Meta:
        model = Menu
        fields = ["id", "name", "is_active", "is_draft", "published_at", "categories"]


class OrderItemSerializer(serializers.ModelSerializer):
    menu_item_name = serializers.CharField(source="menu_item.name", read_only=True)
    line_total = serializers.SerializerMethodField()

    def get_line_total(self, obj):
        return obj.line_total

    class Meta:
        model = OrderItem
        fields = [
            "id",
            "menu_item",
            "menu_item_name",
            "quantity",
            "unit_price",
            "station",
            "notes",
            "status",
            "line_total",
        ]
        read_only_fields = ["unit_price"]


class OrderSerializer(serializers.ModelSerializer):
    items = OrderItemSerializer(many=True, read_only=True)
    table_label = serializers.SerializerMethodField()

    class Meta:
        model = Order
        fields = [
            "id",
            "session",
            "waiter",
            "status",
            "notes",
            "is_priority",
            "items",
            "subtotal",
            "table_label",
            "created_at",
        ]
        read_only_fields = ["subtotal", "table_label"]

    def get_table_label(self, obj):
        return str(obj.session.table)


class OrderCreateSerializer(serializers.Serializer):
    session_id = serializers.IntegerField()
    notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        session = TableSession.objects.select_related("table").get(pk=validated_data["session_id"])
        waiter = self.context["request"].user.employee_profile
        return create_order(session, waiter, validated_data.get("notes", ""))


class OrderItemCreateSerializer(serializers.Serializer):
    menu_item_id = serializers.IntegerField()
    quantity = serializers.IntegerField(min_value=1, default=1)
    modifier_ids = serializers.ListField(child=serializers.IntegerField(), required=False)
    station = serializers.ChoiceField(choices=["kitchen", "bar", "grill"], default="kitchen")
    notes = serializers.CharField(required=False, allow_blank=True)

    def create(self, validated_data):
        order = self.context["order"]
        menu_item = MenuItem.objects.get(pk=validated_data["menu_item_id"])
        return add_item_to_order(
            order,
            menu_item,
            quantity=validated_data.get("quantity", 1),
            modifier_ids=validated_data.get("modifier_ids"),
            station=validated_data.get("station", "kitchen"),
            notes=validated_data.get("notes", ""),
        )


class BillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Bill
        fields = [
            "id",
            "order",
            "subtotal",
            "tax",
            "discount",
            "total",
            "payment_method",
            "is_paid",
            "paid_at",
        ]


class EmployeeProfileSerializer(serializers.ModelSerializer):
    username = serializers.CharField(source="user.username", read_only=True)

    class Meta:
        model = EmployeeProfile
        fields = ["id", "username", "role", "is_active_shift", "restaurant", "branch"]
