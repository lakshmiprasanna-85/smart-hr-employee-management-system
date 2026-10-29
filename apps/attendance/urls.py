from django.urls import path

from . import pages

urlpatterns = [
    path("", pages.my_attendance, name="attendance-home"),
    path("check-in/", pages.check_in_page, name="attendance-check-in"),
    path("check-out/", pages.check_out_page, name="attendance-check-out"),
    path("team/", pages.team_attendance, name="attendance-team"),
]
