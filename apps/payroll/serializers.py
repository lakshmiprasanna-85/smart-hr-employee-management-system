from rest_framework import serializers

from .models import PayrollRecord


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    period = serializers.CharField(source="period.label", read_only=True)

    class Meta:
        model = PayrollRecord
        fields = [
            "id",
            "employee_code",
            "period",
            "gross_amount",
            "total_deductions",
            "net_amount",
            "payment_status",
        ]
