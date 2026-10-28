# Database schema notes

The diagram below renders automatically on GitHub. A PNG copy is in
`docs/er_diagram.png`.

```mermaid
erDiagram
    USER ||--o| EMPLOYEE : "has profile"
    DEPARTMENT |o--o{ EMPLOYEE : contains
    EMPLOYEE |o--o{ EMPLOYEE : "manages"
    EMPLOYEE ||--o{ ATTENDANCE : records
    EMPLOYEE ||--o{ LEAVE_REQUEST : submits
    LEAVE_TYPE ||--o{ LEAVE_REQUEST : classifies
    USER |o--o{ LEAVE_REQUEST : "reviews"
    LEAVE_REQUEST ||--o{ LEAVE_STATUS_HISTORY : "logs changes"
    USER |o--o{ LEAVE_STATUS_HISTORY : "changed by"
    EMPLOYEE ||--o{ EMPLOYEE_SALARY_COMPONENT : "is paid with"
    SALARY_COMPONENT ||--o{ EMPLOYEE_SALARY_COMPONENT : defines
    EMPLOYEE ||--o{ PAYROLL_RECORD : "is paid via"
    PAYROLL_PERIOD ||--o{ PAYROLL_RECORD : groups
    PAYROLL_RECORD ||--o{ PAYROLL_RECORD_LINE : "is made of"
    USER |o--o{ AUDIT_EVENT : performs
    USER |o--o{ NOTIFICATION_LOG : receives

    USER {
        int id PK
        string username UK
        string email
        string role "admin, hr, employee"
        bool is_active
    }
    DEPARTMENT {
        int id PK
        string name UK
        text description
    }
    EMPLOYEE {
        int id PK
        int user_id FK, UK
        string employee_code UK
        int department_id FK
        int manager_id FK
        string job_title
        string employment_status "probation, active, on_leave, terminated"
        date joining_date
        date exit_date
        string phone
        date date_of_birth
        text address
    }
    ATTENDANCE {
        int id PK
        int employee_id FK
        date date
        datetime check_in
        datetime check_out
        string status "present, absent, late, half_day, on_leave"
        bool is_corrected
    }
    LEAVE_TYPE {
        int id PK
        string name UK
        int annual_quota_days
        bool is_paid
        bool is_active
    }
    LEAVE_REQUEST {
        int id PK
        int employee_id FK
        int leave_type_id FK
        date start_date
        date end_date
        string status "pending, approved, rejected, cancelled"
        int reviewed_by_id FK
        text reviewer_note
        datetime decided_at
    }
    LEAVE_STATUS_HISTORY {
        int id PK
        int leave_request_id FK
        string from_status
        string to_status
        int changed_by_id FK
        text note
        datetime changed_at
    }
    PAYROLL_PERIOD {
        int id PK
        int year
        int month
        date start_date
        date end_date
        string status "open, closed"
    }
    SALARY_COMPONENT {
        int id PK
        string name UK
        string component_type "earning, deduction"
        string calculation_type "fixed, percent_of_basic"
        decimal default_value
        bool is_active
    }
    EMPLOYEE_SALARY_COMPONENT {
        int id PK
        int employee_id FK
        int component_id FK
        decimal value
    }
    PAYROLL_RECORD {
        int id PK
        int employee_id FK
        int period_id FK
        decimal gross_amount
        decimal total_deductions
        decimal net_amount
        string payment_status "pending, paid, on_hold"
        date paid_on
        file payslip_file
        datetime payslip_generated_at
    }
    PAYROLL_RECORD_LINE {
        int id PK
        int record_id FK
        string name
        string component_type "earning, deduction"
        decimal amount
    }
    AUDIT_EVENT {
        int id PK
        int actor_id FK
        string action "create, update, delete, status_change, login"
        string entity_type
        string entity_id
        json changes
        datetime created_at
    }
    NOTIFICATION_LOG {
        int id PK
        int recipient_id FK
        string recipient_email
        string notification_type
        string subject
        string status "queued, sent, failed"
        text error_message
        datetime sent_at
    }
```

## Where each table lives

| Django app | Tables |
|---|---|
| `accounts` | `User` |
| `employees` | `Department`, `Employee` |
| `attendance` | `Attendance` |
| `leave_management` | `LeaveType`, `LeaveRequest`, `LeaveStatusHistory` |
| `payroll` | `PayrollPeriod`, `SalaryComponent`, `EmployeeSalaryComponent`, `PayrollRecord`, `PayrollRecordLine` |
| `reports` | `AuditEvent`, `NotificationLog` |

## Integrity rules enforced by the database

| Table | Rule | Constraint name |
|---|---|---|
| Employee | One employee record per user | `user` one-to-one |
| Employee | Unique `employee_code` | unique field |
| Employee | `exit_date` is empty or not before `joining_date` | `employee_exit_not_before_joining` |
| Attendance | One row per employee per day | `uniq_attendance_employee_date` |
| Attendance | `check_out` after `check_in` when both are set | `attendance_checkout_after_checkin` |
| LeaveRequest | `end_date` not before `start_date` | `leave_end_not_before_start` |
| PayrollPeriod | One period per year and month | `uniq_payroll_period_year_month` |
| EmployeeSalaryComponent | One value per employee per component | `uniq_employee_salary_component` |
| PayrollRecord | One record per employee per period | `uniq_payroll_employee_period` |
| PayrollRecord | Gross and deductions are not negative | `payroll_amounts_not_negative` |

## Delete behaviour (why each `on_delete` was chosen)

* `Employee.department` is `SET_NULL`: removing a department keeps its people.
* `Employee.user` is `CASCADE`: an employee record has no meaning without its login.
* `PayrollRecordLine.record` is `CASCADE`: the lines are a snapshot owned by their record.
* `PayrollRecord.employee` and `.period` are `PROTECT`: payroll history cannot be
  lost by deleting an employee or a period.
* `LeaveRequest.leave_type` and `EmployeeSalaryComponent.component` are `PROTECT`:
  a type or component that is in use cannot be removed (mark it inactive instead).
* Audit and review references to a user (`actor`, `reviewed_by`, `changed_by`)
  are `SET_NULL`, so history survives when an account is removed.

## Indexes

Beyond primary keys, foreign keys and unique constraints, `AuditEvent` has an
index on `(entity_type, entity_id)` so the history of one record is quick to load.
