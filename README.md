# MyCareer

Performance Management System for MedImpact International.

## Current status

Phases 2-5 are implemented as of 20 October 2026 (Asia/Calcutta): secure sign-in, HR / Super Admin user administration, manager assignments, appraisal cycle setup, workbook-based employee goals and self-assessment, draft/review/submission, and preserved revisions. Manager ratings, HR calibration and approval, manager release, secure supporting attachments, and employee acknowledgement are implemented. The supplied workbook is unchanged.

The HR operations increment adds combined Manager + HR access, appraisal monitoring, a versioned form builder, Excel/PDF reports, and validated bulk Excel user import. See [HR operations and usage](docs/11-hr-operations.md).

See [setup and execution](docs/07-running.md) and [current implementation status](docs/10-phase-5-status.md). No default application accounts exist; create the initial administrator with the documented secure CLI command.

The approved scoring policy uses zero for an empty contributions section, retaining its weight. Rules are versioned and finalized results are preserved. See [Phase 5 policy and validation](docs/10-phase-5-status.md).

Start with [the discovery summary](docs/01-discovery.md). The documents distinguish confirmed source requirements from proposed designs and decisions requiring business approval.

| Deliverable | Document |
|---|---|
| Requirements summary, repository inspection, permission matrix, workflow | [Discovery](docs/01-discovery.md) |
| Source fields, instructions, formulas, formatting, discrepancies | [Workbook specification](docs/02-workbook-specification.md) |
| Tables, constraints, relationships, historical integrity | [Database design](docs/03-database-design.md) |
| API endpoint inventory, authorization, DTO contracts | [API proposal](docs/04-api-contract.md) |
| Folder structure, security, dependencies, branding | [Technical architecture](docs/05-technical-architecture.md) |
| Business decisions, assumptions, implementation phases and acceptance tests | [Delivery plan](docs/06-delivery-plan.md) |

Exact source evidence is in [the cell inventory](docs/evidence/workbook-cells.md), [workbook metadata](docs/evidence/workbook-inventory.json), [branding inventory](docs/evidence/branding-inventory.json), and [candidate package metadata](docs/evidence/version-candidates.json).

## Reproduce discovery

`tools/inspect_assets.py` uses Python's standard library to read XLSX ZIP/XML without changing or recalculating the workbook and retrieves the public corporate homepage and linked CSS. Run `python tools/inspect_assets.py` from the repository root. Network access is required. This replaces only generated evidence files under `docs/evidence/`; remote website evidence can change between runs.

Run `python tools/verify_discovery.py` to check the source hash, complete cell inventory, verified formula addresses, and documentation links. This validates discovery evidence, not application behavior.

Application setup, exact dependency locks, Docker configuration, and foundation tests are now available. See the delivery plan for subsequent phase gates and unresolved business rules.
