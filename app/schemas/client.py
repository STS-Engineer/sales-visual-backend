from datetime import datetime

from pydantic import BaseModel, ConfigDict


class KamResponse(BaseModel):
    id: int
    name: str
    email: str

    model_config = ConfigDict(from_attributes=True)


class ClientResponse(BaseModel):
    id: int
    name: str
    power_bi_url: str | None
    power_bi_label: str | None
    vp_sales_name: str | None
    person_name: str
    is_active: bool
    kams: list[KamResponse] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ClientUpdate(BaseModel):
    power_bi_url: str | None = None
    power_bi_label: str | None = None
    vp_sales_name: str | None = None


class ClientWithReportsResponse(ClientResponse):
    reports: list["MonthlyReportResponse"] = []


from app.schemas.report import MonthlyReportResponse

ClientWithReportsResponse.model_rebuild()
