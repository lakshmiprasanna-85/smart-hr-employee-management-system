# Requirements (Week 1)

This document records the rules the system is built around. Week 1 models and
tests the rules below; Weeks 2 to 4 build the workflows that enforce them.

## 1. Scope

| Week | Focus | Status |
|------|-------|--------|
| 1 | Requirements, data model, Django/DRF foundation, authentication, role-aware dashboard shells, tests | Done |
| 2 | Employee, department, attendance and leave workflows | Teammate |
| 3 | Payroll, payslips, e-mail notifications, audit logging | Planned |
| 4 | Charts, downloadable reports, security review, final documentation | Planned |

## 2. Roles

| Role | Who | Summary |
|------|-----|---------|
| Admin | System owner | Manages user accounts and roles, can see every area, owns audit and configuration. |
| HR | HR staff | Manages employees, departments, attendance, leave decisions and payroll records. |
| Employee | Everyone else | Self-service only: own profile, own attendance, own leave, own payslips. |

The role is stored on the login account (`accounts.User.role`). A superuser
created with `createsuperuser` is automatically an Admin.

Users who are not Admin or HR can never see another employee's personal or
payroll information.

## 3. Employee lifecycle

```
Probation -> Active <-> On leave -> Terminated
```

* An `Employee` record is linked one-to-one with a login account.
* `employee_code` is unique (for example `EMP001`).
* `joining_date` is required. `exit_date` is optional but, when set, cannot be
  before `joining_date` (database check constraint).
* Terminated employees keep their history (attendance, leave, payroll) for
  reporting. Deleting a department never deletes its employees.
* Planned for Week 2: terminating an employee also deactivates their login.

## 4. Attendance rules

Modelled now, enforced in Week 2.

* One attendance record per employee per day (unique on `employee + date`).
* If both times are present, `check_out` must be after `check_in` (check
  constraint).
* Statuses: Present, Absent, Late, Half day, On leave.
* Employees record only their own attendance. HR/Admin can correct any record;
  a corrected record is flagged `is_corrected` and written to the audit log.
* The working-hours thresholds that decide Late and Half day will be settings
  chosen in Week 2.
* Monthly summary = count of each status per employee per calendar month.

## 5. Leave states

```
            +--> Approved --> Cancelled
Pending ----+--> Rejected
            +--> Cancelled
```

| From | Allowed next states |
|------|---------------------|
| Pending | Approved, Rejected, Cancelled |
| Approved | Cancelled |
| Rejected | none (final) |
| Cancelled | none (final) |

* The transition table lives in `apps/leave_management/states.py`
  (`ALLOWED_TRANSITIONS`, `can_transition`) and is tested in Week 1.
* `end_date` cannot be before `start_date` (check constraint).
* Every status change must create a `LeaveStatusHistory` row (who, when, from,
  to, note). Week 2 wires this into the workflow.
* Proposed for Week 2: nobody can approve or reject their own request.

## 6. Payroll access boundaries

* Payroll periods, salary components and payroll records are visible to Admin
  and HR only. An Employee sees only their own payroll records and payslips.
* The payroll management page (`/payroll/`) returns 403 for Employees and
  redirects anonymous visitors to the login page.
* The payroll API (`/api/payroll/records/`) rejects anonymous requests and
  filters the queryset to the logged-in employee's own rows.
* Money fields use `DecimalField`, never floats. Amounts cannot be negative
  (check constraint). One payroll record per employee per period.
* Payslip files are stored under `media/payslips/`, which is git-ignored, and
  will be served only through permission-checked views (Week 3).

## 7. Cross-cutting requirements

* Secrets and environment-specific settings come from environment variables;
  `.env.example` holds placeholders only.
* Structured logging to the console and to `logs/app.log`.
* Every protected view applies least-privilege authorisation, and the access
  boundaries are covered by automated tests.
* Sensitive actions are recorded in `AuditEvent`. Login events are recorded
  now; employee, leave, attendance and payroll changes are added in Weeks 2-3.
* Only synthetic demo data is used (`scripts/seed_demo_data.py`).

## 8. Out of scope for Week 1

Employee/department screens, attendance entry, leave application and approval,
payslip generation, e-mail sending, charts and exports.
