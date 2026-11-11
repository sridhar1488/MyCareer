# HR operations — 21 October 2026

This increment implements the additional requirements confirmed in testing. It supersedes the earlier single-role assumption in the Phase 3 plan.

## Access and reporting relationships

An account can have an Employee or Manager work role. **Super Admin is reserved for HR** and cannot be combined with the Employee role. HR users who also manage staff can have both **Manager** and **Super Admin**. HR users without direct reports can have the standalone **HR / Super Admin** role. The role editor, API, and bulk import all reject Employee + Super Admin assignments. Administration does not grant permission to score unrelated appraisals or review oneself. Another Super Admin must make your role changes.

All account types can access their own appraisal. Removing a manager role is blocked while reporting/reviewer obligations remain. Role changes revoke sessions. Last-administrator safeguards remain in effect. Manager + Super Admin is supported for HR managers.

## Help and support

The **Help & Support** page provides role-specific workflow walkthroughs, FAQs, and illustrative sample-screen previews. Employee and Manager guides are only returned for signed-in accounts with those roles; Super Admin instructions are returned only to Super Admin accounts. The API enforces this filtering, so hiding a menu or section is not the only access control. Screen previews use fictional sample values.

## Monitoring and approved results

**HR monitoring** shows individual progress and manager totals, with cycle, manager, department, search, workflow status, and overdue filters. Statuses distinguish not started, draft, submitted, under review, returned, finalized, released, and acknowledged. The pending action names its responsible employee or manager. Only employee submission has a configured deadline; no manager or acknowledgement deadline is inferred.

After the manager submits a complete evaluation, it enters **HR approval queue**. HR can adjust individual ratings; the app recalculates the scores. Manager comments and the manager's original submission remain preserved. HR gives a reason for rating changes, and each saved calibration is recorded in immutable history. HR approval creates the immutable final evaluation and returns the approved item to the manager. The manager discusses the approved result with the employee, confirms the meeting, and releases the scores. HR can view and download the approved evaluation. A user's own evaluation remains hidden from them until their manager releases it, including through HR list, detail, and export routes. Monitoring can still show that appraisal's status.

The manager separately releases the HR-approved result, then the employee can acknowledge receipt. Employee responses, manager submission, HR calibration history, approved evaluation, exact scores, and policy are preserved; reports do not recalculate scores. Existing manager-finalized results are carried forward as previously approved.

## Cycle reminders

In **HR monitoring → Cycle reminders**, select the appraisal cycle. Add the manager review and HR calibration deadlines, then choose when reminders should go out before each deadline. Scheduled reminders run for active cycles and use the employee submission deadline from Appraisal Cycles. Manager and HR deadlines are reminder targets.

For a manual send, choose the stage and preview the message and intended recipient count. The default audience is people with work pending. Choose all assigned participants for a cycle-wide message for that stage. Each manager receives one email with their pending review count. MyCareer uses the deployment mail settings for both manual and scheduled reminders.

## Custom appraisal forms

Open **Appraisal forms → Create form**. The builder supports:

- Section titles and order; goal and contribution entry limits (1–100).
- Optional contributions, competencies, and standard development sections.
- Goal/contribution/competency weights totaling 100%; a disabled rated section must have zero weight.
- Up to 50 competencies, with at most one leadership competency eligible for N/A with a reason.
- Up to 20 custom text sections and 100 questions overall. Each section is completed by the employee or manager. Questions can be required before employee submission or manager finalization.
- Draft saving, preview, and publication of an immutable form version.

The first builder retains goals, manager-only whole-number 1–5 ratings, and manager strengths/improvements narratives. It does not introduce arbitrary rating scales or new scored question types. An empty contributions section continues to score zero while retaining its configured weight; populated items require ratings and supporting comments. Exact arithmetic and the approved half-up display precision remain in force.

Choose a **Published appraisal form** while creating/editing a draft cycle. Activation freezes that choice. Changing a template or publishing another version does not rewrite an active cycle or an earlier evaluation. The original workbook form remains selectable and the source workbook is unchanged.

## Employee evidence attachments

