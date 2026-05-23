from django.urls import path

from . import views

urlpatterns = [
    path("tables/", views.TableFloorView.as_view(), name="tables"),
    path("tables/ready-counts/", views.TableReadyCountsView.as_view(), name="table_ready_counts"),
    path("floors/", views.FloorAPIView.as_view(), name="floor_api"),
    path("floors/<int:pk>/", views.FloorDetailAPIView.as_view(), name="floor_detail_api"),
    path("tables/new/", views.TableCreateView.as_view(), name="table_create"),
    path("tables/<int:pk>/edit/", views.TableUpdateView.as_view(), name="table_update"),
    path("tables/<int:pk>/delete/", views.TableDeleteView.as_view(), name="table_delete"),
    path("tables/plan/save/", views.FloorPlanSaveView.as_view(), name="floor_plan_save"),
    path("tables/<int:pk>/assign/", views.AssignWaiterView.as_view(), name="table_assign"),
    path("tables/<int:table_id>/open/", views.OpenSessionView.as_view(), name="table_open"),
    path("company/", views.CompanyDetailsView.as_view(), name="company_details"),
]
