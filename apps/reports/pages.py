"""Week 4 reports: the charts page and the downloadable report endpoints."""
import logging

from django.http import Http404, HttpResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .exports import CONTENT_TYPES, EXTENSIONS, REPORT_BUILDERS, build_report, render_export
from .kpis import MONTHS, month_label, overview, year_month
from .models import AuditEvent
from .services import record_event

logger = logging.getLogger(__name__)


@role_required(User.Role.ADMIN, User.Role.HR)
def reports_home(request):
    """Charts and KPIs for one month. Admin and HR only."""
    year, month = year_month(request.GET.get("year"), request.GET.get("month"))
    context = overview(year, month)
    context.update(
        {
            "year": year,
            "month": month,
            "month_label": month_label(year, month),
            "months": MONTHS,
        }
    )
    return render(request, "reports/index.html", context)


@role_required(User.Role.ADMIN, User.Role.HR)
@require_GET
def export_report(request, kind, fmt):
    """Download one report as CSV, Excel or PDF. Every export is audited."""
    if kind not in REPORT_BUILDERS or fmt not in CONTENT_TYPES:
        raise Http404("Unknown report or format.")

    report = build_report(kind, request.GET)
    actor = request.user.get_full_name().strip() or request.user.get_username()
    payload = render_export(report, fmt, actor)
    record_event(
        request.user,
        AuditEvent.Action.EXPORT,
        "Report",
        kind,
        {"format": fmt, "filters": report["filters"], "rows": len(report["rows"])},
    )
    logger.info("report export %s as %s by %s", kind, fmt, request.user)

    response = HttpResponse(payload, content_type=CONTENT_TYPES[fmt])
    response["Content-Disposition"] = (
        f'attachment; filename="{report["filename"]}.{EXTENSIONS[fmt]}"'
    )
    response["Cache-Control"] = "private, no-store"
    response["Pragma"] = "no-cache"
    return response
