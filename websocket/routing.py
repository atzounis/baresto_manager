from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/kitchen/$", consumers.KitchenConsumer.as_asgi()),
    re_path(r"ws/dashboard/$", consumers.DashboardConsumer.as_asgi()),
    re_path(r"ws/waiter/(?P<staff_id>\d+)/$", consumers.WaiterConsumer.as_asgi()),
    re_path(r"ws/table/(?P<table_id>\d+)/$", consumers.TableConsumer.as_asgi()),
]
