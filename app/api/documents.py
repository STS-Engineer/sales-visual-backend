import logging
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import RedirectResponse, Response

from app.core.auth import get_current_user, require_admin
from app.db.session import get_db_session
from app.models.client import Client
from app.models.client_document import ClientDocument
from app.models.user import User
from app.models.user_client import UserClient
from app.schemas.document import ClientDocumentResponse, ClientWithDocumentsResponse
from app.services.blob_service import delete_blob, upload_document_to_blob

router = APIRouter(prefix="/documents", tags=["documents"])
logger = logging.getLogger(__name__)

MAX_DOCUMENT_FILES = 100
MAX_DOCUMENT_UPLOAD_BYTES = 500 * 1024 * 1024


def _client_documents_response(client: Client) -> ClientWithDocumentsResponse:
    documents = sorted(
        client.documents,
        key=lambda document: document.uploaded_at,
        reverse=True,
    )
    return ClientWithDocumentsResponse(
        client_id=client.id,
        client_name=client.name,
        documents=documents,
    )


def _filter_clients_for_user(query, current_user: User):
    if current_user.role == "admin":
        return query

    return query.where(
        Client.id.in_(
            select(UserClient.client_id).where(UserClient.user_id == current_user.id)
        )
    )


async def _get_document_for_user(
    document_id: int,
    session: AsyncSession,
    current_user: User,
) -> ClientDocument:
    query = (
        select(ClientDocument)
        .join(ClientDocument.client)
        .where(ClientDocument.id == document_id)
    )
    if current_user.role != "admin":
        query = query.where(
            ClientDocument.client_id.in_(
                select(UserClient.client_id).where(UserClient.user_id == current_user.id)
            )
        )

    result = await session.execute(query)
    document = result.scalar_one_or_none()
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document


@router.get("", response_model=list[ClientWithDocumentsResponse])
async def list_documents(
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Client)
        .options(selectinload(Client.documents))
        .where(Client.is_active.is_(True))
        .order_by(Client.name)
    )
    query = _filter_clients_for_user(query, current_user)

    result = await session.execute(query)
    clients = result.scalars().all()
    return [_client_documents_response(client) for client in clients]


@router.post("/upload")
async def upload_document(
    client_id: int = Form(),
    description: str | None = Form(default=None),
    files: list[UploadFile] = File(alias="files[]"),
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    client = await session.get(Client, client_id)
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")

    if len(files) > MAX_DOCUMENT_FILES:
        raise HTTPException(
            status_code=400,
            detail=f"Maximum {MAX_DOCUMENT_FILES} files are allowed",
        )

    file_payloads: list[tuple[UploadFile, bytes]] = []
    total_size = 0
    for file in files:
        file_content = await file.read()
        total_size += len(file_content)
        if total_size > MAX_DOCUMENT_UPLOAD_BYTES:
            raise HTTPException(
                status_code=400,
                detail="Maximum total upload size is 500 MB",
            )
        file_payloads.append((file, file_content))

    uploaded = 0
    failed = 0
    skipped = 0
    results = []

    for file, file_content in file_payloads:
        filename = Path(file.filename or "document.xlsx").name

        if not filename.lower().endswith(".xlsx"):
            failed += 1
            results.append(
                {
                    "filename": filename,
                    "status": "failed",
                    "reason": "Only .xlsx files are accepted",
                }
            )
            continue

        existing = await session.execute(
            select(ClientDocument).where(
                ClientDocument.client_id == client.id,
                ClientDocument.filename == filename,
            )
        )
        if existing.scalar_one_or_none() is not None:
            skipped += 1
            results.append(
                {
                    "filename": filename,
                    "status": "skipped",
                    "reason": "already exists",
                }
            )
            continue

        blob_name = None
        try:
            blob_result = upload_document_to_blob(
                file_content=file_content,
                client_name=client.name,
                filename=filename,
            )
            blob_name = blob_result["blob_name"]

            document = ClientDocument(
                client_id=client.id,
                filename=filename,
                blob_name=blob_name,
                file_url=blob_result["sas_url"],
                file_size=len(file_content),
                uploaded_by=current_user.name,
                description=description or None,
            )
            session.add(document)
            await session.commit()

            uploaded += 1
            results.append(
                {
                    "filename": filename,
                    "status": "uploaded",
                    "reason": None,
                }
            )
        except Exception as exc:
            await session.rollback()
            if blob_name:
                try:
                    delete_blob(blob_name)
                    logger.warning(
                        "Rolled back Azure blob upload after database failure: %s",
                        blob_name,
                    )
                except Exception:
                    logger.exception("Failed to delete blob after database rollback: %s", blob_name)
            failed += 1
            results.append(
                {
                    "filename": filename,
                    "status": "failed",
                    "reason": str(exc),
                }
            )

    return {
        "uploaded": uploaded,
        "failed": failed,
        "skipped": skipped,
        "results": results,
    }


@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(require_admin),
):
    document = await session.get(ClientDocument, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")

    if document.blob_name:
        delete_blob(document.blob_name)

    await session.delete(document)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{document_id}/download")
async def download_document(
    document_id: int,
    session: AsyncSession = Depends(get_db_session),
    current_user: User = Depends(get_current_user),
):
    document = await _get_document_for_user(document_id, session, current_user)
    if document.file_url and document.file_url.startswith("https://"):
        return RedirectResponse(url=document.file_url)

    raise HTTPException(status_code=404, detail="File not found")
