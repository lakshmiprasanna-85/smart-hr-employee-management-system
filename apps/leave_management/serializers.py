from rest_framework import serializers

from apps.employees.models import Employee

from .models import LeaveRequest, LeaveStatusHistory, LeaveType
from .states import LeaveStatus


class LeaveTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveType
        fields = ["id", "name", "annual_quota_days", "is_paid", "is_active"]


class LeaveRequestSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)
    reviewed_by_username = serializers.CharField(
        source="reviewed_by.username", read_only=True, default=None
    )

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "employee_code",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "total_days",
            "reason",
            "status",
            "reviewed_by_username",
            "reviewer_note",
            "decided_at",
            "created_at",
        ]
        read_only_fields = ["status", "reviewer_note", "decided_at"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        leave_type = attrs.get("leave_type")
        if leave_type and not leave_type.is_active:
            raise serializers.ValidationError({"leave_type": "This leave type is not active."})
        return attrs


class LeaveRequestCreateSerializer(serializers.ModelSerializer):
    """Employees submit their own request; the employee is set from the session."""

    leave_type_name = serializers.CharField(source="leave_type.name", read_only=True)

    class Meta:
        model = LeaveRequest
        fields = [
            "id",
            "leave_type",
            "leave_type_name",
            "start_date",
            "end_date",
            "reason",
            "status",
            "total_days",
        ]
        read_only_fields = ["status"]

    def validate(self, attrs):
        start = attrs.get("start_date")
        end = attrs.get("end_date")
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        leave_type = attrs.get("leave_type")
        if leave_type and not leave_type.is_active:
            raise serializers.ValidationError({"leave_type": "This leave type is not active."})
        return attrs

    def create(self, validated_data):
        user = self.context["request"].user
        profile = getattr(user, "employee_profile", None)
        if profile is None:
            raise serializers.ValidationError("This account has no employee profile.")
        validated_data["employee"] = profile
        return super().create(validated_data)


class LeaveStatusHistorySerializer(serializers.ModelSerializer):
    changed_by_username = serializers.CharField(
        source="changed_by.username", read_only=True, default=None
    )

    class Meta:
        model = LeaveStatusHistory
        fields = ["id", "from_status", "to_status", "changed_by_username", "note", "changed_at"]


class LeaveDecisionSerializer(serializers.Serializer):
    """Payload for approve / reject / cancel."""

    decision = serializers.ChoiceField(
        choices=[
            LeaveStatus.APPROVED,
            LeaveStatus.REJECTED,
            LeaveStatus.CANCELLED,
        ]
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")
