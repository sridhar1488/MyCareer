from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.dependencies import Identity, active_identity
from app.modules.users.models import RoleCode

router = APIRouter(prefix="/help", tags=["Help and support"])


class ScreenPreview(BaseModel):
    page_title: str
    nav_items: list[str]
    eyebrow: str
    status: str
    details: list[str]
    action: str


class HelpStep(BaseModel):
    title: str
    description: str
    bullets: list[str]
    screenshot: ScreenPreview


class FAQ(BaseModel):
    question: str
    answer: str


class Guide(BaseModel):
    audience: str
    title: str
    summary: str
    steps: list[HelpStep]
    faqs: list[FAQ]


class HelpContent(BaseModel):
    guides: list[Guide]


def screen(page_title, nav_items, eyebrow, status, details, action):
    return ScreenPreview(
        page_title=page_title,
        nav_items=nav_items,
        eyebrow=eyebrow,
        status=status,
        details=details,
        action=action,
    )


EMPLOYEE_GUIDE = Guide(
    audience="Available to everyone",
    title="Complete your self-assessment",
    summary="Prepare your reflection, add supporting evidence, and follow the review through to release.",
    steps=[
        HelpStep(
            title="Open your appraisal cycle",
            description="When HR opens a cycle, MyCareer shows it in Your appraisal cycles. The notice includes your deadline and copies your manager.",
            bullets=["Select Open self-assessment on the cycle you need to complete."],
            screenshot=screen(
                "Your appraisal cycles",
                ["My appraisal", "Account security"],
                "YOUR APPRAISAL CYCLES",
                "DRAFT",
                ["Performance Evaluation Cycle", "Deadline: 30 Nov 2026", "Reporting manager: Jordan Lee"],
                "Open self-assessment",
            ),
        ),
        HelpStep(
            title="Write goals and contributions",
            description="Use the form sections to describe your goals, outcomes, contributions, achievements, and development needs.",
            bullets=[
                "Complete the required number of goals shown for the cycle.",
                "Save a draft if you want to return later.",
            ],
            screenshot=screen(
                "Self-assessment",
                ["My appraisal", "Account security"],
                "GOALS AND JOB RESPONSIBILITIES",
                "DRAFT",
                [
                    "Goal 1",
                    "Describe the goal and the progress you made",
                    "Contribution 1",
                    "Add your achievement narrative",
                ],
                "Save draft",
            ),
        ),
        HelpStep(
            title="Attach supporting documents",
            description="Add evidence such as certifications, appreciation, client feedback, or other work-related documents.",
            bullets=[
                "Check the file type and per-file size limit displayed beside the upload control.",
                "Only attach material relevant to your appraisal.",
            ],
            screenshot=screen(
                "Supporting documents",
                ["My appraisal", "Account security"],
                "EVIDENCE",
                "1 FILE ATTACHED",
                ["Leadership certificate.pdf", "Uploaded to this appraisal", "Add another document"],
                "Choose files",
            ),
        ),
        HelpStep(
            title="Submit and follow the review",
            description="After submission, your manager reviews the appraisal and sends the evaluation to HR for calibration and approval. Your manager releases the approved scores after discussing them with you.",
            bullets=[
                "If the manager returns the appraisal, make the requested updates and submit again.",
                "Once your evaluation is released, view it in MyCareer and acknowledge receipt.",
            ],
            screenshot=screen(
                "Appraisal status",
                ["My appraisal", "Account security"],
                "PERFORMANCE EVALUATION CYCLE",
                "IN REVIEW",
                [
                    "Self-assessment submitted",
                    "Manager review",
                    "HR calibration and approval",
                    "Manager release",
                ],
                "View evaluation when released",
            ),
        ),
    ],
    faqs=[
        FAQ(
            question="Can I edit after I submit?",
            answer="Submitted responses are locked while they are under review. If your manager returns the appraisal, edit the requested sections and submit the revision.",
        ),
        FAQ(
            question="Can I add more than five goals?",
            answer="Use Add goal to include additional goals when the form allows it. The cycle also shows its minimum goal requirement.",
        ),
        FAQ(
            question="Who can see my attachments?",
            answer="Appraisal evidence is available only to people authorized to review that appraisal as it moves through the workflow.",
        ),
    ],
)

