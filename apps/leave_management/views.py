from rest_framework.generics import ListCreateAPIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import IsHROrAdmin

from .models import LeaveRequest
from .serializers import (
    LeaveDecisionSerializer,
    LeaveRequestCreateSerializer,
    LeaveRequestSerializer,
    LeaveStatusHistorySerializer,
)
from .services import LeaveTransitionError, decide
from .states import LeaveStatus


class LeaveRequestListCreateView(ListCreateAPIView):
    """
    Leave requests.

    Admin/HR see every request; an employee sees only their own. Employees
    submit new requests for themselves.
    """

    permission_classes = [IsAuthenticated]

    def get_serializer_class(self):
        if self.request.method == "POST":
            return LeaveRequestCreateSerializer
        return LeaveRequestSerializer

    def get_queryset(self):
        queryset = LeaveRequest.objects.select_related("employee", "leave_type", "reviewed_by")
        user = self.request.user
        if user.role in (User.Role.ADMIN, User.Role.HR):
            status = self.request.query_params.get("status")
            if status:
                queryset = queryset.filter(status=status)
            return queryset
        return queryset.filter(employee__user=user)


class LeaveRequestDecisionView(APIView):
    """Admin/HR approve or reject; the owner (or Admin/HR) may cancel."""

    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        try:
            leave_request = LeaveRequest.objects.select_related("employee").get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)

        serializer = LeaveDecisionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        to_status = serializer.validated_data["decision"]
        note = serializer.validated_data.get("note", "")

        is_privileged = request.user.role in (User.Role.ADMIN, User.Role.HR)
        is_owner = leave_request.employee.user_id == request.user.id
        # Only Admin/HR may approve or reject; cancelling is open to the owner too.
        if to_status in (LeaveStatus.APPROVED, LeaveStatus.REJECTED) and not is_privileged:
            return Response({"detail": "Only Admin or HR may decide this request."}, status=403)
        if to_status == LeaveStatus.CANCELLED and not (is_privileged or is_owner):
            return Response({"detail": "You may only cancel your own request."}, status=403)

        try:
            decide(leave_request, to_status, request.user, note)
        except LeaveTransitionError as exc:
            return Response({"detail": str(exc)}, status=409)
        return Response(LeaveRequestSerializer(leave_request).data)


class LeaveRequestHistoryView(APIView):
    """The full status history of one leave request."""

    permission_classes = [IsAuthenticated]

    def get(self, request, pk):
        try:
            leave_request = LeaveRequest.objects.get(pk=pk)
        except LeaveRequest.DoesNotExist:
            return Response({"detail": "Not found."}, status=404)
        is_privileged = request.user.role in (User.Role.ADMIN, User.Role.HR)
        if not is_privileged and leave_request.employee.user_id != request.user.id:
            return Response({"detail": "Not found."}, status=404)
        history = leave_request.history.select_related("changed_by")
        return Response(LeaveStatusHistorySerializer(history, many=True).data)
