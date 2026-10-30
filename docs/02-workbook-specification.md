# Workbook-derived form specification

Source: unchanged `MI Performance Appraisal Development Form YE2025.xlsx`. Exact text for all 136 non-empty/formula cells is in [workbook-cells.md](evidence/workbook-cells.md). [workbook-inventory.json](evidence/workbook-inventory.json) includes blank styled cells and source XML metadata. Sheet/cell references below are verified, not inferred field positions.

## Sheet inventory and formatting

| Sheet | XML used dimension | Meaningful content | Visibility |
|---|---|---|---|
| Sample Evaluation Form | A1:AN79 | A1:F72; 119 populated cells including 10 formulas | Visible |
| RatingScale | D5:D21 | 17 populated text cells, no formulas | Visible |

The form uses 78 merged ranges. Employee goal/contribution descriptions occupy A:B, self-evaluation C:D, manager comments E, manager ratings F. Competency labels occupy A and manager comments B:E. Overall narrative prompts span A:F; there are no separately labelled answers for every subquestion. Headings, borders, tinted bands, wrapped multiline instructions, and tall narrative rows establish the sections. Fonts include Times New Roman, Arial, and Calibri. Totals show integer format `0`, section averages and overall score `0.0`, weighted components `0.00`. Form page orientation is landscape; printing is horizontally and vertically centered. These spreadsheet conventions inform structure, not the web application's corporate theme.

Whole-number 1–5 data validation exists only at F19 and F20:F23/F39:F49, with blank values permitted. Contribution rating cells F30:F32 have no such validation and are populated with numeric zero. The application must reject zero, fractions, strings, booleans, and out-of-range ratings in every section despite these source defects. Sheet-protection metadata is not an authorization mechanism. The sole defined name, local `OLE_LINK1`, points to RatingScale!D5 and has no scoring role. No hidden form fields or embedded logo were found.

## Header fields

| Cell / answer region | Workbook label/value | Proposed application field |
|---|---|---|
| A1 | Annual Performance Appraisal | Form title |
| B1:F1 | MedImpact India (GBS) Pvt Ltd | Versioned employing entity heading, distinct from product branding |
| A2 / B2:D2 | Employee Name | Read-only employee identity snapshot |
| E2 / F2 | Date / `xx/xx/2025` | Appraisal document date; meaning to confirm, not literal placeholder |
| A3 / B3:D3 | Job Title / Position & Emp ID | Separate designation and employee ID |
| E3 / F3 | Department/Country | Separate department and country |
| A4 / B4:D4 | Appraised by | Assigned reporting-manager snapshot |
| E4 / F4 | Appraisal Period / `2025` | Cycle label and start/end dates |

Source year 2025 and development year 2026 are template values. Future cycles should derive labels from versioned cycle settings; never hardcode production deadlines from this file.

## Instructions to retain

The exact source instructions are in A6:F8 (anchor A6). Employee writes the assessment against job responsibilities; manager evaluates with whole numbers 1–5, specific supporting details, and enters the goal count. Up to five goals are provided; unused spaces should be left blank. Contributions cover additional work for the organization. The manager provides overall comments, meets the employee for a performance discussion, completes forthcoming-year responsibilities/objectives, and both parties sign before forwarding the original to HR.

Instruction 3 mistakenly describes contributions and Section II while referring to Section III and a 20% weight. Section II average label A35 incorrectly says Section I. A55's section label is malformed. Preserve exact source text in evidence and correct display wording only with documented approval; do not copy these errors into business rules.

## Section I: goals / job responsibilities

Five rows: 19–23, no prefilled business goals. `xxxxxxxxxxxxxxxxxx` and `Manager to write` are template placeholders, not sample employee data.

