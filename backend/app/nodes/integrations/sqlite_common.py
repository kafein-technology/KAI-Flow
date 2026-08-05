"""SQLite-only helpers shared by the SQLite action and Tool nodes.

This module intentionally has no import from the MySQL integration.  Keeping the
SQLite SQL parser and configuration helpers here means the SQLite nodes can be
installed and discovered without PyMySQL, SSH-tunnel, or MySQL node modules.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, List, Mapping, Sequence


_SUPPORTED_OPERATIONS = {"delete_table", "execute_query", "insert", "upsert", "select", "update"}
_SUPPORTED_CONDITIONS = {"=", "!=", "LIKE", ">", "<", ">=", "<=", "IS NULL", "IS NOT NULL"}
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
    if isinstance(value, dict) and {"nodeId", "success", "output"}.issubset(value):
        return value["output"]
    return value


def _connected_payload(value: Any) -> Any:
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        return value["rows"]
    return value


def _flatten_node_configuration(user_data: Any) -> Dict[str, Any]:
    if not isinstance(user_data, dict):
        return {}
    configuration = dict(user_data)
    nested_inputs = user_data.get("inputs")
    if isinstance(nested_inputs, dict):
        configuration.update(nested_inputs)
    return configuration


def _records(inputs: Mapping[str, Any], connected: Any) -> List[Dict[str, Any]]:
    if str(inputs.get("data_mode") or "auto_map") == "manual":
        value = _parse_json(inputs.get("values"), default={}, field_name="Values to Send")
    else:
        value = connected
    if isinstance(value, dict) and isinstance(value.get("rows"), list):
        value = value["rows"]
    records = value if isinstance(value, list) else [value]
    if not records or not all(isinstance(record, dict) and record for record in records):
        raise ValueError("Rows must be a JSON object or a non-empty array of objects.")
    return [dict(record) for record in records]


def _common_columns(records: Sequence[Mapping[str, Any]]) -> List[str]:
    if not records:
        raise ValueError("At least one input row is required.")
    columns = list(records[0])
    expected = set(columns)
    for record in records[1:]:
        if set(record) != expected:
            raise ValueError("All rows in an insert batch must contain the same columns.")
    return columns


def _where_clause(identifier, inputs: Mapping[str, Any]) -> tuple[str, List[Any]]:
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
        value = condition.get("value")
        if operator in {">", "<", ">=", "<="}:
            try:
                value = float(value)
            except (TypeError, ValueError) as exc:
                raise ValueError(f"Select Rows entry {index + 1} requires a numeric value.") from exc
        clause = f"{identifier(condition['column'])} {operator}"
        if operator not in {"IS NULL", "IS NOT NULL"}:
            clause += " ?"
            values.append(value)
        clauses.append(clause)
    return (f" WHERE {f' {combine} '.join(clauses)}" if clauses else ""), values


def _sort_clause(identifier, value: Any) -> str:
    rules = _parse_json(value, default=[], field_name="Sort")
    if not isinstance(rules, list):
        raise ValueError("Sort must be a JSON array.")
    parts: List[str] = []
    for index, rule in enumerate(rules):
        if not isinstance(rule, dict) or not rule.get("column"):
            raise ValueError(f"Sort entry {index + 1} must contain a column.")
        direction = str(rule.get("direction") or "ASC").upper()
        if direction not in {"ASC", "DESC"}:
            raise ValueError("Sort direction must be ASC or DESC.")
        parts.append(f"{identifier(rule['column'])} {direction}")
    return f" ORDER BY {', '.join(parts)}" if parts else ""


def _columns(qualified_identifier, value: str) -> str:
    if value.strip() == "*":
        return "*"
    columns = [column.strip() for column in value.split(",") if column.strip()]
    if not columns:
        raise ValueError("At least one output column is required.")
    return ", ".join(qualified_identifier(column) for column in columns)


def _prepare_query(qualified_identifier, query: str, parameters: Any) -> tuple[str, Sequence[Any] | Mapping[str, Any]]:
    if isinstance(parameters, dict):
        if _POSITIONAL_PARAMETER.search(query):
            raise ValueError("$1 parameters require a JSON array; use SQLite :name placeholders for an object.")
        return query, parameters
    if not isinstance(parameters, (list, tuple)):
        raise ValueError("Query Parameters must be a JSON array or object.")

    values: List[Any] = []
    pieces: List[str] = []
    last = 0
    quote: str | None = None
    index = 0
    while index < len(query):
        char = query[index]
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
                    pieces.append(qualified_identifier(parameters[parameter_index]))
                else:
                    pieces.append("?")
                    values.append(parameters[parameter_index])
                index = match.end()
                last = index
                continue
        index += 1
    pieces.append(query[last:])
    return "".join(pieces), values if values else list(parameters)


def _serializable_row(row: Mapping[str, Any], inputs: Mapping[str, Any]) -> Dict[str, Any]:
    def convert(value: Any) -> Any:
        if isinstance(value, Decimal):
            return float(value) if _as_bool(inputs.get("decimal_numbers")) else str(value)
        if isinstance(value, int) and abs(value) > _MAX_SAFE_INTEGER and str(inputs.get("large_numbers_output") or "text") == "text":
            return str(value)
        if isinstance(value, (dt.datetime, dt.date, dt.time)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray)):
            return bytes(value).hex()
        return value
    return {str(key): convert(value) for key, value in row.items()}


def _error_item(error: Exception, item_index: int) -> Dict[str, Any]:
    return {"success": False, "message": str(error), "error_type": type(error).__name__, "item_index": item_index}


# Tool-only safety helpers.  These intentionally parse SQLite syntax rather than MySQL syntax.
_READ_COMMANDS = {"SELECT", "EXPLAIN"}
_SQLITE_TABLE_REFERENCE = re.compile(
    r"\b(?:FROM|JOIN|INTO|UPDATE)\s+((?:\"[^\"]+\"|`[^`]+`|[A-Za-z0-9_$]+)(?:\.(?:\"[^\"]+\"|`[^`]+`|[A-Za-z0-9_$]+))?)",
    re.IGNORECASE,
)


def _allowed_commands(configuration: Mapping[str, Any]):
    commands = set()
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


def _mask_sqlite_strings(statement: str) -> str:
    output: List[str] = []
    quote = False
    index = 0
    while index < len(statement):
        char = statement[index]
        if quote:
            output.append(" ")
            if char == "'":
                if index + 1 < len(statement) and statement[index + 1] == "'":
                    output.append(" ")
                    index += 1
                else:
                    quote = False
        elif char == "'":
            quote = True
            output.append(" ")
        else:
            output.append(char)
        index += 1
    return "".join(output)


def _strip_code_fence(query: str) -> str:
    value = str(query or "").strip()
    match = re.fullmatch(r"```(?:sql)?\s*(.*?)\s*```", value, flags=re.IGNORECASE | re.DOTALL)
    return match.group(1).strip() if match else value


def _validate_single_statement(statement: str) -> str:
    quote: str | None = None
    semicolons: List[int] = []
    index = 0
    while index < len(statement):
        char = statement[index]
        next_char = statement[index + 1] if index + 1 < len(statement) else ""
        if quote:
            if char == quote:
                if next_char == quote:
                    index += 1
                else:
                    quote = None
        elif char in {"'", '"', "`"}:
            quote = char
        elif (char == "-" and next_char == "-") or (char == "/" and next_char == "*"):
            raise ValueError("SQL comments are disabled for SQLite Tool queries.")
        elif char == ";":
            semicolons.append(index)
        index += 1
    if quote:
        raise ValueError("The SQL query contains an unterminated quoted value.")
    if semicolons:
        final_non_space = len(statement.rstrip()) - 1
        if len(semicolons) > 1 or semicolons[0] != final_non_space:
            raise ValueError("SQLite Tool accepts exactly one SQL statement per call.")
        statement = statement[:semicolons[0]].rstrip()
    if not statement:
        raise ValueError("Provide a SQL query.")
    return statement


def _statement_command(statement: str) -> str:
    masked = _mask_sqlite_strings(statement)
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


def _requires_where_clause(statement: str) -> bool:
    return bool(re.search(r"\bWHERE\b", _mask_sqlite_strings(statement), re.IGNORECASE))


def _normalized_allowed_tables(value: Any):
    parts = value if isinstance(value, list) else str(value or "").split(",")
    return {str(part).strip().strip("`").strip('"').lower() for part in parts if str(part).strip()}


def _referenced_tables(statement: str):
    masked = _mask_sqlite_strings(statement)
    cte_aliases = {
        match.group(1).replace("`", "").replace('"', "").lower()
        for match in re.finditer(r"(?:\bWITH\b|,)\s*(\"[^\"]+\"|`[^`]+`|[A-Za-z0-9_$]+)(?:\s*\([^)]*\))?\s+AS\s*\(", masked, re.IGNORECASE)
    }
    tables = set()
    for match in _SQLITE_TABLE_REFERENCE.finditer(masked):
        raw = match.group(1).replace("`", "").replace('"', "").lower()
        if raw not in cte_aliases:
            tables.add(raw)
            tables.add(raw.rsplit(".", 1)[-1])
    return tables


_TEXT_PREDICATE = re.compile(
    r"((?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*)(?:\.(?:\"[^\"]+\"|`[^`]+`|[A-Za-z_][A-Za-z0-9_$]*))?)\s*(<>|!=|=|(?:NOT\s+)?LIKE)\s*('(?:''|[^'])*')",
    re.IGNORECASE,
)
_DATE_LIKE = re.compile(r"^\d{4}-\d{2}-\d{2}([ T]\d{2}:\d{2}(:\d{2})?)?$")


def _case_insensitive_predicates(statement: str) -> str:
    masked = _mask_sqlite_strings(statement)
    where = re.search(r"\bWHERE\b", masked, re.IGNORECASE)
    if not where:
        return statement
    prefix = statement[:where.end()]
    predicate = statement[where.end():]

    def replace(match: re.Match[str]) -> str:
        literal = match.group(3)
        body = literal[1:-1]
        if _DATE_LIKE.match(body.strip()) or not any(char.isalpha() for char in body):
            return match.group(0)
        return f"LOWER({match.group(1)}) {match.group(2)} LOWER({literal})"

    return prefix + _TEXT_PREDICATE.sub(replace, predicate)
