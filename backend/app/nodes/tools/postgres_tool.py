"""
PostgreSQL Tool
===============

Gives an agent a callable tool for working with a PostgreSQL database.

Where the PostgreSQL node runs a statement the flow author wrote, this node
hands the agent a tool and lets it compose the statement itself. That is a good
deal more power, so the node is built around deciding how much of it to grant:

- Reading, inserting, updating and deleting are enabled one by one. Nothing but
  reading is on to begin with.
- An allow list can narrow the tool down to named tables.
- Updates and deletes can be required to carry a WHERE clause, which is what
  stops a single careless statement from rewriting a whole table.
- Statements that change the schema are always refused.
- Result sets are capped so a broad query cannot flood the agent's context.
- The table layout can be described to the agent, which keeps it from guessing
  column names that do not exist.
"""

from __future__ import annotations

import re
import logging
from datetime import date, datetime, time as time_type, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional, Set

import psycopg2
from psycopg2.extras import RealDictCursor
from langchain_core.tools import Tool

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

# Leading keywords grouped by the permission that covers them.
READ_KEYWORDS = {"select", "with", "show", "explain", "table", "values"}
INSERT_KEYWORDS = {"insert"}
UPDATE_KEYWORDS = {"update"}
DELETE_KEYWORDS = {"delete", "truncate"}

# Schema changes and administrative commands are never granted. Data can be
# read and written; the shape of the database cannot be altered.
FORBIDDEN_KEYWORDS = {
    "drop", "create", "alter", "grant", "revoke", "comment", "vacuum",
    "reindex", "cluster", "copy", "call", "do", "listen", "notify",
    "prepare", "execute", "deallocate", "set", "reset", "begin", "commit",
    "rollback", "savepoint", "lock", "refresh", "analyze", "checkpoint",
}

# Tables named in a statement, read off the clauses that introduce one.
TABLE_REFERENCE_PATTERN = re.compile(
    r"\b(?:from|join|into|update|table)\s+"
    r"(?:only\s+)?"
    r"([A-Za-z_][A-Za-z0-9_]*)(?:\.([A-Za-z_][A-Za-z0-9_]*))?",
    re.IGNORECASE,
)

# Common table expressions name themselves and are not real tables.
CTE_PATTERN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s+as\s*\(", re.IGNORECASE)

# A quoted value compared inside a WHERE clause. PostgreSQL compares text letter
# for letter, so 'ankara' would pass over a row holding 'Ankara'.
QUOTED_COMPARISON_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s*(=|!=|<>)\s*('(?:[^']|'')*')"
)

