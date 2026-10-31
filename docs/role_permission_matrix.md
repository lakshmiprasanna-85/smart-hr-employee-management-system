# Role-permission matrix

Legend: **Yes** = allowed, **Own** = only their own records, **No** = forbidden
(HTTP 403 for logged-in users; anonymous users are redirected to the login page).

"Week" shows when the feature is built. Rows marked **Enforced and tested**
already have automated tests in `tests/`.

| Area / action | Admin | HR | Employee | Week | Notes |
|---|---|---|---|---|---|
| Log in / log out | Yes | Yes | Yes | 1 | Enforced and tested |
| Admin dashboard `/dashboard/admin/` | Yes | No | No | 1 | Enforced and tested |
| HR dashboard `/dashboard/hr/` | Yes | Yes | No | 1 | Enforced and tested |
| Employee dashboard `/dashboard/employee/` | Yes | Yes | Yes | 1 | Shows the viewer's own profile; enforced and tested |
| Django admin site `/admin/` (accounts, roles, raw data) | Yes | No | No | 1 | Needs `is_staff`; seed data gives it to Admin only |
| Who am I API `/api/accounts/me/` | Yes | Yes | Yes | 1 | Login required; enforced and tested |
| Payroll page `/payroll/` | Yes | Yes | No | 1 | Enforced and tested |
| Payroll records API `/api/payroll/records/` | All | All | Own | 1 | Anonymous rejected; enforced and tested |
| Create / edit user accounts and roles | Yes | No | No | 1 | Through the Django admin site |
| View audit log | Yes | No | No | 1 | Read-only in the Django admin site |
| Employee and department management | Yes | Yes | No | 2 | |
| View own profile | Own | Own | Own | 2 | |
| View other employees' personal details | Yes | Yes | No | 2 | Phone, date of birth, address |
| Record own attendance | Own | Own | Own | 2 | Needs an employee profile; page `/attendance/` and API; tested |
| View anyone's attendance | Yes | Yes | No | 2 | Page `/attendance/team/` and API; tested |
| Correct anyone's attendance | Yes | Yes | No | 2 | Planned; not built yet |
| Apply for / cancel own leave | Own | Own | Own | 2 | Needs an employee profile; page `/leave/` and API; tested |
| Approve / reject leave | Yes | Yes | No | 2 | Never your own request; page `/leave/review/` and API; tested |
| Employee directory page `/employees/` | Yes | Yes | No | 2 | No personal details on the page; tested |
| Payroll periods and salary components | Yes | Yes | No | 3 | Enforced and tested; salary changes are audited |
| Manage payroll records (generate, mark paid, close period) | Yes | Yes | No | 3 | Enforced and tested; status changes are audited |
| Download payslip | All | All | Own | 3 | Permission-checked view, not a static URL; other people's payslips return 404; tested |
| My payslips page `/payroll/my/` | Own | Own | Own | 3 | Login required; lists only the viewer's own records |
| View notification logs | Yes | No | No | 3 | Read-only in the Django admin site |
| Dashboards charts and CSV/Excel/PDF exports | Yes | Yes | No | 4 | |

Admin and HR rows marked "Own" apply only when that user also has an Employee
profile.

**Assumptions:** the brief does not say whether HR may manage payroll or only
Admin may, nor whether Admin may open the Employee dashboard. This project
assumes that Admin and HR both manage payroll, that Employees see only their
own payroll and payslips, and that Admin may open the Employee dashboard (useful
only when the Admin has an Employee profile). The matrix above reflects the
current implementation; changing a row means changing one decorator and its
test.
