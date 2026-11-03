# Running MyCareer

Authentication, user administration, cycles, employee self-assessment and evidence uploads, manager review, HR calibration/approval, manager release and employee receipt acknowledgement are implemented. See [current status](10-phase-5-status.md).

## Requirements

Validated on Windows with Python **3.12.14**, Node **24.19.0**, pnpm **11.25.0**, and MySQL **8.4.13**. Exact dependencies are in `backend/requirements.lock`, `backend/requirements-dev.lock`, and `frontend/pnpm-lock.yaml`. The stack uses React 19.3.1, Vite 8.3.4, FastAPI 0.151.0, SQLAlchemy 2.1.5, Alembic 1.20.0, TypeScript 5.9.3 and Argon2id. HTTPX2 supplies the Starlette test client.

## Configure and migrate

From the root in PowerShell, for a new installation:

```powershell
py -3.12 -m venv backend/.venv
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements-dev.lock
Copy-Item .env.example .env
backend/.venv/Scripts/python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

Put the generated secret in `MI_SECRET_KEY`; configure MySQL and URL-encoded credentials in `MI_DATABASE_URL`. Preserve existing `.env` files and never commit credentials. On Linux/macOS use `.venv/bin/python`. Run migrations from `backend/` so settings find the root `.env`:

```powershell
Set-Location backend
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m alembic check
```

Migrations never run at API startup; readiness checks the exact revision. Use separate migration/application credentials in deployment. `MI_MIGRATION_DATABASE_URL` optionally overrides only Alembic. MySQL migrations require trigger-creation privileges; with binary logging use a DBA-approved migration account. Do not weaken global security settings. SQLite is only a local/test convenience and is rejected in production.

The Phase 3-4 migration preserves profiles, normalizes departments and adds reporting/appraisal tables. Legacy HR assignments become Super Admin and their prior sessions are invalidated. Downgrade does not infer which Super Admin accounts were formerly HR; restore an approved backup if that distinction is required. Rehearse destructive rollbacks only on disposable databases.

## Initial administrator

No default application account/password exists. From `backend/`:

```powershell
.venv/Scripts/python.exe -m app.cli bootstrap-admin --email YOUR_WORK_EMAIL --employee-id YOUR_EMPLOYEE_ID --name "YOUR_FULL_NAME"
```

The CLI privately prompts twice for a temporary password. Bootstrap serializes its check and is disabled after any account exists. First sign-in requires changing the password. Create subsequent accounts in User directory; never use the E2E seeder for real accounts.

## Start locally

In `frontend/`:

```powershell
npm install --global pnpm@11.25.0
pnpm install --frozen-lockfile
pnpm dev
```

In a second terminal from `backend/`:

```powershell
.venv/Scripts/python.exe -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000 --no-proxy-headers
```

Open [MyCareer](http://127.0.0.1:5173) or [Swagger](http://127.0.0.1:8000/api/docs). Vite proxies `/api` so cookies stay same-origin. On this Windows workspace, `tools/start-local.ps1` starts API/Vite hidden, records process IDs/start times and writes ignored logs under `.local/`. `tools/stop-local.ps1` stops only those verified process trees. Manage MySQL separately.

Portable MySQL is under ignored `.local/mysql/`, with existing data in `.local/mysql-data/`, loopback **127.0.0.1:33306**, and generated local credentials in ignored `.env`. It is not a Windows service. If stopped, start its `mysqld.exe` with the same `--basedir`, `--datadir`, `--bind-address=127.0.0.1`, `--port=33306`, `--mysqlx=0` arguments. Do not reinitialize the data directory.

## Register employees and assign appraisals

1. Sign in as **HR / Super Admin**. In **User directory > Create user**, enter the real profile, unique work email/employee ID and Employee, Manager or HR / Super Admin role. Set a temporary password and share privately; first sign-in requires replacement.
2. Create manager accounts first, then **Assign manager** for their reports. Choose an active Manager. Self-reporting and circular chains are rejected. Accounts may initially lack a manager, but need a separate reviewer before cycle activation. Top-level managers may remain outside participants until a reviewer is configured.
3. In **Appraisal cycles > Create cycle**, enter the period, future submission deadline, minimum completed goals (1-5), explicit late-submission policy and explicit participants. Save, review and activate. Activation validates all participants and preserves identity, reviewer and workbook version. Active cycle settings are frozen in this increment.
4. Participants of every role open **My appraisal > Open self-assessment**. Enter goals and achievement narratives, up to three optional contributions, and achievements/development/support narratives. **Add goal** supports more than five goals (technical maximum 100). Competencies are manager-only; employees enter no numerical self-rating.
5. **Save draft** persists partial work. **Save and review submission** saves first and displays the review. **Submit to reporting manager** requires the minimum completed goals and both fields for every entered goal/contribution. Contributions/development may be empty. The server enforces the deadline policy.
6. Submissions become read-only. Managers open **Team appraisals**, select an assigned submission, begin review, enter ratings/comments and save a manager draft. **Return for revision** requires a reason; the employee sees it and can edit/resubmit under the existing cycle deadline policy. A resubmission starts a fresh manager review; prior drafts remain in manager review history. Workflow history and employee submitted revisions remain preserved. After saving a complete manager review, **Submit to HR** preserves the manager ratings and requires confirmation that the appraisal meeting took place. HR reviews the submission, can adjust individual ratings with a reason, and approves the recalculated score. The manager then **releases the HR-approved evaluation** to the employee. HR approval and calibration history remain auditable. The employee opens **View appraisal** and can select **I acknowledge receipt**. Empty contributions score zero with their 10% weight retained; populated applicable items require ratings/comments. Only leadership may be N/A with a reason. See the [approved Phase 5 policy](10-phase-5-status.md).

Writes use version checks. Role changes, deactivation and resets revoke sessions. The last active Super Admin is protected. Active reports must be reassigned before manager removal; unfinished reviewer assignments block demotion/deactivation. Directory changes never rewrite existing appraisal reviewers. HR / Super Admin cannot read/edit others' responses through these employee endpoints. **Account audit log** shows administrative/security events without narratives or credentials.

## Password resets and security

Use **User directory > Reset password** for another active account. It invalidates sessions and outstanding reset links, and requires private handoff and replacement at next sign-in. Administrators change their own password in **Account security**. A local authorized operator can issue a one-use reset link:

```powershell
.venv/Scripts/python.exe -m app.cli issue-reset --email ACCOUNT_OWNER_EMAIL
```

Treat the printed link as a credential and hand it off privately. The browser removes the token fragment immediately; completion checks expiry/one-use status. Public reset requests consistently direct known/unknown accounts to administrator assistance. Email transport is not configured.

Configurable technical defaults: eight-hour absolute sessions, thirty-minute idle timeout/reset-link expiry, ten attempts per principal per fifteen-minute window, IP ceiling five times that limit, and separate durable counters per auth operation. Production security policy D17 remains open. New passwords allow spaces/Unicode and must contain 8–15 characters; changes/resets must differ from the previous password. Existing longer passwords remain usable for sign-in. Argon2id uses 64 MiB, three iterations and two lanes.

Cookies are HttpOnly, SameSite=Lax and scoped to `/api`. Production requires Secure cookies, MySQL and exact HTTPS origins. Mutations need an allowed Origin; authenticated mutations additionally need session-bound CSRF. No wildcard CORS is enabled. Secret rotation needs planned session/CSRF invalidation.

## Verification

From `backend/`:

```powershell
.venv/Scripts/python.exe -m ruff check app tests tools migrations
.venv/Scripts/python.exe -m ruff format --check app tests tools migrations
$env:MI_TEST_DATABASE_URL = 'mysql+pymysql://TEST_USER:ENCODED_PASSWORD@127.0.0.1:3306/leapmetrics_test'
.venv/Scripts/python.exe -m pytest -q
.venv/Scripts/python.exe -m tools.export_openapi
```

Use only an isolated database ending `_test`. Without its URL MySQL tests are skipped, which is not full verification. API tests use rollback-only outer transactions/savepoints. Workflow concurrency tests use independent committed connections in randomly named disposable schemas and need CREATE/DROP DATABASE privileges on the isolated test server. One SQLite parameter intentionally skips the MySQL audit-trigger check.

For migration rehearsal, create a **new empty** database ending `_migration_test`, set `MI_MIGRATION_REHEARSAL_URL`, and run `python -m tools.check_migrations`. It refuses populated schemas and exercises upgrade/downgrade/upgrade plus metadata drift checking. Never use the application database.

From `frontend/`:

```powershell
pnpm api:types
pnpm lint
pnpm test
pnpm build
pnpm exec playwright install chromium
# Stop development API/Vite first; the runner refuses occupied ports.
$env:MI_E2E_DATABASE_URL = 'mysql+pymysql://TEST_USER:ENCODED_PASSWORD@127.0.0.1:3306/leapmetrics_e2e_test'
pnpm test:e2e
```

E2E seeding refuses non-test environments and databases without the `_e2e_test` suffix. The runner generates test-only credentials, migrates, prepares isolated accounts, starts API/Vite, runs Chromium and stops owned process trees, including Windows launcher children. Test records never enter the development database. Failure traces contain test-only data. Export OpenAPI and regenerate frontend types together; export does not connect to the database or reveal local credentials. Hosted CI checks generated contracts; it has not been run remotely here.

## Containers and branding

The on-prem package builds the React UI and FastAPI API into one `mycareer-app` image. MySQL remains a separate container with its own durable volume so database storage and backups are independent of application image upgrades. The app container serves the UI and `/api` from the same origin.

The Linux `amd64` image is built as version 1.1. The transferable archive is `deployment/mycareer-app_1.1_linux_amd64.tar` (about 80 MB). The app image is for Linux x86-64 servers; verify the target with `uname -m` (`x86_64` is expected). `deployment/compose.onprem.yaml` defines MySQL, migrations and the app. The app port is published on all host interfaces at `8080` so a network TLS proxy can reach it. Set `MI_ALLOWED_ORIGINS` and `MI_PUBLIC_BASE_URL` to the exact HTTPS app origin/hostname; never use a wildcard or a localhost value in an on-prem deployment. Install Docker Engine and the Compose v2 plugin using the official instructions for the target Linux distribution; for Ubuntu, see [Docker Engine on Ubuntu](https://docs.docker.com/engine/install/ubuntu/). Restrict cleartext port 8080 to trusted proxy/network sources with host or network firewall rules, and expose HTTPS to users.

### Installation or upgrade on an Ubuntu/Debian-style Linux server

1. Install and start Docker Engine with the Compose v2 plugin, following the official instructions for the exact Linux distribution. Confirm `sudo docker version` and `sudo docker compose version` work. Keep administrative access restricted; membership in the `docker` group grants root-equivalent control of the host.
2. Copy these files from this workspace to the server, for example with SCP or an approved file transfer tool:
   - `deployment/mycareer-app_1.1_linux_amd64.tar`
   - `deployment/compose.onprem.yaml`
   - `deployment/onprem.env.example`
3. Create a private deployment directory and load the app image:

```sh
sudo mkdir -p /opt/mycareer
sudo chown "$USER":"$USER" /opt/mycareer
cd /opt/mycareer
# Place the three copied files in this directory, then:
sudo docker load --input mycareer-app_1.1_linux_amd64.tar
cp onprem.env.example .env
chmod 600 .env
```

4. Before starting an existing installation, inspect its volumes and preserve their exact names. Older installations may use names prefixed with `mi-leapmetrics_`; the newer project may use `mycareer_`. Never select a new empty volume for an existing installation. Set `MI_DATABASE_VOLUME` and `MI_ATTACHMENTS_VOLUME` in `.env` to the existing names, and keep `MI_DATABASE_NAME` and `MI_DATABASE_USER` equal to the old database settings. For an older `mi-leapmetrics` deployment these may be `mi-leapmetrics_database`, `mi-leapmetrics_attachments`, `leapmetrics`, and `leapmetrics`, respectively. For a first installation, keep the `mycareer_database`, `mycareer_attachments`, `mycareer`, and `mycareer` values from the example and create the volumes explicitly:

```sh
sudo docker volume create mycareer_database
sudo docker volume create mycareer_attachments
```

5. Generate three separate secrets and edit `.env` locally on the server. Use fresh hexadecimal values for both database passwords and the application secret:

```sh
openssl rand -hex 32
openssl rand -hex 32
openssl rand -hex 32
```

   Put the first two values in `MYSQL_PASSWORD` and `MYSQL_ROOT_PASSWORD`; use the third for `MI_SECRET_KEY`. Set the exact HTTPS origin as a JSON array, for example `MI_ALLOWED_ORIGINS=["https://mycareer.example.local"]`. Do not reuse development secrets, put secrets in shell history, or commit `.env`.
6. Check the Compose configuration and initialize the database schema, then start the app:

```sh
sudo docker compose --env-file .env -f compose.onprem.yaml config --quiet
sudo docker compose --env-file .env -f compose.onprem.yaml up -d db
sudo docker compose --env-file .env -f compose.onprem.yaml --profile tools run --rm migrate
sudo docker compose --env-file .env -f compose.onprem.yaml up -d app
sudo docker compose --env-file .env -f compose.onprem.yaml ps
```

7. Configure the TLS reverse proxy and certificate. It must forward the original `Host` header to the server's app listener on port 8080. The app port is bound on all interfaces; restrict its cleartext access to the trusted reverse proxy using host/network firewall rules. Do not publish MySQL. Allow inbound HTTPS at the host/network firewall. Production uses secure cookies and rejects non-HTTPS origins.
8. Verify readiness through the HTTPS proxy, then create the first application administrator:

```sh
curl --fail --show-error https://mycareer.example.local/api/v1/health/ready
sudo docker compose --env-file .env -f compose.onprem.yaml exec -it app \
  python -m app.cli bootstrap-admin \
  --email YOUR_WORK_EMAIL --employee-id YOUR_EMPLOYEE_ID --name "YOUR_FULL_NAME"
