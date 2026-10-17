from rest_framework import serializers

from .models import Department, Employee


class DepartmentSerializer(serializers.ModelSerializer):
    employee_count = serializers.IntegerField(source="employees.count", read_only=True)

    class Meta:
        model = Department
        fields = ["id", "name", "description", "employee_count"]


class EmployeeSerializer(serializers.ModelSerializer):
    """Full employee record including personal fields (Admin/HR only)."""

    username = serializers.CharField(source="user.username", read_only=True)
    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "username",
            "full_name",
            "employee_code",
            "department",
            "department_name",
            "job_title",
            "employment_status",
            "joining_date",
            "exit_date",
            "manager",
            "phone",
            "date_of_birth",
            "address",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username


class EmployeePublicSerializer(serializers.ModelSerializer):
    """Directory view without personal information, safe for any logged-in user."""

    full_name = serializers.SerializerMethodField()
    department_name = serializers.CharField(source="department.name", read_only=True)

    class Meta:
        model = Employee
        fields = [
            "id",
            "full_name",
            "employee_code",
            "department_name",
            "job_title",
            "employment_status",
        ]

    def get_full_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
