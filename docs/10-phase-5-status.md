# Phase 5 - manager review and scoring

20 October 2026. Phase 5 manager review, scoring, finalization, release and employee acknowledgement are implemented. Earlier policy questions were resolved by the project owner in this chat on this date.

## Approved policy: mi-2026-10-20-v1

Approver: project owner (user in the implementation chat). The user amended the empty-contributions proposal to **zero**, approved the precision policy, and approved the workflow. This supersedes the earlier proposals in the [decision register](06-delivery-plan.md).

| Rule | Implemented behavior |
|---|---|
| Weights | Goals 70%, contributions 10%, competencies 20%. |
| Denominators | Count populated applicable items; unused source slots are excluded. |
| Empty contributions | Section average and weighted component are zero; its 10% weight stays in place. No redistribution or artificial item rating is used. |
| Missing ratings | A populated applicable item needs an integer 1-5 and supporting manager comment before finalization. Missing ratings are not zero. |
| Minimum valid content | At least one submitted goal; all required competencies rated. Existing employee submission rules still apply. |
| N/A | Leadership competency alone may be N/A with a reason and no simultaneous rating; exclude it from the competency denominator. |
| Manager narrative | Complete source strengths and improvement narratives before sign-off. |
| Arithmetic | Exact rational values (numerator/denominator) are persisted; no intermediate rounding. |
| Display | Section averages and overall score: one decimal. Weighted components: two decimals. Half-up rounding; no overall category label. |
| Manager submission | Assigned manager signs off a complete saved review of the current employee revision and submits it to HR for calibration and approval. No employee meeting is required at this stage. |
| Manager release | After HR approval, the assigned manager discusses the approved scores with the employee and confirms that meeting before releasing the result. |
| Acknowledgement | Separate dated employee receipt event; no score or state change. Duplicate requests are idempotent. |
| Resubmission | Mandatory return reason; existing cycle submission deadline/late policy applies. A fresh submitted revision requires a fresh manager review. |
| Form extensions | Retain the workbook strengths/improvements fields; no new discussion-comment or next-year-objective fields. |

The empty-contribution rule can yield an overall below 1.0 even when all entered ratings are at least 1: all goals/competencies rated 1 with no contributions gives **0.9**. This is the direct result of the approved zero section and unchanged weights; scores are not clamped or assigned a misleading overall scale label.

## Delivered workflow and controls

Managers use **Team appraisals** to search/filter/page their snapshot-assigned records while keeping their own appraisal separate. Submitted employee responses are read-only. The manager can begin review, save incomplete ratings/comments, return with a nonblank reason, view old manager drafts, and review resubmissions. Returned live employee edits are never exposed to the manager before resubmission. A new employee revision starts a fresh review and preserves previous drafts.

The backend produces a score preview only when the saved evaluation is complete. **Review and finalize** shows the score and requires meeting confirmation. Finalization atomically stores the source submission, identity/form snapshot, manager evaluation, exact score, full scoring policy, actor and timestamp. Ordinary write operations reject all subsequent content changes. **Release to employee** is a separate confirmation. Employees can then read the final evaluation and acknowledge receipt. Acknowledgement is a separate immutable record and leaves the score unchanged.

Employee, HR / Super Admin and unrelated-manager requests cannot write manager evaluations or finalization/release state. Self-review is rejected independently of role. Owners cannot read unreleased results even when their account is Manager or Super Admin. Appraisal-version and submitted-revision checks prevent stale writes. The backend serializes conflicting actions. Manager removal protection includes finalized-but-unreleased appraisals, preventing a pending release from losing its reviewer.

MySQL/SQLite triggers protect submitted revisions, manager review events, final evaluations, releases and acknowledgements against updates/deletes. Employee response DTOs contain no unreleased evaluation or score fields. Released result endpoints enforce ownership separately.

## Versioning and migrations

`p5manager` adds review/sign-off records and ordering for new workflow events. `p5scoring` binds existing and new cycles to approved policy **mi-2026-10-20-v1**. Readiness requires `p5scoring`. Existing account/profile and employee response data are preserved. The original workbook is unchanged.

Future business-rule changes require a new policy version for future cycles, retaining the previous policy implementation for cycles already bound to it. Never edit an issued policy version or recalculate finalized evaluations. Finalized reads use their preserved score and policy, rather than calling the current calculator. No policy-edit UI or historical recalculation endpoint is exposed in this phase.

## Validation

Scoring tests cover all-1/all-5 ratings, independent 70/10/20 fixtures, zero contributions, missing versus empty, unused slots, 100 goals, leadership N/A, required competency rules, comments, exact recurring fractions and half-up ties. API checks cover mandatory meeting confirmation, stale revisions, incomplete finalization, owner/unrelated-role privacy, immutable database artifacts, separate release, acknowledgement replay and unchanged historical results after the policy registry changes.

Independent MySQL connections test finalize versus return/save/finalize, duplicate release and simultaneous acknowledgement. Chromium covers manager save/return/resubmit, leadership N/A, full completion, meeting confirmation, finalization, hidden unreleased score, release, employee result viewing, acknowledgement and mobile overflow. The released-score layout was visually inspected.

Final regression: **207 backend tests passed**, with one intentional SQLite skip for a MySQL-specific audit-trigger check; **9 Chromium E2E tests passed**; **8 component tests passed**. Ruff lint/format, ESLint, TypeScript and the production build passed. Empty disposable MySQL upgrade/downgrade/upgrade and metadata drift checks pass. The development database was backed up under ignored `.local/` and migrated, preserving its existing administrator account. API readiness and frontend startup passed after restart. Test users/appraisals remain restricted to isolated test databases.

HR monitoring/alerts, organizational reporting/exports and production hardening remain subsequent phases. Docker execution and hosted CI were not run in this environment. Digital events record application sign-off/receipt; no legal equivalence to a handwritten signature is asserted.
