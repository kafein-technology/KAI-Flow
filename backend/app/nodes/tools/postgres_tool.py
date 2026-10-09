"""
PostgreSQL Tool
===============

Provides an agent-callable tool for controlled PostgreSQL access.

The agent composes each SQL statement at runtime, so access is governed by
explicit permissions and database scope:

- Reading, inserting, updating and deleting are enabled one by one. Nothing but
  reading is on to begin with.
- Table access requires an explicit allow list or an explicit schema-wide grant.
- Updates and deletes must include a syntactically valid WHERE clause to prevent
  unbounded data modification.
- Statements that change the schema are always refused.
- Result sets are capped so a broad query cannot flood the agent's context.
- Table metadata can be included in the tool description to provide accurate
  schema context.
"""

from __future__ import annotations

import json
import logging
import re
import uuid as uuid_module
from contextlib import suppress
from dataclasses import dataclass
from datetime import date, datetime, time as time_type, timedelta
from decimal import Decimal
from typing import Any, Dict, FrozenSet, List, Optional, Sequence, Set, Tuple

import psycopg2
from pglast import Error as PglastError, ast, enums, parse_sql
from pglast.visitors import Visitor
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
from langchain_core.tools import Tool, ToolException

from ..base import (
    ProviderNode,
    NodeOutput,
    NodeType,
    NodeProperty,
    NodePropertyType,
    NodePosition,
)

logger = logging.getLogger(__name__)

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*([^\s,;]+)"
)
MAX_CONFIGURED_ROWS = 500
MAX_RETURN_ALL_ROWS = 5000
MAX_STATEMENT_TIMEOUT = 120
MAX_ALLOWED_TABLES = 500
MAX_TOOL_NAME_CHARACTERS = 64
MAX_CUSTOM_DESCRIPTION_CHARACTERS = 10000
MAX_CELL_CHARACTERS = 4000
MAX_OUTPUT_CHARACTERS = 50000
MAX_SCHEMA_COLUMNS = 500
MAX_SCHEMA_DESCRIPTION_CHARACTERS = 20000


@dataclass(frozen=True)
class RelationReference:
    schema: Optional[str]
    table: str


@dataclass(frozen=True)
class StatementAnalysis:
    operations: FrozenSet[str]
    relations: Tuple[RelationReference, ...]
    cte_names: FrozenSet[str]
    streamable: bool

    @property
    def writes(self) -> bool:
        return bool(self.operations - {"read"})


class _StatementVisitor(Visitor):
    def __init__(self) -> None:
        self.operations: set[str] = set()
        self.relations: list[RelationReference] = []
        self.cte_names: set[str] = set()

    def visit_InsertStmt(self, ancestors, node) -> None:
        self.operations.add("insert")
        if node.onConflictClause is not None and (
            node.onConflictClause.action == enums.OnConflictAction.ONCONFLICT_UPDATE
        ):
            self.operations.add("update")

    def visit_UpdateStmt(self, ancestors, node) -> None:
        if node.whereClause is None:
            raise ValueError(
                "An UPDATE without a WHERE clause would affect every row. "
                "Add a WHERE clause that identifies the intended rows."
            )
        self.operations.add("update")
        if node.fromClause:
            self.operations.add("read")

    def visit_DeleteStmt(self, ancestors, node) -> None:
        if node.whereClause is None:
            raise ValueError(
                "A DELETE without a WHERE clause would affect every row. "
                "Add a WHERE clause that identifies the intended rows."
            )
        self.operations.add("delete")
        if node.usingClause:
            self.operations.add("read")

    def visit_SelectStmt(self, ancestors, node) -> None:
        if node.intoClause is not None:
            raise ValueError("SELECT INTO is not allowed because it creates a table.")
        if node.fromClause:
            self.operations.add("read")

    def visit_RangeVar(self, ancestors, node) -> None:
        self.relations.append(RelationReference(node.schemaname, node.relname))

    def visit_CommonTableExpr(self, ancestors, node) -> None:
        self.cte_names.add(node.ctename)


