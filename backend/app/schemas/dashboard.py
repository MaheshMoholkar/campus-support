from pydantic import BaseModel


class Count(BaseModel):
    label: str
    count: int


class DashboardOut(BaseModel):
    by_status: list[Count]
    by_ticket_for: list[Count]
    by_institute: list[Count]
    open_per_developer: list[Count]
    avg_hours_queue_to_close: float | None
