from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ClientDocumentResponse(BaseModel):
    id: int
    client_id: int
    filename: str
    file_url: str | None
    file_size: int | None
    uploaded_by: str | None
    uploaded_at: datetime
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class ClientWithDocumentsResponse(BaseModel):
    client_id: int
    client_name: str
    documents: list[ClientDocumentResponse]
