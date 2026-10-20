from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    class Role(models.TextChoices):
        ADMIN = 'ADMIN', 'Administrator'
        HR = 'HR', 'HR Manager'
        EMPLOYEE = 'EMPLOYEE', 'Employee'

    role = models.CharField(
        max_length=20,
        choices=Role.choices,
        default=Role.EMPLOYEE,
        help_text='Designates the role and dashboard permissions for this user.'
    )
    phone_number = models.CharField(max_length=20, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['username']
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return f"{self.username} ({self.get_role_display()})"

    @property
    def is_admin_role(self):
        return self.role == self.Role.ADMIN or self.is_superuser

    @property
    def is_hr_role(self):
        return self.role == self.Role.HR

    @property
    def is_employee_role(self):
        return self.role == self.Role.EMPLOYEE

    @property
    def has_hr_privileges(self):
        """Returns True if user is either HR or Admin"""
        return self.role in [self.Role.HR, self.Role.ADMIN] or self.is_superuser
