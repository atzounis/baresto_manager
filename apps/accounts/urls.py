from django.urls import path

from . import staff_views, views

urlpatterns = [
    path("", views.HomeView.as_view(), name="home"),
    path("login/", views.StaffLoginView.as_view(), name="login"),
    path("login/pin/", views.PinLoginView.as_view(), name="pin_login"),
    path("logout/", views.StaffLogoutView.as_view(), name="logout"),
    path("staff/users/", staff_views.StaffUserListView.as_view(), name="staff_user_list"),
    path("staff/users/new/", staff_views.StaffUserCreateView.as_view(), name="staff_user_create"),
    path("staff/users/<int:pk>/edit/", staff_views.StaffUserUpdateView.as_view(), name="staff_user_edit"),
]
