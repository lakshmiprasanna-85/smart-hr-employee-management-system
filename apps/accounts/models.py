from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models


class HRUserManager(UserManager):
    """Superusers created from the command line are always Admins."""

    def create_superuser(self, username, email=None, password=None, **extra_fields):
        extra_fields.setdefault("role", self.model.Role.ADMIN)
        return super().create_superuser(username, email, password, **extra_fields)


class User(AbstractUser):
    """Login account. The `role` field drives all role-based access control."""

    class Role(models.TextChoices):
        ADMIN = "admin", "Admin"
        HR = "hr", "HR"
        EMPLOYEE = "employee", "Employee"

    role = models.CharField(max_length=20, choices=Role.choices, default=Role.EMPLOYEE)

    objects = HRUserManager()

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN

    @property
    def is_hr_role(self):
        return self.role == self.Role.HR

    @property
    def is_employee_role(self):
        return self.role == self.Role.EMPLOYEE

    def __str__(self):
        return f"{self.get_username()} ({self.get_role_display()})"
