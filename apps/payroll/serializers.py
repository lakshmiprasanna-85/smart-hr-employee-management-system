from rest_framework import serializers

from apps.reports.models import AuditEvent
from apps.reports.services import record_event

from .models import EmployeeSalaryComponent, PayrollPeriod, PayrollRecord, SalaryComponent
from .services import PayrollError, create_period


class PayrollRecordSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    period = serializers.CharField(source="period.label", read_only=True)
    payslip_available = serializers.SerializerMethodField()

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
            "paid_on",
            "payslip_available",
        ]

    def get_payslip_available(self, obj):
        return bool(obj.payslip_file)


class PayrollStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=PayrollRecord.PaymentStatus.choices)


class PayrollPeriodSerializer(serializers.ModelSerializer):
    label = serializers.CharField(read_only=True)

    class Meta:
        model = PayrollPeriod
        fields = ["id", "year", "month", "label", "start_date", "end_date", "status"]
        read_only_fields = ["start_date", "end_date", "status"]
        validators = []  # uniqueness is checked by create_period

    def validate_year(self, value):
        if not 2000 <= value <= 2100:
            raise serializers.ValidationError("Year must be between 2000 and 2100.")
        return value

    def create(self, validated_data):
        try:
            return create_period(validated_data["year"], validated_data["month"], self.context["request"].user)
        except PayrollError as exc:
            raise serializers.ValidationError({"detail": str(exc)}) from exc


def _check_value(calculation_type, value, field="value"):
    if value < 0:
        raise serializers.ValidationError({field: "Must not be negative."})
    if calculation_type == SalaryComponent.CalculationType.PERCENT_OF_BASIC and value > 100:
        raise serializers.ValidationError({field: "A percentage cannot be more than 100."})


class SalaryComponentSerializer(serializers.ModelSerializer):
    class Meta:
        model = SalaryComponent
        fields = ["id", "name", "component_type", "calculation_type", "default_value", "is_active"]

    def validate(self, attrs):
        calc = attrs.get("calculation_type", getattr(self.instance, "calculation_type", None))
        value = attrs.get("default_value", getattr(self.instance, "default_value", 0))
        _check_value(calc, value, "default_value")
        return attrs


class EmployeeSalaryComponentSerializer(serializers.ModelSerializer):
    employee_code = serializers.CharField(source="employee.employee_code", read_only=True)
    component_name = serializers.CharField(source="component.name", read_only=True)

    class Meta:
        model = EmployeeSalaryComponent
        fields = ["id", "employee", "employee_code", "component", "component_name", "value"]

    def validate(self, attrs):
        component = attrs.get("component", getattr(self.instance, "component", None))
        value = attrs.get("value", getattr(self.instance, "value", 0))
        if component is not None:
            if not component.is_active:
                raise serializers.ValidationError({"component": "This salary component is not active."})
            _check_value(component.calculation_type, value)
        return attrs

    def update(self, instance, validated_data):
        # The employee and component of an existing row never change; edit the value only.
        validated_data.pop("employee", None)
        validated_data.pop("component", None)
        return super().update(instance, validated_data)


def audit_salary_change(actor, action, instance, before=None):
    """Salary components are sensitive: every change is written to the audit history."""
    changes = {"employee": instance.employee.employee_code, "component": instance.component.name}
    if before is not None:
        changes["before"] = str(before)
    if action != AuditEvent.Action.DELETE:
        changes["after"] = str(instance.value)
    record_event(actor, action, "EmployeeSalaryComponent", instance.pk, changes)
