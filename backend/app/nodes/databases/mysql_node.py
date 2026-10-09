"""MySQL processor node with shared dynamic controls and safe table operations."""

from __future__ import annotations

import contextlib
import datetime as dt
import json
import logging
import os
import re
import ssl
import tempfile
import time
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Set

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
    "delete", "execute_query", "insert", "select", "truncate", "update", "upsert",
}
WRITE_OPERATIONS = {"delete", "insert", "truncate", "update", "upsert"}
WRITE_KEYWORDS = {
    "alter", "call", "create", "delete", "drop", "grant", "insert", "load",
    "lock", "rename", "replace", "revoke", "truncate", "update",
}
CONDITION_OPERATORS = {
    "equals": "=",
    "not_equals": "<>",
    "greater_than": ">",
    "greater_or_equal": ">=",
    "less_than": "<",
    "less_or_equal": "<=",
    "like": "LIKE BINARY",
    "ilike": "LIKE",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
}
_POSITIONAL_PARAMETER = re.compile(r"\$(\d+)(:name)?")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991
_MAX_RESULT_ROWS = 10_000
_SYSTEM_SCHEMAS = {"information_schema", "mysql", "performance_schema", "sys"}
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
    """Read the row list out of an upstream MySQL result payload."""
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return value["rows"]
    return value


def _flatten_node_configuration(user_data: Any) -> Dict[str, Any]:
    """Return form values regardless of the frontend's flat/nested storage shape."""
    if not isinstance(user_data, dict):
        return {}
    configuration = dict(user_data)
    nested_inputs = user_data.get("inputs")
    if isinstance(nested_inputs, dict):
        configuration.update(nested_inputs)
    return configuration


def _credential_secret(node: ProcessorNode, credential_id: Any) -> Dict[str, Any]:
    if not credential_id:
        raise ValueError("A MySQL credential must be selected.")
    credential = node.get_credential(str(credential_id))
    if not credential:
        raise ValueError("The selected MySQL credential could not be found.")
    if credential.get("service_type") != "mysql":
        raise ValueError("The selected credential is not a MySQL credential.")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise ValueError("The selected MySQL credential has an invalid secret payload.")
    return secret


