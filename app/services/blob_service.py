import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path


EXCEL_CONTENT_TYPE = (
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
)
DEFAULT_SAS_EXPIRY_HOURS = 720


def _get_blob_config() -> tuple[str | None, str]:
    return (
        os.getenv("AZURE_CONNECTION_STRING"),
        os.getenv("AZURE_BLOB_CONTAINER", "sales-visual-files"),
    )


def _require_blob_config() -> tuple[str, str]:
    connection_string, container_name = _get_blob_config()
    if not connection_string:
        raise RuntimeError("AZURE_CONNECTION_STRING is not configured")
    if not container_name:
        raise RuntimeError("AZURE_BLOB_CONTAINER is not configured")
    return connection_string, container_name


def _sanitize_path_segment(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", value).strip("_") or "client"


def _parse_connection_string(connection_string: str) -> dict[str, str]:
    parts: dict[str, str] = {}
    for item in connection_string.split(";"):
        if not item or "=" not in item:
            continue
        key, value = item.split("=", 1)
        parts[key] = value
    return parts


def _get_blob_clients():
    from azure.storage.blob import BlobServiceClient, ContainerClient

    connection_string, container_name = _require_blob_config()
    service_client = BlobServiceClient.from_connection_string(connection_string)
    container_client = ContainerClient.from_connection_string(
        connection_string,
        container_name=container_name,
    )
    return service_client, container_client, connection_string, container_name


def ensure_container_exists() -> None:
    """Create container if it doesn't exist."""
    connection_string, container_name = _get_blob_config()
    if not connection_string:
        return

    from azure.core.exceptions import ResourceExistsError
    from azure.storage.blob import ContainerClient

    container_client = ContainerClient.from_connection_string(
        connection_string,
        container_name=container_name,
    )
    try:
        container_client.create_container(exist_ok=True)
    except TypeError:
        try:
            container_client.create_container()
        except ResourceExistsError:
            pass


def generate_sas_url(blob_name: str, expiry_hours: int = DEFAULT_SAS_EXPIRY_HOURS) -> str:
    """Generate a fresh SAS URL for an existing blob (30 days default)."""
    service_client, container_client, connection_string, container_name = _get_blob_clients()
    blob_client = container_client.get_blob_client(blob_name)
    parts = _parse_connection_string(connection_string)
    account_name = parts.get("AccountName") or service_client.account_name
    account_key = parts.get("AccountKey")

    if not account_key:
        raise RuntimeError("AccountKey is required to generate blob SAS URLs")

    from azure.storage.blob import BlobSasPermissions, generate_blob_sas

    expires_at = datetime.now(timezone.utc) + timedelta(hours=expiry_hours)
    sas_token = generate_blob_sas(
        account_name=account_name,
        container_name=container_name,
        blob_name=blob_name,
        account_key=account_key,
        permission=BlobSasPermissions(read=True),
        expiry=expires_at,
    )
    return f"{blob_client.url}?{sas_token}"


def upload_excel_to_blob(
    file_content: bytes,
    client_name: str,
    year: int,
    month: int,
    filename: str,
) -> dict:
    """
    Upload an Excel file to Azure Blob Storage.
    Returns blob metadata including a 30-day read SAS URL.
    """
    _service_client, container_client, _connection_string, _container_name = _get_blob_clients()
    safe_client_name = _sanitize_path_segment(client_name)
    safe_filename = Path(filename or "report.xlsx").name
    blob_name = f"clients/{safe_client_name}/{year}-{month:02d}/{safe_filename}"
    blob_client = container_client.get_blob_client(blob_name)

    from azure.storage.blob import ContentSettings

    blob_client.upload_blob(
        file_content,
        overwrite=True,
        content_settings=ContentSettings(content_type=EXCEL_CONTENT_TYPE),
    )

    sas_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=DEFAULT_SAS_EXPIRY_HOURS
    )
    sas_url = generate_sas_url(blob_name, expiry_hours=DEFAULT_SAS_EXPIRY_HOURS)

    return {
        "blob_name": blob_name,
        "blob_url": blob_client.url,
        "sas_url": sas_url,
        "sas_expires_at": sas_expires_at.isoformat(),
    }


def upload_document_to_blob(
    file_content: bytes,
    client_name: str,
    filename: str,
) -> dict:
    """
    Upload a historical client Excel document to Azure Blob Storage.
    Returns blob metadata including a 30-day read SAS URL.
    """
    _service_client, container_client, _connection_string, _container_name = _get_blob_clients()
    safe_client_name = _sanitize_path_segment(client_name)
    safe_filename = Path(filename or "document.xlsx").name
    blob_name = f"documents/{safe_client_name}/{safe_filename}"
    blob_client = container_client.get_blob_client(blob_name)

    from azure.storage.blob import ContentSettings

    blob_client.upload_blob(
        file_content,
        overwrite=True,
        content_settings=ContentSettings(content_type=EXCEL_CONTENT_TYPE),
    )

    sas_expires_at = datetime.now(timezone.utc) + timedelta(
        hours=DEFAULT_SAS_EXPIRY_HOURS
    )
    sas_url = generate_sas_url(blob_name, expiry_hours=DEFAULT_SAS_EXPIRY_HOURS)

    return {
        "blob_name": blob_name,
        "blob_url": blob_client.url,
        "sas_url": sas_url,
        "sas_expires_at": sas_expires_at.isoformat(),
    }


def delete_blob(blob_name: str) -> bool:
    """Delete a blob by its name. Returns True if deleted."""
    if not blob_name:
        return False

    from azure.core.exceptions import ResourceNotFoundError

    _service_client, container_client, _connection_string, _container_name = _get_blob_clients()
    blob_client = container_client.get_blob_client(blob_name)

    try:
        blob_client.delete_blob()
    except ResourceNotFoundError:
        return False

    return True
