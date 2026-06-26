from datetime import datetime

from pydantic import BaseModel, ConfigDict


class NotificationLogResponse(BaseModel):
    id: int
    report_id: int
    sent_to: str
    sent_at: datetime
    success: bool
    error_msg: str | None

    model_config = ConfigDict(from_attributes=True)
