# Security review (Week 4)

Scope: the whole application, with extra attention to the new reports page,
the CSV/Excel/PDF exports and the production settings. Reviewed on
2026-11-01 against the project requirements and the OWASP Top 10 categories that
apply to a small server-rendered Django app.

## Summary

| # | Area | Result |
|---|---|---|
| 1 | Access control on reports and exports | Fixed: Admin/HR only, tested for anonymous, Employee, Admin and HR |
| 2 | Personal data in exports | Fixed: the employee report excludes phone, date of birth and address |
| 3 | Spreadsheet formula injection | Fixed: dangerous leading characters are neutralised in CSV and Excel |
| 4 | PDF markup injection | Fixed: all report text is XML-escaped before it reaches ReportLab |
| 5 | Caching of sensitive downloads | Fixed: `private, no-store` (plus `Pragma: no-cache`) on every export |
| 6 | Audit trail for downloads | Fixed: each export writes an `export` `AuditEvent` with actor, format, filters and row count |
| 7 | Input validation on exports | Confirmed: report/format are allow-listed (unknown values 404); month/year are clamped |
| 8 | Production transport and cookie settings | Improved: secure cookies when `DEBUG=False`; opt-in HTTPS redirect and HSTS |
| 9 | Secrets and debug mode | Confirmed: secrets come from `.env`; `DEBUG=False` requires `SECRET_KEY` |
| 10 | Dependency surface | Noted: one new dependency (`openpyxl`) for real `.xlsx` output |

## What was checked

### 1. Authorisation and least privilege

* `/reports/` uses `role_required(User.Role.ADMIN, User.Role.HR)`, which rejects
  anonymous visitors with a login redirect and Employees with 403.
* Every export path (`/reports/export/<kind>/<fmt>/`) uses the same decorator.
* The reports navigation link and dashboard tiles are only rendered for Admin
  and HR, so an Employee does not see the feature at all.
* Payroll data in charts and exports is limited to the same two roles. Employees
  still see only their own payslips through the existing payslip view.
* Tests: `tests/test_reports_pages.py` and `tests/test_report_exports.py` cover
  anonymous, Employee, Admin and HR for all four reports and three formats.

### 2. Data minimisation

* The employee report contains employee number, name, department, job title,
  status and joining date. Phone, date of birth and address are not selected
  into the report at all, so they cannot leak through a format-specific bug.
* The report tests assert that a seeded phone number and address never appear in
  CSV or Excel output.
* Charts aggregate counts; they do not expose individual salaries. The payroll
  chart exposes period totals to Admin/HR only.

### 3. CSV and Excel formula injection

A spreadsheet can execute a cell that starts with `=`, `+`, `-`, `@`, a tab or a
carriage return. `exports.safe_text()` prefixes those cells with an apostrophe
before writing CSV or `.xlsx`, so the value is displayed as text. Numeric columns
are written as real numbers in Excel and as plain fixed-point text in CSV.
Tests use a department name beginning with `=HYPERLINK(...)` and confirm the
neutralised value in both formats.

### 4. PDF output

Report titles, subtitles, cell text and the footer are passed through
`xml.sax.saxutils.escape()` before they become ReportLab `Paragraph`s. A test
renders a report with `<b>` and `&` in an employee name and confirms a valid PDF
is still produced. Numeric values are formatted separately.

### 5. Caching and browser history

Exports can contain payroll and workforce data, so responses send
`Cache-Control: private, no-store` and `Pragma: no-cache`. A test asserts the
header. Download URLs are GET links (no state changes), and each download is
audited, which is the compensating control for a URL appearing in a history
entry.

### 6. Audit and logging

Exports write an `AuditEvent` with `action="export"`, `entity_type="Report"`,
`entity_id=<kind>` and changes `{format, filters, rows}`. The same action is
logged through the `apps` logger, which goes to the console and the rotating
`logs/app.log`. A test checks the audit row's actor, format, filters and row
count.

### 7. Input handling

* `kind` and `fmt` are looked up in allow-lists; anything else raises 404. There
  is no path, SQL or template value taken from the URL beyond those lookups.
* Month and year are parsed with bounds (2000-2100, 1-12); invalid values fall
  back to today. Tests cover `month=99&year=abc`.
* Filenames are generated from static names and validated dates, not from user
  text, so header injection is not possible.
* The view is GET-only (`require_GET`); a POST returns 405.

### 8. Configuration and transport

* When `DEBUG=False`, session and CSRF cookies are `Secure`, content-type
  sniffing is disabled, the referrer policy is `same-origin`, and framing is
  denied.
* `HTTPS=True` adds `SECURE_SSL_REDIRECT` and HSTS (one year, subdomains,
  preload). It must only be enabled behind real TLS; setting it on a plain HTTP
  deployment locks users out. If a reverse proxy sets `X-Forwarded-Proto`,
  configure `SECURE_PROXY_SSL_HEADER` in the deployment (not enabled by default).
* `DEBUG=False` refuses to start without `SECRET_KEY`. The development fallback
  key is only used while `DEBUG=True`.
* `.env` is git-ignored; `.env.example` contains placeholders only.
* `media/payslips/` is private and every payslip is served by a
  permission-checked view, not by `MEDIA_URL`.

### 9. Django built-ins still in force

CSRF middleware on all POST forms, session authentication, password validators,
the `SecurityMiddleware`, role checks on API views, and the Django admin limited
to Admin (`is_staff`) accounts. The admin also exposes the audit log read-only.

## Accepted residual risks (and the plan)

| Risk | Why it remains | Mitigation / next step |
|---|---|---|
| No rate limiting on downloads | Not in the internship brief; exports are synchronous | Add a reverse-proxy limit on `/reports/export/`; audit events make abuse visible |
| No MFA for Admin/HR | Out of scope for this project | Use SSO/MFA at the proxy or add `django-otp` in a future week |
| Exports load all rows into memory | Dataset is small and the feature runs in-request | Add a row cap, streaming, or a background job if data grows |
| No CSP header | Charts use a few inline width styles | Add a CSP with hashes/nonces when a CSP middleware is introduced |
| Audit rows are append-only by convention, not by the database | SQLite/PostgreSQL permissions are deployment concerns | Revoke UPDATE/DELETE on the audit table from the app role |
| Dependency CVEs are not scanned automatically | No CI pipeline in the brief | Add `pip-audit` and Dependabot/Renovate |
| E-mail TLS depends on configuration | SMTP settings are environment-specific | Use `EMAIL_USE_TLS=True` with a provider that requires TLS |
| DEMO data uses a known password | Required for the demo | Never run the seed script in production (see deployment notes) |

## How to re-run the checks

```bash
python -m pytest tests/test_reports_pages.py tests/test_report_exports.py -v
python -m pytest
python manage.py check --deploy   # with DEBUG=False and HTTPS=True for a production review
```

`manage.py check --deploy` will still warn about HSTS/preload when HTTPS is off;
that is expected for a local or internal HTTP setup. Resolve the warnings in the
real production environment before going live.

## Sign-off

The Week 4 reports and exports meet the access, data-minimisation and audit
requirements in `docs/requirements.md`. The residual risks above are documented
and accepted for this release; none of them is a blocker for a small internal
deployment behind an authenticated, TLS-terminated proxy.