MANAGER_GUIDE = Guide(
    audience="Manager role",
    title="Review your team's appraisals",
    summary="Review employee submissions, record ratings and comments, submit to HR, then release approved results after the discussion.",
    steps=[
        HelpStep(
            title="Find work awaiting your review",
            description="Open Team appraisals to see submissions assigned to you and their current workflow status.",
            bullets=["Open an employee's submission to begin reviewing the submitted revision."],
            screenshot=screen(
                "Team appraisals",
                ["My appraisal", "Team appraisals", "Account security"],
                "YOUR TEAM",
                "1 NEEDS REVIEW",
                [
                    "Avery Morgan | Self-assessment submitted",
                    "Taylor Rivera | Under review",
                    "Cycle deadline: 30 Nov 2026",
                ],
                "Review appraisal",
            ),
        ),
        HelpStep(
            title="Evaluate and save your review",
            description="Review the employee's responses and enter ratings, evidence-based comments, and the form's manager-only assessments.",
            bullets=[
                "Save a manager draft while work is in progress.",
                "If the employee needs to revise their submission, return it with a clear reason.",
            ],
            screenshot=screen(
                "Manager review",
                ["My appraisal", "Team appraisals", "Account security"],
                "MANAGER EVALUATION",
                "DRAFT",
                [
                    "Goal 1 rating: 4 - Exceeds expectations",
                    "Comment: Delivered the planned outcome",
                    "Competencies and contributions",
                ],
                "Save manager draft",
            ),
        ),
        HelpStep(
            title="Submit the evaluation to HR",
            description="When your review is complete, confirm the review meeting and submit the evaluation to HR for calibration and approval.",
            bullets=[
                "Your submitted evaluation is preserved for HR review.",
                "The employee does not see the scores at this stage.",
            ],
            screenshot=screen(
                "Submit evaluation to HR",
                ["My appraisal", "Team appraisals", "Account security"],
                "REVIEW SIGN-OFF",
                "READY FOR HR",
                ["Confirm review meeting took place", "Manager evaluation saved", "Scores remain unreleased"],
                "Submit to HR for approval",
            ),
        ),
        HelpStep(
            title="Release after HR approval and your discussion",
            description="Once HR approves or calibrates the evaluation, it returns to you. Discuss the approved result with the employee, confirm the meeting in MyCareer, and release the scores.",
            bullets=[
                "The employee is notified after you release the evaluation.",
                "The employee can then view the result and acknowledge receipt.",
            ],
            screenshot=screen(
                "Evaluation release",
                ["My appraisal", "Team appraisals", "Account security"],
                "HR-APPROVED RESULT",
                "READY TO RELEASE",
                ["HR calibration complete", "Review meeting confirmed", "Employee: Avery Morgan"],
                "Release scores to employee",
            ),
        ),
    ],
    faqs=[
        FAQ(
            question="What if the employee has not submitted?",
            answer="The appraisal remains in the employee's draft state. Contact the employee before the cycle deadline if they need help.",
        ),
        FAQ(
            question="Can I change scores after submitting to HR?",
            answer="The manager submission is preserved as a record. HR handles any calibration changes; the approved evaluation returns to you for the employee discussion and release.",
        ),
        FAQ(
            question="Does HR approval release the scores automatically?",
            answer="No. After HR approves, you discuss the approved result with the employee and release it from your manager workflow.",
        ),
    ],
)