# The same thing written as a list.
QUOTED_IN_PATTERN = re.compile(
    r"([A-Za-z_][A-Za-z0-9_]*(?:\.[A-Za-z_][A-Za-z0-9_]*)?)\s+(NOT\s+IN|IN)\s*\(\s*"
    r"((?:'(?:[^']|'')*'\s*,\s*)*'(?:[^']|'')*')\s*\)",
    re.IGNORECASE,
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
                    name="allowed_tables",
                    displayName="Allowed Tables",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Tables the tool may touch. Leave empty to allow every table in the "
                        "schema."
                    ),
                    placeholder="All tables in the schema",
                    required=True,
                    default="",
                    multiple=True,
                    optionsMethod="load_tables",
                    optionsDependsOn=["credential_id", "schema_name"],
                    hint=(
                        "Naming the tables keeps the agent away from anything it has no business "
                        "reading, and shortens the description it has to work through."
                    ),
                    tabName="basic",
                ),

                # --- Permissions ------------------------------------------
                NodeProperty(
                    name="return_all",
                    displayName="Return All Rows",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return every row a read produces. Turn this off to cap the number, "
                        "which keeps a broad query from filling the agent's context."
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
                        "Include the table and column layout in the tool description. Without it "
                        "the agent has to guess the names, and usually guesses wrong."
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
                        "Replaces the generated description. Leave empty to let the node write "
                        "one from the settings above."
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
                    default=False,
                    tabName="advanced",
                ),
            ],
        }

    # ------------------------------------------------------------------
    # Connection helpers
    # ------------------------------------------------------------------

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

    def _fetch_one_column(
        self, credential_id: str, statement: str, params: tuple = ()
    ) -> List[str]:
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
        """Fill the schema dropdown."""
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
        """Fill the allowed tables dropdown."""
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
        """Read a comma separated selection into lower-cased identifiers."""
        if not raw:
            return []
        parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
        names = []
        for part in parts:
            name = str(part).strip()
            if name and IDENTIFIER_PATTERN.match(name):
                names.append(name.lower())
        return names

    @staticmethod
    def _split_statements(query: str) -> List[str]:
        """Split on semicolons, keeping only the parts that hold a statement."""
        return [part.strip() for part in query.split(";") if part.strip()]

    @staticmethod
    def _leading_keyword(statement: str) -> str:
        """Read the keyword that decides what a statement does."""
        return re.split(r"\s+", statement.strip(), maxsplit=1)[0].lower()

    def _guard_permissions(self, statement: str, granted: Set[str]) -> None:
        """Refuse a statement the tool has not been granted."""
        keyword = self._leading_keyword(statement)

        if keyword in FORBIDDEN_KEYWORDS:
            raise ValueError(
                f"'{keyword.upper()}' is never allowed through this tool. It can read and write "
                "rows, but cannot change the database structure or session state."
            )

        if keyword in READ_KEYWORDS:
            needed = "read"
        elif keyword in INSERT_KEYWORDS:
            needed = "insert"
        elif keyword in UPDATE_KEYWORDS:
            needed = "update"
        elif keyword in DELETE_KEYWORDS:
            needed = "delete"
        else:
            raise ValueError(
                f"'{keyword.upper()}' is not a statement this tool recognises. "
                "Use SELECT, INSERT, UPDATE or DELETE."
            )

        if needed not in granted:
            allowed = ", ".join(sorted(granted)) if granted else "nothing"
            raise ValueError(
                f"This tool is not allowed to {needed}. It may only: {allowed}."
            )

    @staticmethod
    def _guard_where_clause(statement: str) -> None:
        """Refuse an update or delete that would touch every row."""
        keyword = re.split(r"\s+", statement.strip(), maxsplit=1)[0].lower()
        if keyword not in {"update", "delete", "truncate"}:
            return

        if keyword == "truncate":
            raise ValueError(
                "TRUNCATE empties the whole table and cannot be filtered. "
                "Use DELETE with a WHERE clause instead."
            )

        if not re.search(r"\bwhere\b", statement, re.IGNORECASE):
            raise ValueError(
                f"A {keyword.upper()} without a WHERE clause would affect every row. "
                "Add a WHERE clause that picks out the rows you mean."
            )

    @classmethod
    def _fold_case_in_filter(cls, statement: str) -> str:
        """
        Rewrite the filter so a difference in capitalisation cannot hide a row.

        PostgreSQL compares text letter for letter, which means a filter written
        as city = 'bursa' passes over the rows holding 'Bursa' and 'BURSA'. Rows
        that should have been read, updated or deleted are then quietly missed,
        and nothing in the result says so.

        Both sides are folded to lower case instead, so every spelling matches.
        The cast to text keeps this working on columns that hold numbers, dates
        or booleans, where a comparison behaves exactly as before.

        Only the filter is touched. Values being written in a SET clause or an
        INSERT keep the capitalisation they were given.
        """
        where = re.search(r"\bwhere\b", statement, re.IGNORECASE)
        if not where:
            return statement

        head, clause = statement[: where.end()], statement[where.end() :]

        def one(match: "re.Match") -> str:
            column, operator, literal = match.group(1), match.group(2), match.group(3)
            return f"LOWER({column}::text) {operator} LOWER({literal})"

        def many(match: "re.Match") -> str:
            column, operator, literals = match.group(1), match.group(2), match.group(3)
            folded = ", ".join(
                f"LOWER({item.strip()})" for item in re.findall(r"'(?:[^']|'')*'", literals)
            )
            return f"LOWER({column}::text) {operator} ({folded})"

        clause = QUOTED_IN_PATTERN.sub(many, clause)
        clause = QUOTED_COMPARISON_PATTERN.sub(one, clause)
        return head + clause

    def _guard_allowed_tables(self, statement: str, allowed: List[str]) -> None:
        """Refuse a statement that names a table outside the allow list."""
        if not allowed:
            return

        referenced = set()
        for match in TABLE_REFERENCE_PATTERN.finditer(statement):
            # A qualified name puts the table in the second group.
            referenced.add((match.group(2) or match.group(1)).lower())

        for match in CTE_PATTERN.finditer(statement):
            referenced.discard(match.group(1).lower())

        blocked = sorted(referenced - set(allowed))
        if blocked:
            raise ValueError(
                f"This tool may only touch: {', '.join(sorted(allowed))}. "
                f"The statement named {', '.join(blocked)}."
            )

    # ------------------------------------------------------------------
    # Result shaping
    # ------------------------------------------------------------------

    @classmethod
    def _serialize(cls, value: Any, numbers_as_text: bool = False) -> Any:
        """Turn driver types into something that reads well in a reply."""
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
            return {key: cls._serialize(item, numbers_as_text) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize(item, numbers_as_text) for item in value]
        return str(value)

    @classmethod
    def _format_rows(
        cls, rows: List[Dict[str, Any]], truncated: bool, numbers_as_text: bool
    ) -> str:
        """Render rows as a compact table the model can read."""
        if not rows:
            return "The statement ran and matched no rows."

        columns = list(rows[0].keys())
        cell = lambda row, column: str(cls._serialize(row[column], numbers_as_text))

        widths = {
            column: max(len(column), *(len(cell(row, column)) for row in rows))
            for column in columns
        }

        lines = [
            " | ".join(column.ljust(widths[column]) for column in columns),
            "-+-".join("-" * widths[column] for column in columns),
        ]
        lines += [
            " | ".join(cell(row, column).ljust(widths[column]) for column in columns)
            for row in rows
        ]
        lines += ["", f"{len(rows)} row(s)."]

        if truncated:
            lines.append(
                "The result was cut short. Narrow the query or aggregate in SQL to see the rest."
            )
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Tool description
    # ------------------------------------------------------------------

    def _describe_tables(self, credential_id: str, schema: str, allowed: List[str]) -> str:
        """Summarise the table layout so the agent stops guessing column names."""
        connection = None
        try:
            connection = psycopg2.connect(
                self._build_connection_string(credential_id), connect_timeout=10
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
                        """,
                        (schema, allowed),
                    )
                else:
                    cursor.execute(
                        """
                        SELECT table_name, column_name, data_type, is_nullable
                        FROM information_schema.columns
                        WHERE table_schema = %s
                        ORDER BY table_name, ordinal_position
                        """,
                        (schema,),
                    )
                rows = cursor.fetchall()
        except Exception as exc:
            logger.warning(f"Could not describe the tables: {exc}")
            return ""
        finally:
            if connection is not None:
                connection.close()

        if not rows:
            return ""

        tables: Dict[str, List[str]] = {}
        for table_name, column_name, data_type, is_nullable in rows:
            marker = "" if is_nullable == "YES" else " NOT NULL"
            tables.setdefault(table_name, []).append(f"{column_name} {data_type}{marker}")

        lines = ["", "Tables:"]
        for table_name, columns in tables.items():
            lines.append(f"  {table_name}({', '.join(columns)})")
        return "\n".join(lines)

    def _build_description(
        self,
        custom: str,
        schema: str,
        allowed: List[str],
        granted: Set[str],
        max_rows: int,
        layout: str,
    ) -> str:
        """Write what the agent reads before deciding to call the tool."""
        if custom and custom.strip():
            return custom.strip()

        verbs = {
            "read": "read rows with SELECT",
            "insert": "add rows with INSERT",
            "update": "change rows with UPDATE",
            "delete": "remove rows with DELETE",
        }
        can_do = [verbs[name] for name in ("read", "insert", "update", "delete") if name in granted]
        scope = ", ".join(allowed) if allowed else f"any table in the {schema} schema"

        parts = [
            "Work with a PostgreSQL database by passing one complete SQL statement as the input.",
            f"You can {'; '.join(can_do)}." if can_do else "This tool currently grants nothing.",
            f"Scope: {scope}.",
            (
                f"Reads return at most {max_rows} rows, so filter and aggregate in SQL "
                f"rather than asking for everything."
                if max_rows
                else "Reads return every matching row, so keep queries narrow."
            ),
        ]

        if "update" in granted or "delete" in granted:
            parts.append(
                "An UPDATE or DELETE must carry a WHERE clause that names the rows you mean; "
                "one without a filter is refused."
            )

        parts.append(
            "Filters are matched without regard to capitalisation, so WHERE city = 'ankara' "
            "finds Ankara, ANKARA and ankara alike. Write the value however it comes to you."
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

    def execute(self, **kwargs) -> Dict[str, Any]:
        """Build the tool the agent will call."""
        credential_id = self._setting(kwargs, "credential_id", None)
        schema = str(self._setting(kwargs, "schema_name", "public")).strip() or "public"
        allowed = self._parse_list(self._setting(kwargs, "allowed_tables", ""))
        return_all = bool(self._setting(kwargs, "return_all", False))
        max_rows = 0 if return_all else int(self._setting(kwargs, "max_rows", 50))
        timeout = int(self._setting(kwargs, "statement_timeout", 15))
        describe = bool(self._setting(kwargs, "describe_schema", True))
        numbers_as_text = bool(self._setting(kwargs, "numbers_as_text", False))
        tool_name = str(self._setting(kwargs, "tool_name", "postgres_database")).strip()
        custom_description = str(self._setting(kwargs, "tool_description", "") or "")

        granted: Set[str] = set()
        if bool(self._setting(kwargs, "allow_read", True)):
            granted.add("read")
        if bool(self._setting(kwargs, "allow_insert", False)):
            granted.add("insert")
        if bool(self._setting(kwargs, "allow_update", False)):
            granted.add("update")
        if bool(self._setting(kwargs, "allow_delete", False)):
            granted.add("delete")

        if not granted:
            raise ValueError(
                "No permission is granted, so the tool would refuse every statement. "
                "Turn on at least Allow Read."
            )

        if not IDENTIFIER_PATTERN.match(tool_name):
            raise ValueError(
                f"Tool name '{tool_name}' is not usable. "
                "Use letters, digits and underscores, starting with a letter or underscore."
            )

        if not IDENTIFIER_PATTERN.match(schema):
            raise ValueError(f"Schema '{schema}' is not a valid identifier.")

        connection_string = self._build_connection_string(credential_id)

        logger.info(
            "PostgresTool ready: schema=%s tables=%s granted=%s max_rows=%s",
            schema, allowed or "all", sorted(granted), max_rows,
        )

        def run_sql(query: str) -> str:
            """Called by the agent. Returns rows as text, or an explanation."""
            query = (query or "").strip()
            if not query:
                return "No statement was supplied."

            statements = self._split_statements(query)
            if not statements:
                return "No statement was supplied."
            if len(statements) > 1:
                return (
                    "Only one statement can be run per call. "
                    "Send them one at a time so each result can be checked."
                )

            statement = statements[0]

            try:
                self._guard_permissions(statement, granted)
                self._guard_allowed_tables(statement, allowed)
                # Always enforced: a statement without a filter would rewrite or
                # empty the whole table, and the agent cannot undo that.
                self._guard_where_clause(statement)
            except ValueError as exc:
                # Returned as text so the agent can correct itself and retry.
                return f"Refused: {exc}"

            keyword = self._leading_keyword(statement)
            writes = keyword not in READ_KEYWORDS

            # Filters are matched without regard to case, so the agent does not
            # have to guess how a value was capitalised when it was stored.
            statement = self._fold_case_in_filter(statement)

            connection = None
            try:
                connection = psycopg2.connect(connection_string, connect_timeout=10)
                # A write runs inside a transaction so a failure leaves nothing behind.
                connection.autocommit = not writes

                with connection.cursor(cursor_factory=RealDictCursor) as cursor:
                    cursor.execute("SET statement_timeout = %s", (timeout * 1000,))
                    cursor.execute(f"SET search_path TO {schema}")
                    cursor.execute(statement)

                    if cursor.description is None:
                        affected = max(cursor.rowcount, 0)
                        if writes:
                            connection.commit()
                        return f"{keyword.upper()} ran. {affected} row(s) affected."

                    if max_rows:
                        # One row past the cap tells us whether anything was left behind.
                        rows = [dict(record) for record in cursor.fetchmany(max_rows + 1)]
                        truncated = len(rows) > max_rows
                        rows = rows[:max_rows]
                    else:
                        rows = [dict(record) for record in cursor.fetchall()]
                        truncated = False
                    body = self._format_rows(rows, truncated, numbers_as_text)

                if writes:
                    connection.commit()
                return body

            except psycopg2.Error as exc:
                if connection is not None and writes:
                    connection.rollback()
                message = str(exc).strip()
                logger.warning(f"PostgresTool statement failed: {message}")
                return f"The database rejected the statement: {message}"
            except Exception as exc:
                if connection is not None and writes:
                    connection.rollback()
                logger.error(f"PostgresTool failed: {exc}")
                return f"The statement could not be run: {exc}"
            finally:
                if connection is not None:
                    connection.close()

        layout = self._describe_tables(credential_id, schema, allowed) if describe else ""
        description = self._build_description(
            custom_description, schema, allowed, granted, max_rows, layout
        )

        return {
            "sql_tool": {
                "tool": Tool(name=tool_name, description=description, func=run_sql)
            }
        }

    def get_required_packages(self) -> List[str]:
        """Packages this node needs."""
        return ["psycopg2-binary>=2.9.0", "langchain-core>=0.1.0"]


__all__ = ["PostgresToolNode"]