"""SQLite processor node with dynamic controls and safe table operations."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import re
import sqlite3
import time
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProcessorNode,
)


logger = logging.getLogger(__name__)

SUPPORTED_OPERATIONS = {
    "delete",
    "execute_query",
    "insert",
    "select",
    "truncate",
    "update",
    "upsert",
}
WRITE_OPERATIONS = {"delete", "insert", "truncate", "update", "upsert"}
READ_COMMANDS = {"EXPLAIN", "SELECT", "VALUES"}
DISALLOWED_COMMANDS = {
    "ATTACH",
    "BEGIN",
    "COMMIT",
    "DETACH",
    "END",
    "RELEASE",
    "ROLLBACK",
    "SAVEPOINT",
    "VACUUM",
}
CONDITION_OPERATORS = {
    "equals": "=",
    "not_equals": "<>",
    "greater_than": ">",
    "greater_or_equal": ">=",
    "less_than": "<",
    "less_or_equal": "<=",
    "like": "LIKE",
    "ilike": "LIKE",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
}
_POSITIONAL_PARAMETER = re.compile(r"\$(\d+)(:name)?")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_MAX_RESULT_ROWS = 10_000
_SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*([^\s,;]+)"
)


@dataclass
class QuerySpec:
    sql: str
    parameters: Sequence[Any] | Mapping[str, Any] = field(default_factory=list)
    item_index: int = 0


@dataclass
class QueryResult:
    sql: str
    rows: List[Dict[str, Any]]
    affected_rows: int
    last_insert_id: int | None
    item_index: int
    truncated: bool = False


def _parse_json(value: Any, *, default: Any, field_name: str) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list, int, float, bool)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must contain valid JSON: {exc.msg}") from exc


def _as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _unwrap_connected_value(value: Any) -> Any:
    """Remove KAI-Flow's standard output envelope without changing row payloads."""
    if isinstance(value, dict) and {"nodeId", "success", "output"}.issubset(value):
        return value["output"]
    return value


def _connected_payload(value: Any) -> Any:
    """Read rows from an upstream database result payload."""
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return value["rows"]
    return value


def _flatten_node_configuration(user_data: Any) -> Dict[str, Any]:
    """Return form values regardless of the frontend's flat or nested storage shape."""
    if not isinstance(user_data, dict):
        return {}
    configuration = dict(user_data)
    nested_inputs = user_data.get("inputs")
    if isinstance(nested_inputs, dict):
        configuration.update(nested_inputs)
    return configuration


def _credential_secret(node: ProcessorNode, credential_id: Any) -> Dict[str, Any]:
    if not credential_id:
        raise ValueError("A SQLite credential must be selected.")
    credential = node.get_credential(str(credential_id))
    if not credential:
        raise ValueError("The selected SQLite credential could not be found.")
    if credential.get("service_type") != "sqlite":
        raise ValueError("The selected credential is not a SQLite credential.")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise ValueError("The selected SQLite credential has an invalid secret payload.")
    return secret


def _database_path(secret: Mapping[str, Any]) -> str:
    raw_path = str(secret.get("database_path") or "").strip()
    if not raw_path:
        raise ValueError("SQLite Database Path is required.")
    if raw_path == ":memory:":
        return raw_path

    path = Path(raw_path).expanduser()
    if not path.is_absolute():
        raise ValueError("SQLite Database Path must be absolute.")
    return str(path.resolve())


