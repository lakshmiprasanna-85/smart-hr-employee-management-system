from django.urls import path

from . import pages

urlpatterns = [
    path("", pages.my_leave, name="leave-home"),
    path("<int:pk>/cancel/", pages.cancel_leave, name="leave-cancel"),
    path("review/", pages.review_leave, name="leave-review"),
    path("<int:pk>/decide/", pages.decide_leave, name="leave-decide"),
]
