import json

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer


def _load_staff_ws_context(user_id):
    """Load staff profile + branch IDs for WebSocket group membership (sync ORM)."""
    from apps.accounts.models import EmployeeProfile

    profile = (
        EmployeeProfile.objects.select_related("branch", "restaurant")
        .filter(user_id=user_id)
        .first()
    )
    if not profile:
        return None

    branch = profile.branch
    if branch is None and profile.restaurant_id:
        branch = profile.restaurant.branches.filter(is_active=True).only("id").first()

    return {
        "profile_id": profile.pk,
        "role": profile.role,
        "restaurant_id": profile.restaurant_id,
        "branch_id": branch.pk if branch else None,
    }


class KitchenConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        ctx = await database_sync_to_async(_load_staff_ws_context)(user.pk)
        branch_id = ctx["branch_id"] if ctx else None
        if not branch_id and not user.is_superuser:
            await self.close()
            return
        if branch_id:
            self.group_name = f"kitchen.{branch_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def kitchen_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))


class DashboardConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return

        ctx = await database_sync_to_async(_load_staff_ws_context)(user.pk)
        branch_id = ctx["branch_id"] if ctx else None
        if not branch_id and not user.is_superuser:
            await self.close()
            return
        if branch_id:
            self.group_name = f"dashboard.{branch_id}"
            await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        if hasattr(self, "group_name"):
            await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def dashboard_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))


class WaiterConsumer(AsyncWebsocketConsumer):
    """Personal + branch-wide groups so any waiter tablet gets kitchen-ready alerts."""

    ALERT_ROLES = frozenset({"waiter", "cashier", "manager", "admin"})

    async def connect(self):
        user = self.scope["user"]
        staff_id = int(self.scope["url_route"]["kwargs"]["staff_id"])
        if user.is_anonymous:
            await self.close()
            return

        ctx = await database_sync_to_async(_load_staff_ws_context)(user.pk)
        if ctx and ctx["profile_id"] != staff_id and not user.is_superuser:
            await self.close()
            return

        self.group_names = [f"waiter.{staff_id}"]
        if ctx and ctx["role"] in self.ALERT_ROLES:
            if ctx["branch_id"]:
                self.group_names.append(f"waiters.branch.{ctx['branch_id']}")
            if ctx["restaurant_id"]:
                self.group_names.append(f"waiters.restaurant.{ctx['restaurant_id']}")

        for group_name in self.group_names:
            await self.channel_layer.group_add(group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        for group_name in getattr(self, "group_names", []):
            await self.channel_layer.group_discard(group_name, self.channel_name)

    async def waiter_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))


class TableConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        table_id = self.scope["url_route"]["kwargs"]["table_id"]
        self.group_name = f"table.{table_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    async def table_message(self, event):
        await self.send(text_data=json.dumps(event["payload"]))