| Region | Ownership | Meaning |
|---|---|---|
| A18:B18; A19:B23 | Employee | Responsibility/performance parameter, grounded in role/job description |
| C18:D18; C19:D23 | Employee | Task/goal/objective achievement summary, business contributions and accomplishments |
| E18; E19:E23 | Assigned manager | Reviewer's evaluation with specific supporting details |
| F18; F19:F23 | Assigned manager | Integer rating 1–5 per used row |
| A25:E25 / F25 | Manager count in source | Number of Goals/Objectives/KRA; stored template value 5 |

There is no dedicated expected outcome, target, due date, individual goal weight, or separate achievements-plus-employee-comment pair. Proposed web model has responsibility and achievement narrative, with optional additions only after approval. Maximum five is source-confirmed; minimum count and required text rules are not.

## Section II: practice / organizational contributions

Rows 30–32 provide three slots. A28 examples: training, interviews, team engagement, work on CoEs, knowledge sharing, buddying, coaching, mentoring. A29:D29 asks the employee to name the area and explain contributions.

| Region | Ownership | Meaning |
|---|---|---|
| A30:B32 | Employee | Contribution area/description |
| C30:D32 | Employee | Contribution explanation/self-appraisal narrative; inferred from paired layout and Section II instructions, no separate column header here |
| E30:E32 | Manager | Evaluation comments |
| F30:F32 | Manager | Ratings; source zero values are invalid draft placeholders |
| A34:E34 / F34 | Manager count in source | Reused Number of Goals/Objectives/KRA label; stored template value 3 |

No instruction explicitly permits an entirely empty section or defines a minimum contribution count. The three slots and manual count do not establish a policy for zero contributions.

## Section III: professional competencies

Heading A37 explicitly says supervisor/manager completion. B38:E38 requests manager comments supporting the score. F38 is Rating (1–5). Each row uses label A, manager narrative B:E, numerical rating F. No employee competency-comment column exists.

| Row | Source label |
|---|---|
| 39 | Job Knowledge/Technical Proficiency |
| 40 | Commitment to Teamwork & Collaboration |
| 41 | Communiction & Interpersonal Skills |
| 42 | Productivity & Quality |
| 43 | Customer Focus & Engagement |
| 44 | Adaptability, Dependability & Integrity |
| 45 | Initiative & Innovation |
| 46 | Problem Solving Skills |
| 47 | Administration & Compliance |
| 48 | Learning & Development |
| 49 | Leadership & Team Management Skills (if applicable) |

Retain source labels as versioned provenance; proposed display correction “Communication” requires a recorded editorial decision. Do not invent competency behavioral rubrics: the separate rating scale provides generic competency guidance only. Leadership's applicability test and who declares it are not defined.

## Section IV: overall evaluation and development

| Anchor / area | Source question or instruction | Proposed field/owner |
|---|---|---|
| A59:F59 | Overall evaluation heading says manager completion | Section heading has ambiguous scope because following prompts address employee |
| A60:F60 | Describe areas of excellence, brief points to discuss with manager | Employee section instruction |
| A61:F61 | Most important company/project achievements/contributions during year | Employee business achievements narrative |
| A62:F62 | Important personal/professional development achievements during year | Employee development achievements narrative |
| A63:F63, subquestion 1 | Professional development goals for 2026; growth/development in next six months | Employee proposed six-month growth goals after discussion; ownership to confirm |
| A63:F63, subquestion 2 | Technical and personal development needs/plans in 2026 and support required | Proposed separate employee needs, plan, support fields, retaining one combined source prompt |
| A64:F64 | Manager's Comments | Manager section instruction |
| A65:F66 | What employee did particularly well to drive results, add value, consult/collaborate, take accountability; add rows as necessary | Manager strengths narrative / repeated points |
| A67:F69 | How employee could be more effective in those areas; add rows as necessary | Manager improvement narrative / repeated points |
| A70:F70 | Sign Off | Sign-off section |
| A71; B71:C71; D71; E71:F71 | Manager Signature, signature space, Date, date space | Manager sign-off event, mapping to finalization/release to confirm |
| A72; B72:C72; D72; E72:F72 | Employee Signature, signature space, Date, date space | Employee acknowledgement event, equivalence to signature to confirm |

