from django.urls import path

from . import pages

urlpatterns = [
    path("", pages.employee_directory, name="employees-home"),
]
