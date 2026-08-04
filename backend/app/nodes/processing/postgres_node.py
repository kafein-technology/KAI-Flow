"""
PostgreSQL Node
===============

Performs database operations against a PostgreSQL server: running raw SQL,
selecting rows, inserting, updating, upserting and deleting.

Design notes
------------
- Values are always passed as query parameters, never interpolated into the SQL
  string. This is what prevents SQL injection.
- Identifiers (schema, table, column names) cannot be parameterized by the
  driver, so they are validated and quoted through ``psycopg2.sql`` instead.
- Connections are opened per execution and always closed in a ``finally`` block.
"""

from __future__ import annotations

import re
import time
import uuid as uuid_module
import logging
from datetime import date, datetime, time as time_type, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set, Tuple

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor, execute_values

from ..base import (
    ProcessorNode,
    NodeInput,
    NodeOutput,
    NodeType,
    NodeProperty,
    NodePropertyType,
    NodePosition,
)

logger = logging.getLogger(__name__)

# Identifiers must be plain names. Anything else is rejected before it reaches
# the database, so a crafted table name cannot break out of its context.
IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Operations that change data. Used by read-only mode.
WRITE_OPERATIONS = {"insert", "update", "upsert", "delete"}

# Statements that change data or structure. A statement starting with any of
# these is refused while read-only mode is on.
WRITE_KEYWORDS = {
    "insert", "update", "delete", "truncate", "drop", "create", "alter",
    "grant", "revoke", "comment", "merge", "copy", "vacuum", "reindex",
    "refresh", "call", "do",
}

# Comparison operators exposed in the condition builder, mapped to SQL.
# Equality on text ignores case, so a filter written in lower case still finds
# rows stored with capitals.
CASE_FOLDED_OPERATORS = {"equals", "not_equals"}

CONDITION_OPERATORS = {
    "equals": "=",
    "not_equals": "!=",
    "greater_than": ">",
    "greater_or_equal": ">=",
    "less_than": "<",
    "less_or_equal": "<=",
    "like": "LIKE",
    "ilike": "ILIKE",
    "is_null": "IS NULL",
    "is_not_null": "IS NOT NULL",
}


