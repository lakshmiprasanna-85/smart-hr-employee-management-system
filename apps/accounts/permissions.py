from functools import wraps
from django.contrib.auth.mixins import AccessMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect
from rest_framework import permissions


class RoleRequiredMixin(AccessMixin):
    """CBV Mixin to restrict view access to specific roles."""
    allowed_roles = []

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()

        if request.user.is_superuser:
            return super().dispatch(request, *args, **kwargs)

        user_role = getattr(request.user, 'role', None)
        if user_role not in self.allowed_roles:
            raise PermissionDenied("You do not have permission to view this resource.")

        return super().dispatch(request, *args, **kwargs)


class AdminRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['ADMIN']


class HRRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['HR', 'ADMIN']


class EmployeeRequiredMixin(RoleRequiredMixin):
    allowed_roles = ['EMPLOYEE', 'HR', 'ADMIN']


def role_required(allowed_roles):
    """FBV Decorator to restrict view access to specific roles."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect('accounts:login')
            if request.user.is_superuser or request.user.role in allowed_roles:
                return view_func(request, *args, **kwargs)
            raise PermissionDenied("You do not have permission to access this page.")
        return _wrapped_view
    return decorator


def hr_or_admin_required(view_func):
    return role_required(['HR', 'ADMIN'])(view_func)


def admin_only_required(view_func):
    return role_required(['ADMIN'])(view_func)


# Django REST Framework Permissions

class IsAdminUserRole(permissions.BasePermission):
    """Allows access only to users with ADMIN role or superusers."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            (request.user.role == 'ADMIN' or request.user.is_superuser)
        )


class IsHROrAdminRole(permissions.BasePermission):
    """Allows access to users with HR or ADMIN roles."""
    def has_permission(self, request, view):
        return bool(
            request.user and request.user.is_authenticated and
            (request.user.role in ['HR', 'ADMIN'] or request.user.is_superuser)
        )


class IsEmployeeOwnerOrHROrAdmin(permissions.BasePermission):
    """
    Object-level permission allowing an employee to access their own records,
    or allowing HR/Admin to access any record.
    """
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)

    def has_object_permission(self, request, view, obj):
        if request.user.is_superuser or request.user.role in ['HR', 'ADMIN']:
            return True

        # Check if the object is an Employee or linked to an Employee
        if hasattr(obj, 'user'):
            return obj.user == request.user
        if hasattr(obj, 'employee'):
            return obj.employee.user == request.user

        return False
