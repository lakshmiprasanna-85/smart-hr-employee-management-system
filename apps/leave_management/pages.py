"""Web pages for leave. Rules come from services.py and the API serializer."""
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required

from .models import LeaveRequest, LeaveType
from .serializers import LeaveRequestCreateSerializer
from .services import LeavePermissionError, LeaveTransitionError, process_decision
from .states import LeaveStatus

PRIVILEGED = (User.Role.ADMIN, User.Role.HR)


def _error_text(errors):
    """Turn serializer errors into short sentences for the page."""
    lines = []
    for field, problems in errors.items():
        label = field.replace("_", " ").capitalize()
        for problem in problems if isinstance(problems, list) else [problems]:
            text = str(problem)
            general = field in ("non_field_errors", "detail") or text.startswith(label)
            lines.append(text if general else f"{label}: {text}")
    return lines


@login_required
def my_leave(request):
    """Apply for leave and see your own requests."""
    profile = getattr(request.user, "employee_profile", None)
    form, errors = {}, []

    if request.method == "POST" and profile is None:
        messages.error(request, "This account has no employee profile.")
        return redirect("leave-home")

    if request.method == "POST":
        form = {k: request.POST.get(k, "") for k in ("leave_type", "start_date", "end_date", "reason")}
        # Blank boxes are left out so the messages say "This field is required".
        data = {key: value for key, value in form.items() if value != ""}
        serializer = LeaveRequestCreateSerializer(data=data, context={"request": request})
        if serializer.is_valid():
            serializer.save()
            messages.success(request, "Leave request submitted.")
            return redirect("leave-home")
        errors = _error_text(serializer.errors)

    requests_ = LeaveRequest.objects.filter(employee=profile).select_related("leave_type", "reviewed_by") if profile else []
    return render(
        request,
        "leave/index.html",
        {
            "profile": profile,
            "types": LeaveType.objects.filter(is_active=True),
            "requests": requests_,
            "form": form,
            "errors": errors,
        },
    )


@login_required
@require_POST
def cancel_leave(request, pk):
    leave = get_object_or_404(LeaveRequest.objects.select_related("employee", "leave_type"), pk=pk)
    if request.user.role not in PRIVILEGED and leave.employee.user_id != request.user.id:
        return redirect("leave-home")  # never confirm that someone else's request exists
    try:
        process_decision(request.user, leave, LeaveStatus.CANCELLED)
    except (LeavePermissionError, LeaveTransitionError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, "Leave request cancelled.")
    return redirect("leave-home")


@role_required(*PRIVILEGED)
def review_leave(request):
    """Pending requests to approve or reject, and the latest decisions (Admin/HR only)."""
    base = LeaveRequest.objects.select_related("employee__user", "leave_type", "reviewed_by")
    return render(
        request,
        "leave/review.html",
        {
            "pending": base.filter(status=LeaveStatus.PENDING).order_by("start_date"),
            "recent": base.exclude(status=LeaveStatus.PENDING).order_by("-updated_at")[:15],
        },
    )


@role_required(*PRIVILEGED)
@require_POST
def decide_leave(request, pk):
    leave = get_object_or_404(LeaveRequest.objects.select_related("employee__user", "leave_type"), pk=pk)
    decision = request.POST.get("decision", "")
    if decision not in (LeaveStatus.APPROVED, LeaveStatus.REJECTED):
        messages.error(request, "Choose approve or reject.")
        return redirect("leave-review")
    try:
        process_decision(request.user, leave, decision, request.POST.get("note", "").strip())
    except (LeavePermissionError, LeaveTransitionError) as exc:
        messages.error(request, str(exc))
    else:
        messages.success(request, f"Request from {leave.employee.employee_code} {leave.get_status_display().lower()}.")
    return redirect("leave-review")