def analyze_statement(query: str) -> StatementAnalysis:
    try:
        parsed = parse_sql(query)
    except PglastError as exc:
        raise ValueError("The SQL statement is not valid PostgreSQL syntax.") from exc

    if len(parsed) != 1:
        raise ValueError("Exactly one SQL statement is required per tool call.")

    statement = parsed[0].stmt
    supported = (
        ast.SelectStmt,
        ast.InsertStmt,
        ast.UpdateStmt,
        ast.DeleteStmt,
        ast.ExplainStmt,
        ast.VariableShowStmt,
    )
    if not isinstance(statement, supported):
        raise ValueError(
            "Only SELECT, SHOW, EXPLAIN, INSERT, UPDATE, and DELETE statements are allowed."
        )

    visitor = _StatementVisitor()
    visitor(parsed)

    operations = set(visitor.operations)
    if isinstance(statement, (ast.SelectStmt, ast.ExplainStmt, ast.VariableShowStmt)):
        operations.add("read")

    return StatementAnalysis(
        operations=frozenset(operations),
        relations=tuple(visitor.relations),
        cte_names=frozenset(visitor.cte_names),
        streamable=isinstance(statement, ast.SelectStmt) and operations == {"read"},
    )


def validate_relations(
    analysis: StatementAnalysis,
    selected_schema: str,
    allowed_tables: Sequence[str],
    schema_tables: Sequence[str],
) -> None:
    available = set(schema_tables)
    allowed = set(allowed_tables)

    missing = sorted(allowed - available)
    if missing:
        raise ValueError(
            "Allowed Tables contains names that are not present in schema "
            f"'{selected_schema}': {', '.join(missing)}."
        )

    for relation in analysis.relations:
        if relation.schema is not None and relation.schema != selected_schema:
            raise ValueError(
                f"The statement references schema '{relation.schema}', but this tool is limited "
                f"to schema '{selected_schema}'."
            )

        is_cte = relation.schema is None and relation.table in analysis.cte_names
        if is_cte and relation.table not in available:
            continue

        if relation.table not in available:
            raise ValueError(
                f"Table '{relation.table}' is not present in schema '{selected_schema}'."
            )

        if allowed and relation.table not in allowed:
            raise ValueError(
                f"This tool may only access: {', '.join(sorted(allowed))}. "
                f"The statement references '{relation.table}'."
            )


