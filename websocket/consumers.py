import json

from channels.generic.websocket import AsyncWebsocketConsumer


def _get_staff_branch(user):
    profile = getattr(user, "employee_profile", None)
    if not profile:
        return None
    if profile.branch_id:
        return profile.branch
    return profile.restaurant.branches.filter(is_active=True).first()


class KitchenConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        user = self.scope["user"]
        if user.is_anonymous:
            await self.close()
            return
        branch = _get_staff_branch(user)
        if not branch and not user.is_superuser:
            await self.close()
            return
        if branch:
            self.group_name = f"kitchen.{branch.id}"
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
        branch = _get_staff_branch(user)
        if not branch and not user.is_superuser:
            await self.close()
            return
        if branch:
            self.group_name = f"dashboard.{branch.id}"
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
        profile = getattr(user, "employee_profile", None)
        if profile and profile.pk != staff_id and not user.is_superuser:
            await self.close()
            return

        self.group_names = [f"waiter.{staff_id}"]
        branch = _get_staff_branch(user)
        if profile and profile.role in self.ALERT_ROLES:
            if branch:
                self.group_names.append(f"waiters.branch.{branch.id}")
            restaurant = profile.restaurant
            if restaurant:
                self.group_names.append(f"waiters.restaurant.{restaurant.id}")

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
