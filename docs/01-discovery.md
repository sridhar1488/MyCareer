# Phase 1 discovery

Prepared: 20 October 2026. Product: **MI LeapMetrics**. Scope: discovery and architecture, as explicitly requested in section 19 of the supplied master prompt.

## Repository inspection

The workspace initially contained exactly one file: `MI Performance Appraisal Development Form YE2025.xlsx` (22,840 bytes). No application source, dependency manifest, environment configuration, tests, Git metadata, or AGENTS.md was present in the workspace. No AGENTS.md was found at the inspected parent locations `C:/My_Space` and `C:/`. There is no existing implementation to preserve or migrate. The original workbook remains the authoritative source for form structure.

Both visible sheets were inspected directly from the XLSX XML, including all stored cells, formulas, cached results, merged ranges, formats, validation, sheet protection metadata, drawing, and print settings. The only drawing is an empty text box; no embedded logo, comments, external links, or additional sheets were found. See [the workbook specification](02-workbook-specification.md) and the generated evidence for provenance. Cached errors and values have not been presented as newly calculated results.

The [official corporate homepage](https://medimpactinternational.com/) was inspected through its HTML, linked stylesheet, inline Elementor theme declarations, and rendered browser header. The source and extracted values are retained under `evidence/`. These are current website assets, not a supplied corporate brand manual.

## Concise requirements summary

| Area | Confirmed requirement |
|---|---|
| Identity | One account and employee profile per person. Four roles: SUPER_ADMIN, HR, MANAGER, EMPLOYEE. Every role can complete its own appraisal. |
| Employee form | Up to five responsibilities/goals; three contribution slots; achievements, personal development, future development needs/plans/support. Employee responses are narrative only. |
| Manager form | Ratings as whole numbers 1–5, evaluation comments, eleven competencies including conditional leadership, strengths and improvement feedback. |
| Calculation | Workbook weights are 70%, 10%, 20%. One backend scoring service. No missing-value-to-zero conversion or invalid finalization. Divisor, applicability, and rounding policy require decisions. |
| Workflow | Employee draft and submission; assigned manager review, return with reason, finalization, release. Final evaluation content is immutable after finalization. Release and acknowledgement are recorded events. |
| HR | Cycles, versioned configuration, monitoring, concerns, escalation, reminders, authorized read/report/export. No editing appraisal responses or ratings and no workflow bypass. |
| Super Admin | Accounts, roles, activation, password setup/reset, manager assignments, audit. No appraisal content editing or scoring by administrative privilege. |
| Reporting | Individual, team, department/organization, operational reports; filtered CSV/XLSX/PDF exports; consistent stored scores and audited sensitive exports. |
| Notifications | In-app first, configurable intervals/thresholds, delivery attempts/retry/deduplication. Extensible email transport. |
| Quality | React/TypeScript, FastAPI, MySQL, SQLAlchemy 2.x, Alembic, modular monolith; backend authorization, secure sessions, audit; unit/integration/authorization/UI/E2E tests; containers and setup documentation. |

The workbook does not contain separate expected-outcome fields or competency employee-comment fields. Do not add these as source-derived requirements. The workbook has explicit future development support and signatures, and instructions mention a review meeting, employee discussion comments, and next-year manager objectives without separate dedicated fields. These differences are recorded for decision in [the delivery plan](06-delivery-plan.md).

## Role-permission matrix

All write permissions additionally require an active actor, resource-level authorization, permitted state, and current version. “Own” applies to every role independently of privileged dashboards. A role alone never authorizes self-review.

| Action | EMPLOYEE | MANAGER | HR | SUPER_ADMIN |
|---|---|---|---|---|
| Read/update own draft or returned employee responses | Own | Own | Own | Own |
| Submit/resubmit own appraisal | Own | Own | Own | Own |
| Read own unreleased manager ratings/comments | No | No | No through own-appraisal view | No |
| Read own released results / acknowledge | Own | Own | Own | Own |
| Read assigned employee submission and history | No | Assigned team | Organization monitoring, scope to confirm | No by admin role |
| Edit another employee's responses | No | No | No | No |
| Rate/comment/start review/return/finalize/release | No | Assigned manager only, never own | No | No |
| Read another manager's review | No | No unless authorized relationship | Authorized HR read scope | No by admin role |
| Create cycles, deadlines, new config versions | No | No | Yes | No by admin role |
| Monitor organization / manage concerns / trigger reminders | No | Team read only where authorized | Yes | No by admin role |
| Individual/team reports and exports | Own released summary | Assigned scope | Authorized organization scope | Own released summary only |
| Department/organization/operational reports and exports | No | Team subset | Yes | No by admin role |
| Manage accounts, role assignments, reporting relationships | No | No | No | Yes |
| Read account administration audits | No | No | Authorized subset only, scope to confirm | Yes |
| Read appraisal transition history | Own | Own + assigned | Authorized HR scope | Own |
| Alter finalized content or score / reopen finalized record | No | No | No | No |
| Update/delete audit entries | No | No | No | No |

Proposed conflict rule: HR must not use organization read privileges to see its own unreleased evaluation; deny this across reports/exports too. Decide the same restriction for connected HR staff who are also reviewers if multiple roles are authorized. Additional manager functions require an explicit MANAGER assignment plus the appraisal's manager snapshot, not simply being named in a directory. Multi-role policy and HR read scope are approval items.

Super Admin cannot change its own role assignments. Protect the last active Super Admin in a transaction. Prevent self-manager assignment, reporting cycles, or account changes that implicitly transfer in-flight review ownership. Deactivation revokes sessions without deleting history. Initial Super Admin bootstrap is a one-time secured deployment operation, not a public registration API.

## Proposed centralized workflow

| From | Command / actor | To | Required checks |
|---|---|---|---|
| DRAFT | Submit / owner | SUBMITTED | Active cycle, submission policy, required narrative fields, assigned eligible reviewer |
| RETURNED_FOR_REVISION | Resubmit / owner | SUBMITTED | Same validation; revision recorded; review draft cannot finalize stale response version |
| SUBMITTED | Start review / assigned manager | UNDER_REVIEW | Actor not owner, valid assignment, optimistic version |
| UNDER_REVIEW | Return / assigned manager | RETURNED_FOR_REVISION | Nonblank reason; retain prior response/review history |
| UNDER_REVIEW | Finalize / assigned manager | FINALIZED | Required comments/ratings complete, applicable sections valid, current employee revision, verified score policy |
| FINALIZED | Release / assigned manager | RELEASED | Final snapshot exists; release metadata/event only; scores and response snapshot unchanged |
| RELEASED | Acknowledge / owner | RELEASED | Separate actor/time/comment event, no score change |

`UNDER_REVIEW → FINALIZED` does not require a return cycle. Returning is an optional branch. No generic status PATCH and no reopen route. Review-draft saves do not advance the state. All other transitions reject. An uncreated eligible appraisal is “not started,” a monitoring classification rather than another persisted workflow state. Proposed activation creates all eligible DRAFT records and uses `started_at IS NULL` to distinguish not started; population and activation policy need confirmation.

State, content revision, score snapshot, history, audit event, and notification outbox event commit together. Use version checks and a row lock for finalization; a racing return, save, or finalize must fail with 409 instead of overwriting data. Notifications and exports cannot invoke workflow commands.

## Discovery outcome

Phase 1 output is available. Critical ambiguities are identified, with proposals rather than silently accepted policies. No feature implementation began. Continue to Phase 2 only within its independent scope; enable scoring, workflow finalization, or historical configuration migration only after the relevant decisions in the delivery plan are recorded.
