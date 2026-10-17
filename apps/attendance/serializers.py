from rest_framework import serializers

from .models import Attendance


class AttendanceSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)

    class Meta:
        model = Attendance
        fields = [
            "id",
            "employee_code",
            "date",
            "check_in",
            "check_out",
            "status",
            "notes",
            "is_corrected",
        ]
        read_only_fields = ["is_corrected"]
