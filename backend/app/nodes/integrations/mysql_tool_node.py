"""Security-scoped MySQL tool provider for AI agents."""

from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Set

from langchain_core.tools import Tool

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProviderNode,
)
from .mysql_node import _as_bool, _credential_secret, _flatten_node_configuration, mysql_connection


_READ_COMMANDS: Set[str] = {"SHOW", "DESCRIBE", "DESC", "EXPLAIN", "SELECT"}

_WHERE_CLAUSE = re.compile(r"\bWHERE\b", re.IGNORECASE)


def _allowed_commands(configuration: Mapping[str, Any]) -> Set[str]:
    """Build the allowed SQL command set from the per-operation permission toggles."""
    commands: Set[str] = set()
    allow_insert = _as_bool(configuration.get("allow_insert", False))
    allow_delete = _as_bool(configuration.get("allow_delete", False))
    if _as_bool(configuration.get("allow_read", True)):
        commands |= _READ_COMMANDS
    if allow_insert:
        commands.add("INSERT")
    if _as_bool(configuration.get("allow_update", False)):
        commands.add("UPDATE")
    if allow_delete:
        commands.add("DELETE")
    if allow_insert and allow_delete:
        commands.add("REPLACE")
    return commands


def _requires_where_clause(statement: str) -> bool:
    return bool(_WHERE_CLAUSE.search(_mask_string_literals(statement)))


_TABLE_REFERENCE = re.compile(
    r"\b(?:(?:FROM|JOIN|INTO|UPDATE)\s+|TABLE\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?)"
    r"((?:`[^`]+`|[A-Za-z0-9_$]+)(?:\.(?:`[^`]+`|[A-Za-z0-9_$]+))?)",
    re.IGNORECASE,
)


def _strip_code_fence(query: str) -> str:
    value = str(query or "").strip()
    match = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else value


def _validate_single_statement(statement: str) -> str:
    """Reject comments and stacked SQL while respecting quoted string contents."""
    quote: str | None = None
    escaped = False
    semicolons: List[int] = []
    index = 0
    while index < len(statement):
        char = statement[index]
        next_char = statement[index + 1] if index + 1 < len(statement) else ""
        if escaped:
            escaped = False
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                if next_char == quote:
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif (char == "-" and next_char == "-") or char == "#" or (char == "/" and next_char == "*"):
            raise ValueError("SQL comments are disabled for MySQL Tool queries.")
        elif char == ";":
            semicolons.append(index)
        index += 1

    if quote:
        raise ValueError("The SQL query contains an unterminated quoted value.")
    if semicolons:
        final_non_space = len(statement.rstrip()) - 1
        if len(semicolons) > 1 or semicolons[0] != final_non_space:
            raise ValueError("MySQL Tool accepts exactly one SQL statement per call.")
        statement = statement[:semicolons[0]].rstrip()
    if not statement:
        raise ValueError("Provide a SQL query.")
    return statement


def _mask_quoted_sql(statement: str) -> str:
    output: List[str] = []
    quote: str | None = None
    escaped = False
    for char in statement:
        if escaped:
            escaped = False
            output.append(" ")
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            output.append(" ")
        elif char in {"'", '"', "`"}:
            quote = char
            output.append(" ")
        else:
            output.append(char)
    return "".join(output)


def _mask_string_literals(statement: str) -> str:
    """Mask string literals while preserving backtick-quoted identifiers."""
    output: List[str] = []
    quote: str | None = None
    escaped = False
    for char in statement:
        if escaped:
            escaped = False
            output.append(" ")
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                quote = None
            output.append(" ")
        elif char in {"'", '"'}:
            quote = char
            output.append(" ")
        else:
            output.append(char)
    return "".join(output)


def _string_literal_spans(statement: str) -> List[tuple[int, int]]:
    """Return the (start, end) offsets of every single/double quoted literal."""
    spans: List[tuple[int, int]] = []
    quote: str | None = None
    escaped = False
    start = 0
    index = 0
    while index < len(statement):
        char = statement[index]
        if escaped:
            escaped = False
        elif quote:
            if char == "\\":
                escaped = True
            elif char == quote:
                if index + 1 < len(statement) and statement[index + 1] == quote:
                    index += 1
                else:
                    if quote != "`":
                        spans.append((start, index + 1))
                    quote = None
        elif char in {"'", '"', "`"}:
            quote = char
            start = index
        index += 1
    return spans


