# Phase 2 implementation status

Historical record: see [Phase 3-4 status](09-phase-3-4-status.md) for the current implementation and approved role/workflow changes.

20 October 2026. This document supplements the Phase 1 design; it does not retroactively approve the decision register.

## Delivered

- Feature modules for authentication, account identity and append-only audit, shared configuration/errors/security, database sessions and API dependencies.
- React/TypeScript application with verified corporate color tokens, official logo reference, responsive sign-in/reset/password-change views, personal profile workspace, account security, and Super Admin account counts. No mock counts or inactive feature buttons.
- SQLAlchemy account/role/credential/session/token/rate-limit/audit models, explicit initial Alembic migration, seeded role catalog and operator guard, MySQL audit protection triggers, readiness version check.
- Argon2id hashing, opaque hashed session tokens, idle/absolute expiry, CSRF and Origin checks, restricted first-login session, active-account enforcement, password change, one-use expiring operator-issued reset links, session invalidation and shared atomic rate limiting.
- Role and ownership/assigned-manager guards that do not grant appraisal editing to HR/Super Admin; strict request DTOs and credential-safe errors. The only administration HTTP endpoint in this increment is a read-only account summary.
- One-time administrator CLI bootstrap and a local reset-link operator command. No default application account, no public registration, no seeded production credentials, and no public reset-token disclosure.
- Public OpenAPI snapshot and generated frontend DTO types; exact dependency locks; backend/frontend tests; real MySQL checks; Chromium E2E; CI workflow; container configuration; setup and local start/stop instructions.

## Scope and decisions

Implementation continues the independent foundation work authorized by “Begin Implementation.” The scoring/applicability/rounding, HR read-scope, role combinations, cycle and sign-off questions remain open. No scoring service, workflow-finalization operation, user role-assignment API, HR content-write route or administrative appraisal override was enabled. Each current account can enter its own workspace; self-appraisal forms are Phase 4 work.

Operational auth defaults are documented in [running instructions](07-running.md), environment-configurable for timeouts/limits, and require production policy review under D17. Secure manual handoff is implemented as an operator capability; the public UI truthfully directs users to their administrator because email delivery is not configured. Bootstrap supports only the initial Super Admin; subsequent directory management is Phase 3.

The initial account schema stores department/designation/country as profile strings. Phase 3 should migrate department master data into its proposed normalized entity while preserving existing profile values; appraisal snapshots do not yet exist. Multiple role assignments are representable in the schema, but no assignment UI/API or unapproved role combination is enabled.

## Validation

| Check | Observed result |
|---|---|
| Backend Pytest in a fresh environment installed only from locks | **69 passed, 1 skipped**; all MySQL tests ran. The intentional skip is the MySQL-trigger check for the SQLite parameter. |
| Frontend component/regression tests | **6 passed**, including reset-token initialization under React StrictMode. |
| Chromium E2E against FastAPI and MySQL | **7 passed**: four-role sign-in/reload/sign-out, mandatory password change, reset-token reuse rejection, mobile/error/reset assistance. |
| Backend Ruff lint and formatting | Passed. |
| Frontend ESLint, TypeScript and production build | Passed. No peer dependency conflicts. |
| MySQL migrations | Upgrade → downgrade → upgrade and metadata drift check passed in an empty disposable database. Fixed generated downgrade indexes that MySQL still needed for foreign keys. |
| Clean locked installation | Installed successfully; `pip check`, application import and OpenAPI export passed without an editable application install. |
| Public API contract | Exported and frontend types regenerated; actual custom error-envelope responses are documented. |
| Dependency registry audit | Frontend registry audit returned zero advisories at verification time. This is not a general security certification or a backend advisory scan. |
| Source/discovery verification | All 10 checks passed, including workbook hash and local documentation links. |
| Development runtime | API readiness passed; desktop branding and sign-in layout inspected in browser; local process start/stop verified. |
| Container images | All four selected image tags/digests verified against official registry metadata. Builds/start not run: Docker unavailable. |
| Hosted CI | Workflow supplied for backend, frontend, and browser checks; not executed remotely. |

MySQL is tested locally via a loopback-only portable instance, with separate test/E2E databases. The source workbook remains unchanged. No production deployment, WCAG certification, or complete PMS release is claimed.

## Next increment

Phase 3: Super Admin directory, validated account creation/editing, role/reporting-manager assignment, activation/deactivation, reset UI and administrative audit views, with concurrent last-admin and manager-hierarchy tests. Appraisal editing remains separate from these privileges. Resolve the relevant decision-register entries before enabling combinations or exceptions that change access.
