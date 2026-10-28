# Demo script

A short walkthrough for showing Weeks 1 and 2. It takes about 10 minutes.

## Before you start

1. Activate the virtual environment and make sure `.env` is set up (see the README).
2. Create the tables and demo accounts:

   ```
   python manage.py migrate
   python scripts/seed_demo_data.py
   ```

3. Start the app with `python manage.py runserver` and open http://127.0.0.1:8000/.

All demo accounts use the password from `SEED_PASSWORD` (default `Demo@12345`).

| Username | Role |
|---|---|
| `admin_demo` | Admin |
| `hr_demo` | HR |
| `employee_demo` | Employee |
| `employee_demo2` | Employee |

## 1. Login and role-based dashboards

1. Log in as `admin_demo`. You land on the Admin dashboard with links to user admin, the HR desk and payroll.
2. Log out and log in as `hr_demo`. You land on the HR dashboard (no user admin link).
3. Log out and log in as `employee_demo`. You land on "My space" with your employee number, department and job title.

What to point out: each role sees a different dashboard and a different navigation bar.

## 2. Access control

1. While logged in as `employee_demo`, open http://127.0.0.1:8000/payroll/. You see the "This page is not for your role" page (HTTP 403).
2. Also try http://127.0.0.1:8000/dashboard/admin/. Same result.
3. Log in as `hr_demo` and open `/payroll/`. It opens. Open `/dashboard/admin/`. It is denied (only Admin).

What to point out: access is checked on the server for every page, not just hidden in the menu. The full table is in `docs/role_permission_matrix.md`.

## 3. API and data privacy (Week 2)

Use the browsable API while logged in:

| URL | As Admin / HR | As Employee |
|---|---|---|
| `/api/employees/employees/` | Full records, including personal fields | Public directory only (no phone or address) |
| `/api/attendance/records/` | All attendance | Own attendance only |
| `/api/leave/requests/` | All leave requests | Own requests only |

Workflows to show with the API (or Django admin for the data):

1. As `employee_demo`, apply for leave at `/api/leave/requests/`.
2. As `hr_demo`, approve it at `/api/leave/requests/<id>/decide/`.
3. Try to approve your own request as HR. It is refused (403).

## 4. Audit log

1. Log out, then try to log in with a wrong password for `employee_demo`.
2. Log in as `admin_demo` and open http://127.0.0.1:8000/admin/ and then **Audit events**.
3. You see a login event for the successful logins, and an event with `{"result": "failed", "username": "employee_demo"}` for the failed attempt. The password is never stored.

## 5. Payroll, payslips and e-mail (Week 3)

1. Log in as `hr_demo` and click **Payroll**. You see the August period (closed) and the September period (open).
2. Open September. Each employee has gross pay, deductions and net pay. Click **Mark paid** on one row, then try **Close period**: it refuses while another record is still pending.
3. Click **Download** on a payslip. A PDF opens with the earnings, deductions and net pay.
4. Open `/admin/` as `admin_demo` and then **Audit events**: the payment status change is there with who did it. In the terminal running the server you can also see the e-mail printed when a payslip or a leave decision is sent; **Notification logs** in the admin shows each one as sent or failed.
5. Log in as `employee_demo` and click **My payslips**. Only that employee's own payslips are listed. Try a colleague's payslip address (change the number in `/payroll/payslips/<id>/download/`): the answer is "not found".
6. Try http://127.0.0.1:8000/media/payslips/2026-09-EMP003.pdf: it is not found, because payslips are never served from a public address.

What to point out: pay is calculated from salary components (a percentage of Basic or a fixed amount), paid records are final, every sensitive change is audited, and payslip e-mails contain no salary figures.

## 6. Tests

```
python -m pytest
```

All tests pass (123 at the time of writing). They cover authentication, the role matrix, model rules, the Week 2 workflows, login auditing, payroll rules, payslip generation and download access, e-mail notifications and the payroll pages.

## Notes for questions

* Passwords are hashed by Django; secrets live in `.env`, which is never committed.
* The database is PostgreSQL (SQLite works for a quick local start).
* Charts, downloadable reports and the deployment guide are Week 4.
