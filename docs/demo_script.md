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

## 5. Tests

```
python -m pytest
```

All tests pass (53 at the time of writing). They cover authentication, the role matrix, model rules, payroll access, the Week 2 workflows and login auditing.

## Notes for questions

* Passwords are hashed by Django; secrets live in `.env`, which is never committed.
* The database is PostgreSQL (SQLite works for a quick local start).
* Payroll pages, payslips and e-mail notifications are Week 3; charts and reports are Week 4.
