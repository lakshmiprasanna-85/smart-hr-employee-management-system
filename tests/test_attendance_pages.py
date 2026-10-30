from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.attendance.models import Attendance

from .helpers import PASSWORD, make_employee, make_user

HR, EMPLOYEE = User.Role.HR, User.Role.EMPLOYEE


class AttendancePageTests(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.client.login(username="alice", password=PASSWORD)

    def login(self, username):
        self.client.logout()
        self.client.login(username=username, password=PASSWORD)

    def test_anonymous_is_sent_to_login(self):
        self.client.logout()
        for name in ("attendance-home", "attendance-team"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 302)
                self.assertTrue(response.url.startswith(reverse("login")))

    def test_check_in_then_check_out_through_the_page(self):
        page = self.client.get(reverse("attendance-home"))
        self.assertContains(page, "Check in")

        response = self.client.post(reverse("attendance-check-in"), follow=True)
        self.assertContains(response, "Checked in.")
        record = Attendance.objects.get(employee=self.alice)
        self.assertIsNotNone(record.check_in)
        self.assertContains(response, "Check out")  # the button changes after checking in

        # The service refuses a check-out in the same instant as the check-in,
        # so move the check-in back a little.
        record.check_in = timezone.now() - timezone.timedelta(hours=8)
        record.save()
        response = self.client.post(reverse("attendance-check-out"), follow=True)
        self.assertContains(response, "Checked out.")
        self.assertContains(response, "Done for today")

    def test_rules_still_apply_through_the_page(self):
        self.client.post(reverse("attendance-check-in"))
        response = self.client.post(reverse("attendance-check-in"), follow=True)
        self.assertContains(response, "Already checked in for today.")
        self.assertEqual(Attendance.objects.filter(employee=self.alice).count(), 1)

    def test_check_out_without_check_in_is_refused(self):
        response = self.client.post(reverse("attendance-check-out"), follow=True)
        self.assertContains(response, "No open check-in for today.")

    def test_actions_are_post_only(self):
        for name in ("attendance-check-in", "attendance-check-out"):
            with self.subTest(action=name):
                self.assertEqual(self.client.get(reverse(name)).status_code, 405)

    def test_account_without_profile_gets_a_clear_message(self):
        make_user("noprofile", EMPLOYEE)
        self.login("noprofile")
        self.assertContains(self.client.get(reverse("attendance-home")), "No employee profile is linked")
        response = self.client.post(reverse("attendance-check-in"), follow=True)
        self.assertContains(response, "no employee profile")
        self.assertEqual(Attendance.objects.count(), 0)

    def test_page_lists_only_my_own_records(self):
        today = timezone.localdate()
        Attendance.objects.create(employee=self.alice, date=today)
        Attendance.objects.create(employee=self.bob, date=today - timezone.timedelta(days=1))
        response = self.client.get(reverse("attendance-home"))
        self.assertEqual([r.employee_id for r in response.context["records"]], [self.alice.pk])


class TeamAttendanceTests(TestCase):
    def setUp(self):
        self.hr = make_user("hr_user", HR)
        self.alice = make_employee(make_user("alice", EMPLOYEE), "EMP001")
        self.bob = make_employee(make_user("bob", EMPLOYEE), "EMP002")
        self.today = timezone.localdate()
        Attendance.objects.create(employee=self.alice, date=self.today, status="late")

    def test_hr_sees_today_and_the_monthly_summary(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("attendance-team"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "EMP001")
        self.assertContains(response, "No record yet")  # Bob has not checked in
        self.assertEqual(response.context["summary"][0]["late"], 1)

    def test_employee_cannot_open_the_team_page(self):
        self.client.login(username="alice", password=PASSWORD)
        self.assertEqual(self.client.get(reverse("attendance-team")).status_code, 403)

    def test_bad_month_and_year_do_not_crash(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("attendance-team") + "?month=99&year=abc")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["month"], self.today.month)
        self.assertEqual(response.context["year"], self.today.year)

    def test_other_month_shows_an_empty_message(self):
        self.client.login(username="hr_user", password=PASSWORD)
        response = self.client.get(reverse("attendance-team") + "?month=1&year=2020")
        self.assertContains(response, "No attendance recorded for 2020-1.")