Source has no distinct labelled “overall manager comments,” post-meeting employee comments, next-year objectives response, or final categorical rating field beyond these narratives and the calculated score. The instructions mention some of these. Record them as unresolved additions, not missing extraction. Digital acknowledgement is proposed; no legal equivalence to a handwritten signature is assumed.

## Rating definitions

Authoritative detailed scale: RatingScale!D6:D21; repeated in Sample Evaluation Form!A10:A14.

| Rating | Label | Goal performance | Competency guidance |
|---|---|---|---|
| 1 | Unsatisfactory | Rarely achieves established goals; significant and immediate improvement | Rarely demonstrates behaviors; significant development |
| 2 | Inconsistent | Achieves some goals; improvement needed | Some or inconsistent behaviors; may fit new/more challenging positions or development needs |
| 3 | Effective | Consistently achieves goals | Consistently effective behaviors |
| 4 | Highly Effective | Achieves and often exceeds goals | Consistently effective, often exceptional behaviors |
| 5 | Exceptional | Significantly and consistently exceeds goals | Consistently exceptional; role model and mentor |

Exact original sentences remain in the cell inventory, including the rating-2 continuation at D18. This scale describes integer item ratings, not bands for fractional overall scores. No overall-score-to-label thresholds are supplied.

## Complete formula inventory

All formulas are on Sample Evaluation Form; there are exactly ten.

| Cell | Exact formula | Source display format | Stored cached result |
|---|---|---|---|
| F24 | `=SUM(F19:F23)` | `0` | 0 |
| F26 | `=F24/F25` | `0.0` | 0 |
| F33 | `=SUM(F30:F32)` | `0` | 0 |
| F35 | `=F33/F34` | `0.0` | 0 |
| F50 | `=SUM(F39:F49)` | `0` | 0 |
| F51 | `=AVERAGE(F39:F49)` | `0.0` | #DIV/0! |
| F53 | `=(F26*(7/10))` | `0.00` | 0 |
| F54 | `=(F35*(1/10))` | `0.00` | 0 |
| F55 | `=(F51*(2/10))` | `0.00` | #DIV/0! |
| F57 | `=SUM(F53:F55)` | `0.0` | #DIV/0! |

The dependency chain confirms `(goals total / entered goal count × .70) + (contribution total / entered contribution count × .10) + (numeric competency average × .20)`. There is no `ROUND`, truncation, or overall category formula. Number formats alter displayed precision, not the values used by downstream formulas. Excel's cached default form cannot produce a valid overall score because the competency section is blank.

## Calculation discrepancy and proposed policy

The master prompt's weights match the workbook. Its “average valid applicable ratings” rule is not identical to source formulas for goals and contributions: Excel SUM skips blank cells, but a manually retained divisor of 5 or 3 still depresses the average. Example: two goal ratings of 4 with F25 still 5 produce 1.6, whereas two complete applicable goals average 4.0. This is a discrepancy requiring a business decision before implementation.

Proposed policy, **not approved**: use active applicable items as the denominator; require a valid rating for every applicable item at finalization; exclude unused goal/contribution slots; distinguish missing ratings from explicit N/A; allow N/A leadership only with an applicability reason and authorized decision. Require at least one applicable rating in each weighted section. Reject finalization for an empty section until an approved alternative policy exists. Do not redistribute weights automatically. Use exact decimal arithmetic without intermediate rounding; display section/overall values at one decimal and components at two to match source formatting. Explicit display tie handling still needs approval. Store the unrounded authoritative result and scoring version; define precision and tie rules before choosing final DECIMAL scale.

Drafts can remain incomplete and must show incomplete status, never a misleading zero score. Numerical employee self-scores are forbidden in API schemas as well as UI. No finalized score is recalculated after configuration changes.
