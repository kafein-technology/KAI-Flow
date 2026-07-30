"""Authenticated schema discovery endpoints used by the MySQL node editor."""

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
from app.services.credential_service import CredentialService
from app.services.dependencies import get_credential_service_dep, get_db_session

from app.nodes.integrations.mysql_node import mysql_connection


logger = logging.getLogger(__name__)
mysql_router = APIRouter(prefix="/mysql", tags=["MySQL"])


class MySQLTableInfo(BaseModel):
    name: str
    type: str


class MySQLColumnInfo(BaseModel):
    name: str
    data_type: str
    column_type: str
    nullable: bool
    default: Any = None
    key: str = ""
    extra: str = ""


async def _mysql_secret(
    credential_id: uuid.UUID,
    current_user: User,
    db: AsyncSession,
    credential_service: CredentialService,
) -> Dict[str, Any]:
    credential = await credential_service.get_decrypted_credential(db, current_user.id, credential_id)
    if not credential:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Credential not found")
    if credential.get("service_type") != "mysql":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential is not a MySQL credential")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Credential payload is invalid")
    return secret


def _read_tables(secret: Dict[str, Any], search: str) -> List[MySQLTableInfo]:
    database = str(secret.get("database") or "").strip()
    if not database:
        raise ValueError("The selected credential does not define a database.")
    pattern = f"%{search}%"
    with mysql_connection(secret) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT TABLE_NAME AS name, TABLE_TYPE AS type "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME LIKE %s "
                "ORDER BY TABLE_NAME LIMIT 200",
                (database, pattern),
            )
            return [MySQLTableInfo(name=row["name"], type=row["type"]) for row in cursor.fetchall()]


def _read_columns(secret: Dict[str, Any], table: str) -> List[MySQLColumnInfo]:
    database = str(secret.get("database") or "").strip()
    with mysql_connection(secret) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COLUMN_NAME AS name, DATA_TYPE AS data_type, COLUMN_TYPE AS column_type, "
                "IS_NULLABLE AS is_nullable, COLUMN_DEFAULT AS column_default, COLUMN_KEY AS column_key, "
                "EXTRA AS extra FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
                (database, table),
            )
            rows = cursor.fetchall()
    if not rows:
        raise ValueError("Table was not found in the credential's database.")
    return [
        MySQLColumnInfo(
            name=row["name"],
            data_type=row["data_type"],
            column_type=row["column_type"],
            nullable=row["is_nullable"] == "YES",
            default=row["column_default"],
            key=row["column_key"] or "",
            extra=row["extra"] or "",
        )
        for row in rows
    ]


@mysql_router.get("/tables", response_model=List[MySQLTableInfo])
async def list_mysql_tables(
    credential_id: uuid.UUID,
    search: str = Query("", max_length=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    secret = await _mysql_secret(credential_id, current_user, db, credential_service)
    try:
        return await asyncio.to_thread(_read_tables, secret, search.strip())
    except Exception as exc:
        logger.warning("MySQL table discovery failed for credential %s: %s", credential_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load MySQL tables") from exc


@mysql_router.get("/columns", response_model=List[MySQLColumnInfo])
async def list_mysql_columns(
    credential_id: uuid.UUID,
    table: str = Query(..., min_length=1, max_length=128),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
    credential_service: CredentialService = Depends(get_credential_service_dep),
):
    secret = await _mysql_secret(credential_id, current_user, db, credential_service)
    try:
        return await asyncio.to_thread(_read_columns, secret, table.strip())
    except Exception as exc:
        logger.warning("MySQL column discovery failed for credential %s: %s", credential_id, exc)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Could not load MySQL columns") from exc