@contextlib.contextmanager
def sqlite_connection(
    secret: Mapping[str, Any],
    options: Mapping[str, Any] | None = None,
) -> Iterator[sqlite3.Connection]:
    """Open a validated SQLite connection with foreign keys enabled."""
    options = options or {}
    database = _database_path(secret)
    read_only = _as_bool(secret.get("read_only")) or _as_bool(options.get("read_only"))
    create_if_missing = _as_bool(secret.get("create_if_missing"))

    if database == ":memory:":
        if read_only:
            raise ValueError("An in-memory SQLite database cannot be opened read-only.")
    else:
        database_path = Path(database)
        if database_path.exists() and not database_path.is_file():
            raise ValueError("SQLite Database Path must point to a file.")
        if not database_path.exists():
            if read_only or not create_if_missing:
                raise ValueError("The SQLite database file does not exist.")
            if not database_path.parent.is_dir():
                raise ValueError("The parent directory for the SQLite database does not exist.")

    credential_timeout = secret.get("timeout_ms")
    if credential_timeout in (None, ""):
        credential_timeout = 30_000
    try:
        credential_timeout_ms = int(credential_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("SQLite Connection Timeout must be a whole number of milliseconds.") from exc
    if credential_timeout_ms < 1 or credential_timeout_ms > 300_000:
        raise ValueError(
            "SQLite Connection Timeout must be between 1 and 300000 milliseconds."
        )

    connection_timeout = options.get("connection_timeout")
    if connection_timeout in (None, ""):
        timeout_seconds = credential_timeout_ms / 1000
    else:
        try:
            timeout_seconds = int(connection_timeout)
        except (TypeError, ValueError) as exc:
            raise ValueError("SQLite connection timeout must be a whole number.") from exc
        if timeout_seconds < 1 or timeout_seconds > 300:
            raise ValueError("SQLite connection timeout must be between 1 and 300 seconds.")

    statement_timeout = options.get("statement_timeout")
    if statement_timeout in (None, ""):
        statement_timeout = 60
    try:
        statement_timeout_seconds = int(statement_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("SQLite statement timeout must be a whole number.") from exc
    if statement_timeout_seconds < 0 or statement_timeout_seconds > 3600:
        raise ValueError("SQLite statement timeout must be between 0 and 3600 seconds.")

    if database == ":memory:":
        target = database
        use_uri = False
    elif read_only:
        target = f"{Path(database).as_uri()}?mode=ro"
        use_uri = True
    else:
        target = database
        use_uri = False

    connection: sqlite3.Connection | None = None
    try:
        connection = sqlite3.connect(
            target,
            timeout=max(0.001, timeout_seconds),
            uri=use_uri,
            check_same_thread=False,
        )
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA case_sensitive_like = ON")
        connection.execute(f"PRAGMA busy_timeout = {int(timeout_seconds * 1000)}")
        if read_only:
            connection.execute("PRAGMA query_only = ON")
        if statement_timeout_seconds:
            deadline = time.monotonic() + statement_timeout_seconds
            connection.set_progress_handler(
                lambda: int(time.monotonic() >= deadline),
                1_000,
            )
        yield connection
    finally:
        if connection is not None:
            connection.set_progress_handler(None, 0)
            connection.close()


class SQLiteNode(ProcessorNode):
    """Runs SQL statements and table operations against a SQLite database."""

    def __init__(self):
        super().__init__()
        operation_options = [
            {"label": "Execute Query", "value": "execute_query"},
            {"label": "Select", "value": "select"},
            {"label": "Insert", "value": "insert"},
            {"label": "Update", "value": "update"},
            {"label": "Insert or Update", "value": "upsert"},
            {"label": "Delete", "value": "delete"},
            {"label": "Truncate", "value": "truncate"},
        ]
        table_operations = ["delete", "insert", "select", "truncate", "update", "upsert"]
        mapped_operations = ["insert", "upsert", "update"]
        filter_operations = ["delete", "select", "update"]
        self._metadata = {
            "name": "SQLiteNode",
            "display_name": "SQLite",
            "description": (
                "Run queries and manage rows in a SQLite database. Supports raw SQL, select, "
                "insert, update, upsert, delete, and truncate operations."
            ),
            "category": "Databases",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "sqlite", "path": "icons/sqlite.svg", "alt": "SQLite"},
            "colors": ["sky-700", "cyan-900"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description=(
                        "Incoming row or rows used by automatic mapping and query batching."
                    ),
                    required=False,
                    is_connection=True,
                    direction=NodePosition.LEFT,
                )
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="dict",
                    description="Selected rows together with SQLite execution metadata.",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
                NodeOutput(
                    name="success",
                    type="boolean",
                    description="Whether the operation completed without an error.",
                ),
                NodeOutput(
                    name="error",
                    type="string",
                    description="Error message when the operation failed.",
                ),
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    description="SQLite database credential.",
                    placeholder="Select Credential",
                    serviceType="sqlite",
                    required=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="operation",
                    displayName="Operation",
                    type=NodePropertyType.SELECT,
                    description="Choose the database action this workflow node will execute.",
                    default="select",
                    options=operation_options,
                    required=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="table_name",
                    displayName="Table",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Table or view to operate on.",
                    placeholder="Select or type a table",
                    default="",
                    optionsMethod="load_tables",
                    optionsDependsOn=["credential_id"],
                    displayOptions={"show": {"operation": table_operations}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="query",
                    displayName="SQL Query",
                    type=NodePropertyType.CODE_EDITOR,
                    description=(
                        "One SQL statement to run. Use $1, $2 placeholders for values and "
                        "$1:name for an identifier."
                    ),
                    placeholder="SELECT id, name FROM customers WHERE status = $1",
                    rows=8,
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=False,
                    default="",
                    maxLength=20_000,
                    tabName="basic",
                ),
                NodeProperty(
                    name="query_parameters",
                    displayName="Query Parameters",
                    type=NodePropertyType.JSON_EDITOR,
                    description=(
                        "JSON array or object of parameter values. Incoming data is used when "
                        "this is empty."
                    ),
                    default="[]",
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="mapping_mode",
                    displayName="Mapping Column Mode",
                    type=NodePropertyType.SELECT,
                    description="Automatically map incoming properties or define values below.",
                    default="manual",
                    options=[
                        {"label": "Map Each Column Manually", "value": "manual"},
                        {"label": "Map Automatically", "value": "auto"},
                    ],
                    displayOptions={
                        "show": {"operation": mapped_operations, "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="match_columns",
                    displayName="Columns to Match On",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Columns whose values identify an existing row and are not updated. "
                        "Insert or Update requires a primary or unique key."
                    ),
                    placeholder="Select one or more columns",
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {"operation": ["upsert", "update"], "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="data",
                    displayName="Values to Send",
                    type=NodePropertyType.COLUMN_MAPPER,
                    description=(
                        "Values for the selected table columns. Omitted columns use database "
                        "defaults."
                    ),
                    default="{}",
                    optionsMethod="load_column_schema",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {
                            "operation": mapped_operations,
                            "mapping_mode": "manual",
                            "table_name": "*",
                        }
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_column",
                    displayName="Filter Column",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Column used by the primary row filter. Update and Delete require this "
                        "filter, an Extra Condition, or match columns."
                    ),
                    placeholder="No filter",
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {"operation": filter_operations, "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_operator",
                    displayName="Filter Operator",
                    type=NodePropertyType.SELECT,
                    description="How the filter column is compared with its value.",
                    default="equals",
                    options=[
                        {"label": "is equal to", "value": "equals"},
                        {"label": "is not equal to", "value": "not_equals"},
                        {"label": "is greater than", "value": "greater_than"},
                        {
                            "label": "is greater than or equal to",
                            "value": "greater_or_equal",
                        },
                        {"label": "is less than", "value": "less_than"},
                        {"label": "is less than or equal to", "value": "less_or_equal"},
                        {"label": "contains", "value": "ilike"},
                        {"label": "contains (case sensitive)", "value": "like"},
                        {"label": "is empty", "value": "is_null"},
                        {"label": "is not empty", "value": "is_not_null"},
                    ],
                    displayOptions={
                        "show": {
                            "operation": filter_operations,
                            "filter_column": "*",
                        }
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_value",
                    displayName="Filter Value",
                    type=NodePropertyType.TEXT,
                    description="Value compared with the filter column.",
                    default="",
                    displayOptions={
                        "show": {
                            "operation": filter_operations,
                            "filter_column": "*",
                            "filter_operator": [
                                "equals",
                                "not_equals",
                                "greater_than",
                                "greater_or_equal",
                                "less_than",
                                "less_or_equal",
                                "like",
                                "ilike",
                            ],
                        }
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="where_conditions",
                    displayName="Extra Conditions",
                    type=NodePropertyType.TEXT,
                    description=(
                        "Additional JSON conditions. Each entry accepts column, operator, "
                        "and value."
                    ),
                    placeholder=(
                        '[{"column": "is_active", "operator": "equals", "value": true}]'
                    ),
                    default="[]",
                    displayOptions={
                        "show": {"operation": filter_operations, "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="combine_conditions",
                    displayName="Combine Conditions",
                    type=NodePropertyType.SELECT,
                    description="Combine row conditions with AND or OR.",
                    default="AND",
                    options=[
                        {"label": "AND - all must match", "value": "AND"},
                        {"label": "OR - any may match", "value": "OR"},
                    ],
                    displayOptions={
                        "show": {"operation": filter_operations, "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="return_all",
                    displayName="Return All",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return matching rows without the configured limit. A 10,000-row "
                        "response safety cap still applies."
                    ),
                    default=False,
                    displayOptions={
                        "show": {"operation": "select", "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="limit",
                    displayName="Limit",
                    type=NodePropertyType.NUMBER,
                    description="Maximum rows to return when Return All is disabled.",
                    default=50,
                    min=1,
                    max=_MAX_RESULT_ROWS,
                    displayOptions={
                        "show": {
                            "operation": "select",
                            "return_all": False,
                        }
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="columns",
                    displayName="Columns",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Columns to return. Leave empty for all columns.",
                    placeholder="All columns",
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {"operation": "select", "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_column",
                    displayName="Sort Column",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Column used to order selected rows.",
                    placeholder="No ordering",
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {"operation": "select", "table_name": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_direction",
                    displayName="Sort Direction",
                    type=NodePropertyType.SELECT,
                    description="Order direction for the sort column.",
                    default="ASC",
                    options=[
                        {"label": "Ascending", "value": "ASC"},
                        {"label": "Descending", "value": "DESC"},
                    ],
                    displayOptions={
                        "show": {"operation": "select", "sort_column": "*"}
                    },
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="read_only",
                    displayName="Read Only",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Open the database in query-only mode. Write operations and mutating "
                        "raw SQL are refused."
                    ),
                    default=False,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="return_columns",
                    displayName="Output Columns",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Columns to return after a write. Leave empty to return every column "
                        "of affected rows."
                    ),
                    placeholder="All columns",
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "table_name"],
                    displayOptions={
                        "show": {
                            "operation": ["delete", "insert", "update", "upsert"],
                            "table_name": "*",
                        }
                    },
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="use_transaction",
                    displayName="Use Transaction",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Wrap the operation in one transaction so a failure rolls back every "
                        "change."
                    ),
                    default=True,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="replace_empty_with_null",
                    displayName="Replace Empty Strings with NULL",
                    type=NodePropertyType.CHECKBOX,
                    description="Convert empty incoming strings to SQL NULL values.",
                    default=False,
                    displayOptions={"show": {"operation": mapped_operations}},
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="select_distinct",
                    displayName="Select Distinct",
                    type=NodePropertyType.CHECKBOX,
                    description="Remove duplicate rows from Select output.",
                    default=False,
                    displayOptions={"show": {"operation": "select"}},
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="numbers_as_text",
                    displayName="Return Large Numbers as Text",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return integers outside JavaScript's safe range as text to preserve "
                        "every digit."
                    ),
                    default=True,
                    displayOptions={"show": {"operation": ["execute_query", "select"]}},
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="skip_on_conflict",
                    displayName="Skip on Conflict",
                    type=NodePropertyType.CHECKBOX,
                    description="Ignore rows that violate a SQLite constraint.",
                    default=False,
                    displayOptions={"show": {"operation": "insert"}},
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="detailed_output",
                    displayName="Output Query Execution Details",
                    type=NodePropertyType.CHECKBOX,
                    description="Include SQL and per-query metadata in the output.",
                    default=False,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="connection_timeout",
                    displayName="Connection Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Maximum time to wait for a locked SQLite database.",
                    default=30,
                    min=1,
                    max=300,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="statement_timeout",
                    displayName="Statement Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Interrupt a statement after this duration. Set 0 to disable.",
                    default=60,
                    min=0,
                    max=3600,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="continue_on_error",
                    displayName="Continue on Error",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Report failed independent items in the output instead of stopping "
                        "the workflow."
                    ),
                    default=False,
                    displayOptions={"show": {"use_transaction": False}},
                    required=False,
                    tabName="advanced",
                ),
            ],
        }

    def get_required_packages(self) -> List[str]:
        return []

    def _fetch_rows(
        self,
        credential_id: Any,
        statement: str,
        parameters: Sequence[Any] = (),
    ) -> List[Dict[str, Any]]:
        secret = _credential_secret(self, credential_id)
        with sqlite_connection(secret, {"statement_timeout": 5}) as connection:
            cursor = connection.execute(statement, parameters)
            return [dict(row) for row in cursor.fetchall()]

    def load_tables(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List user tables and views in the configured database."""
        rows = self._fetch_rows(
            values.get("credential_id"),
            """
            SELECT name
            FROM main.sqlite_schema
            WHERE type IN ('table', 'view')
              AND name NOT LIKE 'sqlite_%'
            ORDER BY name
            """,
        )
        return [{"label": str(row["name"]), "value": str(row["name"])} for row in rows]

    def load_columns(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List columns in the selected table or view."""
        table = str(values.get("table_name") or "").strip()
        if not table:
            return []
        table_name = self._identifier_name(table, "Table")
        rows = self._fetch_rows(
            values.get("credential_id"),
            f"PRAGMA main.table_xinfo({self._identifier(table_name)})",
        )
        return [
            {"label": str(row["name"]), "value": str(row["name"])}
            for row in rows
            if int(row.get("hidden") or 0) in {0, 2, 3}
        ]

    def load_column_schema(self, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Describe writable table columns for the shared column mapper."""
        table = str(values.get("table_name") or "").strip()
        if not table:
            return []
        table_name = self._identifier_name(table, "Table")
        rows = self._fetch_rows(
            values.get("credential_id"),
            f"PRAGMA main.table_xinfo({self._identifier(table_name)})",
        )

        columns: List[Dict[str, Any]] = []
        for row in rows:
            if int(row.get("hidden") or 0) != 0:
                continue
            type_name = str(row.get("type") or "").strip().upper()
            if "BOOL" in type_name:
                widget = "checkbox"
            elif any(
                affinity in type_name
                for affinity in ("INT", "REAL", "FLOA", "DOUB", "NUM", "DEC")
            ):
                widget = "number"
            elif any(temporal in type_name for temporal in ("DATE", "TIME")):
                widget = "datetime"
            elif "JSON" in type_name:
                widget = "json"
            else:
                widget = "text"

            primary_key = bool(row.get("pk"))
            has_default = row.get("dflt_value") is not None or (
                primary_key and "INT" in type_name
            )
            columns.append(
                {
                    "label": str(row["name"]),
                    "value": str(row["name"]),
                    "name": str(row["name"]),
                    "type": type_name.lower() or "text",
                    "widget": widget,
                    "required": bool(row.get("notnull") or primary_key) and not has_default,
                    "hasDefault": has_default,
                }
            )
        return columns

    def _table_columns(self, inputs: Mapping[str, Any]) -> List[str]:
        try:
            columns = [option["value"] for option in self.load_columns(dict(inputs))]
        except Exception as exc:
            logger.warning(
                "Could not load SQLite table columns for automatic mapping: %s",
                self._database_error(exc),
            )
            raise ValueError(
                "SQLite table columns could not be loaded for automatic mapping."
            ) from exc
        if not columns:
            raise ValueError(
                "The selected SQLite table has no accessible columns for automatic mapping."
            )
        return columns

    def execute(
        self,
        inputs: Dict[str, Any],
        connected_nodes: Dict[str, Any] | None = None,
    ) -> Dict[str, Any]:
        started_at = time.time()
        configuration = {**_flatten_node_configuration(self.user_data), **inputs}
        operation = str(configuration.get("operation") or "select").lower()
        if operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported SQLite operation: {operation}")

        continue_on_error = _as_bool(configuration.get("continue_on_error"))
        use_transaction = _as_bool(configuration.get("use_transaction", True))
        read_only = _as_bool(configuration.get("read_only"))
        results: List[QueryResult] = []
        errors: List[Dict[str, Any]] = []
        attempted_rows = 0

        try:
            secret = _credential_secret(self, configuration.get("credential_id"))
            effective_read_only = read_only or _as_bool(secret.get("read_only"))
            if effective_read_only and operation in WRITE_OPERATIONS:
                self._guard_read_only(operation)

            connected = _connected_payload(
                _unwrap_connected_value((connected_nodes or {}).get("input"))
            )
            specs = self._build_queries(operation, configuration, connected)
            if operation in {"insert", "upsert", "update"}:
                attempted_rows = len(specs)

            raw_command = ""
            if operation == "execute_query":
                raw_command = self._statement_command(specs[0].sql)
                if effective_read_only:
                    self._guard_read_only(operation, specs[0].sql)

            with sqlite_connection(secret, configuration) as connection:
                if use_transaction:
                    try:
                        for spec in specs:
                            results.extend(self._execute_spec(connection, spec, configuration))
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise
                else:
                    for spec in specs:
                        try:
                            results.extend(self._execute_spec(connection, spec, configuration))
                            connection.commit()
                        except Exception as exc:
                            connection.rollback()
                            if not continue_on_error:
                                raise
                            errors.append(self._error_item(exc, spec.item_index))

            all_rows = [row for result in results for row in result.rows]
            response_truncated = len(all_rows) > _MAX_RESULT_ROWS
            rows = all_rows[:_MAX_RESULT_ROWS]
            affected_rows = sum(max(0, result.affected_rows) for result in results)
            raw_is_write = bool(raw_command and raw_command not in READ_COMMANDS)
            written_rows = affected_rows if operation in WRITE_OPERATIONS or raw_is_write else 0
            last_insert_id = next(
                (
                    result.last_insert_id
                    for result in reversed(results)
                    if result.last_insert_id is not None
                ),
                None,
            )
            error_message = "; ".join(error["message"] for error in errors) or None
            output: Dict[str, Any] = {
                "rows": rows,
                "row_count": len(rows) if rows else affected_rows,
                "rows_written": written_rows,
                "rows_attempted": attempted_rows,
                "last_insert_id": last_insert_id,
                "operation": operation,
                "duration_ms": round((time.time() - started_at) * 1000, 2),
                "truncated": response_truncated or any(
                    result.truncated for result in results
                ),
                "errors": errors,
            }
            if _as_bool(configuration.get("detailed_output")):
                output["details"] = [
                    {
                        "sql": result.sql,
                        "item_index": result.item_index,
                        "row_count": len(result.rows),
                        "affected_rows": result.affected_rows,
                        "last_insert_id": result.last_insert_id,
                        "truncated": result.truncated,
                    }
                    for result in results
                ] + errors

            return {
                "output": output,
                "success": not errors,
                "error": error_message,
            }

        except Exception as exc:
            message = self._database_error(exc)
            logger.error("SQLiteNode failed operation=%s: %s", operation, message)
            if not continue_on_error:
                if isinstance(exc, sqlite3.Error):
                    raise ValueError(f"SQLite error: {message}") from exc
                raise

            return {
                "output": {
                    "rows": [],
                    "row_count": 0,
                    "rows_written": 0,
                    "rows_attempted": attempted_rows,
                    "operation": operation,
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                    "truncated": False,
                    "errors": [{"success": False, "message": message}],
                },
                "success": False,
                "error": message,
            }

    def _build_queries(
        self,
        operation: str,
        inputs: Mapping[str, Any],
        connected: Any,
    ) -> List[QuerySpec]:
        if operation == "execute_query":
            return self._execute_query_specs(inputs, connected)

        table = self._table_identifier(inputs)
        if operation == "truncate":
            return [QuerySpec(f"DELETE FROM {table}")]

        if operation == "delete":
            where_sql, where_values = self._where_clause(inputs)
            if not where_sql:
                raise ValueError(
                    "Delete requires at least one filter condition. Use Truncate when the "
                    "explicit intention is to empty the whole table."
                )
            return [
                QuerySpec(
                    f"DELETE FROM {table}{where_sql}{self._returning_clause(inputs)}",
                    where_values,
                )
            ]

        if operation == "select":
            columns = self._columns(inputs.get("columns"))
            distinct = " DISTINCT" if _as_bool(inputs.get("select_distinct")) else ""
            where_sql, values = self._where_clause(inputs)
            sort_sql = self._sort_clause(inputs)
            if _as_bool(inputs.get("return_all")):
                limit = _MAX_RESULT_ROWS + 1
            else:
                limit_value = inputs.get("limit")
                if limit_value in (None, ""):
                    limit_value = 50
                try:
                    limit = int(limit_value)
                except (TypeError, ValueError) as exc:
                    raise ValueError("Limit must be a whole number.") from exc
                if limit < 1 or limit > _MAX_RESULT_ROWS:
                    raise ValueError(
                        f"Limit must be between 1 and {_MAX_RESULT_ROWS}."
                    )
            return [
                QuerySpec(
                    f"SELECT{distinct} {columns} FROM {table}"
                    f"{where_sql}{sort_sql} LIMIT ?",
                    [*values, limit],
                )
            ]

        records = self._records(inputs, connected)
        if _as_bool(inputs.get("replace_empty_with_null")):
            records = [
                {key: (None if value == "" else value) for key, value in row.items()}
                for row in records
            ]

        if operation == "insert":
            return self._insert_specs(table, records, inputs)
        if operation == "upsert":
            return self._upsert_specs(table, records, inputs)
        return self._update_specs(table, records, inputs)

    def _execute_query_specs(
        self,
        inputs: Mapping[str, Any],
        connected: Any,
    ) -> List[QuerySpec]:
        query = str(inputs.get("query") or "").strip()
        if not query:
            raise ValueError("SQL Query is required.")
        self._ensure_single_statement(query)
        command = self._statement_command(query)
        if command in DISALLOWED_COMMANDS:
            raise ValueError(
                f"{command} statements are not allowed. The node manages the configured "
                "database connection and transaction."
            )

        raw_parameters = _parse_json(
            inputs.get("query_parameters"),
            default=[],
            field_name="Query Parameters",
        )
        if raw_parameters in ([], {}) and connected is not None:
            parameter_sets = connected if isinstance(connected, list) else [connected]
        else:
            parameter_sets = [raw_parameters]

        specs: List[QuerySpec] = []
        for index, parameters in enumerate(parameter_sets):
            prepared, values = self._prepare_query(query, parameters)
            specs.append(QuerySpec(prepared, values, index))
        return specs

    def _records(
        self,
        inputs: Mapping[str, Any],
        connected: Any,
    ) -> List[Dict[str, Any]]:
        automatic = str(inputs.get("mapping_mode") or "manual") == "auto"
        if automatic:
            value = self._unwrap_payload(connected)
        else:
            value = _parse_json(
                inputs.get("data"),
                default={},
                field_name="Values to Send",
            )
        records = value if isinstance(value, list) else [value]
        if not records or not all(isinstance(record, dict) and record for record in records):
            if automatic:
                raise ValueError(
                    "Automatic mapping requires an input connection that produces an object "
                    "or a list of objects."
                )
            raise ValueError(
                "Values to Send must contain a non-empty object or array of objects."
            )

        known_columns: Optional[Dict[str, str]] = None
        if automatic:
            columns = self._table_columns(inputs)
            known_columns = {column.casefold(): column for column in columns}

        cleaned: List[Dict[str, Any]] = []
        for record in records:
            if known_columns is None:
                row = {str(key): value for key, value in record.items()}
            else:
                row = {
                    known_columns[str(key).casefold()]: value
                    for key, value in record.items()
                    if str(key).casefold() in known_columns
                }
            if not row:
                raise ValueError(
                    "None of the incoming fields match a column of the selected table."
                )
            cleaned.append(
                {
                    self._identifier_name(key, "Column"): value
                    for key, value in row.items()
                }
            )
        return cleaned

    def _insert_specs(
        self,
        table: str,
        records: List[Dict[str, Any]],
        inputs: Mapping[str, Any],
    ) -> List[QuerySpec]:
        columns = self._common_columns(records)
        command = "INSERT OR IGNORE" if _as_bool(inputs.get("skip_on_conflict")) else "INSERT"
        column_sql = ", ".join(self._identifier(column) for column in columns)
        placeholders = ", ".join("?" for _ in columns)
        sql = (
            f"{command} INTO {table} ({column_sql}) VALUES ({placeholders})"
            f"{self._returning_clause(inputs)}"
        )
        return [
            QuerySpec(sql, [record[column] for column in columns], index)
            for index, record in enumerate(records)
        ]

    def _upsert_specs(
        self,
        table: str,
        records: List[Dict[str, Any]],
        inputs: Mapping[str, Any],
    ) -> List[QuerySpec]:
        match_columns = self._split_columns(inputs.get("match_columns"))
        if not match_columns:
            raise ValueError("Insert or Update requires at least one match column.")

        specs: List[QuerySpec] = []
        for index, record in enumerate(records):
            row = dict(record)
            missing = [column for column in match_columns if column not in row]
            if missing:
                raise ValueError(
                    f"Incoming row {index + 1} is missing match column(s): "
                    f"{', '.join(missing)}."
                )
            columns = list(row)
            update_columns = [
                column for column in columns if column not in match_columns
            ]
            column_sql = ", ".join(self._identifier(column) for column in columns)
            placeholders = ", ".join("?" for _ in columns)
            conflict_columns = ", ".join(
                self._identifier(column) for column in match_columns
            )
            if update_columns:
                action = "DO UPDATE SET " + ", ".join(
                    f"{self._identifier(column)} = excluded.{self._identifier(column)}"
                    for column in update_columns
                )
            else:
                action = "DO NOTHING"
            specs.append(
                QuerySpec(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
                    f"ON CONFLICT ({conflict_columns}) {action}"
                    f"{self._returning_clause(inputs)}",
                    [row[column] for column in columns],
                    index,
                )
            )
        return specs

    def _update_specs(
        self,
        table: str,
        records: List[Dict[str, Any]],
        inputs: Mapping[str, Any],
    ) -> List[QuerySpec]:
        match_columns = self._split_columns(inputs.get("match_columns"))
        filter_sql, filter_values = self._where_clause(inputs)
        if not match_columns and not filter_sql:
            raise ValueError(
                "Update requires at least one match column or filter condition. A filterless "
                "update could overwrite every row in the table."
            )
        if len(records) > 1 and not match_columns:
            raise ValueError("Updating multiple input rows requires Columns to Match On.")

        specs: List[QuerySpec] = []
        for index, record in enumerate(records):
            row = dict(record)
            missing = [column for column in match_columns if column not in row]
            if missing:
                raise ValueError(
                    f"Incoming row {index + 1} is missing match column(s): "
                    f"{', '.join(missing)}."
                )
            update_columns = [
                column for column in row if column not in match_columns
            ]
            if not update_columns:
                raise ValueError("Update needs at least one non-match column.")

            assignments = ", ".join(
                f"{self._identifier(column)} = ?" for column in update_columns
            )
            match_sql = " AND ".join(
                f"{self._identifier(column)} = ?" for column in match_columns
            )
            filter_part = (
                f"({filter_sql.removeprefix(' WHERE ')})" if filter_sql else ""
            )
            where_parts = [part for part in (match_sql, filter_part) if part]
            parameters = [row[column] for column in update_columns]
            parameters.extend(row[column] for column in match_columns)
            parameters.extend(filter_values)
            specs.append(
                QuerySpec(
                    f"UPDATE {table} SET {assignments} "
                    f"WHERE {' AND '.join(where_parts)}"
                    f"{self._returning_clause(inputs)}",
                    parameters,
                    index,
                )
            )
        return specs

    def _execute_spec(
        self,
        connection: sqlite3.Connection,
        spec: QuerySpec,
        inputs: Mapping[str, Any],
    ) -> List[QueryResult]:
        cursor = connection.cursor()
        try:
            timeout_value = inputs.get("statement_timeout")
            if timeout_value in (None, ""):
                timeout_value = 60
            statement_timeout = int(timeout_value)
            if statement_timeout:
                deadline = time.monotonic() + statement_timeout
                connection.set_progress_handler(
                    lambda: int(time.monotonic() >= deadline),
                    1_000,
                )
            cursor.execute(spec.sql, spec.parameters or ())
            raw_rows = cursor.fetchmany(_MAX_RESULT_ROWS + 1) if cursor.description else []
            truncated = len(raw_rows) > _MAX_RESULT_ROWS
            rows = raw_rows[:_MAX_RESULT_ROWS]
            command = self._statement_command(spec.sql)
            last_insert_id = (
                int(cursor.lastrowid)
                if cursor.lastrowid is not None and command in {"INSERT", "REPLACE"}
                else None
            )
            return [
                QueryResult(
                    sql=spec.sql,
                    rows=[self._serializable_row(dict(row), inputs) for row in rows],
                    affected_rows=max(0, int(cursor.rowcount or 0)),
                    last_insert_id=last_insert_id,
                    item_index=spec.item_index,
                    truncated=truncated,
                )
            ]
        finally:
            connection.set_progress_handler(None, 0)
            cursor.close()

    @classmethod
    def _prepare_query(
        cls,
        query: str,
        parameters: Any,
    ) -> tuple[str, Sequence[Any] | Mapping[str, Any]]:
        if isinstance(parameters, dict):
            if _POSITIONAL_PARAMETER.search(cls._masked_sql(query)):
                raise ValueError(
                    "$1 parameters require a JSON array; use SQLite named placeholders "
                    "for a JSON object."
                )
            return query, parameters
        if not isinstance(parameters, (list, tuple)):
            raise ValueError("Query Parameters must be a JSON array or object.")

        output: List[str] = []
        values: List[Any] = []
        referenced: set[int] = set()
        index = 0
        while index < len(query):
            if query.startswith("--", index):
                end = query.find("\n", index + 2)
                end = len(query) if end == -1 else end
                output.append(query[index:end])
                index = end
                continue
            if query.startswith("/*", index):
                end = query.find("*/", index + 2)
                end = len(query) if end == -1 else end + 2
                output.append(query[index:end])
                index = end
                continue

            char = query[index]
            if char in {"'", '"', chr(96), "["}:
                closing = "]" if char == "[" else char
                end = index + 1
                while end < len(query):
                    if query[end] == closing:
                        if (
                            closing != "]"
                            and end + 1 < len(query)
                            and query[end + 1] == closing
                        ):
                            end += 2
                            continue
                        end += 1
                        break
                    end += 1
                output.append(query[index:end])
                index = end
                continue

            if char == "$":
                match = _POSITIONAL_PARAMETER.match(query, index)
                if match:
                    parameter_index = int(match.group(1)) - 1
                    if parameter_index < 0 or parameter_index >= len(parameters):
                        raise ValueError(
                            "The query references $"
                            + match.group(1)
                            + f" but only {len(parameters)} parameter(s) were supplied."
                        )
                    if match.group(2):
                        output.append(
                            cls._qualified_identifier(parameters[parameter_index])
                        )
                    else:
                        output.append("?")
                        values.append(parameters[parameter_index])
                    referenced.add(parameter_index)
                    index = match.end()
                    continue

            output.append(char)
            index += 1

        unused = [
            position + 1
            for position in range(len(parameters))
            if position not in referenced
        ]
        if unused:
            labels = ", ".join("$" + str(position) for position in unused)
            raise ValueError(f"Query Parameters contains unused value(s): {labels}.")
        return "".join(output), values

    @classmethod
    def _ensure_single_statement(cls, query: str) -> None:
        statements: List[str] = []
        current: List[str] = []
        for char in query:
            current.append(char)
            candidate = "".join(current)
            if char == ";" and sqlite3.complete_statement(candidate):
                if cls._masked_sql(candidate).strip().strip(";"):
                    statements.append(candidate)
                current = []

        remainder = "".join(current)
        if cls._masked_sql(remainder).strip().strip(";"):
            statements.append(remainder)
        if len(statements) != 1:
            raise ValueError("Exactly one SQL statement is required per execution.")

    @staticmethod
    def _masked_sql(statement: str) -> str:
        output: List[str] = []
        index = 0
        while index < len(statement):
            if statement.startswith("--", index):
                end = statement.find("\n", index + 2)
                end = len(statement) if end == -1 else end
                output.extend(" " * (end - index))
                index = end
                continue
            if statement.startswith("/*", index):
                end = statement.find("*/", index + 2)
                end = len(statement) if end == -1 else end + 2
                output.extend(" " * (end - index))
                index = end
                continue
            char = statement[index]
            if char in {"'", '"', chr(96), "["}:
                closing = "]" if char == "[" else char
                output.append(" ")
                index += 1
                while index < len(statement):
                    output.append(" ")
                    if statement[index] == closing:
                        if (
                            closing != "]"
                            and index + 1 < len(statement)
                            and statement[index + 1] == closing
                        ):
                            index += 1
                            output.append(" ")
                        else:
                            index += 1
                            break
                    index += 1
                continue
            output.append(char)
            index += 1
        return "".join(output)

    @classmethod
    def _statement_command(cls, statement: str) -> str:
        masked = cls._masked_sql(statement)
        first = re.match(r"\s*([A-Za-z]+)", masked)
        if not first:
            raise ValueError("Unable to determine the SQL command.")
        command = first.group(1).upper()
        if command != "WITH":
            return command

        depth = 0
        for match in re.finditer(r"[A-Za-z_]+|[()]", masked[first.end() :]):
            token = match.group(0).upper()
            if token == "(":
                depth += 1
            elif token == ")":
                depth = max(0, depth - 1)
            elif depth == 0 and token in {
                "DELETE",
                "INSERT",
                "REPLACE",
                "SELECT",
                "UPDATE",
                "VALUES",
            }:
                return token
        raise ValueError("Unable to determine the command following WITH.")

    @classmethod
    def _collect_conditions(
        cls,
        inputs: Mapping[str, Any],
    ) -> List[Dict[str, Any]]:
        conditions: List[Dict[str, Any]] = []
        column = str(inputs.get("filter_column") or "").strip()
        if column:
            operator = str(inputs.get("filter_operator") or "equals").lower()
            condition: Dict[str, Any] = {
                "column": column,
                "operator": operator,
            }
            if operator not in {"is_null", "is_not_null"}:
                condition["value"] = inputs.get("filter_value")
            conditions.append(condition)

        extra = _parse_json(
            inputs.get("where_conditions"),
            default=[],
            field_name="Extra Conditions",
        )
        if isinstance(extra, dict):
            extra = [
                {
                    "column": key,
                    "operator": "is_null" if value is None else "equals",
                    "value": value,
                }
                for key, value in extra.items()
            ]
        if not isinstance(extra, list):
            raise ValueError("Extra Conditions must contain a JSON array or object.")
        conditions.extend(extra)
        return conditions

    @classmethod
    def _where_clause(
        cls,
        inputs: Mapping[str, Any],
    ) -> tuple[str, List[Any]]:
        conditions = cls._collect_conditions(inputs)
        combine = str(inputs.get("combine_conditions") or "AND").upper()
        if combine not in {"AND", "OR"}:
            raise ValueError("Combine Conditions must be AND or OR.")

        clauses: List[str] = []
        values: List[Any] = []
        for index, condition in enumerate(conditions):
            if not isinstance(condition, dict) or not condition.get("column"):
                raise ValueError(f"Condition {index + 1} must contain a column.")
            operator_key = str(condition.get("operator") or "equals").lower()
            if operator_key not in CONDITION_OPERATORS:
                raise ValueError(f"Unsupported condition operator: {operator_key}")

            identifier = cls._identifier(condition["column"])
            operator_sql = CONDITION_OPERATORS[operator_key]
            if operator_key in {"is_null", "is_not_null"}:
                clause = f"{identifier} {operator_sql}"
            else:
                value = condition.get("value")
                if operator_key in {"like", "ilike"} and isinstance(value, str):
                    if "%" not in value and "_" not in value:
                        value = f"%{value}%"
                if operator_key == "ilike":
                    clause = f"LOWER(CAST({identifier} AS TEXT)) LIKE LOWER(?)"
                elif operator_key in {"equals", "not_equals"} and isinstance(value, str):
                    clause = (
                        f"LOWER(CAST({identifier} AS TEXT)) {operator_sql} LOWER(?)"
                    )
                else:
                    clause = f"{identifier} {operator_sql} ?"
                values.append(value)
            clauses.append(clause)
        return (f" WHERE {f' {combine} '.join(clauses)}" if clauses else ""), values

    @classmethod
    def _sort_clause(cls, inputs: Mapping[str, Any]) -> str:
        column = str(inputs.get("sort_column") or "").strip()
        if not column:
            return ""
        direction = str(inputs.get("sort_direction") or "ASC").upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("Sort direction must be ASC or DESC.")
        return f" ORDER BY {cls._identifier(column)} {direction}"

    @classmethod
    def _returning_clause(cls, inputs: Mapping[str, Any]) -> str:
        return f" RETURNING {cls._columns(inputs.get('return_columns'))}"

    @classmethod
    def _error_item(cls, error: Exception, item_index: int) -> Dict[str, Any]:
        return {
            "success": False,
            "message": cls._database_error(error),
            "error_type": type(error).__name__,
            "item_index": item_index,
        }

    @staticmethod
    def _database_error(error: Exception) -> str:
        message = str(error).strip()
        normalized = message.lower()
        if "unable to open database file" in normalized:
            return "Could not open the configured SQLite database file."
        if "readonly database" in normalized or "read-only database" in normalized:
            return "The configured SQLite database is read-only."
        if "database is locked" in normalized or "database is busy" in normalized:
            return "The SQLite database is locked by another operation."
        if "unique constraint failed" in normalized:
            return "The statement conflicts with an existing unique value."
        if "foreign key constraint failed" in normalized:
            return "The statement violates a foreign key constraint."
        if "not null constraint failed" in normalized:
            return "A required SQLite column received a null value."
        if "no such table" in normalized:
            return "A referenced SQLite table does not exist or is not accessible."
        if "no such column" in normalized:
            return "A referenced SQLite column does not exist."
        if "interrupted" in normalized:
            return "The SQLite statement exceeded its timeout."
        safe_message = message or "The SQLite operation failed."
        return _SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", safe_message)[:500]

    @staticmethod
    def _serializable_row(
        row: Mapping[str, Any],
        inputs: Mapping[str, Any],
    ) -> Dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value) if _as_bool(inputs.get("numbers_as_text")) else float(value)
            if (
                isinstance(value, int)
                and abs(value) > _MAX_SAFE_INTEGER
                and _as_bool(inputs.get("numbers_as_text"))
            ):
                return str(value)
            if isinstance(value, (dt.datetime, dt.date, dt.time)):
                return value.isoformat()
            if isinstance(value, dt.timedelta):
                return value.total_seconds()
            if isinstance(value, (bytes, bytearray, memoryview)):
                return bytes(value).hex()
            return value

        return {str(key): convert(value) for key, value in row.items()}

    @staticmethod
    def _common_columns(records: Iterable[Mapping[str, Any]]) -> List[str]:
        rows = list(records)
        if not rows:
            raise ValueError("At least one input row is required.")
        columns = list(rows[0])
        expected = set(columns)
        for record in rows[1:]:
            if set(record) != expected:
                raise ValueError(
                    "All rows in an insert batch must contain the same columns."
                )
        return columns

    @classmethod
    def _split_columns(cls, value: Any) -> List[str]:
        if not value:
            return []
        if isinstance(value, str):
            parts = value.split(",")
        elif isinstance(value, (list, tuple, set)):
            parts = [str(part) for part in value]
        else:
            parts = [str(value)]
        return [
            cls._identifier_name(part, "Column")
            for part in parts
            if str(part).strip()
        ]

    @classmethod
    def _columns(cls, value: Any) -> str:
        columns = cls._split_columns(value)
        return ", ".join(cls._identifier(column) for column in columns) if columns else "*"

    @staticmethod
    def _identifier_name(value: Any, label: str) -> str:
        identifier = str(value or "").strip()
        if not identifier or "\x00" in identifier:
            raise ValueError(f"{label} is required and cannot contain a null byte.")
        return identifier

    @classmethod
    def _identifier(cls, value: Any) -> str:
        identifier = cls._identifier_name(value, "Identifier")
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    @classmethod
    def _table_identifier(cls, inputs: Mapping[str, Any]) -> str:
        table = cls._identifier_name(inputs.get("table_name"), "Table")
        return f'{cls._identifier("main")}.{cls._identifier(table)}'

    @classmethod
    def _qualified_identifier(cls, value: Any) -> str:
        parts = [part.strip() for part in str(value).split(".")]
        if not parts or any(not part for part in parts) or len(parts) > 2:
            raise ValueError("A SQLite identifier may contain a table, or schema and table.")
        return ".".join(cls._identifier(part) for part in parts)

    ENVELOPE_KEYS = (
        "webhook_data",
        "payload",
        "body",
        "json",
        "data",
        "result",
        "rows",
    )

    @classmethod
    def _unwrap_payload(cls, value: Any, depth: int = 4) -> Any:
        if depth <= 0 or not isinstance(value, dict):
            return value
        for key in cls.ENVELOPE_KEYS:
            inner = value.get(key)
            if isinstance(inner, dict) and inner:
                return cls._unwrap_payload(inner, depth - 1)
            if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                return inner
        return value

    @classmethod
    def _guard_read_only(cls, operation: str, query: str = "") -> None:
        if operation in WRITE_OPERATIONS:
            raise ValueError(
                f"Read Only is enabled, so the '{operation}' operation is not allowed."
            )
        if operation != "execute_query" or not query:
            return
        command = cls._statement_command(query)
        if command not in READ_COMMANDS:
            raise ValueError(
                f"Read Only is enabled, so {command} statements are not allowed."
            )