Employees can attach up to 25 supporting documents to an appraisal (10 MB each), including PDF, PNG/JPG, Word, Excel, PowerPoint and Outlook (.msg). Outlook messages are download-only. The employee confirms before removing a draft attachment. Attachments are private to the employee while in draft. After submission, the assigned manager and HR can access them. Files stay in private persistent storage and are served through authenticated downloads.

## Downloads

In **Final evaluations**, filter the list and use **Download filtered evaluations · Excel / PDF**, or open one evaluation to download only that evaluation. Filters and authorization apply to both formats.

Excel includes evaluation summaries, section scores, and employee/manager responses, with typed scores/dates, exact score numerators/denominators, form version, and scoring policy. Employee identifiers remain text, preserving leading zeros. User-supplied text is exported as literal text, never formulas. PDF includes a repeating branded header, an employee-details table, a prominent score summary, colored section bands, employee/manager comparison tables, competency ratings, and structured development and sign-off sections. Long narratives continue across pages with repeated column headings. Page numbers, UTC generation time, and embedded regular/bold fonts support printed and shared copies. Times in reports are UTC.

Per download, Excel supports up to 1,000 evaluations and PDF up to 100. Narrow the filters if that limit is exceeded. View/export events are audited without storing narrative content in the audit event.

## Bulk Excel user import

Open **User directory → Import users from Excel**:

1. Download the HRMS-format template and fill the **Users** sheet without changing these headers: Employee Number, Full Name, Work Email, Location, Department, Job Title, Reporting To, and Date Joined.
2. Employee Number is stored as MyCareer Employee ID. Preserve it as text to retain leading zeros. Location and Date Joined are stored separately on the user profile; Date Joined accepts an Excel date or `YYYY-MM-DD` and may be blank when unknown.
3. Reporting To may contain the manager's Employee Number or unique Full Name. People referenced by another row are assigned the Manager role; other imported users are Employees. HR / Super Admin accounts are managed separately and are not imported from this workbook. Existing accounts referenced as managers must already be active Managers. Self-management, ambiguous names, and reporting cycles are rejected.
4. Upload and review the validation preview. Fix all errors before confirming. An import creates new accounts only; existing or duplicate IDs/emails are rejected.
5. Confirm within 30 minutes. The complete batch is revalidated under the administrator write guard and created atomically. Replaying a consumed preview is rejected.
6. When live email is enabled, MyCareer automatically queues a password-setup email to every imported employee. In mail test mode, the test mailbox receives a notification with no working setup link. If email is disabled or a link needs secure handoff, copy it from the success screen and share it only with that employee. No passwords belong in Excel. One-time links are valid for seven days by default and are stored only as hashes.

The private links appear once. For a lost/expired link, choose **Create setup link** on the employee's directory row. If live email is enabled, this also queues the new link to the employee; in test mode it queues a test notification without the working link. Creating a replacement revokes existing sessions and earlier setup links. Setup-link lifetime is configurable with `MI_SETUP_LINK_MINUTES` (seven days by default, up to 30 days). Use **Account security** for your own password. Imports accept `.xlsx` only, up to 200 users and 5 MB. Formula cells, macros, external links, excessive expanded ZIP size, malformed workbooks, and ambiguous admin flags are rejected. Import previews are tied to the administrator who uploaded them.

## Upgrade and validation

Install `backend/requirements.lock`, migrate to Alembic head **hrmsmaster**, regenerate OpenAPI/client types, and rebuild/restart the application as described in [Running](07-running.md). The migrations add calibration records, private attachment metadata, and HRMS location/date-joined profile fields, and remove the Employee role from any pre-existing Super Admin accounts while preserving their accounts, admin access, and appraisal records. Previously finalized evaluations are carried forward as approved, and existing released results remain available. Back up private attachment storage together with the database.

Automated checks cover the existing authentication/appraisal workflow plus additive roles, HR authorization and own-result privacy, monitoring totals, form publication/binding, required custom questions and respondent boundaries, configurable scoring, import validation, revalidation and atomicity, one-time setup tokens, report values, and browser workflows. MySQL upgrade/downgrade/upgrade and schema drift checks are rehearsed against a disposable database. PDF layout is checked with synthetic long narratives and escaped markup.
