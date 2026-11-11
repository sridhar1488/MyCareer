from sqlalchemy import case

from app.modules.appraisals.models import Appraisal
from app.modules.reviews.models import Acknowledgement


def appraisal_stage():
    return case(
        (Appraisal.state == "DRAFT", case((Appraisal.started_at.is_(None), "NOT_STARTED"), else_="DRAFT")),
        (Acknowledgement.appraisal_id.is_not(None), "ACKNOWLEDGED"),
        else_=Appraisal.state,
    )
