"""n8n-compatible MySQL database action node.

The UI in KAI-Flow deliberately uses JSON editors for repeatable collections
(filters, sort rules, and column mappings).  The execution semantics mirror the
six database operations and options exposed by n8n's MySQL v2 node. Agent
access intentionally lives in the separate MySQL Tool provider node.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import io
import json
import os
import re
import ssl
import tempfile
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Sequence

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProcessorNode,
)


_SUPPORTED_OPERATIONS = {
    "delete_table",
    "execute_query",
    "insert",
    "upsert",
    "select",
    "update",
}
_SUPPORTED_CONDITIONS = {"=", "!=", "LIKE", "LIKE BINARY", ">", "<", ">=", "<=", "IS NULL", "IS NOT NULL"}
_POSITIONAL_PARAMETER = re.compile(r"\$(\d+)(:name)?")
_MAX_SAFE_INTEGER = 9_007_199_254_740_991


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


def _load_private_key(value: str, passphrase: str | None = None):
    import paramiko

    password = passphrase or None
    errors: List[Exception] = []
    for key_type in (paramiko.RSAKey, paramiko.ECDSAKey, paramiko.Ed25519Key):
        try:
            return key_type.from_private_key(io.StringIO(value), password=password)
        except Exception as exc:  # pragma: no cover - depends on the supplied key type
            errors.append(exc)
    raise ValueError("SSH private key could not be parsed.") from errors[-1]


@contextlib.contextmanager
def mysql_connection(secret: Mapping[str, Any], options: Mapping[str, Any] | None = None) -> Iterator[Any]:
    """Open a direct, TLS, or SSH-tunnelled PyMySQL connection."""
    import pymysql
    from pymysql.constants import CLIENT
    from pymysql.cursors import DictCursor

    options = options or {}
    host = str(secret.get("host") or "localhost")
    port = int(secret.get("port") or 3306)
    tunnel = None

    if _as_bool(secret.get("ssh_tunnel")):
        from sshtunnel import SSHTunnelForwarder

        ssh_host = str(secret.get("ssh_host") or "").strip()
        ssh_user = str(secret.get("ssh_username") or "").strip()
        if not ssh_host or not ssh_user:
            raise ValueError("SSH host and username are required when SSH tunneling is enabled.")
        tunnel_kwargs: Dict[str, Any] = {
            "ssh_address_or_host": (ssh_host, int(secret.get("ssh_port") or 22)),
            "ssh_username": ssh_user,
            "remote_bind_address": (host, port),
            "local_bind_address": ("127.0.0.1", 0),
        }
        if str(secret.get("ssh_authenticate_with") or "password") == "private_key":
            key_value = str(secret.get("ssh_private_key") or "").strip()
            if not key_value:
                raise ValueError("An SSH private key is required.")
            tunnel_kwargs["ssh_pkey"] = _load_private_key(
                key_value,
                str(secret.get("ssh_passphrase") or "") or None,
            )
        else:
            tunnel_kwargs["ssh_password"] = str(secret.get("ssh_password") or "")
        tunnel = SSHTunnelForwarder(**tunnel_kwargs)
        tunnel.start()
        host, port = "127.0.0.1", int(tunnel.local_bind_port)

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
        if tunnel is not None:
            tunnel.stop()
        for path in temporary_certificate_paths:
            with contextlib.suppress(OSError):
                os.unlink(path)
        raise

    timeout_ms = options.get("connection_timeout_ms") or secret.get("connect_timeout") or 10_000
    connection = None
    try:
        connection = pymysql.connect(
            host=host,
            port=port,
            database=str(secret.get("database") or ""),
            user=str(secret.get("username") or secret.get("user") or ""),
            password=str(secret.get("password") or ""),
            charset=str(secret.get("charset") or "utf8mb4"),
            connect_timeout=max(1, int(timeout_ms) // 1000),
            cursorclass=DictCursor,
            autocommit=False,
            ssl=ssl_options,
            client_flag=CLIENT.MULTI_STATEMENTS,
        )
        yield connection
    finally:
        if connection is not None:
            connection.close()
        if tunnel is not None:
            tunnel.stop()
        for path in temporary_certificate_paths:
            with contextlib.suppress(OSError):
                os.unlink(path)


class MySQLNode(ProcessorNode):
    """Read and mutate MySQL data with n8n-compatible operations."""

    def __init__(self):
        super().__init__()
        operation_options = [
            {"label": "Delete table or rows", "value": "delete_table"},
            {"label": "Execute a SQL query", "value": "execute_query"},
            {"label": "Insert rows in a table", "value": "insert"},
            {"label": "Insert or update rows in a table", "value": "upsert"},
            {"label": "Select rows from a table", "value": "select"},
            {"label": "Update rows in a table", "value": "update"},
        ]
        table_operations = ["delete_table", "insert", "upsert", "select", "update"]
        mapped_operations = ["insert", "upsert", "update"]
        filter_operations = ["delete_table", "select"]
        self._metadata = {
            "name": "MySQL",
            "display_name": "MySQL",
            "description": "Get, add, update, and delete MySQL data with the complete n8n MySQL action set.",
            "category": "Integration",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "mysql", "path": "icons/mysql.svg", "alt": "MySQL"},
            "colors": ["cyan-700", "blue-800"],
            "version": "3.0.0",
            "documentation_url": "https://docs.n8n.io/integrations/builtin/app-nodes/n8n-nodes-base.mysql/",
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
                    type="any",
                    description="Selected rows or MySQL execution metadata.",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    description="MySQL connection credential.",
                    serviceType="mysql",
                    required=True,
                ),
                NodeProperty(
                    name="operation",
                    displayName="Operation",
                    type=NodePropertyType.SELECT,
                    description="Choose the database action this workflow node will execute.",
                    default="insert",
                    options=operation_options,
                    required=True,
                ),
                NodeProperty(
                    name="table",
                    displayName="Table",
                    type=NodePropertyType.TEXT,
                    description="Table name, optionally qualified with a database name.",
                    placeholder="customers or kai_demo.customers",
                    displayOptions={"show": {"operation": table_operations}},
                    required=True,
                ),
                NodeProperty(
                    name="delete_command",
                    displayName="Command",
                    type=NodePropertyType.SELECT,
                    description="TRUNCATE keeps the structure, DELETE can filter rows, and DROP removes the table.",
                    default="truncate",
                    options=[
                        {"label": "Truncate", "value": "truncate"},
                        {"label": "Delete", "value": "delete"},
                        {"label": "Drop", "value": "drop"},
                    ],
                    displayOptions={"show": {"operation": "delete_table"}},
                    required=True,
                ),
                NodeProperty(
                    name="query",
                    displayName="SQL Query",
                    type=NodePropertyType.TEXT_AREA,
                    description="SQL to run. Use $1, $2, ... for values and $1:name for identifiers.",
                    placeholder="SELECT id, name FROM customers WHERE status = $1",
                    rows=8,
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=True,
                ),
                NodeProperty(
                    name="query_parameters",
                    displayName="Query Parameters",
                    type=NodePropertyType.JSON_EDITOR,
                    description="JSON array or object of parameter values. Incoming data is used when this is empty.",
                    default="[]",
                    displayOptions={"show": {"operation": "execute_query"}},
                    required=False,
                ),
                NodeProperty(
                    name="data_mode",
                    displayName="Data Mode",
                    type=NodePropertyType.SELECT,
                    description="Automatically map incoming property names or define values below.",
                    default="auto_map",
                    options=[
                        {"label": "Auto-map input data to columns", "value": "auto_map"},
                        {"label": "Map each column manually", "value": "manual"},
                    ],
                    displayOptions={"show": {"operation": mapped_operations}},
                    required=True,
                ),
                NodeProperty(
                    name="values",
                    displayName="Values to Send",
                    type=NodePropertyType.JSON_EDITOR,
                    description="A JSON object or array of objects containing column/value pairs.",
                    default="{}",
                    displayOptions={"show": {"operation": mapped_operations, "data_mode": "manual"}},
                    required=True,
                ),
                NodeProperty(
                    name="match_column",
                    displayName="Column to Match On",
                    type=NodePropertyType.TEXT,
                    description="Unique column used to match the row. It is not changed during update.",
                    placeholder="email",
                    displayOptions={"show": {"operation": ["upsert", "update"]}},
                    required=True,
                ),
                NodeProperty(
                    name="match_value",
                    displayName="Value of Column to Match On",
                    type=NodePropertyType.TEXT,
                    description="Match value used in manual mapping mode.",
                    displayOptions={"show": {"operation": ["upsert", "update"], "data_mode": "manual"}},
                    required=True,
                ),
                NodeProperty(
                    name="where",
                    displayName="Select Rows",
                    type=NodePropertyType.JSON_EDITOR,
                    description=(
                        "JSON condition array, for example "
                        '[{"column":"status","condition":"=","value":"active"}]. '
                        "Supported operators: =, !=, LIKE, >, <, >=, <=, IS NULL, IS NOT NULL."
                    ),
                    default="[]",
                    displayOptions={"show": {"operation": filter_operations}},
                    required=False,
                ),
                NodeProperty(
                    name="combine_conditions",
                    displayName="Combine Conditions",
                    type=NodePropertyType.SELECT,
                    description="Combine Select Rows conditions with AND or OR.",
                    default="AND",
                    options=[{"label": "AND", "value": "AND"}, {"label": "OR", "value": "OR"}],
                    displayOptions={"show": {"operation": filter_operations}},
                    required=True,
                ),
                NodeProperty(
                    name="return_all",
                    displayName="Return All",
                    type=NodePropertyType.CHECKBOX,
                    description="Return every matching row instead of applying a limit.",
                    default=False,
                    displayOptions={"show": {"operation": "select"}},
                    required=True,
                ),
                NodeProperty(
                    name="limit",
                    displayName="Limit",
                    type=NodePropertyType.NUMBER,
                    description="Maximum rows to return when Return All is disabled.",
                    default=50,
                    min=1,
                    max=1_000_000,
                    displayOptions={"show": {"operation": "select", "return_all": False}},
                    required=True,
                ),
                NodeProperty(
                    name="output_columns",
                    displayName="Output Columns",
                    type=NodePropertyType.TEXT,
                    description="Comma-separated columns to return, or * for every column.",
                    default="*",
                    displayOptions={"show": {"operation": "select"}},
                    required=True,
                ),
                NodeProperty(
                    name="sort",
                    displayName="Sort",
                    type=NodePropertyType.JSON_EDITOR,
                    description='JSON sort rules, for example [{"column":"created_at","direction":"DESC"}].',
                    default="[]",
                    displayOptions={"show": {"operation": "select"}},
                    required=False,
                ),
                NodeProperty(
                    name="query_batching",
                    displayName="Query Batching",
                    type=NodePropertyType.SELECT,
                    description="Run input items as one batch, independently, or in a transaction.",
                    default="single",
                    options=[
                        {"label": "Single Query", "value": "single"},
                        {"label": "Independent", "value": "independent"},
                        {"label": "Transaction", "value": "transaction"},
                    ],
                    tabName="options",
                    required=False,
                ),
                NodeProperty(
                    name="connection_timeout_ms",
                    displayName="Connection Timeout (ms)",
                    type=NodePropertyType.NUMBER,
                    description="Time reserved for opening the database connection.",
                    default=30_000,
                    min=1,
                    tabName="options",
                    required=False,
                ),
                NodeProperty(
                    name="connection_limit",
                    displayName="Connections Limit",
                    type=NodePropertyType.NUMBER,
                    description="Maximum connections reserved for MySQL work by this node configuration.",
                    default=10,
                    min=1,
                    max=100,
                    tabName="options",
                    required=False,
                ),
                NodeProperty(
                    name="replace_empty_strings",
                    displayName="Replace Empty Strings with NULL",
                    type=NodePropertyType.CHECKBOX,
                    description="Convert empty incoming strings to SQL NULL values.",
                    default=False,
                    tabName="options",
                    displayOptions={"show": {"operation": ["insert", "update", "upsert", "execute_query"]}},
                    required=False,
                ),
                NodeProperty(
                    name="select_distinct",
                    displayName="Select Distinct",
                    type=NodePropertyType.CHECKBOX,
                    description="Remove duplicate rows from Select output.",
                    default=False,
                    tabName="options",
                    displayOptions={"show": {"operation": "select"}},
                    required=False,
                ),
                NodeProperty(
                    name="large_numbers_output",
                    displayName="Output Large-Format Numbers As",
                    type=NodePropertyType.SELECT,
                    description="Return BIGINT values as text to avoid precision loss or as numbers.",
                    default="text",
                    options=[{"label": "Text", "value": "text"}, {"label": "Numbers", "value": "numbers"}],
                    tabName="options",
                    displayOptions={"show": {"operation": ["select", "execute_query"]}},
                    required=False,
                ),
                NodeProperty(
                    name="decimal_numbers",
                    displayName="Output Decimals as Numbers",
                    type=NodePropertyType.CHECKBOX,
                    description="Return DECIMAL values as numbers instead of text.",
                    default=False,
                    tabName="options",
                    displayOptions={"show": {"operation": ["select", "execute_query"]}},
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
                    tabName="options",
                    displayOptions={"show": {"operation": "insert"}},
                    required=False,
                ),
                NodeProperty(
                    name="skip_on_conflict",
                    displayName="Skip on Conflict",
                    type=NodePropertyType.CHECKBOX,
                    description="Use INSERT IGNORE for rows that violate a unique constraint.",
                    default=False,
                    tabName="options",
                    displayOptions={"show": {"operation": "insert"}},
                    required=False,
                ),
                NodeProperty(
                    name="detailed_output",
                    displayName="Output Query Execution Details",
                    type=NodePropertyType.CHECKBOX,
                    description="Include SQL, item index, row count, and insert ID for each statement.",
                    default=False,
                    tabName="options",
                    required=False,
                ),
                NodeProperty(
                    name="continue_on_fail",
                    displayName="Continue on Fail",
                    type=NodePropertyType.CHECKBOX,
                    description="Return an error item and continue with remaining independent queries.",
                    default=False,
                    tabName="options",
                    required=False,
                ),
            ],
            "examples": [
                {"operation": "select", "table": "customers", "where": [{"column": "status", "condition": "=", "value": "active"}]},
                {"operation": "execute_query", "query": "SELECT * FROM orders WHERE total >= $1", "query_parameters": [100]},
            ],
        }

    def get_required_packages(self) -> List[str]:
        return [
            "PyMySQL>=1.1.1,<2.0.0",
            "sshtunnel>=0.4.0,<1.0.0",
            "paramiko>=2.7.2,<4.0.0",
        ]

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        configuration = {**_flatten_node_configuration(self.user_data), **inputs}
        operation = str(configuration.get("operation") or "insert")
        if operation not in _SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported MySQL operation: {operation}")

        secret = _credential_secret(self, inputs.get("credential_id") or self.user_data.get("credential_id"))
        connected = _unwrap_connected_value((connected_nodes or {}).get("input"))
        specs = self._build_queries(operation, inputs, connected)
        mode = str(inputs.get("query_batching") or "single")
        if mode not in {"single", "independent", "transaction"}:
            raise ValueError("Query batching must be single, independent, or transaction.")

        results: List[QueryResult] = []
        errors: List[Dict[str, Any]] = []
        with mysql_connection(secret, inputs) as connection:
            if mode == "independent":
                for spec in specs:
                    try:
                        results.extend(self._execute_spec(connection, spec, inputs))
                        connection.commit()
                    except Exception as exc:
                        connection.rollback()
                        if not _as_bool(inputs.get("continue_on_fail")):
                            raise
                        errors.append(self._error_item(exc, spec.item_index))
            else:
                try:
                    for spec in specs:
                        results.extend(self._execute_spec(connection, spec, inputs))
                    connection.commit()
                except Exception:
                    connection.rollback()
                    raise

        rows = [row for result in results for row in result.rows]
        affected_rows = sum(max(0, result.affected_rows) for result in results)
        last_insert_id = next(
            (result.last_insert_id for result in reversed(results) if result.last_insert_id),
            None,
        )
        if _as_bool(inputs.get("detailed_output")):
            output: Any = [
                {
                    "sql": result.sql,
                    "item_index": result.item_index,
                    "data": result.rows if result.rows else {
                        "success": True,
                        "affected_rows": result.affected_rows,
                        "last_insert_id": result.last_insert_id,
                    },
                }
                for result in results
            ] + errors
        else:
            output = rows if rows else ({"success": not errors, "affected_rows": affected_rows, "last_insert_id": last_insert_id, "errors": errors})

        return {
            "output": output,
            "rows": rows,
            "row_count": len(rows),
            "affected_rows": affected_rows,
            "last_insert_id": last_insert_id,
            "operation": operation,
            "errors": errors,
        }

    def _build_queries(self, operation: str, inputs: Mapping[str, Any], connected: Any) -> List[QuerySpec]:
        if operation == "execute_query":
            return self._execute_query_specs(inputs, connected)

        table = self._qualified_identifier(inputs.get("table"))
        if operation == "delete_table":
            command = str(inputs.get("delete_command") or "truncate").lower()
            if command == "drop":
                return [QuerySpec(f"DROP TABLE IF EXISTS {table}")]
            if command == "truncate":
                return [QuerySpec(f"TRUNCATE TABLE {table}")]
            if command != "delete":
                raise ValueError("Delete command must be drop, truncate, or delete.")
            where_sql, where_values = self._where_clause(inputs)
            return [QuerySpec(f"DELETE FROM {table}{where_sql}", where_values)]

        if operation == "select":
            columns = self._columns(str(inputs.get("output_columns") or "*"))
            distinct = " DISTINCT" if _as_bool(inputs.get("select_distinct")) else ""
            where_sql, values = self._where_clause(inputs)
            sort_sql = self._sort_clause(inputs.get("sort"))
            limit_sql = ""
            if not _as_bool(inputs.get("return_all")):
                limit = max(1, int(inputs.get("limit") or 50))
                limit_sql = " LIMIT %s"
                values = [*values, limit]
            return [QuerySpec(f"SELECT{distinct} {columns} FROM {table}{where_sql}{sort_sql}{limit_sql}", values)]

        records = self._records(inputs, connected)
        if not records:
            raise ValueError("At least one input row is required.")
        replace_empty = _as_bool(inputs.get("replace_empty_strings"))
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
        raw_parameters = _parse_json(inputs.get("query_parameters"), default=[], field_name="Query Parameters")
        parameter_sets: List[Any]
        if raw_parameters in ([], {}) and connected is not None:
            parameter_sets = connected if isinstance(connected, list) else [connected]
        else:
            parameter_sets = [raw_parameters]
        specs = []
        for index, parameters in enumerate(parameter_sets):
            if _as_bool(inputs.get("replace_empty_strings")):
                if isinstance(parameters, list):
                    parameters = [None if value == "" else value for value in parameters]
                elif isinstance(parameters, dict):
                    parameters = {key: (None if value == "" else value) for key, value in parameters.items()}
            prepared, values = self._prepare_query(query, parameters)
            specs.append(QuerySpec(prepared, values, index))
        return specs

    def _records(self, inputs: Mapping[str, Any], connected: Any) -> List[Dict[str, Any]]:
        if str(inputs.get("data_mode") or "auto_map") == "manual":
            value = _parse_json(inputs.get("values"), default={}, field_name="Values to Send")
        else:
            value = connected
        if isinstance(value, dict) and "rows" in value and isinstance(value["rows"], list):
            value = value["rows"]
        records = value if isinstance(value, list) else [value]
        if not records or not all(isinstance(record, dict) and record for record in records):
            raise ValueError("Rows must be a JSON object or a non-empty array of objects.")
        return [dict(record) for record in records]

    def _insert_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        columns = self._common_columns(records)
        priority = str(inputs.get("priority") or "none")
        priority_sql = f" {priority}" if priority in {"LOW_PRIORITY", "HIGH_PRIORITY"} else ""
        ignore_sql = " IGNORE" if _as_bool(inputs.get("skip_on_conflict")) else ""
        column_sql = ", ".join(self._identifier(column) for column in columns)
        placeholder = ", ".join("%s" for _ in columns)
        sql = f"INSERT{priority_sql}{ignore_sql} INTO {table} ({column_sql}) VALUES ({placeholder})"
        return [QuerySpec(sql, [record[column] for column in columns], index) for index, record in enumerate(records)]

    def _upsert_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        match_column = str(inputs.get("match_column") or "").strip()
        if not match_column:
            raise ValueError("Column to Match On is required for Insert or Update.")
        manual = str(inputs.get("data_mode") or "auto_map") == "manual"
        specs = []
        for index, record in enumerate(records):
            row = dict(record)
            if manual:
                row[match_column] = inputs.get("match_value")
            if match_column not in row:
                raise ValueError(f"Incoming row {index} does not contain match column '{match_column}'.")
            columns = list(row)
            update_columns = [column for column in columns if column != match_column]
            if not update_columns:
                raise ValueError("Insert or Update needs at least one non-match column.")
            column_sql = ", ".join(self._identifier(column) for column in columns)
            placeholders = ", ".join("%s" for _ in columns)
            updates = ", ".join(f"{self._identifier(column)} = %s" for column in update_columns)
            values = [row[column] for column in columns] + [row[column] for column in update_columns]
            specs.append(QuerySpec(f"INSERT INTO {table} ({column_sql}) VALUES ({placeholders}) ON DUPLICATE KEY UPDATE {updates}", values, index))
        return specs

    def _update_specs(self, table: str, records: List[Dict[str, Any]], inputs: Mapping[str, Any]) -> List[QuerySpec]:
        match_column = str(inputs.get("match_column") or "").strip()
        if not match_column:
            raise ValueError("Column to Match On is required for Update.")
        manual = str(inputs.get("data_mode") or "auto_map") == "manual"
        specs = []
        for index, record in enumerate(records):
            row = dict(record)
            match_value = inputs.get("match_value") if manual else row.get(match_column)
            if not manual and match_column not in row:
                raise ValueError(f"Incoming row {index} does not contain match column '{match_column}'.")
            update_columns = [column for column in row if column != match_column]
            if not update_columns:
                raise ValueError("Update needs at least one non-match column.")
            assignments = ", ".join(f"{self._identifier(column)} = %s" for column in update_columns)
            values = [row[column] for column in update_columns] + [match_value]
            specs.append(QuerySpec(f"UPDATE {table} SET {assignments} WHERE {self._identifier(match_column)} = %s", values, index))
        return specs

    def _execute_spec(self, connection: Any, spec: QuerySpec, inputs: Mapping[str, Any]) -> List[QueryResult]:
        output: List[QueryResult] = []
        with connection.cursor() as cursor:
            if spec.parameters in (None, [], (), {}):
                cursor.execute(spec.sql)
            else:
                cursor.execute(spec.sql, spec.parameters)
            while True:
                rows = list(cursor.fetchall()) if cursor.description else []
                output.append(
                    QueryResult(
                        sql=spec.sql,
                        rows=[self._serializable_row(row, inputs) for row in rows],
                        affected_rows=int(cursor.rowcount or 0),
                        last_insert_id=int(cursor.lastrowid) if cursor.lastrowid else None,
                        item_index=spec.item_index,
                    )
                )
                if not cursor.nextset():
                    break
        return output

    @classmethod
    def _prepare_query(cls, query: str, parameters: Any) -> tuple[str, Sequence[Any] | Mapping[str, Any]]:
        if isinstance(parameters, dict):
            if _POSITIONAL_PARAMETER.search(query):
                raise ValueError("$1 parameters require a JSON array; use PyMySQL %(name)s placeholders for an object.")
            return query, parameters
        if not isinstance(parameters, (list, tuple)):
            raise ValueError("Query Parameters must be a JSON array or object.")

        values: List[Any] = []
        pieces: List[str] = []
        last = 0
        quote: str | None = None
        escaped = False
        index = 0
        while index < len(query):
            char = query[index]
            if escaped:
                escaped = False
                index += 1
                continue
            if char == "\\" and quote:
                escaped = True
                index += 1
                continue
            if char in {"'", '"', "`"}:
                quote = None if quote == char else (char if quote is None else quote)
                index += 1
                continue
            if char == "$" and quote is None:
                match = _POSITIONAL_PARAMETER.match(query, index)
                if match:
                    parameter_index = int(match.group(1)) - 1
                    if parameter_index < 0 or parameter_index >= len(parameters):
                        raise ValueError(f"Query references ${match.group(1)} but no replacement was supplied.")
                    pieces.append(query[last:index])
                    if match.group(2):
                        pieces.append(cls._qualified_identifier(parameters[parameter_index]))
                    else:
                        pieces.append("%s")
                        values.append(parameters[parameter_index])
                    index = match.end()
                    last = index
                    continue
            index += 1
        pieces.append(query[last:])
        prepared = "".join(pieces)
        return prepared, values if pieces[:-1] else list(parameters)

    @classmethod
    def _where_clause(cls, inputs: Mapping[str, Any]) -> tuple[str, List[Any]]:
        raw = _parse_json(inputs.get("where"), default=[], field_name="Select Rows")
        if isinstance(raw, dict):
            raw = [{"column": column, "condition": "IS NULL" if value is None else "=", "value": value} for column, value in raw.items()]
        if not isinstance(raw, list):
            raise ValueError("Select Rows must be a JSON array or object.")
        combine = str(inputs.get("combine_conditions") or "AND").upper()
        if combine not in {"AND", "OR"}:
            raise ValueError("Combine Conditions must be AND or OR.")
        clauses: List[str] = []
        values: List[Any] = []
        for index, condition in enumerate(raw):
            if not isinstance(condition, dict) or not condition.get("column"):
                raise ValueError(f"Select Rows entry {index + 1} must contain a column.")
            operator = str(condition.get("condition") or condition.get("operator") or "=").upper()
            if operator == "EQUAL":
                operator = "="
            if operator not in _SUPPORTED_CONDITIONS:
                raise ValueError(f"Unsupported Select Rows operator: {operator}")
            if operator in {">", "<", ">=", "<="}:
                try:
                    value: Any = float(condition.get("value"))
                except (TypeError, ValueError) as exc:
                    raise ValueError(f"Select Rows entry {index + 1} requires a numeric value.") from exc
            else:
                value = condition.get("value")
            clause = f"{cls._identifier(condition['column'])} {operator}"
            if operator not in {"IS NULL", "IS NOT NULL"}:
                clause += " %s"
                values.append(value)
            clauses.append(clause)
        return (f" WHERE {f' {combine} '.join(clauses)}" if clauses else ""), values

    @classmethod
    def _sort_clause(cls, value: Any) -> str:
        rules = _parse_json(value, default=[], field_name="Sort")
        if not isinstance(rules, list):
            raise ValueError("Sort must be a JSON array.")
        parts = []
        for index, rule in enumerate(rules):
            if not isinstance(rule, dict) or not rule.get("column"):
                raise ValueError(f"Sort entry {index + 1} must contain a column.")
            direction = str(rule.get("direction") or "ASC").upper()
            if direction not in {"ASC", "DESC"}:
                raise ValueError("Sort direction must be ASC or DESC.")
            parts.append(f"{cls._identifier(rule['column'])} {direction}")
        return f" ORDER BY {', '.join(parts)}" if parts else ""

    @staticmethod
    def _error_item(error: Exception, item_index: int) -> Dict[str, Any]:
        return {"success": False, "message": str(error), "error_type": type(error).__name__, "item_index": item_index}

    @staticmethod
    def _serializable_row(row: Mapping[str, Any], inputs: Mapping[str, Any]) -> Dict[str, Any]:
        def convert(value: Any) -> Any:
            if isinstance(value, Decimal):
                return float(value) if _as_bool(inputs.get("decimal_numbers")) else str(value)
            if isinstance(value, int) and abs(value) > _MAX_SAFE_INTEGER and str(inputs.get("large_numbers_output") or "text") == "text":
                return str(value)
            if isinstance(value, (dt.datetime, dt.date, dt.time)):
                return value.isoformat()
            if isinstance(value, (bytes, bytearray)):
                return bytes(value).decode("utf-8", errors="replace")
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
    def _columns(cls, value: str) -> str:
        if value.strip() == "*":
            return "*"
        columns = [column.strip() for column in value.split(",") if column.strip()]
        if not columns:
            raise ValueError("At least one output column is required.")
        return ", ".join(cls._qualified_identifier(column) for column in columns)

    @staticmethod
    def _identifier(value: Any) -> str:
        identifier = str(value).strip()
        if not identifier or "\x00" in identifier:
            raise ValueError("MySQL identifiers cannot be empty or contain a null byte.")
        return f"`{identifier.replace('`', '``')}`"

    @classmethod
    def _qualified_identifier(cls, value: Any) -> str:
        parts = [part.strip() for part in str(value).split(".")]
        if not parts or any(not part for part in parts) or len(parts) > 2:
            raise ValueError("A MySQL identifier may contain a table, or database and table.")
        return ".".join(cls._identifier(part) for part in parts)
