# Phase 3–4 implementation status

For the subsequent manager-review increment and current migration head, see [Phase 5 progress](10-phase-5-status.md).

20 October 2026. This supersedes the Phase 2 status for delivered functionality. [Running instructions](07-running.md) include the employee-registration and appraisal workflow.

## Approved decisions

- HR uses **Super Admin**. New accounts select exactly one role: Employee, Manager or HR / Super Admin. The historical HR catalog value remains for compatibility/security regression coverage; the API rejects new HR assignments, and migration consolidates existing HR assignments into Super Admin and invalidates their sessions.
- Follow the workbook's employee fields and reserve competencies/ratings for managers. Additional goals are supported beyond the five source slots, with an explicit technical maximum of 100; organizational contributions retain three slots. The original workbook and its source snapshot retain their original five-slot structure.
- HR / Super Admin creates cycles with explicit participants, dates, deadlines and minimum completed goals. At least one complete goal is required; contributions and development narratives are optional. An explicit allow/block-late-submission setting is stored per cycle. Scoring, applicability/N/A, rounding and manager finalization remain Phase 5 decisions/work.

These decisions come from the user's replies in this implementation session and override relevant earlier proposals in documents 01–06. They do not approve unresolved scoring or production policy.

## Delivered

Phase 3 includes a searchable, filtered, sorted, paginated directory; account creation/profile editing; one-role assignment; active manager selection; activation/deactivation; temporary-password resets and administrative/security audit views. Normalized departments and dated reporting relationships preserve account history. Version checks reject stale edits. A serialized administrator guard protects the final active administrator, reporting hierarchy changes and concurrent account creation. Role/status/reset changes revoke sessions. Credentials are absent from response/audit DTOs. Password setup requires private handoff and first-login replacement.

Phase 4 includes HR cycle draft/edit/review/activation, atomic participant/reviewer validation and unique participant/cycle appraisals. Activation preserves identity, manager and workbook form version. Every role has its own appraisal workspace. Employees can add/remove goals, enter achievement narratives, add up to three contributions, enter achievements/development/support narratives, save partial drafts, review saved content, submit, inspect workflow history and view preserved submitted revisions. Unsaved-work navigation is guarded. Server-side ownership, strict fields, deadline checks and version checks protect all writes. Submitted/finalized records are read-only; returned records can be edited and resubmitted without changing prior revisions.

MySQL and SQLite triggers reject updates/deletes of form versions, workflow history and submission revisions. Submission uses locking reads to prevent stale repeatable-read content after concurrent draft changes. Account administration never grants access to another person's employee responses. A changed directory manager applies to future cycles; existing reviewers are preserved. Managers with active reports or unfinished assigned appraisals cannot be demoted/deactivated through these account operations.

Public OpenAPI and generated frontend types are updated. The migration is `c3d4foundation`. Readiness requires that revision. Existing local accounts are preserved and a private pre-upgrade database backup is kept under ignored `.local/`.

## Verification

| Check | Result |
|---|---|
| Backend, including real MySQL | 121 passed, one intentional SQLite skip for the MySQL audit-trigger check. |
| Workflow concurrency | Independent committed MySQL connections verify competing admin removal, duplicate creation, stale draft writes and submission after an earlier read snapshot. |
| Browser | **8 passed**. Authentication regression scenarios and the full HR-create-user / cycle-activate / employee-password-change / seven-goal-save-reload-review-submit / read-only-history workflow passed against real API/MySQL. Mobile appraisal overflow checked. |
| Frontend | **8 component tests passed**; ESLint, TypeScript and production build passed. |
| Migrations | Empty disposable MySQL upgrade → downgrade → upgrade and metadata drift checks passed. Local development upgrade preserved the existing account/profile values. |
| Source integrity | Workbook remains unchanged; versioned form data records its SHA-256. |

Browser tests use only the dedicated E2E database and generated credentials. No employees or appraisal cycles were seeded in the real development database. Docker execution and hosted CI remain unexecuted in this environment.

## Phase 5 boundary

Assigned-manager review screens, the actual manager return action, manager ratings/comments, scoring, finalization/release and acknowledgement are not included. The employee returned-state contract is implemented and tested using a returned fixture; it is not an administrative bypass. HR monitoring/reporting/export and deployment hardening remain later phases. Email delivery remains unconfigured. Active cycle settings and existing reviewer snapshots are frozen; no reassignment exception or deadline-edit override is exposed.
