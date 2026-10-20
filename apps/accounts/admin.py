from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import User


@admin.register(User)
class HRUserAdmin(UserAdmin):
    list_display = ("username", "email", "role", "is_active", "is_staff")
    list_filter = ("role", "is_active", "is_staff")
    fieldsets = UserAdmin.fieldsets + (("HR role", {"fields": ("role",)}),)
    add_fieldsets = UserAdmin.add_fieldsets + (("HR role", {"fields": ("role",)}),)