_DATE_LIKE = re.compile(r"^'?\s*\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?\s*'?$")
_COMPARISON_TARGET = re.compile(
    r"((?:`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*)(?:\.(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*))?)"
    r"\s*(<>|!=|=|(?:NOT\s+)?LIKE)\s*$",
    re.IGNORECASE,
)
_IN_TARGET = re.compile(
    r"((?:`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*)(?:\.(?:`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*))?)"
    r"\s+(NOT\s+)?IN\s*\($",
    re.IGNORECASE,
)


def _is_text_literal(literal: str) -> bool:
    """Only rewrite literals that carry letters and are not dates, so date and
    numeric comparisons keep MySQL's own type handling."""
    body = literal[1:-1] if len(literal) >= 2 else literal
    if _DATE_LIKE.match(body.strip()):
        return False
    return any(char.isalpha() for char in body)


def _case_insensitive_predicates(statement: str) -> str:
    """Make text comparisons in the WHERE clause ignore letter case.

    Only the predicate part is rewritten: an `UPDATE ... SET city = 'Bursa'`
    assignment must stay untouched, while `WHERE city = 'ankara'` has to match
    'Ankara' and 'ANKARA' as well, whatever collation the column was created with.
    """
    masked = _mask_string_literals(statement)
    where = _WHERE_CLAUSE.search(masked)
    if not where:
        return statement

    spans = [span for span in _string_literal_spans(statement) if span[0] >= where.end()]
    edits: List[tuple[int, int, str]] = []
    consumed: Set[int] = set()

    for start, end in spans:
        if start in consumed:
            continue
        literal = statement[start:end]

        comparison = _COMPARISON_TARGET.search(masked[:start])
        if comparison and _is_text_literal(literal):
            column = statement[comparison.start(1):comparison.end(1)]
            operator = statement[comparison.start(2):comparison.end(2)]
            edits.append((comparison.start(1), end, f"LOWER({column}) {operator} LOWER({literal})"))
            continue

        in_clause = _IN_TARGET.search(masked[:start])
        if not in_clause:
            continue
        closing = masked.find(")", start)
        if closing == -1:
            continue
        items = [span for span in spans if start <= span[0] and span[1] <= closing]
        remainder = masked[in_clause.end():closing]
        for item_start, item_end in items:
            offset = in_clause.end()
            remainder = remainder[:item_start - offset] + " " * (item_end - item_start) + remainder[item_end - offset:]
        if remainder.strip(" ,") or not any(_is_text_literal(statement[s:e]) for s, e in items):
            continue
        column = statement[in_clause.start(1):in_clause.end(1)]
        negation = "NOT " if in_clause.group(2) else ""
        values = ", ".join(f"LOWER({statement[s:e]})" for s, e in items)
        edits.append((in_clause.start(1), closing + 1, f"LOWER({column}) {negation}IN ({values})"))
        consumed.update(item[0] for item in items)

    for edit_start, edit_end, replacement in reversed(edits):
        statement = statement[:edit_start] + replacement + statement[edit_end:]
    return statement


def _statement_command(statement: str) -> str:
    """Return the effective command, including the command following a WITH CTE."""
    masked = _mask_quoted_sql(statement)
    first = re.match(r"\s*([A-Za-z]+)", masked)
    if not first:
        raise ValueError("Unable to determine the SQL command.")
    command = first.group(1).upper()
    if command != "WITH":
        return command

    depth = 0
    for match in re.finditer(r"[A-Za-z_]+|[()]", masked[first.end():]):
        token = match.group(0).upper()
        if token == "(":
            depth += 1
        elif token == ")":
            depth = max(0, depth - 1)
        elif depth == 0 and token in {"SELECT", "INSERT", "UPDATE", "DELETE", "REPLACE"}:
            return token
    raise ValueError("Unable to determine the command following WITH.")


def _normalized_allowed_tables(value: Any) -> Set[str]:
    if isinstance(value, list):
        parts = value
    else:
        parts = str(value or "").split(",")
    return {str(part).strip().strip("`").lower() for part in parts if str(part).strip()}


