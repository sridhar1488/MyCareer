# Proposed API contract

REST prefix `/api/v1`. This is an endpoint proposal, not implemented OpenAPI. FastAPI will generate and validate OpenAPI from separate Pydantic request/response DTOs. Never return ORM objects directly.

## Shared contract and authorization

Every protected request validates session, account activity, role, ownership/manager snapshot, cycle/state, and expected resource version where writing. Server sets actors/timestamps. Deny unknown input keys (`extra='forbid'`); employee DTOs contain no rating, manager comments, manager ID, score, role, or status fields. Response projection excludes unreleased evaluations from owner responses. The same projection policy covers reports, exports, notifications, history payloads, and error details.

Paginated collections accept `page` (1+), `page_size` (default 25, maximum 100), allowlisted `sort` and direction. Return `{items,total,page,page_size}`. Filters include only authorized scope; manager requests cannot expand scope with an employee ID. Mutations require `If-Match` version or an equivalent expected_version DTO; stale writes return 409. Return 401 for absent/invalid sessions, 403 for prohibited functions, 404 for inaccessible resource IDs to avoid enumeration, 409 for state/version/unique conflicts, 422 for invalid inputs, 429 for throttling with Retry-After. Error shape: `{error:{code,message,field_errors,request_id}}`, without private values or stack traces.

## Endpoint inventory

In paths below, `{id}` is a server-issued resource ID. “Owner” includes every role. “Assigned manager” requires MANAGER role and the appraisal manager snapshot and excludes self-review. HR own-record visibility restrictions apply to every read surface.

| Method / path | Purpose | Permission |
|---|---|---|
| GET /health/live; GET /health/ready | Liveness / DB readiness without configuration disclosure | Infrastructure policy |
| POST /auth/login | Verify password; issue/rotate opaque cookie session | Public, rate-limited |
| POST /auth/logout | Revoke current session | Authenticated, CSRF |
| GET /auth/me | Safe profile, effective functions, mandatory password-change state | Authenticated |
| GET /auth/csrf | Session-bound CSRF material | Session context |
| POST /auth/change-password | Verify current credential, update hash, revoke other sessions | Authenticated; allowed for restricted first-login session |
| POST /auth/forgot-password | Generic response, queue secure reset where configured | Public, rate-limited |
| POST /auth/complete-password-setup | Consume SETUP/RESET token, set password, invalidate sessions | One-use token, rate-limited |
| GET /users | Search/filter/sort/paginate directory | SUPER_ADMIN |
| POST /users | Create profile, account and initial password setup | SUPER_ADMIN |
| GET /users/{id} | Account details, no password hash/tokens | SUPER_ADMIN |
| PATCH /users/{id} | Allowlisted name/employee ID/email/department/designation/country | SUPER_ADMIN |
| PUT /users/{id}/roles | Replace explicit roles; no self-elevation, protect last admin | SUPER_ADMIN |
| POST /users/{id}/activate; POST /users/{id}/deactivate | Change account availability, revoke sessions on deactivate | SUPER_ADMIN |
| POST /users/{id}/password-reset | Issue setup/reset process or temporary password under selected policy | SUPER_ADMIN, sensitive audit |
| GET /users/{id}/reporting-relationships | View assignment history | SUPER_ADMIN |
| POST /users/{id}/reporting-relationships | Effective-date new directory assignment | SUPER_ADMIN; no appraisal reassignment |
| GET /roles; GET /admin/summary | Role catalog and account/role counts | SUPER_ADMIN |
| GET /departments | Minimal authorized lookup | Authenticated, scoped |
| POST /departments; PATCH /departments/{id} | Directory master data | Proposed SUPER_ADMIN, confirm ownership |
| GET /lookups/reviewers; GET /lookups/responsible-users | Minimal active IDs/display names for permitted forms | SUPER_ADMIN or HR as needed; not full directory access |
| GET /cycles | Own applicable cycles / manager team / HR all | Scoped authenticated |
| POST /cycles; PATCH /cycles/{id} | Create cycle, permitted deadlines/parameters | HR; audited version |
| GET /cycles/{id}/participants | Eligibility and assignment preview | HR |
| PUT /cycles/{id}/participants | Set explicit eligible population before activation | HR; no appraisal content write |
| POST /cycles/{id}/activate; POST /cycles/{id}/close | Administrative lifecycle | HR, closure constraints unresolved |
| GET /appraisal-configs; GET /appraisal-configs/{id} | Read applicable published form; HR also drafts | Scoped authenticated |
| POST /appraisal-configs | Create draft version | HR |
| PATCH /appraisal-configs/{id} | Edit unpublished version only | HR |
| POST /appraisal-configs/{id}/publish | Publish validated future config | HR; approval policy to confirm |
| GET /me/dashboard; GET /me/appraisals | Personal summary/history including not started | Owner |
| GET /appraisals/{id} | Employee content and permitted review projection | Owner / assigned manager / authorized HR |
| PUT /appraisals/{id}/self-assessment | Save full employee draft DTO transactionally | Owner, DRAFT/RETURNED_FOR_REVISION |
| POST /appraisals/{id}/submit | Validate and submit/resubmit | Owner, allowed state |
| GET /appraisals/{id}/history | Safe transition/revision history | Owner / assigned manager / authorized HR |
| GET /appraisals/{id}/revisions/{revision} | Prior submitted version, proper field projection | Same resource scope |
| GET /team/dashboard; GET /team/appraisals | Assigned team status and deadlines | MANAGER |
| POST /appraisals/{id}/review/start | SUBMITTED to UNDER_REVIEW | Assigned manager |
| PUT /appraisals/{id}/review | Save ratings, supporting comments, feedback draft | Assigned manager, UNDER_REVIEW |
| GET /appraisals/{id}/review/validation | Completeness and backend-calculated preview | Assigned manager, permitted review state |
| POST /appraisals/{id}/return | Return with mandatory reason | Assigned manager, UNDER_REVIEW |
| POST /appraisals/{id}/finalize | Validate, compute and freeze once | Assigned manager, UNDER_REVIEW |
| POST /appraisals/{id}/release | Release immutable final snapshot | Assigned manager, FINALIZED |
| GET /appraisals/{id}/result | Final summary projection | Owner only RELEASED; assigned manager; authorized HR |
| POST /appraisals/{id}/acknowledgement | Record acknowledgement, optional comment | Owner, RELEASED |
| GET /hr/dashboard; GET /hr/appraisals | Organization status, delays, pending actor/action | HR |
| GET /concerns; GET /concerns/{id} | Concern list/detail/history projection | HR; team/responsible-person read scope pending |
| POST /concerns; PATCH /concerns/{id} | Create / update description, priority, responsibility, due date | HR |
| POST /concerns/{id}/transitions | OPEN/IN_PROGRESS/RESOLVED/CLOSED validated commands and resolution | HR |
| GET /concerns/{id}/history | Concern events | HR |
| POST /concerns/{id}/escalations | Escalate with reason and responsible actor | HR |
| PATCH /escalations/{id} | Record escalation outcome/resolution | HR |
| GET /notifications; POST /notifications/{id}/read | Personal inbox and mark read | Recipient |
| GET /hr/notification-policies | Intervals/thresholds by cycle | HR |
| PUT /hr/notification-policies/{id} | Version allowed scheduling settings | HR |
| POST /hr/reminders | Queue authorized filtered reminders with deduplication | HR |
| GET /hr/notification-history | Delivery attempts, failures, retry info | HR |
| POST /hr/notifications/{id}/retry | Retry failed delivery using original idempotency key | HR |
| GET /reports/individual/{appraisal_id} | Appraisal summary including sections/development | Owner RELEASED / assigned manager / authorized HR |
| GET /reports/team | Team status, scores, distribution and concerns | Assigned manager / authorized HR |
| GET /reports/organization | Department/org metrics and valid cycle comparison | HR |
| GET /reports/operations | Stage delays, responsible actors, concern aging, escalations/delivery | HR |
| POST /reports/exports | Generate authorized CSV/XLSX/PDF for selected report/filters | Same underlying report scope, sensitive audit |
| GET /audit-events | Search immutable permitted audit subset | SUPER_ADMIN account scope / HR authorized administrative scope |