ADMIN_GUIDE = Guide(
    audience="Super Admin / HR role",
    title="Set up and administer appraisal cycles",
    summary="Configure the form and participants, monitor progress, complete calibration, approve results, and download final reports.",
    steps=[
        HelpStep(
            title="Configure the appraisal form",
            description="Use Appraisal forms to create sections and questions for future cycles. Published form versions remain attached to the cycles that use them.",
            bullets=[
                "Review section labels and question instructions before publishing.",
                "Confirm scoring weights and manager-only items for the intended audience.",
            ],
            screenshot=screen(
                "Appraisal form builder",
                [
                    "HR approval queue",
                    "HR monitoring",
                    "Final evaluations",
                    "Appraisal forms",
                    "User directory",
                ],
                "FORM DESIGN",
                "DRAFT VERSION",
                ["Goals and responsibilities", "Contributions", "Competencies", "Section weights"],
                "Publish form version",
            ),
        ),
        HelpStep(
            title="Create a cycle and assign participants",
            description="Create an appraisal cycle, select its form and participants, set a submission deadline, then activate it when ready.",
            bullets=[
                "Every participant needs an active reporting manager.",
                "Activation notifies assigned employees and copies each employee's manager.",
            ],
            screenshot=screen(
                "Appraisal cycles",
                [
                    "HR approval queue",
                    "HR monitoring",
                    "Final evaluations",
                    "Appraisal forms",
                    "User directory",
                ],
                "CYCLE SETUP",
                "DRAFT",
                ["Cycle: Performance Evaluation Cycle", "Participants: 42", "Deadline: 30 Nov 2026"],
                "Activate cycle",
            ),
        ),
        HelpStep(
            title="Monitor progress and calibrate evaluations",
            description="Use HR monitoring to check employee and manager progress. In HR approval queue, review manager submissions and apply calibration changes where needed.",
            bullets=[
                "Finalized manager submissions are preserved for audit history.",
                "Approve the calibrated result to return it to the manager for discussion and release.",
            ],
            screenshot=screen(
                "HR approval queue",
                [
                    "HR approval queue",
                    "HR monitoring",
                    "Final evaluations",
                    "Appraisal forms",
                    "User directory",
                ],
                "CALIBRATION",
                "AWAITING APPROVAL",
                [
                    "Employee: Avery Morgan",
                    "Manager submission: Received",
                    "Calibration changes: 1 rating updated",
                ],
                "Approve evaluation",
            ),
        ),
        HelpStep(
            title="Download completed evaluations",
            description="After evaluations are finalized, open Final evaluations to filter the results and download an Excel or PDF report.",
            bullets=[
                "HR access to finalized evaluations is view-only.",
                "Use the report filters to select the completed cycles and population you need.",
            ],
            screenshot=screen(
                "Final evaluations",
                [
                    "HR approval queue",
                    "HR monitoring",
                    "Final evaluations",
                    "Appraisal forms",
                    "User directory",
                ],
                "COMPLETED EVALUATIONS",
                "FINAL",
                [
                    "Cycle: Performance Evaluation Cycle",
                    "Results: Approved and released",
                    "Export format: Excel or PDF",
                ],
                "Download report",
            ),
        ),
    ],
    faqs=[
        FAQ(
            question="Can HR also manage employees?",
            answer="Yes. Super Admin is an additional role, so an HR account may also have Manager access when it has direct reports.",
        ),
        FAQ(
            question="Can an Employee account receive Super Admin access?",
            answer="No. Employee and Super Admin access cannot be combined. Create an HR / Super Admin account, or use Manager plus additional Super Admin access when the HR user also manages staff.",
        ),
        FAQ(
            question="Do form edits change a cycle already in progress?",
            answer="No. A cycle keeps the form version assigned when it was created. Publish changes for future cycles.",
        ),
        FAQ(
            question="Can HR edit a completed final evaluation?",
            answer="Final evaluations are view-only after approval. Use the calibration workflow before approval to make rating corrections.",
        ),
    ],
)


@router.get("/content", response_model=HelpContent)
def content(actor: Identity = Depends(active_identity)):
    roles = set(actor.user.roles)
    guides = [EMPLOYEE_GUIDE]
    if RoleCode.MANAGER in roles:
        guides.append(MANAGER_GUIDE)
    if RoleCode.SUPER_ADMIN in roles:
        guides.append(ADMIN_GUIDE)
    return HelpContent(guides=guides)
