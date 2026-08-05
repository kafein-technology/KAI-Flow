"""Authenticated schema discovery endpoints used by the SQLite node editors."""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_current_user
from app.models.user import User
from app.nodes.integrations.sqlite_node import SQLiteNode, sqlite_connection
from app.services.credential_service import CredentialService
from app.services.dependencies import get_credential_service_dep, get_db_session


logger = logging.getLogger(__name__)
sqlite_router = APIRouter(prefix="/sqlite", tags=["SQLite"])


class SQLiteTableInfo(BaseModel):
    name: str
    type: str


class SQLiteColumnInfo(BaseModel):
    name: str
    data_type: str
    column_type: str
    nullable: bool
    default: Any = None
    key: str = ""
    extra: str = ""


async def _sqlite_secret(
    credential_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    credential_service: CredentialService,
) -> Dict[str, Any]:
    credential = await credential_service.get_decrypted_credential(db, current_user.id, credential_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    if credential.get("service_type") != "sqlite":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential is not a SQLite credential")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential payload is invalid")
    return secret


def _read_tables(secret: Dict[str, Any], search: str) -> List[SQLiteTableInfo]:
    with sqlite_connection(secret) as connection:
        rows = connection.execute(
            "SELECT name, type FROM sqlite_master "
            "WHERE type IN ('table', 'view') AND name NOT LIKE 'sqlite_%' AND name LIKE ? "
            "ORDER BY name LIMIT 200",
            (f"%{search}%",),
        ).fetchall()
    return [SQLiteTableInfo(name=row["name"], type=row["type"].upper()) for row in rows]


def _read_columns(secret: Dict[str, Any], table: str) -> List[SQLiteColumnInfo]:
    identifier = SQLiteNode._identifier(table)
    with sqlite_connection(secret) as connection:
        rows = connection.execute(f"PRAGMA table_info({identifier})").fetchall()
    if not rows:
        raise ValueError("Table was not found in the SQLite database.")
    return [
        SQLiteColumnInfo(
            name=row["name"],
            data_type=str(row["type"] or "").split("(", 1)[0].lower(),
            column_type=str(row["type"] or ""),
            nullable=not bool(row["notnull"]),
            default=row["dflt_value"],
            key="PRI" if row["pk"] else "",
            extra="",
        )
        for row in rows
    ]


@sqlite_router.get("/tables", response_model=List[SQLiteTableInfo])
async def list_sqlite_tables(
    credential_id: uuid.UUID,
    search: str = Query("", max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    secret = await _sqlite_secret(credential_id, current_user, db, credential_service)
    try:
        return await asyncio.to_thread(_read_tables, secret, search.strip())
    except Exception as exc:
        logger.warning("SQLite table discovery failed for credential %s: %s", credential_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load SQLite tables") from exc


@sqlite_router.get("/columns", response_model=List[SQLiteColumnInfo])
async def list_sqlite_columns(
    credential_id: uuid.UUID,
    table: str = Query(..., min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    secret = await _sqlite_secret(credential_id, current_user, db, credential_service)
    try:
        return await asyncio.to_thread(_read_columns, secret, table.strip())
    except Exception as exc:
        logger.warning("SQLite column discovery failed for credential %s: %s", credential_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load SQLite columns") from exc