No public registration, generic workflow-state update, appraisal reopening, audit mutation, score override, HR appraisal editing, or admin review editing route is proposed. A deferred background export implementation may introduce job/status/download routes later, with reauthorization and expiring downloads.

## Representative DTOs

`SelfAssessmentWrite`: expected content version, goals[{position,description,achievement_narrative}], contributions[{position,description,employee_narrative}], business_achievements, development_achievements, six_month_growth, development_needs, development_plan, support_requested. Server-owned item IDs are verified against the appraisal. Max counts come from its pinned config. Narrative length limits and required fields are decision items; empty drafts are allowed.

`ReviewWrite`: expected appraisal/content revision, item_evaluations[{item_id,rating,comment}], competency_evaluations[{competency_id,applicability,reason,rating,comment}], strengths, improvement_areas. Rating validation uses strict integers, never boolean coercion. N/A permitted only under approved rules. No employee-response fields are accepted.

`TransitionCommand`: expected_version and reason where required. From/to state, actor, timestamps, final score and revision binding are server-generated. Repeated submit/finalize/release requests are either idempotently identified via Idempotency-Key or return a clear state conflict; they never duplicate finalization or notifications.

`MonitoringRow`: employee ID/name, historical department/designation/country, assigned manager, cycle, state, stage, pending_action, responsible_person, applicable_deadline, overdue_duration, submitted_at, review_started_at, finalized_at, released_at. “Not started” and “draft” are mutually exclusive display categories. Deadline logic lives in one backend service.

`ExportRequest`: report kind, cycle, validated filters, format. Export includes generated_at with timezone, cycle and filter metadata. All formats use the same authorized report query and snapshot score fields. Individual reports include source narratives; consolidated metrics distinguish denominators, not-applicable values, and incomplete/unreleased populations. Avoid leaking another person's score through aggregate filters or suppressed small groups; HR scope/privacy threshold remains a decision.
