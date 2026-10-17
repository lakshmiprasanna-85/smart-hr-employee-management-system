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
| Record own attendance | Own | Own | Own | 2 | Needs an employee profile |
| View / correct anyone's attendance | Yes | Yes | No | 2 | Corrections are audited |
| Apply for / cancel own leave | Own | Own | Own | 2 | Needs an employee profile |
| Approve / reject leave | Yes | Yes | No | 2 | Proposed: never your own request |
| Payroll periods and salary components | Yes | Yes | No | 3 | |
| Manage payroll records | Yes | Yes | No | 3 | |
| Download payslip | All | All | Own | 3 | Permission-checked view, not a static URL |
| View notification logs | Yes | No | No | 3 | |
| Dashboards charts and CSV/Excel/PDF exports | Yes | Yes | No | 4 | |

Admin and HR rows marked "Own" apply only when that user also has an Employee
profile.

**Open decisions to confirm with your mentor:** whether HR may manage payroll
or only Admin may, and whether Admin should be able to open the Employee
dashboard. The matrix above reflects the current implementation; changing a
row means changing one decorator and its test.