def _referenced_tables(statement: str) -> Set[str]:
    tables: Set[str] = set()
    masked = _mask_string_literals(statement)
    cte_aliases = {
        match.group(1).replace("`", "").lower()
        for match in re.finditer(r"(?:\bWITH\b|,)\s*(`[^`]+`|[A-Za-z0-9_$]+)(?:\s*\([^)]*\))?\s+AS\s*\(", masked, re.IGNORECASE)
    }
    for match in _TABLE_REFERENCE.finditer(masked):
        raw = match.group(1).replace("`", "").lower()
        if raw not in {"select", "set"} and raw not in cte_aliases:
            tables.add(raw)
            tables.add(raw.rsplit(".", 1)[-1])
    index_target = re.search(r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b.*?\bON\s+(`[^`]+`|[A-Za-z0-9_$]+)", masked, re.IGNORECASE | re.DOTALL)
    if index_target:
        tables.add(index_target.group(1).replace("`", "").lower())
    return tables


class MySQLToolNode(ProviderNode):
    """Provide a single-statement, permission-scoped MySQL tool to an Agent."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "MySQLTool",
            "display_name": "MySQL Tool",
            "description": "Give an Agent explicitly scoped access to a MySQL database.",
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {"name": "mysql", "path": "icons/mysql.svg", "alt": "MySQL Tool"},
            "colors": ["cyan-700", "blue-900"],
            "version": "1.0.0",
            "inputs": [
                NodeInput(name="credential_id", type="str", description="Selected MySQL credential ID.", required=True),
                NodeInput(name="allowed_tables", type="str", description="Optional table allowlist.", default="", required=False),
                NodeInput(name="return_all_rows", type="bool", description="Ignore max_rows and return every matching row.", default=False, required=False),
                NodeInput(name="max_rows", type="int", description="Maximum returned rows.", default=200, required=False),
                NodeInput(name="allow_read", type="bool", description="Allow SELECT and schema inspection commands.", default=True, required=False),
                NodeInput(name="allow_insert", type="bool", description="Allow INSERT statements.", default=False, required=False),
                NodeInput(name="allow_update", type="bool", description="Allow UPDATE statements.", default=False, required=False),
                NodeInput(name="allow_delete", type="bool", description="Allow DELETE statements.", default=False, required=False),
                NodeInput(name="tool_name", type="str", description="Name exposed to the Agent.", default="mysql_database", required=False),
                NodeInput(name="connection_timeout_ms", type="int", description="Connection timeout in milliseconds.", default=30000, required=False),
            ],
            "outputs": [
                NodeOutput(
                    name="tool",
                    displayName="Tool",
                    type="BaseTool",
                    description="Permission-scoped MySQL tool for an Agent's Tools input.",
                    is_connection=True,
                    direction=NodePosition.TOP,
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id", displayName="Credential", type=NodePropertyType.CREDENTIAL_SELECT,
                    serviceType="mysql", required=True, description="MySQL credential used only by this tool."
                ),
                NodeProperty(
                    name="allowed_tables", displayName="Allowed Tables", type=NodePropertyType.TEXT,
                    placeholder="customers, orders", required=False,
                    description="Optional allowlist. Leave empty to allow all tables permitted by the database user."
                ),
                NodeProperty(
                    name="return_all_rows", displayName="Return All Rows", type=NodePropertyType.CHECKBOX,
                    default=False, required=False,
                    description="Ignore the row limit below and return every matching row (up to a hard safety ceiling)."
                ),
                NodeProperty(
                    name="max_rows", displayName="Maximum Rows", type=NodePropertyType.NUMBER,
                    default=200, min=1, max=5000, required=False,
                    description="Stops returning rows after this limit to protect Agent context and memory."
                ),
                NodeProperty(
                    name="allow_read", displayName="Allow Read", type=NodePropertyType.CHECKBOX,
                    default=True, required=False,
                    description="Allow SELECT and schema inspection commands (SHOW, DESCRIBE, EXPLAIN)."
                ),
                NodeProperty(
                    name="allow_insert", displayName="Allow Insert", type=NodePropertyType.CHECKBOX,
                    default=False, required=False,
                    description="Allow INSERT statements."
                ),
                NodeProperty(
                    name="allow_update", displayName="Allow Update", type=NodePropertyType.CHECKBOX,
                    default=False, required=False,
                    description="Allow UPDATE statements."
                ),
                NodeProperty(
                    name="allow_delete", displayName="Allow Delete", type=NodePropertyType.CHECKBOX,
                    default=False, required=False,
                    description="Allow DELETE statements (and REPLACE, when Insert is also allowed)."
                ),
                NodeProperty(
                    name="tool_name", displayName="Tool Name", type=NodePropertyType.TEXT,
                    default="mysql_database", required=False, tabName="options",
                    description="Stable name exposed to the Agent."
                ),
                NodeProperty(
                    name="connection_timeout_ms", displayName="Connection Timeout (ms)", type=NodePropertyType.NUMBER,
                    default=30000, min=1000, max=300000, required=False, tabName="options"
                ),
            ],
        }

    def get_required_packages(self) -> List[str]:
        return ["PyMySQL>=1.1.1,<2.0.0", "sshtunnel>=0.4.0,<1.0.0", "paramiko>=2.7.2,<4.0.0"]

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        configuration = {**_flatten_node_configuration(self.user_data), **kwargs}
        secret = _credential_secret(self, configuration.get("credential_id"))
        allowed_commands = _allowed_commands(configuration)
        allowed_tables = _normalized_allowed_tables(configuration.get("allowed_tables"))
        return_all_rows = _as_bool(configuration.get("return_all_rows", False))
        max_rows = 50000 if return_all_rows else min(5000, max(1, int(configuration.get("max_rows") or 200)))
        raw_name = str(configuration.get("tool_name") or "mysql_database").strip()
        tool_name = re.sub(r"[^a-zA-Z0-9_-]", "_", raw_name) or "mysql_database"

        def run_query(query: str) -> str:
            try:
                statement = _validate_single_statement(_strip_code_fence(query))
                command = _statement_command(statement)
                if command not in allowed_commands:
                    return json.dumps({
                        "error": f"{command} is not allowed by the current permission settings."
                    })
                # Untargeted writes are always refused: a missing WHERE clause
                # would rewrite or erase every row in the table.
                if command in {"UPDATE", "DELETE"} and not _requires_where_clause(statement):
                    return json.dumps({
                        "error": f"{command} statements must include a WHERE clause that selects the rows to change."
                    })

                if allowed_tables:
                    referenced = _referenced_tables(statement)
                    unauthorized = sorted(
                        table for table in referenced
                        if table not in allowed_tables and table.rsplit(".", 1)[-1] not in allowed_tables
                    )
                    if unauthorized:
                        return json.dumps({"error": f"Table access denied: {', '.join(unauthorized)}"})
                    # When a table allowlist exists, never run a statement whose
                    # table scope cannot be proven. This also prevents SHOW TABLES
                    # and similar metadata queries from revealing unlisted tables.
                    if command != "SET" and not referenced:
                        return json.dumps({"error": "Could not verify table access for this query."})

                statement = _case_insensitive_predicates(statement)

                rows: List[Dict[str, Any]] = []
                affected_rows = 0
                last_insert_id = None
                truncated = False
                with mysql_connection(secret, configuration) as connection:
                    try:
                        with connection.cursor() as cursor:
                            cursor.execute(statement)
                            if cursor.description:
                                fetched = list(cursor.fetchmany(max_rows + 1))
                                truncated = len(fetched) > max_rows
                                rows = [self._serialize_row(row) for row in fetched[:max_rows]]
                            affected_rows = max(0, int(cursor.rowcount or 0))
                            last_insert_id = int(cursor.lastrowid) if cursor.lastrowid else None
                        connection.commit()
                    except Exception:
                        connection.rollback()
                        raise

                return json.dumps({
                    "rows": rows,
                    "row_count": len(rows),
                    "truncated": truncated,
                    "max_rows": max_rows,
                    "affected_rows": affected_rows,
                    "last_insert_id": last_insert_id,
                }, ensure_ascii=False, default=str)
            except Exception as exc:
                return json.dumps({"error": str(exc)}, ensure_ascii=False)

        permission_text = ", ".join(sorted(allowed_commands)) or "none"
        table_text = ", ".join(sorted(allowed_tables)) if allowed_tables else "all credential-visible tables"
        tool = Tool(
            name=tool_name,
            func=run_query,
            description=(
                f"Run one SQL statement against MySQL database '{secret.get('database') or 'default'}'. "
                f"Allowed commands: {permission_text}. Allowed tables: {table_text}. "
                "If the schema is unknown, inspect it before querying. Never invent table or column names. "
                "UPDATE and DELETE always require a WHERE clause that selects the rows to change. "
                "Text values in the WHERE clause are matched case-insensitively, so 'ankara' also matches 'Ankara'. "
                f"Return at most {max_rows} rows and prefer selective WHERE clauses."
            ),
        )
        return {"mysql_database": {"tool": tool}}

    @staticmethod
    def _serialize_row(row: Mapping[str, Any]) -> Dict[str, Any]:
        serialized: Dict[str, Any] = {}
        for key, value in row.items():
            if isinstance(value, Decimal):
                serialized[key] = str(value)
            elif isinstance(value, (bytes, bytearray)):
                serialized[key] = bytes(value).hex()
            else:
                serialized[key] = value
        return serialized