```

   The bootstrap command prompts privately for a temporary password. Sign in and change it. Create subsequent accounts and appraisal cycles from the application.

MySQL and appraisal attachments persist in explicitly named external Compose volumes selected by `MI_DATABASE_VOLUME` and `MI_ATTACHMENTS_VOLUME`; database name and user are explicit in `MI_DATABASE_NAME` and `MI_DATABASE_USER`. This avoids silently selecting a different volume or database when the Compose project name, folder or product name changes. Compose fails if required values are missing or selected volumes do not exist. Set up tested backups of both volumes before production use and every upgrade. Never run `docker compose down -v` on a live installation. For an upgrade, keep the existing volume names and database settings, back up both volumes, load the replacement image, run the migration command, recreate the app container, and verify readiness and known accounts before releasing the service.

### Lifecycle email alerts

The API queues lifecycle notifications in the same database transaction as the appraisal action, then sends them through the configured company SMTP relay. Failed deliveries are retried; SMTP credentials are read from environment variables and never stored in the outbox. Messages cover cycle launch (participant, with manager copied), employee submission (assigned manager, including return-for-revision guidance), manager return for revision (employee, including the manager's reason and deadline), manager submission for HR approval (active Super Admins), manager release (employee), bulk-import onboarding (employee, with a one-time setup link), and setup-link creation from User directory. Account passwords are never emailed. Setup links expire after seven days by default and work once; the lifetime is configurable with `MI_SETUP_LINK_MINUTES` up to 30 days.

Mail is disabled by default. For Microsoft 365 client SMTP submission, configure these values in the deployment `.env` and recreate the app container. Enter the mailbox password only in that private server file, never in chat or Git:

```dotenv
MI_MAIL_ENABLED=true
MI_MAIL_TEST_MODE=true
MI_MAIL_TEST_RECIPIENT=controlled-test-mailbox@company.example
MI_MAIL_FROM_ADDRESS=hr-mailbox@your-company.com
MI_MAIL_FROM_NAME=MyCareer
MI_SMTP_HOST=smtp.office365.com
MI_SMTP_PORT=587
MI_SMTP_USERNAME=hr-mailbox@your-company.com
MI_SMTP_PASSWORD=enter-mailbox-password-here
MI_SMTP_STARTTLS=true
MI_PUBLIC_BASE_URL=https://mycareer.company.example
MI_SETUP_LINK_MINUTES=10080
```

In test mode, every message is redirected to the test mailbox; real `To` and `Cc` recipients are included in the body for verification and are never sent the message. Onboarding and user-directory setup-link test emails omit working setup links. Verify event types and links. Only then set `MI_MAIL_TEST_MODE=false` to enable live delivery. Use an authorized sender and relay credentials supplied through the server's secret management process. Do not put secrets in chat, Git, or logs. Delivery uses an at-least-once queue, so a relay disconnect immediately after accepting a message can result in a duplicate retry. When changing an existing deployment, update `MI_SETUP_LINK_MINUTES` in its private `.env` to `10080` and recreate the app container; changing the example file alone does not alter a server's existing `.env`.

For Microsoft 365, use a licensed organizational mailbox to authenticate and send from that same address, with port 587 and STARTTLS. Ask the Microsoft 365 administrator to enable Authenticated SMTP for that mailbox and confirm outbound TCP 587 is allowed. MyCareer's current SMTP implementation uses mailbox username/password authentication; if tenant policy requires OAuth, this build needs an OAuth-capable mail transport before it can connect. Microsoft says Basic SMTP AUTH behavior is unchanged through December 2026, after which it is disabled by default for existing tenants; plan the OAuth transition with IT.

For the local development stack, use fresh URL-safe MySQL passwords and an application secret:

```powershell
docker compose --env-file .env -f deployment/compose.yaml up -d db
docker compose --env-file .env -f deployment/compose.yaml --profile tools run --rm migrate
docker compose --env-file .env -f deployment/compose.yaml up --build -d api web
docker compose --env-file .env -f deployment/compose.yaml exec api python -m app.cli bootstrap-admin --email YOUR_WORK_EMAIL --employee-id YOUR_EMPLOYEE_ID --name "YOUR_FULL_NAME"
```

The development container publishes port 8080 on all host interfaces. Open [the development container app](http://localhost:8080) on this machine, or set `MI_DOCKER_ALLOWED_ORIGINS` in `.env` to the exact origin used from another machine. MySQL has no host port mapping. Do not use `down -v` unless intentionally destroying data.

Colors follow verified corporate tokens. Dark surfaces use the official white logo; `VITE_CORPORATE_LOGO_URL` accepts an approved alternative at build time. Light surfaces use a text company name. The web interface uses system fonts. PDF exports embed the redistributable DejaVu Sans font with its license. Production CSP permits corporate-hosted images and no arbitrary remote scripts.


## HR operations upgrade (21 October 2026)

Install the updated backend runtime lock, run `python -m alembic upgrade head` from `backend`, regenerate API types and rebuild the frontend, then restart both processes. Expected migration head is `hrmsmaster`. The migration preserves previously finalized evaluations as approved and adds HRMS location/date-joined fields to user profiles. Appraisal attachments are stored in a private persistent directory; back up that directory along with the database. See [HR operations](11-hr-operations.md) for combined roles, monitoring, immutable form publication, final report downloads, and Excel imports with private setup links. No existing user needs to be recreated.