class PostgresToolNode(ProviderNode):
    """Exposes a scoped PostgreSQL tool to an agent."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "PostgresTool",
            "display_name": "PostgreSQL Tool",
            "description": (
                "Let an agent read from and write to a PostgreSQL database. Each kind of "
                "operation is granted separately, and the tool can be limited to named tables."
            ),
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {
                "name": "postgresql_vectorstore",
                "path": "icons/postgresql_vectorstore.svg",
                "alt": "PostgreSQL",
            },
            "colors": ["indigo-500", "purple-600"],
            "inputs": [],
            "outputs": [
                NodeOutput(
                    name="sql_tool",
                    displayName="SQL Tool",
                    type="BaseTool",
                    description="A database tool the agent can call.",
                    is_connection=True,
                    direction=NodePosition.TOP,
                ),
            ],
            "properties": [
                # ----------------------------------------------------------
                # Basic
                # ----------------------------------------------------------
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    description="PostgreSQL connection the tool will use.",
                    placeholder="Select Credential",
                    required=True,
                    serviceType="postgresql_vectorstore",
                    tabName="basic",
                ),
                NodeProperty(
                    name="schema_name",
                    displayName="Schema",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Schema the tool works in.",
                    placeholder="Select or type a schema",
                    required=True,
                    default="public",
                    optionsMethod="load_schemas",
                    optionsDependsOn=["credential_id"],
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_all_tables",
                    displayName="Allow All Tables in Schema",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Grant access to every current and future table in the selected schema. "
                        "Leave this disabled to require an explicit table allowlist."
                    ),
                    required=True,
                    default=False,
                    hint=(
                        "Enable only when schema-wide access is intentional. Existing table "
                        "selections are ignored while this option is enabled."
                    ),
                    tabName="basic",
                ),
                NodeProperty(
                    name="allowed_tables",
                    displayName="Allowed Tables",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Tables the tool may access. Select at least one table unless schema-wide "
                        "access is explicitly enabled."
                    ),
                    placeholder="Select one or more tables",
                    required=True,
                    default="",
                    multiple=True,
                    optionsMethod="load_tables",
                    optionsDependsOn=["credential_id", "schema_name"],
                    displayOptions={"show": {"allow_all_tables": False}},
                    hint=(
                        "Only selected tables are available to the agent. An empty selection is "
                        "rejected instead of granting broader access."
                    ),
                    tabName="basic",
                ),
                # --- Permissions ------------------------------------------
                NodeProperty(
                    name="return_all",
                    displayName="Return All Rows",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return rows up to the tool's safety ceiling. Turn this off to configure "
                        "a smaller limit for each result."
                    ),
                    required=True,
                    default=False,
                    hint="Leaving this off is safer; the agent can always narrow its query.",
                    tabName="basic",
                ),
                NodeProperty(
                    name="max_rows",
                    displayName="Maximum Rows",
                    type=NodePropertyType.NUMBER,
                    description="Largest number of rows a single read may return.",
                    required=True,
                    default=50,
                    min=1,
                    max=500,
                    displayOptions={"show": {"return_all": False}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="permissions_title",
                    displayName="Permissions",
                    type=NodePropertyType.TITLE,
                    description="What the agent is allowed to do with the database.",
                    required=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_read",
                    displayName="Allow Read",
                    type=NodePropertyType.CHECKBOX,
                    description="Let the agent run SELECT and other read statements.",
                    required=True,
                    default=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_insert",
                    displayName="Allow Insert",
                    type=NodePropertyType.CHECKBOX,
                    description="Let the agent add rows.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_update",
                    displayName="Allow Update",
                    type=NodePropertyType.CHECKBOX,
                    description="Let the agent change existing rows.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_delete",
                    displayName="Allow Delete",
                    type=NodePropertyType.CHECKBOX,
                    description="Let the agent remove rows.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                # ----------------------------------------------------------
                # Advanced
                # ----------------------------------------------------------
                NodeProperty(
                    name="describe_schema",
                    displayName="Describe Tables to the Agent",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Include table and column metadata in the tool description so the agent "
                        "can compose statements against the configured schema."
                    ),
                    required=False,
                    default=True,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="tool_name",
                    displayName="Tool Name",
                    type=NodePropertyType.TEXT,
                    description="Name the agent will see. Letters, digits and underscores only.",
                    placeholder="postgres_database",
                    required=False,
                    default="postgres_database",
                    tabName="advanced",
                ),
                NodeProperty(
                    name="tool_description",
                    displayName="Tool Description",
                    type=NodePropertyType.TEXT_AREA,
                    description=(
                        "Add task-specific guidance to the generated security, scope, and schema "
                        "description."
                    ),
                    required=False,
                    default="",
                    rows=4,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="statement_timeout",
                    displayName="Statement Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Cancel a statement that runs longer than this.",
                    required=False,
                    default=15,
                    min=1,
                    max=120,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="numbers_as_text",
                    displayName="Return Numbers as Text",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return NUMERIC and DECIMAL values as text to keep every digit. Useful "
                        "for money amounts."
                    ),
                    required=False,
                    default=True,
                    tabName="advanced",
                ),
            ],
        }

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

    def _build_connection_kwargs(self, credential_id: Optional[str]) -> Dict[str, Any]:
        """Read the credential without interpolating secrets into a URL."""
        if not credential_id:
            raise ValueError("A PostgreSQL credential is required.")

        credential = self.get_credential(credential_id)
        if not credential or not credential.get("secret"):
            raise ValueError(
                "The selected credential could not be read. It may have been created with a "
                "different encryption key; try recreating it."
            )

        secret = credential["secret"]
        connection_args: Dict[str, Any] = {
            "host": secret.get("host", "localhost"),
            "port": int(secret.get("port", 5432)),
            "dbname": secret.get("database", "postgres"),
            "user": secret.get("username", "postgres"),
            "password": secret.get("password", ""),
        }
        for key in ("sslmode", "sslcert", "sslkey", "sslrootcert", "application_name"):
            if secret.get(key) not in (None, ""):
                connection_args[key] = secret[key]
        return connection_args

    def _fetch_one_column(
        self, credential_id: str, statement: str, params: tuple = ()
    ) -> List[str]:
        """Open a short-lived connection and read a single column."""
        connection = None
        try:
            connection = psycopg2.connect(
                **self._build_connection_kwargs(credential_id), connect_timeout=10
            )
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 5000")
                cursor.execute(statement, params or None)
                return [row[0] for row in cursor.fetchall()]
        finally:
            if connection is not None:
                connection.close()

    def load_schemas(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """Load schemas for the schema selector."""
        names = self._fetch_one_column(
            values.get("credential_id"),
            """
            SELECT schema_name
            FROM information_schema.schemata
            WHERE schema_name NOT IN ('information_schema', 'pg_catalog', 'pg_toast')
              AND schema_name NOT LIKE 'pg_temp%'
              AND schema_name NOT LIKE 'pg_toast_temp%'
            ORDER BY schema_name
            """,
        )
        return [{"label": name, "value": name} for name in names]

    def _load_schema_tables(self, credential_id: str, schema: str) -> List[str]:
        return self._fetch_one_column(
            credential_id,
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
            """,
            (schema,),
        )

    def load_tables(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """Load tables for the allowed-table selector."""
        schema = (values.get("schema_name") or "public").strip()
        names = self._fetch_one_column(
            values.get("credential_id"),
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
            """,
            (schema,),
        )
        return [{"label": name, "value": name} for name in names]

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_list(raw: Any) -> List[str]:
        """Parse table selections without weakening an invalid allowlist."""
        if not raw:
            return []
        parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
        names: List[str] = []
        for part in parts:
            name = str(part).strip()
            if not name:
                continue
            if "\x00" in name or len(name.encode("utf-8")) > 63:
                raise ValueError(
                    f"Allowed table name '{name}' is not a valid PostgreSQL name."
                )
            names.append(name)
        if len(names) != len(set(names)):
            raise ValueError("Allowed Tables contains duplicate names.")
        if len(names) > MAX_ALLOWED_TABLES:
            raise ValueError(
                f"Allowed Tables may contain at most {MAX_ALLOWED_TABLES} names."
            )
        return names

    @classmethod
    def _resolve_allowed_tables(cls, raw: Any, allow_all_tables: Any) -> List[str]:
        if cls._coerce_bool(allow_all_tables, "Allow All Tables in Schema"):
            return []
        allowed = cls._parse_list(raw)
        if not allowed:
            raise ValueError(
                "Select at least one Allowed Table or explicitly enable "
                "Allow All Tables in Schema."
            )
        return allowed

    @staticmethod
    def _guard_permissions(analysis: StatementAnalysis, granted: Set[str]) -> None:
        """Require every operation represented in the PostgreSQL syntax tree."""
        missing = sorted(analysis.operations - granted)
        if missing:
            raise ValueError(
                f"This tool is not allowed to {', '.join(missing)}. "
                f"Granted operations: {', '.join(sorted(granted))}."
            )

    # ------------------------------------------------------------------
    # Result shaping
    # ------------------------------------------------------------------

    @classmethod
    def _serialize(cls, value: Any, numbers_as_text: bool = False) -> Any:
        """Convert database driver values into tool-safe output values."""
        if value is None:
            return None
        if isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value) if numbers_as_text else float(value)
        if isinstance(value, (datetime, date, time_type)):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "<binary>"
        if isinstance(value, dict):
            return {
                key: cls._serialize(item, numbers_as_text)
                for key, item in value.items()
            }
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize(item, numbers_as_text) for item in value]
        return str(value)

    @classmethod
    def _format_rows(
        cls,
        rows: List[Dict[str, Any]],
        truncated: bool,
        numbers_as_text: bool,
        operations: List[str],
    ) -> str:
        """Return an explicit, bounded result contract for agent interpretation."""
        rendered_rows: List[Dict[str, Any]] = []
        rendered_size = 0
        output_truncated = False
        for row in rows:
            rendered: Dict[str, Any] = {}
            for column, value in row.items():
                serialized = cls._serialize(value, numbers_as_text)
                encoded = json.dumps(serialized, ensure_ascii=False, default=str)
                if len(encoded) > MAX_CELL_CHARACTERS:
                    serialized = encoded[: MAX_CELL_CHARACTERS - 1] + "…"
                    output_truncated = True
                rendered[column] = serialized

            row_size = len(json.dumps(rendered, ensure_ascii=False, default=str))
            if rendered_size + row_size > MAX_OUTPUT_CHARACTERS - 1000:
                output_truncated = True
                break
            rendered_rows.append(rendered)
            rendered_size += row_size

        complete = not truncated and not output_truncated
        if not rows:
            guidance = (
                "The executed query returned zero rows. This proves only that this query matched "
                "nothing; do not describe the entire table as empty unless the query tested the "
                "entire table."
            )
        elif not complete:
            guidance = (
                "This is a partial result. Do not call it an exhaustive list or infer facts from "
                "omitted rows. Narrow, aggregate, or paginate with a deterministic ORDER BY."
            )
        else:
            guidance = "Base the answer on the returned row values exactly as provided."

        payload = {
            "status": "success",
            "operations": operations,
            "database_rows_fetched": len(rows),
            "rows_in_output": len(rendered_rows),
            "result_complete": complete,
            "database_row_limit_reached": truncated,
            "output_limit_reached": output_truncated,
            "rows": rendered_rows,
            "guidance": guidance,
        }
        result = json.dumps(payload, ensure_ascii=False, default=str)
        while len(result) > MAX_OUTPUT_CHARACTERS and rendered_rows:
            rendered_rows.pop()
            payload["rows_in_output"] = len(rendered_rows)
            payload["result_complete"] = False
            payload["output_limit_reached"] = True
            payload["guidance"] = (
                "This is a partial result. Do not call it an exhaustive list or infer facts from "
                "omitted rows. Narrow, aggregate, or paginate with a deterministic ORDER BY."
            )
            result = json.dumps(payload, ensure_ascii=False, default=str)
        return result

    @staticmethod
    def _format_affected_result(operations: List[str], affected_rows: int) -> str:
        guidance = (
            "No rows were changed. This means the statement matched no writable rows; it does "
            "not prove that the table is empty."
            if affected_rows == 0
            else "Report the affected row count without inferring changes beyond this statement."
        )
        return json.dumps(
            {
                "status": "success",
                "operations": operations,
                "affected_rows": affected_rows,
                "result_complete": True,
                "guidance": guidance,
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _format_tool_error(category: str, message: str) -> str:
        return json.dumps(
            {
                "status": "error",
                "category": category,
                "message": message,
                "guidance": (
                    "Do not interpret this error as an empty result or claim any database fact. "
                    "Explain the limitation or correct the statement before retrying."
                ),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _has_result_set(analysis: StatementAnalysis, cursor: Any) -> bool:
        return analysis.streamable or cursor.description is not None

    # ------------------------------------------------------------------
    # Tool description
    # ------------------------------------------------------------------

    def _describe_tables(
        self, credential_id: str, schema: str, allowed: List[str]
    ) -> str:
        """Build a bounded schema summary for the tool description."""
        connection = None
        try:
            connection = psycopg2.connect(
                **self._build_connection_kwargs(credential_id), connect_timeout=10
            )
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 5000")
                if allowed:
                    cursor.execute(
                        """
                        SELECT table_name, column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s AND table_name = ANY(%s)
                        ORDER BY table_name, ordinal_position
                        LIMIT %s
                        """,
                        (schema, allowed, MAX_SCHEMA_COLUMNS + 1),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT table_name, column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s
                        ORDER BY table_name, ordinal_position
                        LIMIT %s
                        """,
                        (schema, MAX_SCHEMA_COLUMNS + 1),
                    )
                rows = cursor.fetchall()
        except Exception:
            logger.warning("PostgreSQL tool could not load the table description.")
            return ""
        finally:
            if connection is not None:
                connection.close()

        if not rows:
            return ""

        truncated = len(rows) > MAX_SCHEMA_COLUMNS
        tables: Dict[str, List[str]] = {}
        for table_name, column_name, data_type, is_nullable in rows[
            :MAX_SCHEMA_COLUMNS
        ]:
            marker = "" if is_nullable == "YES" else " NOT NULL"
            tables.setdefault(table_name, []).append(
                f"{column_name} {data_type}{marker}"
            )

        lines = ["", "Tables:"]
        for table_name, columns in tables.items():
            lines.append(f"  {table_name}({', '.join(columns)})")
        if truncated:
            lines.append("  Schema description truncated at the safety limit.")
        result = "\n".join(lines)
        if len(result) > MAX_SCHEMA_DESCRIPTION_CHARACTERS:
            result = (
                result[: MAX_SCHEMA_DESCRIPTION_CHARACTERS - 64]
                + "\n  Schema description truncated at the safety limit."
            )
        return result

    def _build_description(
        self,
        custom: str,
        schema: str,
        allowed: List[str],
        granted: Set[str],
        max_rows: int,
        layout: str,
    ) -> str:
        """Build the agent-facing tool description and mandatory policy context."""
        verbs = {
            "read": "read rows with SELECT",
            "insert": "add rows with INSERT",
            "update": "change rows with UPDATE",
            "delete": "remove rows with DELETE",
        }
        can_do = [
            verbs[name]
            for name in ("read", "insert", "update", "delete")
            if name in granted
        ]
        scope = ", ".join(allowed) if allowed else f"any table in the {schema} schema"

        parts = [
            "Work with a PostgreSQL database by passing one complete SQL statement as the input.",
            (
                f"You can {'; '.join(can_do)}."
                if can_do
                else "This tool currently grants nothing."
            ),
            f"Scope: {scope}.",
            f"Reads return at most {max_rows} rows and are also subject to an output-size "
            "safety limit, so filter and aggregate in SQL rather than asking for everything.",
            "The schema summary contains metadata only and never indicates whether tables "
            "contain rows.",
            "For every question about stored values, row counts, record existence, aggregates, "
            "or current database state, call this tool and base the answer only on its result. "
            "Never infer that a table is empty without running an appropriate SELECT statement.",
            "A table or column appearing in schema metadata proves only that it exists, while an "
            "item omitted from an unavailable or truncated schema summary must not be assumed to "
            "be absent.",
            "Treat status=error as a failed or refused operation, never as an empty result. Treat "
            "result_complete=false as partial data and never present it as an exhaustive answer.",
            "For counts, report the aggregate value returned in rows rather than "
            "database_rows_fetched. For exhaustive lists, use deterministic ORDER BY and disclose "
            "any limit. If a request asks both to list and count, return both facts explicitly.",
            "Select only the columns needed for the request and do not expose unrelated or "
            "sensitive fields.",
        ]

        if custom and custom.strip():
            parts.append(f"Additional workflow guidance: {custom.strip()}")

        if granted - {"read"}:
            parts.append(
                "Run INSERT, UPDATE, or DELETE only when the user explicitly requests that data "
                "change. Never perform a write merely to inspect, test, or verify the database."
            )

        if "update" in granted or "delete" in granted:
            parts.append(
                "An UPDATE or DELETE must carry a WHERE clause that names the rows you mean; "
                "one without a filter is refused."
            )

        parts.append(
            "PostgreSQL comparison semantics are preserved. Use ILIKE or an explicit LOWER() "
            "expression only when case-insensitive matching is intended."
        )

        parts.append(
            "Statements that change the database structure, such as CREATE, ALTER or DROP, "
            "are refused."
        )

        return " ".join(parts) + layout

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _setting(self, kwargs: Dict[str, Any], name: str, fallback: Any) -> Any:
        """Read a setting from the call or from the stored configuration."""
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
        stored = getattr(self, "user_data", {}) or {}
        if name in stored and stored[name] is not None:
            return stored[name]
        return fallback

    @staticmethod
    def _coerce_bool(value: Any, name: str) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, int) and value in (0, 1):
            return bool(value)
        if isinstance(value, str):
            normalized = value.strip().lower()
            if normalized in {"true", "1", "yes", "on"}:
                return True
            if normalized in {"false", "0", "no", "off"}:
                return False
        raise ValueError(f"{name} must be a boolean value.")

    @staticmethod
    def _bounded_int(value: Any, name: str, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a whole number.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}.")
        return parsed

    @staticmethod
    def _validate_database_identifier(value: str, name: str) -> None:
        if not value or "\x00" in value or len(value.encode("utf-8")) > 63:
            raise ValueError(f"{name} is not a valid PostgreSQL identifier.")

    @staticmethod
    def _database_error(exc: psycopg2.Error) -> str:
        messages = {
            "23502": "A required column was left empty.",
            "23503": "The statement violates a foreign key constraint.",
            "23505": "The statement conflicts with an existing unique value.",
            "25006": "The database connection is read-only for this statement.",
            "28P01": "PostgreSQL rejected the configured credentials.",
            "42501": "The database user does not have permission for this operation.",
            "42P01": "A referenced table does not exist or is not accessible.",
            "42703": "A referenced column does not exist.",
            "57014": "The statement exceeded the configured timeout.",
        }
        if exc.pgcode in messages:
            return messages[exc.pgcode]
        primary = getattr(getattr(exc, "diag", None), "message_primary", None)
        if primary:
            sanitized = SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", primary.strip())
            return sanitized[:500]
        return "PostgreSQL rejected the statement."

    def validate_configuration(self, **inputs) -> None:
        credential_id = self._setting(inputs, "credential_id", None)
        if not credential_id:
            raise ValueError("A PostgreSQL credential is required.")
        self._build_connection_kwargs(credential_id)

        schema = str(self._setting(inputs, "schema_name", "public")).strip() or "public"
        self._validate_database_identifier(schema, "Schema")
        self._resolve_allowed_tables(
            self._setting(inputs, "allowed_tables", ""),
            self._setting(inputs, "allow_all_tables", False),
        )
        self._bounded_int(
            self._setting(inputs, "max_rows", 50),
            "Maximum Rows",
            1,
            MAX_CONFIGURED_ROWS,
        )
        self._bounded_int(
            self._setting(inputs, "statement_timeout", 15),
            "Statement Timeout",
            1,
            MAX_STATEMENT_TIMEOUT,
        )
        for setting, label, fallback in (
            ("allow_all_tables", "Allow All Tables in Schema", False),
            ("return_all", "Return All Rows", False),
            ("describe_schema", "Describe Tables to the Agent", True),
            ("numbers_as_text", "Return Numbers as Text", True),
            ("allow_read", "Allow Read", True),
            ("allow_insert", "Allow Insert", False),
            ("allow_update", "Allow Update", False),
            ("allow_delete", "Allow Delete", False),
        ):
            self._coerce_bool(self._setting(inputs, setting, fallback), label)

        tool_name = str(self._setting(inputs, "tool_name", "postgres_database")).strip()
        if (
            not IDENTIFIER_PATTERN.fullmatch(tool_name)
            or len(tool_name) > MAX_TOOL_NAME_CHARACTERS
        ):
            raise ValueError(
                "Tool Name must start with a letter or underscore and contain only letters, "
                f"digits, and underscores, with a maximum of {MAX_TOOL_NAME_CHARACTERS} "
                "characters."
            )
        custom_description = str(self._setting(inputs, "tool_description", "") or "")
        if len(custom_description) > MAX_CUSTOM_DESCRIPTION_CHARACTERS:
            raise ValueError(
                "Tool Description may contain at most "
                f"{MAX_CUSTOM_DESCRIPTION_CHARACTERS} characters."
            )

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Build the tool the agent will call."""
        self.validate_configuration(**kwargs)
        credential_id = self._setting(kwargs, "credential_id", None)
        schema = str(self._setting(kwargs, "schema_name", "public")).strip() or "public"
        allowed = self._resolve_allowed_tables(
            self._setting(kwargs, "allowed_tables", ""),
            self._setting(kwargs, "allow_all_tables", False),
        )
        return_all = self._coerce_bool(
            self._setting(kwargs, "return_all", False), "Return All Rows"
        )
        configured_rows = self._bounded_int(
            self._setting(kwargs, "max_rows", 50),
            "Maximum Rows",
            1,
            MAX_CONFIGURED_ROWS,
        )
        max_rows = MAX_RETURN_ALL_ROWS if return_all else configured_rows
        timeout = self._bounded_int(
            self._setting(kwargs, "statement_timeout", 15),
            "Statement Timeout",
            1,
            MAX_STATEMENT_TIMEOUT,
        )
        describe = self._coerce_bool(
            self._setting(kwargs, "describe_schema", True),
            "Describe Tables to the Agent",
        )
        numbers_as_text = self._coerce_bool(
            self._setting(kwargs, "numbers_as_text", True), "Return Numbers as Text"
        )
        tool_name = str(self._setting(kwargs, "tool_name", "postgres_database")).strip()
        custom_description = str(self._setting(kwargs, "tool_description", "") or "")

        granted: Set[str] = set()
        if self._coerce_bool(self._setting(kwargs, "allow_read", True), "Allow Read"):
            granted.add("read")
        if self._coerce_bool(
            self._setting(kwargs, "allow_insert", False), "Allow Insert"
        ):
            granted.add("insert")
        if self._coerce_bool(
            self._setting(kwargs, "allow_update", False), "Allow Update"
        ):
            granted.add("update")
        if self._coerce_bool(
            self._setting(kwargs, "allow_delete", False), "Allow Delete"
        ):
            granted.add("delete")

        if not granted:
            raise ValueError(
                "No permission is granted, so the tool would refuse every statement. "
                "Turn on at least Allow Read."
            )

        connection_kwargs = self._build_connection_kwargs(credential_id)
        schema_tables = self._load_schema_tables(credential_id, schema)
        missing_allowed = sorted(set(allowed) - set(schema_tables))
        if missing_allowed:
            raise ValueError(
                f"Allowed Tables contains names that are not present in schema '{schema}': "
                f"{', '.join(missing_allowed)}."
            )

        logger.info(
            "PostgresTool ready: schema=%s tables=%s granted=%s max_rows=%s",
            schema,
            allowed or "all",
            sorted(granted),
            max_rows,
        )

        def run_sql(query: str) -> str:
            """Execute one policy-compliant statement and return a bounded result."""
            query = (query or "").strip()
            if not query:
                raise ToolException(
                    self._format_tool_error(
                        "invalid_input", "No SQL statement was supplied."
                    )
                )

            try:
                analysis = analyze_statement(query)
                self._guard_permissions(analysis, granted)
                validate_relations(analysis, schema, allowed, schema_tables)
            except ValueError as exc:
                raise ToolException(
                    self._format_tool_error("policy_refusal", str(exc))
                ) from exc

            writes = analysis.writes
            operations = sorted(operation.upper() for operation in analysis.operations)
            logger.info(
                "PostgreSQL tool accepted invocation: operations=%s relations=%s",
                operations,
                [
                    f"{relation.schema or schema}.{relation.table}"
                    for relation in analysis.relations
                ],
            )

            connection = None
            cursor = None
            try:
                connection = psycopg2.connect(**connection_kwargs, connect_timeout=10)
                connection.set_session(readonly=not writes, autocommit=False)

                with connection.cursor() as control_cursor:
                    control_cursor.execute(
                        "SET statement_timeout = %s", (timeout * 1000,)
                    )
                    control_cursor.execute(
                        sql.SQL("SET search_path TO {}").format(sql.Identifier(schema))
                    )

                if analysis.streamable:
                    cursor = connection.cursor(
                        name=f"postgres_tool_{uuid_module.uuid4().hex}",
                        cursor_factory=RealDictCursor,
                    )
                    cursor.itersize = min(max_rows + 1, 100)
                else:
                    cursor = connection.cursor(cursor_factory=RealDictCursor)

                cursor.execute(query)
                if not self._has_result_set(analysis, cursor):
                    affected = max(cursor.rowcount, 0)
                    if writes:
                        connection.commit()
                    logger.info(
                        "PostgreSQL tool completed: operations=%s affected_rows=%s",
                        operations,
                        affected,
                    )
                    return self._format_affected_result(operations, affected)

                rows = [dict(record) for record in cursor.fetchmany(max_rows + 1)]
                truncated = len(rows) > max_rows
                body = self._format_rows(
                    rows[:max_rows], truncated, numbers_as_text, operations
                )

                if writes:
                    connection.commit()
                logger.info(
                    "PostgreSQL tool completed: operations=%s fetched_rows=%s "
                    "row_limit_reached=%s",
                    operations,
                    len(rows[:max_rows]),
                    truncated,
                )
                return body

            except psycopg2.Error as exc:
                if connection is not None:
                    with suppress(Exception):
                        connection.rollback()
                logger.warning(
                    "PostgreSQL tool statement failed with SQLSTATE %s.", exc.pgcode
                )
                raise ToolException(
                    self._format_tool_error("database_error", self._database_error(exc))
                ) from exc
            except Exception as exc:
                if connection is not None:
                    with suppress(Exception):
                        connection.rollback()
                logger.exception("PostgreSQL tool failed while executing a statement.")
                raise ToolException(
                    self._format_tool_error(
                        "execution_error",
                        "The PostgreSQL statement could not be completed.",
                    )
                ) from exc
            finally:
                if cursor is not None:
                    with suppress(Exception):
                        cursor.close()
                if connection is not None:
                    with suppress(Exception):
                        connection.close()

        layout = (
            self._describe_tables(credential_id, schema, allowed) if describe else ""
        )
        description = self._build_description(
            custom_description, schema, allowed, granted, max_rows, layout
        )

        return {
            "sql_tool": {
                "tool": Tool(
                    name=tool_name,
                    description=description,
                    func=run_sql,
                    handle_tool_error=True,
                )
            }
        }

    def get_required_packages(self) -> List[str]:
        """Packages this node needs."""
        return [
            "psycopg2-binary>=2.9.0",
            "langchain-core>=0.1.0",
            "pglast==7.17",
        ]


__all__ = ["PostgresToolNode"]
