from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class VisualResponse(BaseModel):
    id: int
    monday_item_id: str
    name: str
    status: str | None
    power_bi_url: str | None
    file_url: str | None
    kam: str | None
    vp_sales: str | None
    end_date: date | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
