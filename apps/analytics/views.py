import json

from django.http import HttpResponse
from django.utils.translation import gettext as _
from django.views import View
from django.views.generic import TemplateView
from apps.analytics.reports import (
    branch_timezone,
    build_reports_csv,
    daily_series,
    parse_report_date_range,
    range_datetimes,
    report_summary,
    today_in_branch,
    top_items,
    top_items_chart,
)
from apps.common.mixins import RestaurantScopedMixin
from apps.common.permissions import RolePermissionMixin


class ReportsView(RestaurantScopedMixin, RolePermissionMixin, TemplateView):
    template_name = "reports.html"
    required_permission = "view_analytics"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        branch = self.get_branch()
        if not branch:
            ctx.update(self._empty_context())
            return ctx

        tz = branch_timezone(branch)
        date_from, date_to, error = parse_report_date_range(self.request, branch)
        start, end = range_datetimes(date_from, date_to, tz)

        summary = report_summary(branch, start, end)
        daily = daily_series(branch, date_from, date_to, tz, start, end)
        top = top_items(branch, start, end)

        ctx["date_from"] = date_from
        ctx["date_to"] = date_to
        ctx["date_from_iso"] = date_from.isoformat()
        ctx["date_to_iso"] = date_to.isoformat()
        ctx["today_iso"] = today_in_branch(branch).isoformat()
        ctx["date_filter_error"] = error
        ctx["summary"] = summary
        ctx["top_items"] = top
        ctx["chart_daily_json"] = json.dumps(daily)
        ctx["chart_top_items_json"] = json.dumps(top_items_chart(top))
        ctx["chart_i18n_json"] = json.dumps(
            {
                "revenue": _("Revenue (€)"),
                "orders": _("Orders"),
                "sessions": _("Table sessions"),
                "quantity": _("Quantity sold"),
            }
        )
        return ctx

    def _empty_context(self):
        return {
            "date_from_iso": "",
            "date_to_iso": "",
            "today_iso": "",
            "date_filter_error": None,
            "summary": {
                "revenue_total": 0,
                "orders_count": 0,
                "sessions_count": 0,
                "avg_ticket": 0,
            },
            "top_items": [],
            "chart_daily_json": "{}",
            "chart_top_items_json": "{}",
            "chart_i18n_json": "{}",
        }


class ReportsExportView(RestaurantScopedMixin, RolePermissionMixin, View):
    required_permission = "view_analytics"

    def get(self, request):
        branch = self.get_branch()
        if not branch:
            return HttpResponse(_("No branch configured."), status=400)

        tz = branch_timezone(branch)
        date_from, date_to, error = parse_report_date_range(request, branch)
        if error:
            return HttpResponse(error, status=400)

        content, filename = build_reports_csv(branch, date_from, date_to, tz)
        response = HttpResponse(content, content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
