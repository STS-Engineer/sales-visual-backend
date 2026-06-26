from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MonthlyReportResponse(BaseModel):
    id: int
    client_id: int
    monday_item_id: str | None
    report_year: int
    report_month: int
    statut: str
    end_date: date | None
    fichier_filename: str | None
    fichier_path: str | None
    fichier_url: str | None
    marked_done_at: datetime | None
    notification_sent: bool
    notification_sent_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class NotificationSummaryResponse(BaseModel):
    attempted: int
    sent: int
    failed: int


class MarkDoneResponse(BaseModel):
    report_id: int
    notifications: NotificationSummaryResponse


class ReportKamResponse(BaseModel):
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ReportListItemResponse(BaseModel):
    id: int
    client_name: str
    person_name: str
    power_bi_url: str | None
    power_bi_label: str | None
    statut: str
    end_date: date | None
    report_year: int
    report_month: int
    fichier_filename: str | None
    fichier_url: str | None
    notification_sent: bool
    kams: list[ReportKamResponse] = []


class InitMonthRequest(BaseModel):
    year: int = Field(ge=2000, le=2100)
    month: int = Field(ge=1, le=12)


class InitMonthResponse(BaseModel):
    created: int
    skipped: int
