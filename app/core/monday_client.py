"""
Async HTTP client for the Monday.com GraphQL API (version 2025-01).

Provides low-level helpers for authenticated requests and high-level
functions that fetch board items and metadata.
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

MONDAY_API_VERSION = "2025-01"
MONDAY_API_URL = settings.MONDAY_API_URL
API_TOKEN = settings.MONDAY_API_TOKEN


async def monday_request(
    query: str,
    variables: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    Execute a single GraphQL query against Monday.com and return the JSON body.

    Parameters
    ----------
    query : str
        The GraphQL query or mutation string.
    variables : dict or None
        Optional GraphQL variables.

    Returns
    -------
    dict
        Parsed JSON response from the Monday.com API.

    Raises
    ------
    RuntimeError
        If the HTTP status is not 2xx or the response contains an ``errors`` key.
    """
    headers = {
        "Authorization": API_TOKEN,
        "API-Version": MONDAY_API_VERSION,
        "Content-Type": "application/json",
    }

    payload: dict[str, Any] = {"query": query}
    if variables:
        payload["variables"] = variables

    logger.debug(
        "POST %s — query=%.200s… variables=%s",
        MONDAY_API_URL,
        query.strip(),
        variables,
    )

    async with httpx.AsyncClient(timeout=60.0) as client:
        response = await client.post(MONDAY_API_URL, json=payload, headers=headers)

    if response.status_code != 200:
        logger.error(
            "Monday API returned HTTP %s: %s",
            response.status_code,
            response.text,
        )
        raise RuntimeError(
            f"Monday API request failed with status {response.status_code}: "
            f"{response.text[:500]}"
        )

    body: dict[str, Any] = response.json()

    if "errors" in body:
        errors = body["errors"]
        logger.error("Monday API GraphQL errors: %s", errors)
        raise RuntimeError(
            f"Monday API GraphQL errors: {errors}"
        )

    return body.get("data", body)


async def fetch_board_items(board_id: str) -> list[dict[str, Any]]:
    """
    Fetch **all** items from a Monday.com board using cursor-based pagination.

    The function issues successive GraphQL requests with a ``cursor`` parameter
    until the API returns a ``null`` cursor, meaning all pages have been consumed.

    Parameters
    ----------
    board_id : str
        The numeric ID of the Monday.com board (e.g. ``"5280027820"``).

    Returns
    -------
    list[dict]
        Every item on the board. Each item contains at least ``id``, ``name``
        and a ``column_values`` list with ``id``, ``text`` and ``value`` keys.
    """
    query = """
    query GetBoardItems($boardId: ID!, $cursor: String) {
      boards(ids: [$boardId]) {
        items_page(limit: 100, cursor: $cursor) {
          cursor
          items {
            id
            name
            column_values {
              id
              type
              text
              value
              ... on MirrorValue {
                display_value
              }
              ... on FormulaValue {
                display_value
              }
              ... on BoardRelationValue {
                display_value
              }
            }
          }
        }
      }
    }
    """

    all_items: list[dict[str, Any]] = []
    cursor: str | None = None
    page = 0

    while True:
        page += 1
        logger.info("Fetching board %s — page %s", board_id, page)

        data = await monday_request(
            query,
            variables={"boardId": board_id, "cursor": cursor},
        )

        boards = data.get("boards", [])
        if not boards:
            logger.warning("No boards found for ID %s", board_id)
            break

        items_page = boards[0].get("items_page") or {}
        items = items_page.get("items", [])
        cursor = items_page.get("cursor")  # None when no more pages

        if items:
            logger.info("  → received %s items", len(items))
            all_items.extend(items)
        else:
            logger.info("  → empty page, stopping pagination")

        if not cursor:
            break

    logger.info(
        "Finished pagination — total items fetched: %s",
        len(all_items),
    )
    return all_items


async def fetch_board_columns(board_id: str) -> dict[str, Any]:
    """
    Fetch board metadata and column definitions from Monday.com.

    Parameters
    ----------
    board_id : str
        The numeric ID of the Monday.com board (e.g. ``"5280027820"``).

    Returns
    -------
    dict
        Board metadata containing ``id``, ``name`` and a ``columns`` list.
    """
    query = """
    query GetBoardColumns($boardId: ID!) {
      boards(ids: [$boardId]) {
        id
        name
        columns {
          id
          title
          type
        }
      }
    }
    """

    logger.info("Fetching board %s columns", board_id)

    data = await monday_request(
        query,
        variables={"boardId": board_id},
    )

    boards = data.get("boards", [])
    if not boards:
        logger.warning("No boards found for ID %s", board_id)
        return {"id": board_id, "name": None, "columns": []}

    board = boards[0]
    columns = [
        {
            "id": column.get("id"),
            "title": column.get("title"),
            "type": column.get("type"),
        }
        for column in board.get("columns", [])
    ]

    return {
        "id": board.get("id"),
        "name": board.get("name"),
        "columns": columns,
    }


async def fetch_first_board_item(board_id: str) -> dict[str, Any] | None:
    """
    Fetch the first item from a Monday.com board for debugging.

    Parameters
    ----------
    board_id : str
        The numeric ID of the Monday.com board (e.g. ``"5280027820"``).

    Returns
    -------
    dict or None
        The first board item, or ``None`` when the board has no items.
    """
    query = """
    query GetFirstBoardItem($boardId: ID!) {
      boards(ids: [$boardId]) {
        items_page(limit: 1) {
          items {
            id
            name
            group {
              title
            }
            column_values {
              id
              type
              text
              value
              ... on MirrorValue {
                display_value
              }
              ... on FormulaValue {
                display_value
              }
              ... on BoardRelationValue {
                display_value
              }
            }
          }
        }
      }
    }
    """

    logger.info("Fetching first item from board %s", board_id)

    data = await monday_request(
        query,
        variables={"boardId": board_id},
    )

    boards = data.get("boards", [])
    if not boards:
        logger.warning("No boards found for ID %s", board_id)
        return None

    items_page = boards[0].get("items_page") or {}
    items = items_page.get("items", [])
    if not items:
        logger.info("No items found for board %s", board_id)
        return None

    return items[0]


async def fetch_sample_board_items(board_id: str) -> list[dict[str, Any]]:
    """
    Fetch the first 10 items from a Monday.com board for reverse engineering.

    Parameters
    ----------
    board_id : str
        The numeric ID of the Monday.com board (e.g. ``"5280027820"``).

    Returns
    -------
    list[dict]
        Up to 10 board items with group and column values.
    """
    query = """
    query GetSampleBoardItems($boardId: ID!) {
      boards(ids: [$boardId]) {
        items_page(limit: 10) {
          items {
            id
            name
            group {
              title
            }
            column_values {
              id
              type
              text
              value
              ... on MirrorValue {
                display_value
              }
              ... on FormulaValue {
                display_value
              }
              ... on BoardRelationValue {
                display_value
              }
            }
          }
        }
      }
    }
    """

    logger.info("Fetching sample items from board %s", board_id)

    data = await monday_request(
        query,
        variables={"boardId": board_id},
    )

    boards = data.get("boards", [])
    if not boards:
        logger.warning("No boards found for ID %s", board_id)
        return []

    items_page = boards[0].get("items_page") or {}
    return items_page.get("items", [])
