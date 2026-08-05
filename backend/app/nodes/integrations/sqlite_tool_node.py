"""Security-scoped SQLite tool provider for AI agents."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping

from langchain_core.tools import Tool

from ..base import NodeInput, NodeOutput, NodePosition, NodeProperty, NodePropertyType, NodeType, ProviderNode
from .sqlite_common import (
    _allowed_commands,
    _as_bool,
    _case_insensitive_predicates,
    _flatten_node_configuration,
    _mask_sqlite_strings,
    _normalized_allowed_tables,
    _referenced_tables,
    _requires_where_clause,
    _statement_command,
    _strip_code_fence,
    _validate_single_statement,
)
from .sqlite_node import _database_path, _sqlite_credential_secret, sqlite_connection


class SQLiteToolNode(ProviderNode):
    """Expose a SQLite database to an Agent through explicit permissions."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "SQLiteTool",
            "display_name": "SQLite Tool",
            "description": "Give an Agent explicitly scoped access to a SQLite database.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "sqlite", "path": "icons/sqlite.svg", "alt": "SQLite Tool"},
            "colors": ["sky-700", "cyan-900"],
            "version": "1.0.0",
            "inputs": [
                NodeInput(name="credential_id", type="str", description="Selected SQLite credential ID.", required=True),
                NodeInput(name="allowed_tables", type="str", description="Optional table allowlist.", default="", required=False),
                NodeInput(name="return_all_rows", type="bool", description="Ignore max_rows.", default=False, required=False),
                NodeInput(name="max_rows", type="int", description="Maximum returned rows.", default=200, required=False),
                NodeInput(name="allow_read", type="bool", description="Allow SELECT and EXPLAIN.", default=True, required=False),
                NodeInput(name="allow_insert", type="bool", description="Allow INSERT.", default=False, required=False),
                NodeInput(name="allow_update", type="bool", description="Allow UPDATE.", default=False, required=False),
                NodeInput(name="allow_delete", type="bool", description="Allow DELETE.", default=False, required=False),
                NodeInput(name="tool_name", type="str", description="Name exposed to the Agent.", default="sqlite_database", required=False),
                NodeInput(name="connection_timeout_ms", type="int", description="Connection timeout.", default=30000, required=False),
            ],
            "outputs": [
                NodeOutput(
                    name="tool",
                    displayName="Tool",
                    type="BaseTool",
                    description="Permission-scoped SQLite tool for an Agent's Tools input.",
                    is_connection=True,
                    direction=NodePosition.TOP,
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id", displayName="Credential", type=NodePropertyType.CREDENTIAL_SELECT,
                    serviceType="sqlite", required=True, description="SQLite credential used only by this tool.",
                ),
                NodeProperty(
                    name="allowed_tables", displayName="Allowed Tables", type=NodePropertyType.TEXT,
                    placeholder="customers, orders", required=False,
                    description="Optional allowlist. Leave empty to allow all tables in the database file.",
                ),
                NodeProperty(
                    name="return_all_rows", displayName="Return All Rows", type=NodePropertyType.CHECKBOX,
                    default=False, required=False, description="Ignore the row limit up to a hard safety ceiling.",
                ),
                NodeProperty(
                    name="max_rows", displayName="Maximum Rows", type=NodePropertyType.NUMBER,
                    default=200, min=1, max=5000, required=False,
                    description="Maximum rows placed in the Agent context.",
                ),
                NodeProperty(
                    name="allow_read", displayName="Allow Read", type=NodePropertyType.CHECKBOX,
                    default=True, required=False, description="Allow SELECT and EXPLAIN statements.",
                ),
                NodeProperty(
                    name="allow_insert", displayName="Allow Insert", type=NodePropertyType.CHECKBOX,
                    default=False, required=False, description="Allow INSERT statements.",
                ),
                NodeProperty(
                    name="allow_update", displayName="Allow Update", type=NodePropertyType.CHECKBOX,
                    default=False, required=False, description="Allow UPDATE statements.",
                ),
                NodeProperty(
                    name="allow_delete", displayName="Allow Delete", type=NodePropertyType.CHECKBOX,
                    default=False, required=False, description="Allow DELETE statements and REPLACE when Insert is also allowed.",
                ),
                NodeProperty(
                    name="tool_name", displayName="Tool Name", type=NodePropertyType.TEXT,
                    default="sqlite_database", required=False, tabName="options",
                    description="Stable name exposed to the Agent.",
                ),
                NodeProperty(
                    name="connection_timeout_ms", displayName="Connection Timeout (ms)", type=NodePropertyType.NUMBER,
                    default=30000, min=1000, max=300000, required=False, tabName="options",
                ),
            ],
        }

    def get_required_packages(self) -> List[str]:
        return []

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        configuration = {**_flatten_node_configuration(self.user_data), **kwargs}
        secret = _sqlite_credential_secret(self, configuration.get("credential_id"))
        allowed_commands = _allowed_commands(configuration)
        allowed_tables = _normalized_allowed_tables(configuration.get("allowed_tables"))
        return_all_rows = _as_bool(configuration.get("return_all_rows", False))
        max_rows = 50_000 if return_all_rows else min(5000, max(1, int(configuration.get("max_rows") or 200)))
        raw_name = str(configuration.get("tool_name") or "sqlite_database").strip()
        tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name) or "sqlite_database"

        def run_query(query: str) -> str:
            try:
                statement = _validate_single_statement(_strip_code_fence(query))
                command = _statement_command(statement)
                if command not in allowed_commands:
                    return json.dumps({"error": f"{command} is not allowed by the current permission settings."})
                masked_statement = _mask_sqlite_strings(statement)
                if command == "INSERT" and re.search(r"\bINSERT\s+OR\s+REPLACE\b", masked_statement, re.IGNORECASE):
                    if "REPLACE" not in allowed_commands:
                        return json.dumps({"error": "INSERT OR REPLACE requires both Insert and Delete permissions."})
                if command == "INSERT" and re.search(
                    r"\bON\s+CONFLICT\b[\s\S]*?\bDO\s+UPDATE\b",
                    masked_statement,
                    re.IGNORECASE,
                ):
                    if "UPDATE" not in allowed_commands:
                        return json.dumps({"error": "ON CONFLICT DO UPDATE requires Update permission."})
                if command in {"UPDATE", "DELETE"} and not _requires_where_clause(statement):
                    return json.dumps({"error": f"{command} statements must include a WHERE clause that selects the rows to change."})

                if allowed_tables:
                    referenced = _referenced_tables(statement)
                    unauthorized = sorted(
                        table for table in referenced
                        if table not in allowed_tables and table.rsplit(".", 1)[-1] not in allowed_tables
                    )
                    if unauthorized:
                        return json.dumps({"error": f"Table access denied: {', '.join(unauthorized)}"})
                    if not referenced:
                        return json.dumps({"error": "Could not verify table access for this query."})

                statement = _case_insensitive_predicates(statement)
                rows: List[Dict[str, Any]] = []
                affected_rows = 0
                last_insert_id = None
                truncated = False
                with sqlite_connection(secret, configuration) as connection:
                    cursor = connection.cursor()
                    try:
                        cursor.execute(statement)
                        if cursor.description:
                            fetched = list(cursor.fetchmany(max_rows + 1))
                            truncated = len(fetched) > max_rows
                            rows = [self._serialize_row(dict(row)) for row in fetched[:max_rows]]
                        affected_rows = max(0, int(cursor.rowcount or 0))
                        last_insert_id = int(cursor.lastrowid) if cursor.lastrowid else None
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
                    finally:
                        cursor.close()

                return json.dumps(
                    {
                        "rows": rows,
                        "row_count": len(rows),
                        "truncated": truncated,
                        "max_rows": max_rows,
                        "affected_rows": affected_rows,
                        "last_insert_id": last_insert_id,
                    },
                    ensure_ascii=False,
                    default=str,
                )
            except Exception as exc:
                return json.dumps({"error": str(exc)}, ensure_ascii=False)

        permission_text = ", ".join(sorted(allowed_commands)) or "none"
        table_text = ", ".join(sorted(allowed_tables)) if allowed_tables else "all tables in the database file"
        tool = Tool(
            name=tool_name,
            func=run_query,
            description=(
                f"Run one SQL statement against SQLite database '{_database_path(secret)}'. "
                f"Allowed commands: {permission_text}. Allowed tables: {table_text}. "
                "Inspect sqlite_master before querying when the schema is unknown. "
                "UPDATE and DELETE always require a WHERE clause. Text predicates are case-insensitive. "
                f"Return at most {max_rows} rows and prefer selective WHERE clauses."
            ),
        )
        return {"sqlite_database": {"tool": tool}}

    @staticmethod
    def _serialize_row(row: Mapping[str, Any]) -> Dict[str, Any]:
        return {
            str(key): (bytes(value).hex() if isinstance(value, (bytes, bytearray)) else value)
            for key, value in row.items()
        }
