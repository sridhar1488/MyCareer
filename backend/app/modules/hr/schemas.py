from datetime import datetime

from pydantic import BaseModel


class MonitorRow(BaseModel):
    id: str
    employee_id: str
    employee_name: str
    employee_active: bool
    department: str
    designation: str
    manager_id: str
    manager_name: str
    manager_active: bool
    cycle_id: str
    cycle_title: str
    cycle_state: str
    status: str
    pending_action: str
    responsible_name: str | None
    submission_deadline: datetime
    overdue: bool
    deadline_enforced: bool
    submitted_at: datetime | None
    finalized_at: datetime | None
    released_at: datetime | None
    acknowledged_at: datetime | None


class ManagerStatus(BaseModel):
    manager_id: str
    manager_name: str
    manager_active: bool
    total: int
    status_counts: dict[str, int]


class MonitorResponse(BaseModel):
    total: int
    status_counts: dict[str, int]
    items: list[MonitorRow]
    managers: list[ManagerStatus]
    manager_total: int
    page: int
    page_size: int
    view: str


class FilterOption(BaseModel):
    id: str
    label: str


class MonitorOptions(BaseModel):
    cycles: list[FilterOption]
    managers: list[FilterOption]
