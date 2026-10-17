"""Role-based access helpers for both normal Django views and DRF views."""
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from rest_framework.permissions import BasePermission

from .models import User


def role_required(*roles):
    """
    Django view decorator.

    Anonymous users are redirected to the login page; logged-in users whose role
    is not in `roles` get a 403 response.
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            if request.user.role not in roles:
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return login_required(_wrapped)

    return decorator


class _RolePermission(BasePermission):
    allowed_roles = ()

    def has_permission(self, request, view):
        user = request.user
        return bool(user and user.is_authenticated and user.role in self.allowed_roles)


class IsAdminRole(_RolePermission):
    allowed_roles = (User.Role.ADMIN,)


class IsHROrAdmin(_RolePermission):
    allowed_roles = (User.Role.ADMIN, User.Role.HR)