@contextlib.contextmanager
def mysql_connection(secret: Mapping[str, Any], options: Mapping[str, Any] | None = None) -> Iterator[Any]:
    """Open a direct or TLS-protected PyMySQL connection."""
    import pymysql
    from pymysql.cursors import DictCursor

    options = options or {}
    host = str(secret.get("host") or "").strip()
    database = str(secret.get("database") or "").strip()
    username = str(secret.get("username") or secret.get("user") or "").strip()
    if not host:
        raise ValueError("MySQL Host is required.")
    if not database:
        raise ValueError("MySQL Database is required.")
    if not username:
        raise ValueError("MySQL Username is required.")

    try:
        port = int(secret.get("port") or 3306)
    except (TypeError, ValueError) as exc:
        raise ValueError("MySQL Port must be a whole number.") from exc
    if port < 1 or port > 65535:
        raise ValueError("MySQL Port must be between 1 and 65535.")

    ssl_options = None
    temporary_certificate_paths: List[str] = []
    try:
        if _as_bool(secret.get("ssl")):
            ssl_options = ssl.create_default_context()
            ca_certificate = str(secret.get("ca_certificate") or "").replace("\\n", "\n").strip()
            client_certificate = str(secret.get("client_certificate") or "").replace("\\n", "\n").strip()
            client_private_key = str(secret.get("client_private_key") or "").replace("\\n", "\n").strip()
            if ca_certificate:
                ssl_options.load_verify_locations(cadata=ca_certificate)
            if bool(client_certificate) != bool(client_private_key):
                raise ValueError("Both the TLS client certificate and private key must be provided together.")
            if client_certificate and client_private_key:
                for suffix, contents in ((".crt", client_certificate), (".key", client_private_key)):
                    handle = tempfile.NamedTemporaryFile(mode="w", suffix=suffix, delete=False, encoding="utf-8")
                    try:
                        handle.write(contents)
                    finally:
                        handle.close()
                    temporary_certificate_paths.append(handle.name)
                ssl_options.load_cert_chain(
                    certfile=temporary_certificate_paths[0],
                    keyfile=temporary_certificate_paths[1],
                )
    except Exception:
        for path in temporary_certificate_paths:
            with contextlib.suppress(OSError):
                os.unlink(path)
        raise

    credential_timeout_value = secret.get("connect_timeout")
    if credential_timeout_value in (None, ""):
        credential_timeout_value = 10_000
    try:
        credential_timeout_ms = int(credential_timeout_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("MySQL Connect Timeout must be a whole number of milliseconds.") from exc
    if credential_timeout_ms < 1_000 or credential_timeout_ms > 300_000:
        raise ValueError("MySQL Connect Timeout must be between 1000 and 300000 milliseconds.")
    connection_timeout = options.get("connection_timeout")
    if connection_timeout in (None, ""):
        connection_timeout = max(1, credential_timeout_ms // 1000)
    statement_timeout = options.get("statement_timeout")
    if statement_timeout in (None, ""):
        statement_timeout = 60
    try:
        connection_timeout = int(connection_timeout)
        statement_timeout = int(statement_timeout)
    except (TypeError, ValueError) as exc:
        raise ValueError("MySQL timeout values must be whole numbers.") from exc
    if connection_timeout < 1 or connection_timeout > 300:
        raise ValueError("MySQL connection timeout must be between 1 and 300 seconds.")
    if statement_timeout < 1 or statement_timeout > 3600:
        raise ValueError("MySQL statement timeout must be between 1 and 3600 seconds.")
    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            database=database,
            user=username,
            password=str(secret.get("password") or ""),
            charset=str(secret.get("charset") or "utf8mb4"),
            connect_timeout=connection_timeout,
            read_timeout=statement_timeout,
            write_timeout=statement_timeout,
            cursorclass=DictCursor,
            autocommit=False,
            ssl=ssl_options,
        )
        yield connection
    finally:
        if connection is not None:
            connection.close()
        for path in temporary_certificate_paths:
            with contextlib.suppress(OSError):
                os.unlink(path)


class MySQLNode(ProcessorNode):
    """Runs SQL statements and table operations against a MySQL database."""

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
            "name": "MySQLNode",
            "display_name": "MySQL",
            "description": (
                "Run queries and manage rows in a MySQL database. Supports raw SQL, select, "
                "insert, update, upsert, delete, and truncate operations."
            ),
            "category": "Databases",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "mysql", "path": "icons/mysql.svg", "alt": "MySQL"},
            "colors": ["cyan-700", "blue-800"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description="Incoming row or rows used by automatic mapping and query batching.",
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
                    description="Selected rows together with the MySQL execution metadata.",
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
                    description="MySQL connection credential.",
                    placeholder="Select Credential",
                    serviceType="mysql",
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
                    name="schema_name",
                    displayName="Schema",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="MySQL database that contains the table.",
                    placeholder="Select or type a schema",
                    default="",
                    optionsMethod="load_schemas",
                    optionsDependsOn=["credential_id"],
                    displayOptions={"show": {"operation": table_operations}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="table_name",
                    displayName="Table",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Table to operate on. Pick one from the list or type a name.",
                    placeholder="Select or type a table",
                    default="",
                    optionsMethod="load_tables",
                    optionsDependsOn=["credential_id", "schema_name"],
                    displayOptions={"show": {"operation": table_operations, "schema_name": "*"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="query",
                    displayName="SQL Query",
                    type=NodePropertyType.CODE_EDITOR,
                    description="One SQL statement to run. Use $1, $2 placeholders for values.",
                    placeholder="SELECT id, name FROM customers WHERE status = $1",
                    rows=8,
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=False,
                    default="",
                    maxLength=20000,
                    tabName="basic",
                ),
                NodeProperty(
                    name="query_parameters",
                    displayName="Query Parameters",
                    type=NodePropertyType.JSON_EDITOR,
                    description="JSON array or object of parameter values. Incoming data is used when this is empty.",
                    default="[]",
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="mapping_mode",
                    displayName="Mapping Column Mode",
                    type=NodePropertyType.SELECT,
                    description="Automatically map incoming property names or define values below.",
                    default="manual",
                    options=[
                        {"label": "Map Each Column Manually", "value": "manual"},
                        {"label": "Map Automatically", "value": "auto"},
                    ],
                    displayOptions={"show": {"operation": mapped_operations, "table_name": "*"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="match_columns",
                    displayName="Columns to Match On",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Columns whose values identify an existing row and are not updated. "
                        "Insert or Update requires these columns to belong to a primary or unique key."
                    ),
                    placeholder="Select one or more columns",
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": ["upsert", "update"], "table_name": "*"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="data",
                    displayName="Values to Send",
                    type=NodePropertyType.COLUMN_MAPPER,
                    description="Values for the selected table columns. Omitted columns use database defaults.",
                    default="{}",
                    optionsMethod="load_column_schema",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
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
                    description="Column used by the primary row filter.",
                    placeholder="No filter",
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": filter_operations, "table_name": "*"}},
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
                        {"label": "is greater than or equal to", "value": "greater_or_equal"},
                        {"label": "is less than", "value": "less_than"},
                        {"label": "is less than or equal to", "value": "less_or_equal"},
                        {"label": "contains", "value": "ilike"},
                        {"label": "contains (case sensitive)", "value": "like"},
                        {"label": "is empty", "value": "is_null"},
                        {"label": "is not empty", "value": "is_not_null"},
                    ],
                    displayOptions={"show": {"operation": filter_operations, "filter_column": "*"}},
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
                                "equals", "not_equals", "greater_than", "greater_or_equal",
                                "less_than", "less_or_equal", "like", "ilike",
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
                        "JSON condition array, for example "
                        '[{"column":"status","operator":"equals","value":"active"}]. '
                        "Supports comparisons, text matching, and NULL checks."
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
                    options=[{"label": "AND", "value": "AND"}, {"label": "OR", "value": "OR"}],
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
                        "Return matching rows without the configured limit. A 10,000-row response "
                        "safety cap still applies."
                    ),
                    default=False,
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
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
                    max=10_000,
                    displayOptions={"show": {"operation": "select", "return_all": False}},
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
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
                    required=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_column",
                    displayName="Sort Column",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Column used to order the selected rows.",
                    placeholder="No ordering",
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
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
                    displayOptions={"show": {"operation": "select", "sort_column": "*"}},
                    tabName="basic",
                    required=False,
                ),
                NodeProperty(
                    name="read_only",
                    displayName="Read Only",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Allow reading only. Write operations are refused and raw SQL runs in a "
                        "MySQL read-only transaction."
                    ),
                    default=False,
                    displayOptions={"show": {"operation": ["execute_query", "select"]}},
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="connection_timeout",
                    displayName="Connection Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Time reserved for opening the database connection.",
                    default=30,
                    min=1,
                    max=300,
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="statement_timeout",
                    displayName="Statement Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Stop waiting for a statement that exceeds this duration.",
                    default=60,
                    min=1,
                    max=3600,
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="replace_empty_with_null",
                    displayName="Replace Empty Strings with NULL",
                    type=NodePropertyType.CHECKBOX,
                    description="Convert empty incoming strings to SQL NULL values.",
                    default=False,
                    tabName="advanced",
                    displayOptions={"show": {"operation": ["insert", "update", "upsert"]}},
                    required=False,
                ),
                NodeProperty(
                    name="select_distinct",
                    displayName="Select Distinct",
                    type=NodePropertyType.CHECKBOX,
                    description="Remove duplicate rows from Select output.",
                    default=False,
                    tabName="advanced",
                    displayOptions={"show": {"operation": "select"}},
                    required=False,
                ),
                NodeProperty(
                    name="numbers_as_text",
                    displayName="Return Numbers as Text",
                    type=NodePropertyType.CHECKBOX,
                    description="Return BIGINT and DECIMAL values as text to preserve every digit.",
                    default=False,
                    displayOptions={"show": {"operation": ["execute_query", "select"]}},
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="use_transaction",
                    displayName="Use Transaction",
                    type=NodePropertyType.CHECKBOX,
                    description="Roll back every statement in the operation when one of them fails.",
                    default=True,
                    displayOptions={
                        "show": {
                            "operation": ["delete", "execute_query", "insert", "update", "upsert"]
                        }
                    },
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="priority",
                    displayName="Insert Priority",
                    type=NodePropertyType.SELECT,
                    description="Optional MySQL INSERT scheduling priority.",
                    default="none",
                    options=[
                        {"label": "Default", "value": "none"},
                        {"label": "Low Priority", "value": "LOW_PRIORITY"},
                        {"label": "High Priority", "value": "HIGH_PRIORITY"},
                    ],
                    tabName="advanced",
                    displayOptions={"show": {"operation": "insert"}},
                    required=False,
                ),
                NodeProperty(
                    name="skip_on_conflict",
                    displayName="Skip on Conflict",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Use MySQL INSERT IGNORE. Duplicate rows are skipped, and MySQL may turn "
                        "some other data errors into warnings."
                    ),
                    default=False,
                    tabName="advanced",
                    displayOptions={"show": {"operation": "insert"}},
                    required=False,
                ),
                NodeProperty(
                    name="detailed_output",
                    displayName="Output Query Execution Details",
                    type=NodePropertyType.CHECKBOX,
                    description="Include SQL, item index, row count, and insert ID for each statement.",
                    default=False,
                    tabName="advanced",
                    required=False,
                ),
                NodeProperty(
                    name="continue_on_error",
                    displayName="Continue on Error",
                    type=NodePropertyType.CHECKBOX,
                    description="Report failed statements in the output instead of stopping the workflow.",
                    default=False,
                    tabName="advanced",
                    required=False,
                ),
            ],
            "examples": [
                {
                    "operation": "select",
                    "table_name": "customers",
                    "where_conditions": [
                        {"column": "status", "operator": "equals", "value": "active"}
                    ],
                },
                {
                    "operation": "execute_query",
                    "query": "SELECT * FROM orders WHERE total >= $1",
                    "query_parameters": [100],
                },
            ],
        }

    @staticmethod
    def _schema_name(values: Mapping[str, Any], secret: Mapping[str, Any]) -> str:
        schema = str(values.get("schema_name") or secret.get("database") or "").strip()
        if not schema:
            raise ValueError("A MySQL schema must be selected.")
        return MySQLNode._identifier_name(schema, "Schema")

    def _fetch_rows(
        self,
        credential_id: Any,
        statement: str,
        parameters: Sequence[Any] = (),
    ) -> List[Dict[str, Any]]:
        secret = _credential_secret(self, credential_id)
        with mysql_connection(
            secret,
            {"connection_timeout": 10, "statement_timeout": 10},
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute(statement, parameters or None)
                return [dict(row) for row in cursor.fetchall()]

    def load_schemas(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List non-system databases visible to the selected credential."""
        secret = _credential_secret(self, values.get("credential_id"))
        rows = self._fetch_rows(
            values.get("credential_id"),
            "SELECT SCHEMA_NAME AS name FROM information_schema.SCHEMATA ORDER BY SCHEMA_NAME",
        )
        names = [str(row["name"]) for row in rows if row["name"] not in _SYSTEM_SCHEMAS]
        default_schema = str(secret.get("database") or "").strip()
        if default_schema in names:
            names.remove(default_schema)
            names.insert(0, default_schema)
        return [{"label": name, "value": name} for name in names]

    def load_tables(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List tables and views in the selected MySQL database."""
        secret = _credential_secret(self, values.get("credential_id"))
        schema = self._schema_name(values, secret)
        rows = self._fetch_rows(
            values.get("credential_id"),
            """
            SELECT TABLE_NAME AS name
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = %s AND TABLE_TYPE IN ('BASE TABLE', 'VIEW')
            ORDER BY TABLE_NAME
            """,
            (schema,),
        )
        return [{"label": str(row["name"]), "value": str(row["name"])} for row in rows]

    def load_columns(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List the columns of the selected table."""
        table = str(values.get("table_name") or "").strip()
        if not table:
            return []
        self._identifier_name(table, "Table")
        secret = _credential_secret(self, values.get("credential_id"))
        schema = self._schema_name(values, secret)
        rows = self._fetch_rows(
            values.get("credential_id"),
            """
            SELECT COLUMN_NAME AS name
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema, table),
        )
        return [{"label": str(row["name"]), "value": str(row["name"])} for row in rows]

    def load_column_schema(self, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Describe table columns for the shared column-mapper field."""
        table = str(values.get("table_name") or "").strip()
        if not table:
            return []
        self._identifier_name(table, "Table")
        secret = _credential_secret(self, values.get("credential_id"))
        schema = self._schema_name(values, secret)
        rows = self._fetch_rows(
            values.get("credential_id"),
            """
            SELECT COLUMN_NAME AS name, DATA_TYPE AS data_type, COLUMN_TYPE AS column_type,
                   IS_NULLABLE AS is_nullable, COLUMN_DEFAULT AS column_default, EXTRA AS extra
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s
            ORDER BY ORDINAL_POSITION
            """,
            (schema, table),
        )

        number_types = {
            "bigint", "decimal", "double", "float", "int", "integer", "mediumint",
            "numeric", "real", "smallint", "tinyint",
        }
        date_types = {"date", "datetime", "time", "timestamp"}
        columns: List[Dict[str, Any]] = []
        for row in rows:
            data_type = str(row["data_type"]).lower()
            column_type = str(row["column_type"]).lower()
            if data_type == "tinyint" and column_type.startswith("tinyint(1)"):
                widget = "checkbox"
            elif data_type in number_types:
                widget = "number"
            elif data_type in date_types:
                widget = "datetime"
            elif data_type == "json":
                widget = "json"
            else:
                widget = "text"
            has_default = row["column_default"] is not None or "auto_increment" in str(row["extra"])
            columns.append(
                {
                    "label": str(row["name"]),
                    "value": str(row["name"]),
                    "name": str(row["name"]),
                    "type": data_type,
                    "widget": widget,
                    "required": row["is_nullable"] == "NO" and not has_default,
                    "hasDefault": has_default,
                }
            )
        return columns

    def _table_columns(self, inputs: Mapping[str, Any]) -> List[str]:
        try:
            columns = [option["value"] for option in self.load_columns(dict(inputs))]
        except Exception as exc:
            logger.warning("Could not load MySQL table columns for automatic mapping: %s", exc)
            raise ValueError(
                "MySQL table columns could not be loaded for automatic mapping."
            ) from exc
        if not columns:
            raise ValueError(
                "The selected MySQL table has no accessible columns for automatic mapping."
            )
        return columns

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        import pymysql

        started_at = time.time()
        configuration = {**_flatten_node_configuration(self.user_data), **inputs}
        operation = str(configuration.get("operation") or "select").lower()
        if operation not in SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported MySQL operation: {operation}")

        continue_on_error = _as_bool(configuration.get("continue_on_error"))
        read_only = _as_bool(configuration.get("read_only"))
        use_transaction = _as_bool(configuration.get("use_transaction", True))
        results: List[QueryResult] = []
        errors: List[Dict[str, Any]] = []
        attempted_rows = 0

        try:
            if read_only and operation in WRITE_OPERATIONS:
                self._guard_read_only(operation)

            secret = _credential_secret(self, configuration.get("credential_id"))
            connected = _connected_payload(
                _unwrap_connected_value((connected_nodes or {}).get("input"))
            )
            specs = self._build_queries(operation, configuration, connected)
            if operation in {"insert", "upsert", "update"}:
                attempted_rows = len(specs)

            if read_only and operation == "execute_query":
                self._guard_read_only(operation, specs[0].sql)

            with mysql_connection(secret, configuration) as connection:
                if read_only:
                    with connection.cursor() as cursor:
                        cursor.execute("SET TRANSACTION READ ONLY")

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

            rows = [row for result in results for row in result.rows]
            affected_rows = sum(max(0, result.affected_rows) for result in results)
            written_rows = affected_rows if operation in WRITE_OPERATIONS else 0
            last_insert_id = next(
                (result.last_insert_id for result in reversed(results) if result.last_insert_id),
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
                "truncated": any(result.truncated for result in results),
                "errors": errors,
            }
            if _as_bool(configuration.get("detailed_output")):
                output["details"] = [
                    {
                        "sql": result.sql,
                        "item_index": result.item_index,
                        "rows": result.rows,
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
            logger.error("MySQLNode failed operation=%s: %s", operation, message)
            if not continue_on_error:
                if isinstance(exc, pymysql.MySQLError):
                    raise ValueError(f"MySQL error: {message}") from exc
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

    def _build_queries(self, operation: str, inputs: Mapping[str, Any], connected: Any) -> List[QuerySpec]:
        if operation == "execute_query":
            return self._execute_query_specs(inputs, connected)

        table = self._table_identifier(inputs)
        if operation == "truncate":
            return [QuerySpec(f"TRUNCATE TABLE {table}")]

        if operation == "delete":
            command = str(inputs.get("delete_command") or "delete").lower()
            if command == "truncate":
                return [QuerySpec(f"TRUNCATE TABLE {table}")]
            if command != "delete":
                raise ValueError("Delete command must be delete or truncate.")
            where_sql, where_values = self._where_clause(inputs)
            if not where_sql:
                raise ValueError(
                    "Delete requires at least one filter condition. Use Truncate when the "
                    "explicit intention is to empty the whole table."
                )
            return [QuerySpec(f"DELETE FROM {table}{where_sql}", where_values)]

        if operation == "select":
            columns = self._columns(inputs.get("columns"))
            distinct = " DISTINCT" if _as_bool(inputs.get("select_distinct")) else ""
            where_sql, values = self._where_clause(inputs)
            sort_sql = self._sort_clause(inputs)
            values = list(values)
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
                    raise ValueError(f"Limit must be between 1 and {_MAX_RESULT_ROWS}.")
            values.append(limit)
            return [
                QuerySpec(
                    f"SELECT{distinct} {columns} FROM {table}{where_sql}{sort_sql} LIMIT %s",
                    values,
                )
            ]

        records = self._records(inputs, connected)
        replace_empty = _as_bool(inputs.get("replace_empty_with_null"))
        if replace_empty:
            records = [{key: (None if value == "" else value) for key, value in row.items()} for row in records]

        if operation == "insert":
            return self._insert_specs(table, records, inputs)
        if operation == "upsert":
            return self._upsert_specs(table, records, inputs)
        return self._update_specs(table, records, inputs)

    def _execute_query_specs(self, inputs: Mapping[str, Any], connected: Any) -> List[QuerySpec]:
        query = str(inputs.get("query") or "").strip()
        if not query:
            raise ValueError("SQL Query is required.")
        self._ensure_single_statement(query)
        raw_parameters = _parse_json(inputs.get("query_parameters"), default=[], field_name="Query Parameters")
        parameter_sets: List[Any]
        if raw_parameters in ([], {}) and connected is not None:
            parameter_sets = connected if isinstance(connected, list) else [connected]
        else:
            parameter_sets = [raw_parameters]
        specs = []
        for index, parameters in enumerate(parameter_sets):
            prepared, values = self._prepare_query(query, parameters)
            specs.append(QuerySpec(prepared, values, index))
        return specs

    def _records(self, inputs: Mapping[str, Any], connected: Any) -> List[Dict[str, Any]]:
        automatic = str(inputs.get("mapping_mode") or "manual") == "auto"
        if automatic:
            value = self._unwrap_payload(connected)
        else:
            value = _parse_json(inputs.get("data"), default={}, field_name="Values to Send")
        records = value if isinstance(value, list) else [value]
        if not records or not all(isinstance(record, dict) and record for record in records):
            if automatic:
                raise ValueError(
                    "Automatic mapping requires an input connection that produces an object "
                    "or a list of objects."
                )
            raise ValueError("Values to Send must contain a non-empty object or array of objects.")

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
            cleaned.append({self._identifier_name(key, "Column"): value for key, value in row.items()})

        self._common_columns(cleaned)
        return cleaned

    def _insert_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        columns = self._common_columns(records)
        priority = str(inputs.get("priority") or "none")
        if priority not in {"none", "LOW_PRIORITY", "HIGH_PRIORITY"}:
            raise ValueError("Insert Priority must be Default, Low Priority, or High Priority.")
        priority_sql = f" {priority}" if priority in {"LOW_PRIORITY", "HIGH_PRIORITY"} else ""
        ignore_sql = " IGNORE" if _as_bool(inputs.get("skip_on_conflict")) else ""
        column_sql = ", ".join(self._identifier(column) for column in columns)
        placeholder = ", ".join("%s" for _ in columns)
        sql = f"INSERT{priority_sql}{ignore_sql} INTO {table} ({column_sql}) VALUES ({placeholder})"
        return [QuerySpec(sql, [record[column] for column in columns], index) for index, record in enumerate(records)]

    def _upsert_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        match_columns = self._split_columns(inputs.get("match_columns"))
        if not match_columns:
            raise ValueError("Insert or Update requires at least one match column.")
        specs = []
        for index, record in enumerate(records):
            row = dict(record)
            missing = [column for column in match_columns if column not in row]
            if missing:
                raise ValueError(
                    f"Incoming row {index + 1} is missing match column(s): {', '.join(missing)}."
                )
            columns = list(row)
            update_columns = [column for column in columns if column not in match_columns]
            if not update_columns:
                raise ValueError("Insert or Update needs at least one non-match column.")
            column_sql = ", ".join(self._identifier(column) for column in columns)
            placeholders = ", ".join("%s" for _ in columns)
            updates = ", ".join(f"{self._identifier(column)} = %s" for column in update_columns)
            values = [row[column] for column in columns] + [row[column] for column in update_columns]
            specs.append(
                QuerySpec(
                    f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {updates}",
                    values,
                    index,
                )
            )
        return specs

    def _update_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        match_columns = self._split_columns(inputs.get("match_columns"))
        filter_sql, filter_values = self._where_clause(inputs)
        if not match_columns and not filter_sql:
            raise ValueError(
                "Update requires at least one match column or filter condition. A filterless "
                "update could overwrite every row in the table."
            )
        if len(records) > 1 and not match_columns:
            raise ValueError("Updating multiple input rows requires Columns to Match On.")

        specs = []
        for index, record in enumerate(records):
            row = dict(record)
            missing = [column for column in match_columns if column not in row]
            if missing:
                raise ValueError(
                    f"Incoming row {index + 1} is missing match column(s): {', '.join(missing)}."
                )
            update_columns = [column for column in row if column not in match_columns]
            if not update_columns:
                raise ValueError("Update needs at least one non-match column.")
            assignments = ", ".join(f"{self._identifier(column)} = %s" for column in update_columns)
            match_sql = " AND ".join(
                f"{self._identifier(column)} = %s" for column in match_columns
            )
            filter_part = (
                f"({filter_sql.removeprefix(' WHERE ')})" if filter_sql else ""
            )
            where_parts = [part for part in (match_sql, filter_part) if part]
            values = [row[column] for column in update_columns]
            values.extend(row[column] for column in match_columns)
            values.extend(filter_values)
            specs.append(
                QuerySpec(
                    f"UPDATE {table} SET {assignments} WHERE {' AND '.join(where_parts)}",
                    values,
                    index,
                )
            )
        return specs

    def _execute_spec(self, connection: Any, spec: QuerySpec, inputs: Mapping[str, Any]) -> List[QueryResult]:
        output: List[QueryResult] = []
        with connection.cursor() as cursor:
            if spec.parameters in (None, [], (), {}):
                cursor.execute(spec.sql)
            else:
                cursor.execute(spec.sql, spec.parameters)
            while True:
                raw_rows = list(cursor.fetchmany(_MAX_RESULT_ROWS + 1)) if cursor.description else []
                truncated = len(raw_rows) > _MAX_RESULT_ROWS
                rows = raw_rows[:_MAX_RESULT_ROWS]
                output.append(
                    QueryResult(
                        sql=spec.sql,
                        rows=[self._serializable_row(row, inputs) for row in rows],
                        affected_rows=int(cursor.rowcount or 0),
                        last_insert_id=int(cursor.lastrowid) if cursor.lastrowid else None,
                        item_index=spec.item_index,
                        truncated=truncated,
                    )
                )
                if not cursor.nextset():
                    break
        return output

    @classmethod
    def _prepare_query(cls, query: str, parameters: Any) -> tuple[str, Sequence[Any] | Mapping[str, Any]]:
        if isinstance(parameters, dict):
            if _POSITIONAL_PARAMETER.search(query):
                raise ValueError(
                    "$1 parameters require a JSON array; use %(name)s placeholders for an object."
                )
            return query, parameters
        if not isinstance(parameters, (list, tuple)):
            raise ValueError("Query Parameters must be a JSON array or object.")

        output: List[str] = []
        values: List[Any] = []
        referenced: Set[int] = set()
        index = 0
        while index < len(query):
            char = query[index]

            if query.startswith("--", index) or char == "#":
                end = query.find("\n", index + 1)
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

            if char in {"'", '"', "`"}:
                quote = char
                end = index + 1
                while end < len(query):
                    if query[end] == "\\":
                        end += 2
                        continue
                    if query[end] == quote:
                        if end + 1 < len(query) and query[end + 1] == quote:
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
                            f"The query references ${match.group(1)} but only "
                            f"{len(parameters)} parameter(s) were supplied."
                        )
                    if match.group(2):
                        output.append(cls._qualified_identifier(parameters[parameter_index]))
                    else:
                        output.append("%s")
                        values.append(parameters[parameter_index])
                    referenced.add(parameter_index)
                    index = match.end()
                    continue

            output.append(char)
            index += 1

        unused = [position + 1 for position in range(len(parameters)) if position not in referenced]
        if unused:
            labels = ", ".join(f"${position}" for position in unused)
            raise ValueError(f"Query Parameters contains unused value(s): {labels}.")
        return "".join(output), values

    @staticmethod
    def _ensure_single_statement(query: str) -> None:
        """Reject multiple SQL statements while allowing a trailing semicolon."""
        segments: List[List[str]] = [[]]
        index = 0
        while index < len(query):
            char = query[index]
            if query.startswith("--", index) or char == "#":
                end = query.find("\n", index + 1)
                index = len(query) if end == -1 else end + 1
                continue
            if query.startswith("/*", index):
                end = query.find("*/", index + 2)
                index = len(query) if end == -1 else end + 2
                continue
            if char in {"'", '"', "`"}:
                quote = char
                segments[-1].append(char)
                index += 1
                while index < len(query):
                    segments[-1].append(query[index])
                    if query[index] == "\\" and index + 1 < len(query):
                        index += 1
                        segments[-1].append(query[index])
                    elif query[index] == quote:
                        if index + 1 < len(query) and query[index + 1] == quote:
                            index += 1
                            segments[-1].append(query[index])
                        else:
                            index += 1
                            break
                    index += 1
                continue
            if char == ";":
                segments.append([])
            else:
                segments[-1].append(char)
            index += 1

        statements = ["".join(segment).strip() for segment in segments if "".join(segment).strip()]
        if len(statements) != 1:
            raise ValueError("Exactly one SQL statement is required per execution.")

    @classmethod
    def _collect_conditions(cls, inputs: Mapping[str, Any]) -> List[Dict[str, Any]]:
        conditions: List[Dict[str, Any]] = []
        column = str(inputs.get("filter_column") or "").strip()
        if column:
            operator = str(inputs.get("filter_operator") or "equals").lower()
            condition: Dict[str, Any] = {"column": column, "operator": operator}
            if operator not in {"is_null", "is_not_null"}:
                condition["value"] = inputs.get("filter_value")
            conditions.append(condition)

        extra = _parse_json(
            inputs.get("where_conditions"), default=[], field_name="Extra Conditions"
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
    def _where_clause(cls, inputs: Mapping[str, Any]) -> tuple[str, List[Any]]:
        raw = cls._collect_conditions(inputs)
        combine = str(inputs.get("combine_conditions") or "AND").upper()
        if combine not in {"AND", "OR"}:
            raise ValueError("Combine Conditions must be AND or OR.")
        clauses: List[str] = []
        values: List[Any] = []
        for index, condition in enumerate(raw):
            if not isinstance(condition, dict) or not condition.get("column"):
                raise ValueError(f"Condition {index + 1} must contain a column.")
            operator_key = str(condition.get("operator") or "equals").lower()
            if operator_key not in CONDITION_OPERATORS:
                raise ValueError(f"Unsupported condition operator: {operator_key}")
            operator_sql = CONDITION_OPERATORS[operator_key]
            identifier = cls._identifier(condition["column"])
            if operator_key in {"is_null", "is_not_null"}:
                clause = f"{identifier} {operator_sql}"
            else:
                value = condition.get("value")
                if operator_key in {"like", "ilike"} and isinstance(value, str):
                    if "%" not in value and "_" not in value:
                        value = f"%{value}%"
                if operator_key == "ilike":
                    clause = f"LOWER(CAST({identifier} AS CHAR)) LIKE LOWER(%s)"
                elif operator_key in {"equals", "not_equals"} and isinstance(value, str):
                    clause = f"LOWER(CAST({identifier} AS CHAR)) {operator_sql} LOWER(%s)"
                else:
                    clause = f"{identifier} {operator_sql} %s"
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
    def _error_item(cls, error: Exception, item_index: int) -> Dict[str, Any]:
        return {
            "success": False,
            "message": cls._database_error(error),
            "error_type": type(error).__name__,
            "item_index": item_index,
        }

    @staticmethod
    def _database_error(error: Exception) -> str:
        code = error.args[0] if getattr(error, "args", None) else None
        messages = {
            1045: "MySQL rejected the configured credentials.",
            1049: "The configured MySQL database does not exist.",
            1054: "A referenced column does not exist.",
            1062: "The statement conflicts with an existing unique value.",
            1142: "The MySQL user does not have permission for this operation.",
            1146: "A referenced table does not exist or is not accessible.",
            1205: "The statement exceeded the lock wait timeout.",
            1213: "The statement was rolled back because of a deadlock.",
            1317: "The statement was interrupted.",
            2003: "Could not connect to the MySQL server.",
        }
        if code in messages:
            return messages[code]
        message = str(error).strip() or "The MySQL operation failed."
        return _SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", message)[:500]

    @staticmethod
    def _serializable_row(row: Mapping[str, Any], inputs: Mapping[str, Any]) -> Dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return str(value) if _as_bool(inputs.get("numbers_as_text")) else float(value)
            if isinstance(value, int) and abs(value) > _MAX_SAFE_INTEGER and _as_bool(inputs.get("numbers_as_text")):
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
        records = list(records)
        columns = list(records[0])
        expected = set(columns)
        for record in records[1:]:
            if set(record) != expected:
                raise ValueError("All rows in an insert batch must contain the same columns.")
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
        return [cls._identifier_name(part, "Column") for part in parts if str(part).strip()]

    @classmethod
    def _columns(cls, value: Any) -> str:
        columns = cls._split_columns(value)
        return ", ".join(cls._identifier(column) for column in columns) if columns else "*"

    @staticmethod
    def _identifier_name(value: Any, label: str) -> str:
        identifier = str(value or "").strip()
        if not identifier or "\x00" in identifier:
            raise ValueError(f"{label} is required and cannot contain a null byte.")
        if len(identifier.encode("utf-8")) > 64:
            raise ValueError(f"{label} cannot exceed 64 bytes in MySQL.")
        return identifier

    @classmethod
    def _identifier(cls, value: Any) -> str:
        identifier = cls._identifier_name(value, "Identifier")
        return f"`{identifier.replace('`', '``')}`"

    @classmethod
    def _table_identifier(cls, inputs: Mapping[str, Any]) -> str:
        """Qualify the table with the selected schema."""
        table = str(inputs.get("table_name") or "").strip()
        schema = str(inputs.get("schema_name") or "").strip()
        if schema:
            return f"{cls._identifier(schema)}.{cls._identifier(table)}"
        return cls._qualified_identifier(table)

    @classmethod
    def _qualified_identifier(cls, value: Any) -> str:
        parts = [part.strip() for part in str(value).split(".")]
        if not parts or any(not part for part in parts) or len(parts) > 2:
            raise ValueError("A MySQL identifier may contain a table, or database and table.")
        return ".".join(cls._identifier(part) for part in parts)

    ENVELOPE_KEYS = ("webhook_data", "payload", "body", "json", "data", "result", "rows")

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

    @staticmethod
    def _guard_read_only(operation: str, query: str = "") -> None:
        if operation in WRITE_OPERATIONS:
            raise ValueError(
                f"Read Only is enabled, so the '{operation}' operation is not allowed."
            )
        if operation != "execute_query" or not query:
            return
        first_word = re.split(r"\s+", query.lstrip(), maxsplit=1)[0].lower()
        if first_word in WRITE_KEYWORDS:
            raise ValueError(
                f"Read Only is enabled, so a statement starting with "
                f"'{first_word.upper()}' is not allowed."
            )
