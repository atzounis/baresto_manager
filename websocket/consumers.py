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
        self.group_name = f"waiter.{staff_id}"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

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
