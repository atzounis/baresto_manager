from django.urls import path
from django.views.generic import RedirectView

from . import views

urlpatterns = [
    path("dashboard/", RedirectView.as_view(pattern_name="tables", permanent=False), name="dashboard"),
    path("reports/", views.ReportsView.as_view(), name="reports"),
    path("reports/export/", views.ReportsExportView.as_view(), name="reports_export"),
]