class PostgresNode(ProcessorNode):
    """Runs SQL statements and table operations against a PostgreSQL database."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "PostgresNode",
            "display_name": "PostgreSQL",
            "description": (
                "Run queries and manage rows in a PostgreSQL database. Supports raw SQL, "
                "select, insert, update, upsert and delete with parameterized values."
            ),
            "category": "Databases",
            "node_type": NodeType.PROCESSOR,
            "icon": {
                "name": "postgresql_vectorstore",
                "path": "icons/postgresql_vectorstore.svg",
                "alt": "PostgreSQL",
            },
            "colors": ["indigo-500", "purple-600"],
            "inputs": [
                NodeInput(
                    name="input",
                    type="any",
                    description="Incoming data. Used as row values when the Data field is left empty.",
                    is_connection=True,
                    direction=NodePosition.LEFT,
                    required=False,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="dict",
                    description=(
                        "Result of the operation: the rows it returned, how many were affected "
                        "and how long it took."
                    ),
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
                # ----------------------------------------------------------
                # Basic
                # ----------------------------------------------------------
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    description="PostgreSQL connection to use.",
                    placeholder="Select Credential",
                    required=True,
                    serviceType="postgresql_vectorstore",
                    tabName="basic",
                ),
                NodeProperty(
                    name="operation",
                    displayName="Operation",
                    type=NodePropertyType.SELECT,
                    description="The database operation to perform.",
                    required=True,
                    default="select",
                    options=[
                        {"label": "Execute Query", "value": "execute_query"},
                        {"label": "Select", "value": "select"},
                        {"label": "Insert", "value": "insert"},
                        {"label": "Update", "value": "update"},
                        {"label": "Insert or Update", "value": "upsert"},
                        {"label": "Delete", "value": "delete"},
                    ],
                    tabName="basic",
                ),

                # --- Execute Query -----------------------------------------
                NodeProperty(
                    name="query",
                    displayName="Query",
                    type=NodePropertyType.CODE_EDITOR,
                    description=(
                        "SQL statement to run. Use $1, $2 placeholders for values and supply "
                        "them in Query Parameters so they are escaped safely."
                    ),
                    placeholder="SELECT * FROM customers WHERE city = $1;",
                    required=False,
                    default="",
                    rows=8,
                    maxLength=20000,
                    displayOptions={"show": {"operation": "execute_query"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="query_parameters",
                    displayName="Query Parameters",
                    type=NodePropertyType.JSON_EDITOR,
                    description=(
                        "Values for the $1, $2 placeholders, in order. Given as a JSON array, "
                        "for example: [\"aksesuar\", 2000]"
                    ),
                    placeholder='["value1", 100]',
                    required=False,
                    default="[]",
                    displayOptions={"show": {"operation": "execute_query"}},
                    tabName="basic",
                ),

                # --- Table targeting ---------------------------------------
                NodeProperty(
                    name="schema_name",
                    displayName="Schema",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Schema that contains the table. Pick one from the list or type a name, "
                        "which also accepts a template."
                    ),
                    placeholder="Select or type a schema",
                    required=False,
                    default="public",
                    optionsMethod="load_schemas",
                    optionsDependsOn=["credential_id"],
                    displayOptions={"show": {"operation": ["select", "insert", "update", "upsert", "delete"]}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="table_name",
                    displayName="Table",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Table to operate on. Pick one from the list or type a name, which also "
                        "accepts a template."
                    ),
                    placeholder="Select or type a table",
                    required=False,
                    default="",
                    optionsMethod="load_tables",
                    optionsDependsOn=["credential_id", "schema_name"],
                    displayOptions={"show": {"operation": ["select", "insert", "update", "upsert", "delete"], "schema_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="columns",
                    displayName="Columns",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Columns to return. Leave empty for all of them.",
                    placeholder="All columns",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="return_all",
                    displayName="Return All",
                    type=NodePropertyType.CHECKBOX,
                    description="Return every matching row. Turn off to apply a limit.",
                    required=False,
                    default=True,
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="limit",
                    displayName="Limit",
                    type=NodePropertyType.NUMBER,
                    description="Maximum number of rows to return.",
                    required=False,
                    default=50,
                    min=1,
                    max=10000,
                    displayOptions={"show": {"operation": "select", "return_all": False}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_column",
                    displayName="Sort Column",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Column the results are ordered by. Leave empty for no ordering.",
                    placeholder="No ordering",
                    required=False,
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": "select", "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_direction",
                    displayName="Sort Direction",
                    type=NodePropertyType.SELECT,
                    description="Order direction for the sort column.",
                    required=False,
                    default="ASC",
                    options=[
                        {"label": "Ascending", "value": "ASC"},
                        {"label": "Descending", "value": "DESC"},
                    ],
                    displayOptions={"show": {"operation": "select", "sort_column": "*"}},
                    tabName="basic",
                ),

                # --- Conditions --------------------------------------------
                # --- Conditions (Select and Delete) --------------------------
                NodeProperty(
                    name="delete_command",
                    displayName="Command",
                    type=NodePropertyType.SELECT,
                    description="How the data should be removed.",
                    required=False,
                    default="delete",
                    options=[
                        {"label": "Delete - remove matching rows", "value": "delete"},
                        {"label": "Truncate - remove all rows, keep the table", "value": "truncate"},
                    ],
                    hint=(
                        "Truncate is much faster than Delete but empties the whole table; "
                        "any filter below is ignored."
                    ),
                    displayOptions={"show": {"operation": "delete", "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="restart_sequences",
                    displayName="Restart Sequences",
                    type=NodePropertyType.CHECKBOX,
                    description="Reset auto incrementing columns back to their starting value.",
                    required=False,
                    default=False,
                    displayOptions={"show": {"operation": "delete", "delete_command": "truncate"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="cascade",
                    displayName="Cascade",
                    type=NodePropertyType.CHECKBOX,
                    description="Also truncate tables that reference this one through a foreign key.",
                    required=False,
                    default=False,
                    displayOptions={"show": {"operation": "delete", "delete_command": "truncate"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_column",
                    displayName="Filter Column",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Column the rows are matched on. Leave empty to match every row, which "
                        "for Delete means the whole table."
                    ),
                    placeholder="No filter, match every row",
                    required=False,
                    default="",
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": ["select", "update", "delete"], "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_operator",
                    displayName="Filter Operator",
                    type=NodePropertyType.SELECT,
                    description=(
                        "How the column is compared to the value. Text comparisons ignore "
                        "capitalisation, so 'bursa' also matches 'Bursa' and 'BURSA'."
                    ),
                    required=False,
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
                    displayOptions={"show": {"operation": ["select", "update", "delete"], "filter_column": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_value",
                    displayName="Filter Value",
                    type=NodePropertyType.TEXT,
                    description=(
                        "Value the column is compared to. Not needed for the empty and not empty "
                        "operators."
                    ),
                    placeholder="e.g. Istanbul",
                    required=False,
                    default="",
                    displayOptions={"show": {"operation": ["select", "update", "delete"], "filter_column": "*", "filter_operator": ["equals", "not_equals", "greater_than", "greater_or_equal", "less_than", "less_or_equal", "like", "ilike"]}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="where_conditions",
                    displayName="Extra Conditions",
                    type=NodePropertyType.JSON_EDITOR,
                    description=(
                        "Further conditions as a JSON array, for cases the single filter above "
                        "cannot express. Each entry takes column, operator and value."
                    ),
                    placeholder='[{"column": "is_active", "operator": "equals", "value": true}]',
                    required=False,
                    default="[]",
                    hint=(
                        "Operators: equals, not_equals, greater_than, greater_or_equal, "
                        "less_than, less_or_equal, like, ilike, is_null, is_not_null"
                    ),
                    tabName="basic",
                ),
                NodeProperty(
                    name="combine_conditions",
                    displayName="Combine Conditions",
                    type=NodePropertyType.SELECT,
                    description="How multiple conditions are joined together.",
                    required=False,
                    default="AND",
                    options=[
                        {"label": "AND - all must match", "value": "AND"},
                        {"label": "OR - any may match", "value": "OR"},
                    ],
                    tabName="basic",
                ),

                # --- Column mapping (Insert, Update, Upsert) ------------------
                NodeProperty(
                    name="mapping_mode",
                    displayName="Mapping Column Mode",
                    type=NodePropertyType.SELECT,
                    description="How column names are matched to the incoming data.",
                    required=False,
                    default="manual",
                    options=[
                        {
                            "label": "Map Each Column Manually",
                            "value": "manual",
                            "hint": "Write the column values yourself.",
                        },
                        {
                            "label": "Map Automatically",
                            "value": "auto",
                            "hint": "Take the values from the incoming data. Field names must match the column names.",
                        },
                    ],
                    displayOptions={"show": {"operation": ["insert", "update", "upsert"], "table_name": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="match_columns",
                    displayName="Columns to Match On",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Columns used to find the existing row. Their values are read from the "
                        "data, so they must be present there."
                    ),
                    placeholder="Select a column",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    hint=(
                        "For Insert or Update the column has to carry a unique constraint. "
                        "Pick more than one to match on a composite key."
                    ),
                    displayOptions={"show": {"operation": ["update", "upsert"], "table_name": "*"}},
                    tabName="basic",
                ),

                NodeProperty(
                    name="data",
                    displayName="Values to Send",
                    type=NodePropertyType.COLUMN_MAPPER,
                    description=(
                        "Value for each column of the selected table. Columns can be left out; "
                        "the database then applies its own default."
                    ),
                    required=False,
                    default="{}",
                    optionsMethod="load_column_schema",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    hint=(
                        "Switch Mapping Column Mode to Map Automatically to take the values from "
                        "the incoming data instead."
                    ),
                    displayOptions={"show": {"operation": ["insert", "update", "upsert"], "mapping_mode": "manual"}},
                    tabName="basic",
                ),

                # ----------------------------------------------------------
                # Advanced
                # ----------------------------------------------------------
                NodeProperty(
                    name="read_only",
                    displayName="Read Only",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Allow reading only. Insert, update, upsert and delete are refused, and "
                        "raw statements that would change data are rejected before they run. "
                        "Useful when the node is reachable by an agent."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="return_columns",
                    displayName="Output Columns",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Columns to return after a write. Leave empty to return every column of "
                        "the affected rows."
                    ),
                    placeholder="All columns",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_columns",
                    optionsDependsOn=["credential_id", "schema_name", "table_name"],
                    displayOptions={"show": {"operation": ["insert", "update", "upsert", "delete"]}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="use_transaction",
                    displayName="Use Transaction",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Wrap the operation in a transaction so a failure rolls back every change. "
                        "Turn off to commit each statement on its own."
                    ),
                    required=False,
                    default=True,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="skip_on_conflict",
                    displayName="Skip on Conflict",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Ignore rows that violate a unique constraint instead of raising an error."
                    ),
                    required=False,
                    default=False,
                    displayOptions={"show": {"operation": "insert"}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="replace_empty_with_null",
                    displayName="Replace Empty Strings with NULL",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Store empty text values as NULL. Useful for data exported from spreadsheets."
                    ),
                    required=False,
                    default=False,
                    displayOptions={"show": {"operation": ["insert", "update", "upsert"]}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="numbers_as_text",
                    displayName="Return Numbers as Text",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return NUMERIC and DECIMAL columns as text to keep every digit. "
                        "Turn this on for money amounts and other values where rounding is "
                        "not acceptable."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="connection_timeout",
                    displayName="Connection Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="How long to wait for the database to accept the connection.",
                    required=False,
                    default=30,
                    min=1,
                    max=300,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="statement_timeout",
                    displayName="Statement Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Cancel the query if it runs longer than this. Set 0 to disable.",
                    required=False,
                    default=60,
                    min=0,
                    max=3600,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="continue_on_error",
                    displayName="Continue on Error",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Let the workflow carry on when the query fails. The error is reported in "
                        "the output instead of stopping the run."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
            ],
        }

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_identifier(value: str, label: str) -> str:
        """Reject anything that is not a plain SQL identifier."""
        value = (value or "").strip()
        if not value:
            raise ValueError(f"{label} is required.")
        if not IDENTIFIER_PATTERN.match(value):
            raise ValueError(
                f"{label} '{value}' is not a valid identifier. "
                "Use letters, digits and underscores, starting with a letter or underscore."
            )
        return value

    @classmethod
    def _split_columns(cls, raw: str) -> List[str]:
        """Turn a comma separated column list into validated identifiers."""
        if not raw or not raw.strip():
            return []
        return [cls._validate_identifier(part, "Column") for part in raw.split(",") if part.strip()]

    @staticmethod
    def _coerce_json(value: Any, fallback: Any) -> Any:
        """Accept either an already parsed structure or a JSON string."""
        if value is None or value == "":
            return fallback
        if isinstance(value, (dict, list)):
            return value
        if isinstance(value, str):
            import json
            try:
                return json.loads(value)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Could not parse JSON value: {exc}") from exc
        return fallback

    def _build_connection_string(self, credential_id: Optional[str]) -> str:
        """Read the credential and assemble a libpq connection string."""
        if not credential_id:
            raise ValueError("A PostgreSQL credential is required.")

        credential = self.get_credential(credential_id)
        if not credential or not credential.get("secret"):
            raise ValueError(
                "The selected credential could not be read. It may have been created with a "
                "different encryption key; try recreating it."
            )

        secret = credential["secret"]
        host = secret.get("host", "localhost")
        port = secret.get("port", 5432)
        database = secret.get("database", "postgres")
        username = secret.get("username", "postgres")
        password = secret.get("password", "")

        if username and password:
            return f"postgresql://{username}:{password}@{host}:{port}/{database}"
        return f"postgresql://{host}:{port}/{database}"

    # ------------------------------------------------------------------
    # Option loaders
    #
    # Called by the node options endpoint when a dynamic dropdown needs to be
    # filled. Each one receives the values currently entered in the panel.
    # ------------------------------------------------------------------

    def _fetch_one_column(self, credential_id: str, statement: str, params: tuple = ()) -> List[str]:
        """Open a short-lived connection and read a single column."""
        connection = None
        try:
            connection = psycopg2.connect(
                self._build_connection_string(credential_id), connect_timeout=10
            )
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 5000")
                cursor.execute(statement, params or None)
                return [row[0] for row in cursor.fetchall()]
        finally:
            if connection is not None:
                connection.close()

    def load_schemas(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List the schemas the credential can see."""
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

    def load_tables(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List the tables and views in the selected schema."""
        schema = (values.get("schema_name") or "public").strip()
        names = self._fetch_one_column(
            values.get("credential_id"),
            """
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = %s
              AND table_type IN ('BASE TABLE', 'VIEW')
            ORDER BY table_name
            """,
            (schema,),
        )
        return [{"label": name, "value": name} for name in names]

    def load_columns(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """List the columns of the selected table."""
        schema = (values.get("schema_name") or "public").strip()
        table = (values.get("table_name") or "").strip()
        if not table:
            return []
        names = self._fetch_one_column(
            values.get("credential_id"),
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = %s AND table_name = %s
            ORDER BY ordinal_position
            """,
            (schema, table),
        )
        return [{"label": name, "value": name} for name in names]

    # Postgres data types mapped to the input the panel should show.
    WIDGET_BY_TYPE = {
        "boolean": "checkbox",
        "smallint": "number", "integer": "number", "bigint": "number",
        "numeric": "number", "real": "number", "double precision": "number",
        "date": "datetime",
        "timestamp with time zone": "datetime",
        "timestamp without time zone": "datetime",
        "json": "json", "jsonb": "json",
    }

    def load_column_schema(self, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Describe the columns of the selected table.

        Each entry carries the input the panel should render, whether a value is
        required and whether the database fills one in on its own.
        """
        schema = (values.get("schema_name") or "public").strip()
        table = (values.get("table_name") or "").strip()
        if not table:
            return []

        connection = None
        try:
            connection = psycopg2.connect(
                self._build_connection_string(values.get("credential_id")), connect_timeout=10
            )
            with connection.cursor() as cursor:
                cursor.execute("SET statement_timeout = 5000")
                cursor.execute(
                    """
                    SELECT column_name, data_type, is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema = %s AND table_name = %s
                    ORDER BY ordinal_position
                    """,
                    (schema, table),
                )
                rows = cursor.fetchall()
        finally:
            if connection is not None:
                connection.close()

        columns: List[Dict[str, Any]] = []
        for name, data_type, is_nullable, default in rows:
            columns.append({
                "label": name,
                "value": name,
                "name": name,
                "type": data_type,
                "widget": self.WIDGET_BY_TYPE.get(data_type, "text"),
                "required": is_nullable == "NO" and default is None,
                "hasDefault": default is not None,
            })
        return columns

    def _collect_conditions(self, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Gather the row filter.

        The three simple fields cover the common case of one comparison. Anything
        beyond that goes in Extra Conditions, and the two are combined.
        """
        conditions: List[Dict[str, Any]] = []

        column = (inputs.get("filter_column") or "").strip()
        if column:
            operator = str(inputs.get("filter_operator") or "equals").strip()
            condition: Dict[str, Any] = {"column": column, "operator": operator}
            if operator not in ("is_null", "is_not_null"):
                condition["value"] = inputs.get("filter_value")
            conditions.append(condition)

        extra = self._coerce_json(inputs.get("where_conditions"), [])
        if isinstance(extra, dict):
            extra = [extra]
        if isinstance(extra, list):
            conditions.extend(entry for entry in extra if isinstance(entry, dict) and entry)

        return conditions

    def _collect_conditions(self, inputs: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Gather the row filter.

        The three filter fields cover the common case of a single comparison and
        are picked from lists rather than typed. Anything more involved goes in
        Extra Conditions as JSON. Both are merged here, so the rest of the code
        only ever sees one list.
        """
        conditions: List[Dict[str, Any]] = []

        column = (inputs.get("filter_column") or "").strip()
        if column:
            operator = (inputs.get("filter_operator") or "equals").strip()
            condition: Dict[str, Any] = {"column": column, "operator": operator}
            if operator not in ("is_null", "is_not_null"):
                condition["value"] = inputs.get("filter_value", "")
            conditions.append(condition)

        extra = self._coerce_json(inputs.get("where_conditions"), [])
        if isinstance(extra, list):
            conditions.extend(entry for entry in extra if isinstance(entry, dict) and entry)

        return conditions

    @staticmethod
    def _prepare_condition_value(operator: str, value: Any) -> Any:
        """
        Shape a value for the operator it will be used with.

        The contains operators run on LIKE, which treats a plain string as an
        exact match. Wrapping it in wildcards is what someone picking "contains"
        expects. A value that already carries a wildcard is left alone, so a
        deliberate pattern still works.
        """
        if operator not in ("like", "ilike"):
            return value
        if not isinstance(value, str) or not value:
            return value
        if "%" in value or "_" in value:
            return value
        return f"%{value}%"

    def _build_where_clause(
        self, conditions: List[Dict[str, Any]], combiner: str
    ) -> Tuple[Optional[sql.Composed], List[Any]]:
        """Compose a WHERE clause and collect its parameter values."""
        if not conditions:
            return None, []

        joiner = " AND " if str(combiner).upper() != "OR" else " OR "
        fragments: List[sql.Composed] = []
        values: List[Any] = []

        for condition in conditions:
            if not isinstance(condition, dict):
                raise ValueError("Each condition must be an object with column, operator and value.")

            column = self._validate_identifier(condition.get("column", ""), "Condition column")
            operator_key = str(condition.get("operator", "equals")).lower()

            if operator_key not in CONDITION_OPERATORS:
                raise ValueError(
                    f"Unknown operator '{operator_key}'. "
                    f"Supported operators: {', '.join(CONDITION_OPERATORS)}"
                )

            operator_sql = CONDITION_OPERATORS[operator_key]

            # NULL checks take no value on the right hand side.
            if operator_key in ("is_null", "is_not_null"):
                fragments.append(
                    sql.SQL("{} {}").format(sql.Identifier(column), sql.SQL(operator_sql))
                )
            else:
                value = self._prepare_condition_value(operator_key, condition.get("value"))

                # Equality on text is compared without regard to case. Someone
                # filtering on "bursa" means the rows holding "Bursa" and "BURSA"
                # as well; a plain = would quietly pass over them. The cast keeps
                # this safe on columns that are not text.
                if operator_key in CASE_FOLDED_OPERATORS and isinstance(value, str):
                    fragments.append(
                        sql.SQL("LOWER({}::text) {} LOWER(%s)").format(
                            sql.Identifier(column), sql.SQL(operator_sql)
                        )
                    )
                else:
                    fragments.append(
                        sql.SQL("{} {} %s").format(
                            sql.Identifier(column), sql.SQL(operator_sql)
                        )
                    )

                values.append(value)

        return sql.SQL(joiner).join(fragments), values

    # Trigger nodes wrap the payload, sometimes more than once. A webhook, for
    # instance, nests the request body under webhook_data.payload.
    ENVELOPE_KEYS = ("webhook_data", "payload", "body", "json", "data", "result", "rows")

    @classmethod
    def _unwrap_payload(cls, value: Any, depth: int = 4) -> Any:
        """
        Reach the row inside a trigger's envelope.

        A trigger hands over its whole context, with the row sitting alongside
        timestamps, identifiers and configuration. Recognised wrapper keys are
        peeled off one at a time until the row itself is reached.
        """
        if depth <= 0 or not isinstance(value, dict):
            return value

        for key in cls.ENVELOPE_KEYS:
            inner = value.get(key)
            if isinstance(inner, dict) and inner:
                return cls._unwrap_payload(inner, depth - 1)
            if isinstance(inner, list) and inner and isinstance(inner[0], dict):
                return inner

        return value

    def _table_columns(self, inputs: Dict[str, Any]) -> List[str]:
        """Read the column names of the target table, or an empty list on failure."""
        try:
            schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
            table = self._validate_identifier(inputs.get("table_name", ""), "Table")
        except ValueError:
            return []

        try:
            return self._fetch_one_column(
                inputs.get("credential_id"),
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
                ORDER BY ordinal_position
                """,
                (schema, table),
            )
        except Exception as exc:
            logger.warning(f"Could not read the columns of {table}: {exc}")
            return []

    def _resolve_rows(
        self,
        raw_data: Any,
        connected_nodes: Dict[str, Any],
        replace_empty: bool,
        inputs: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect the rows to write.

        Accepts a single object or an array, taken either from the Data field or
        from the input connection. Always returns a list so one row and many rows
        can be handled the same way.

        Data arriving on the connection is filtered down to the table's own
        columns. A trigger usually sends more than the row itself, and passing
        those extras through would only produce an error the author cannot act
        on.
        """
        data = self._coerce_json(raw_data, None)
        from_connection = False

        if not data:
            data = self._unwrap_payload(connected_nodes.get("input"))
            from_connection = True

        if isinstance(data, dict):
            rows = [data]
        elif isinstance(data, list):
            rows = [row for row in data if isinstance(row, dict) and row]
        else:
            rows = []

        if not rows:
            raise ValueError(
                "No column values were supplied. Fill in the Data field or connect a node that "
                "produces an object or a list of objects."
            )

        # Only the table's own columns survive when the data comes off a wire.
        known: Optional[Set[str]] = None
        if from_connection and inputs is not None:
            columns = self._table_columns(inputs)
            if columns:
                known = {name.lower() for name in columns}

        cleaned: List[Dict[str, Any]] = []
        for row in rows:
            if known is not None:
                row = {key: value for key, value in row.items() if str(key).lower() in known}
                if not row:
                    raise ValueError(
                        "None of the incoming fields match a column of the table. "
                        "Check the field names, or switch to Map Each Column Manually."
                    )

            if replace_empty:
                row = {key: (None if value == "" else value) for key, value in row.items()}

            # Column names come from user data, so they are validated too.
            cleaned.append(
                {self._validate_identifier(key, "Column"): value for key, value in row.items()}
            )

        # Every row has to describe the same columns for a single statement to work.
        first_columns = set(cleaned[0].keys())
        for index, row in enumerate(cleaned[1:], start=2):
            if set(row.keys()) != first_columns:
                raise ValueError(
                    f"Row {index} does not have the same columns as the first row. "
                    "Every row must carry the same set of columns."
                )

        return cleaned

    @classmethod
    def _split_match_columns(cls, raw: Any) -> List[str]:
        """Read the match column selection, which may be a string or a list."""
        if not raw:
            return []
        if isinstance(raw, str):
            parts = [part.strip() for part in raw.split(",")]
        elif isinstance(raw, (list, tuple)):
            parts = [str(part).strip() for part in raw]
        else:
            parts = [str(raw).strip()]
        return [cls._validate_identifier(part, "Match column") for part in parts if part]

    @staticmethod
    def _guard_read_only(operation: str, query: str = "") -> None:
        """Refuse anything that would change data while read-only mode is on."""
        if operation in WRITE_OPERATIONS:
            raise ValueError(
                f"Read Only is enabled, so the '{operation}' operation is not allowed. "
                "Turn Read Only off in the Advanced tab to write to the database."
            )

        if operation != "execute_query" or not query:
            return

        # A raw statement can hide a write behind a semicolon, so each statement
        # is checked on its own.
        for statement in query.split(";"):
            statement = statement.strip()
            if not statement:
                continue
            first_word = re.split(r"\s+", statement, maxsplit=1)[0].lower()
            if first_word in WRITE_KEYWORDS:
                raise ValueError(
                    f"Read Only is enabled, so a statement starting with '{first_word.upper()}' "
                    "is not allowed. Only read statements can run in this mode."
                )

    @classmethod
    def _serialize_value(cls, value: Any, numbers_as_text: bool = False) -> Any:
        """
        Convert driver types into values that survive JSON serialization.

        Execution results are stored as JSON, so ``Decimal``, ``datetime`` and
        friends have to be converted before they leave the node.
        """
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value) if numbers_as_text else float(value)
        if isinstance(value, (datetime, date, time_type)):
            return value.isoformat()
        if isinstance(value, timedelta):
            return value.total_seconds()
        if isinstance(value, uuid_module.UUID):
            return str(value)
        if isinstance(value, (bytes, bytearray, memoryview)):
            return bytes(value).hex()
        if isinstance(value, dict):
            return {key: cls._serialize_value(item, numbers_as_text) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize_value(item, numbers_as_text) for item in value]
        return str(value)

    @classmethod
    def _serialize_rows(
        cls, rows: List[Dict[str, Any]], numbers_as_text: bool = False
    ) -> List[Dict[str, Any]]:
        """Apply value serialization across every returned row."""
        return [
            {key: cls._serialize_value(value, numbers_as_text) for key, value in row.items()}
            for row in rows
        ]

    @staticmethod
    def _returning_clause(columns: List[str]) -> sql.Composed:
        """Build the RETURNING part of a write statement."""
        if columns:
            return sql.SQL(" RETURNING {}").format(
                sql.SQL(", ").join(sql.Identifier(column) for column in columns)
            )
        return sql.SQL(" RETURNING *")

    # ------------------------------------------------------------------
    # Statement builders
    # ------------------------------------------------------------------

    def _build_select(self, inputs: Dict[str, Any]) -> Tuple[sql.Composed, List[Any]]:
        schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
        table = self._validate_identifier(inputs.get("table_name", ""), "Table")
        columns = self._split_columns(inputs.get("columns", ""))

        column_part = (
            sql.SQL(", ").join(sql.Identifier(column) for column in columns)
            if columns
            else sql.SQL("*")
        )

        statement = sql.SQL("SELECT {} FROM {}.{}").format(
            column_part, sql.Identifier(schema), sql.Identifier(table)
        )
        values: List[Any] = []

        conditions = self._collect_conditions(inputs)
        where_clause, where_values = self._build_where_clause(
            conditions, inputs.get("combine_conditions", "AND")
        )
        if where_clause is not None:
            statement = statement + sql.SQL(" WHERE ") + where_clause
            values.extend(where_values)

        sort_column = (inputs.get("sort_column") or "").strip()
        if sort_column:
            sort_column = self._validate_identifier(sort_column, "Sort column")
            direction = "DESC" if str(inputs.get("sort_direction", "ASC")).upper() == "DESC" else "ASC"
            statement = statement + sql.SQL(" ORDER BY {} {}").format(
                sql.Identifier(sort_column), sql.SQL(direction)
            )

        if not inputs.get("return_all", True):
            limit = int(inputs.get("limit", 50) or 50)
            statement = statement + sql.SQL(" LIMIT %s")
            values.append(limit)

        return statement, values

    def _build_insert(
        self, inputs: Dict[str, Any], rows: List[Dict[str, Any]]
    ) -> Tuple[sql.Composed, List[Any]]:
        """Build a single INSERT that writes every supplied row."""
        schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
        table = self._validate_identifier(inputs.get("table_name", ""), "Table")

        columns = list(rows[0].keys())
        placeholder_group = sql.SQL("({})").format(
            sql.SQL(", ").join(sql.Placeholder() * len(columns))
        )

        statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES {}").format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join([placeholder_group] * len(rows)),
        )

        if inputs.get("skip_on_conflict", False):
            statement = statement + sql.SQL(" ON CONFLICT DO NOTHING")

        statement = statement + self._returning_clause(
            self._split_columns(inputs.get("return_columns", ""))
        )

        values: List[Any] = []
        for row in rows:
            values.extend(row[column] for column in columns)

        return statement, values

    def _build_update(
        self, inputs: Dict[str, Any], rows: List[Dict[str, Any]]
    ) -> Tuple[sql.Composed, List[Any]]:
        """
        Build an UPDATE statement.

        Rows can be matched two ways. Naming match columns takes their values
        from the data itself, which is how a row is usually identified. Writing
        conditions instead gives a free-form filter.
        """
        if len(rows) > 1:
            raise ValueError(
                "Update writes one set of values to every matching row, so it accepts a single "
                "object rather than a list. Use Insert or Update if each row needs its own values."
            )
        row = dict(rows[0])

        schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
        table = self._validate_identifier(inputs.get("table_name", ""), "Table")
        match_columns = self._split_match_columns(inputs.get("match_columns"))

        # Match columns identify the row, so they are removed from the SET list.
        assignments_source = {
            column: value for column, value in row.items() if column not in match_columns
        }
        if not assignments_source:
            raise ValueError(
                "Every column given is also a match column, so there is nothing left to update."
            )

        assignments = sql.SQL(", ").join(
            sql.SQL("{} = %s").format(sql.Identifier(column)) for column in assignments_source
        )
        statement = sql.SQL("UPDATE {}.{} SET {}").format(
            sql.Identifier(schema), sql.Identifier(table), assignments
        )
        values: List[Any] = list(assignments_source.values())

        where_parts: List[sql.Composed] = []

        for column in match_columns:
            if column not in row:
                raise ValueError(
                    f"Match column '{column}' is missing from the data. "
                    "Its value is read from there, so it has to be present."
                )
            where_parts.append(sql.SQL("{} = %s").format(sql.Identifier(column)))
            values.append(row[column])

        conditions = self._collect_conditions(inputs)
        where_clause, where_values = self._build_where_clause(
            conditions, inputs.get("combine_conditions", "AND")
        )
        if where_clause is not None:
            where_parts.append(where_clause)
            values.extend(where_values)

        if where_parts:
            statement = statement + sql.SQL(" WHERE ") + sql.SQL(" AND ").join(where_parts)

        statement = statement + self._returning_clause(
            self._split_columns(inputs.get("return_columns", ""))
        )
        return statement, values

    def _build_upsert(
        self, inputs: Dict[str, Any], rows: List[Dict[str, Any]]
    ) -> Tuple[sql.Composed, List[Any]]:
        """Build a single INSERT ... ON CONFLICT that writes every supplied row."""
        schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
        table = self._validate_identifier(inputs.get("table_name", ""), "Table")
        match_columns = self._split_match_columns(inputs.get("match_columns"))

        if not match_columns:
            raise ValueError(
                "Insert or Update needs at least one match column so an existing row can be found."
            )

        columns = list(rows[0].keys())
        missing = [column for column in match_columns if column not in columns]
        if missing:
            raise ValueError(
                f"Match column(s) {', '.join(missing)} are missing from the data. "
                "They must be present so an existing row can be found."
            )

        updatable = [column for column in columns if column not in match_columns]
        placeholder_group = sql.SQL("({})").format(
            sql.SQL(", ").join(sql.Placeholder() * len(columns))
        )

        statement = sql.SQL("INSERT INTO {}.{} ({}) VALUES {} ON CONFLICT ({}) DO ").format(
            sql.Identifier(schema),
            sql.Identifier(table),
            sql.SQL(", ").join(sql.Identifier(column) for column in columns),
            sql.SQL(", ").join([placeholder_group] * len(rows)),
            sql.SQL(", ").join(sql.Identifier(column) for column in match_columns),
        )

        if updatable:
            statement = statement + sql.SQL("UPDATE SET ") + sql.SQL(", ").join(
                sql.SQL("{} = EXCLUDED.{}").format(sql.Identifier(column), sql.Identifier(column))
                for column in updatable
            )
        else:
            statement = statement + sql.SQL("NOTHING")

        statement = statement + self._returning_clause(
            self._split_columns(inputs.get("return_columns", ""))
        )

        values: List[Any] = []
        for row in rows:
            values.extend(row[column] for column in columns)

        return statement, values

    def _build_delete(self, inputs: Dict[str, Any]) -> Tuple[sql.Composed, List[Any]]:
        schema = self._validate_identifier(inputs.get("schema_name", "public"), "Schema")
        table = self._validate_identifier(inputs.get("table_name", ""), "Table")
        command = str(inputs.get("delete_command", "delete")).lower()

        if command == "truncate":
            statement = sql.SQL("TRUNCATE TABLE {}.{}").format(
                sql.Identifier(schema), sql.Identifier(table)
            )
            if inputs.get("restart_sequences", False):
                statement = statement + sql.SQL(" RESTART IDENTITY")
            if inputs.get("cascade", False):
                statement = statement + sql.SQL(" CASCADE")
            return statement, []

        statement = sql.SQL("DELETE FROM {}.{}").format(
            sql.Identifier(schema), sql.Identifier(table)
        )
        values: List[Any] = []

        conditions = self._collect_conditions(inputs)
        where_clause, where_values = self._build_where_clause(
            conditions, inputs.get("combine_conditions", "AND")
        )
        if where_clause is not None:
            statement = statement + sql.SQL(" WHERE ") + where_clause
            values.extend(where_values)

        statement = statement + self._returning_clause(
            self._split_columns(inputs.get("return_columns", ""))
        )
        return statement, values

    @staticmethod
    def _build_execute_query(inputs: Dict[str, Any]) -> Tuple[str, List[Any]]:
        """Prepare a raw statement, converting $1 placeholders to driver placeholders."""
        query = (inputs.get("query") or "").strip()
        if not query:
            raise ValueError("The Query field is empty.")

        parameters = PostgresNode._coerce_json(inputs.get("query_parameters"), [])
        if isinstance(parameters, dict):
            parameters = list(parameters.values())
        if not isinstance(parameters, list):
            raise ValueError("Query Parameters must be a JSON array, for example: [\"value\", 10]")

        # psycopg2 expects %s placeholders; $1 style is friendlier to write.
        ordered: List[Any] = []
        if parameters:
            placeholders = sorted(
                {int(match) for match in re.findall(r"\$(\d+)", query)}
            )
            for index in placeholders:
                if index > len(parameters):
                    raise ValueError(
                        f"The query references ${index} but only {len(parameters)} "
                        "parameter(s) were supplied."
                    )
                ordered.append(parameters[index - 1])
            query = re.sub(r"\$\d+", "%s", query)

        return query, ordered

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]) -> Dict[str, Any]:
        started_at = time.time()
        operation = str(inputs.get("operation", "select")).lower()
        continue_on_error = bool(inputs.get("continue_on_error", False))
        read_only = bool(inputs.get("read_only", False))
        written_rows = 0

        # Write operations are refused before a connection is even opened.
        if read_only and operation in WRITE_OPERATIONS:
            self._guard_read_only(operation)

        logger.info("Executing PostgresNode operation=%s", operation)

        connection = None
        try:
            connection_string = self._build_connection_string(inputs.get("credential_id"))
            connect_timeout = int(inputs.get("connection_timeout", 30) or 30)

            connection = psycopg2.connect(connection_string, connect_timeout=connect_timeout)
            connection.autocommit = not bool(inputs.get("use_transaction", True))

            statement_timeout = int(inputs.get("statement_timeout", 60) or 0)

            with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                if statement_timeout > 0:
                    cursor.execute("SET statement_timeout = %s", (statement_timeout * 1000,))

                if operation == "execute_query":
                    statement, values = self._build_execute_query(inputs)
                    if read_only:
                        self._guard_read_only(operation, statement)
                elif operation == "select":
                    statement, values = self._build_select(inputs)
                elif operation in ("insert", "update", "upsert"):
                    rows_in = self._resolve_rows(
                        inputs.get("data"), connected_nodes,
                        bool(inputs.get("replace_empty_with_null", False)),
                        inputs,
                    )
                    written_rows = len(rows_in)
                    if operation == "insert":
                        statement, values = self._build_insert(inputs, rows_in)
                    elif operation == "update":
                        statement, values = self._build_update(inputs, rows_in)
                    else:
                        statement, values = self._build_upsert(inputs, rows_in)
                elif operation == "delete":
                    statement, values = self._build_delete(inputs)
                else:
                    raise ValueError(f"Unknown operation '{operation}'.")

                cursor.execute(statement, values or None)

                rows: List[Dict[str, Any]] = []
                if cursor.description is not None:
                    raw_rows = [dict(record) for record in cursor.fetchall()]
                    rows = self._serialize_rows(
                        raw_rows, bool(inputs.get("numbers_as_text", False))
                    )

                row_count = len(rows) if rows else max(cursor.rowcount, 0)

            if not connection.autocommit:
                connection.commit()

            duration_ms = round((time.time() - started_at) * 1000, 2)
            logger.info(
                "PostgresNode finished operation=%s rows=%s duration=%sms",
                operation, row_count, duration_ms,
            )

            return {
                "output": {
                    "rows": rows,
                    "row_count": row_count,
                    "rows_written": written_rows,
                    "operation": operation,
                    "duration_ms": duration_ms,
                },
                "success": True,
                "error": None,
            }

        except psycopg2.Error as exc:
            if connection is not None and not connection.autocommit:
                connection.rollback()

            # psycopg2 messages carry a trailing newline and often a DETAIL block.
            message = str(exc).strip()
            logger.error("PostgresNode database error operation=%s: %s", operation, message)

            if not continue_on_error:
                raise ValueError(f"PostgreSQL error: {message}") from exc

            return {
                "output": {
                    "rows": [],
                    "row_count": 0,
                    "rows_written": 0,
                    "operation": operation,
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                    "error": message,
                },
                "success": False,
                "error": message,
            }

        except Exception as exc:
            if connection is not None and not connection.autocommit:
                connection.rollback()

            message = str(exc)
            logger.error("PostgresNode failed operation=%s: %s", operation, message)

            if not continue_on_error:
                raise

            return {
                "output": {
                    "rows": [],
                    "row_count": 0,
                    "rows_written": 0,
                    "operation": operation,
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                    "error": message,
                },
                "success": False,
                "error": message,
            }

        finally:
            if connection is not None:
                connection.close()