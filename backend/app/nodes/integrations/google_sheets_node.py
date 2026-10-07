"""Bounded Google Sheets workflow operations."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Mapping, Sequence

import httplib2
from google.oauth2.credentials import Credentials
from google.oauth2.service_account import Credentials as ServiceAccountCredentials
from google_auth_httplib2 import AuthorizedHttp
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from ..base import (
    NodeInput,
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProcessorNode,
)


_DEFAULT_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive.file",
]
_DOCUMENT_ID = re.compile(r"/spreadsheets/d/([A-Za-z0-9_-]+)")
_SHEET_ID = re.compile(r"(?:[?#&]gid=)(\d+)")
_A1_RANGE = re.compile(
    r"(?:[A-Za-z]+\d+(?::[A-Za-z]+\d+)?|[A-Za-z]+:[A-Za-z]+|\d+:\d+)"
)
_SUPPORTED_OPERATIONS = {
    "add_columns",
    "append",
    "append_or_update",
    "clear",
    "create_chart",
    "create_document",
    "create_sheet",
    "delete_document",
    "delete_rows_columns",
    "delete_sheet",
    "format_sheet",
    "get_rows",
    "update",
}
_MAX_READ_ROWS = 10_000
_MAX_WRITE_ROWS = 1_000
_MAX_COLUMNS = 500
_SCHEMA_VERSION = "kai.google_sheets.result.v1"

logger = logging.getLogger(__name__)


def _as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _parse_json(value: Any, *, default: Any, field_name: str) -> Any:
    if value is None or value == "":
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must contain valid JSON: {exc.msg}") from exc


def _bounded_int(
    value: Any,
    *,
    field_name: str,
    default: int,
    minimum: int,
    maximum: int,
) -> int:
    if value in (None, ""):
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field_name} must be a whole number.") from exc
    if parsed < minimum or parsed > maximum:
        raise ValueError(
            f"{field_name} must be between {minimum} and {maximum}."
        )
    return parsed


def _required_text(value: Any, *, field_name: str, max_length: int) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError(f"{field_name} is required.")
    if len(text) > max_length:
        raise ValueError(f"{field_name} must be at most {max_length} characters.")
    return text


def _google_error(exc: Exception) -> str:
    """Return a stable error without exposing tokens or credential contents."""
    if isinstance(exc, ValueError):
        return str(exc)
    if isinstance(exc, HttpError):
        status = getattr(exc.resp, "status", None)
        if status in {401, 403}:
            return (
                "Google rejected the request. Verify the credential, OAuth scopes, "
                "API enablement, and spreadsheet sharing permissions."
            )
        if status == 404:
            return "The requested spreadsheet, sheet, or Google Drive file was not found."
        if status == 429:
            return "Google Sheets quota was exceeded. Retry after the quota window resets."
        if status and status >= 500:
            return "Google Sheets is temporarily unavailable. Try again later."
        return f"Google Sheets request failed (HTTP {status or 'unknown'})."
    if isinstance(exc, TimeoutError):
        return "Google Sheets request timed out."
    return "Google Sheets request failed. Check the credential and node configuration."


def _build_google_service(
    api: str,
    version: str,
    credentials: Any,
    timeout_seconds: int,
) -> Any:
    http = AuthorizedHttp(
        credentials,
        http=httplib2.Http(timeout=timeout_seconds),
    )
    return build(api, version, http=http, cache_discovery=False)


def _configuration(user_data: Any, inputs: Mapping[str, Any]) -> Dict[str, Any]:
    result = dict(user_data) if isinstance(user_data, dict) else {}
    if isinstance(result.get("inputs"), dict):
        result.update(result["inputs"])
    result.update(inputs)
    return result


def _unwrap_connected(value: Any) -> Any:
    while isinstance(value, dict) and {"nodeId", "success", "output"}.issubset(value):
        value = value["output"]
    return value


def _credential_secret(node: ProcessorNode, credential_id: Any) -> Dict[str, Any]:
    if not credential_id:
        raise ValueError("A Google Sheets credential must be selected.")
    credential = node.get_credential(str(credential_id))
    if not credential:
        raise ValueError("The selected Google Sheets credential could not be found.")
    if credential.get("service_type") != "google_sheets":
        raise ValueError("The selected credential is not a Google Sheets credential.")
    secret = credential.get("secret") or {}
    if not isinstance(secret, dict):
        raise ValueError("The selected Google Sheets credential has an invalid secret payload.")
    return secret


def _scopes(secret: Mapping[str, Any]) -> List[str]:
    if not _as_bool(secret.get("custom_scopes")):
        return list(_DEFAULT_SCOPES)
    value = secret.get("enabled_scopes") or secret.get("scopes") or ""
    scopes = list(dict.fromkeys(item for item in re.split(r"[\s,]+", str(value)) if item))
    if not scopes:
        raise ValueError("Enabled Scopes is required when Custom Scopes is enabled.")
    if any(not item.startswith("https://www.googleapis.com/auth/") for item in scopes):
        raise ValueError("Enabled Scopes may only contain Google API OAuth scopes.")
    return scopes


def _google_credentials(secret: Mapping[str, Any]):
    auth_type = str(secret.get("authentication") or "oauth2").lower()
    if auth_type not in {"oauth2", "service_account", "serviceaccount"}:
        raise ValueError("Authentication must be OAuth2 or Service Account.")
    scopes = _scopes(secret)
    if auth_type in {"service_account", "serviceaccount"}:
        email = secret.get("service_account_email") or secret.get("client_email")
        private_key = secret.get("private_key")
        if not email or not private_key:
            raise ValueError("The Google Sheets service account credential requires email and private key.")
        info = {
            "type": "service_account",
            "project_id": secret.get("project_id") or "",
            "private_key_id": secret.get("private_key_id") or "",
            "private_key": str(private_key).replace("\\n", "\n"),
            "client_email": email,
            "client_id": secret.get("client_id") or "",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": secret.get("client_x509_cert_url") or "",
        }
        credentials = ServiceAccountCredentials.from_service_account_info(info, scopes=scopes)
        delegated_user = str(secret.get("delegated_user") or "").strip()
        return credentials.with_subject(delegated_user) if delegated_user else credentials

    missing = [key for key in ("client_id", "client_secret", "refresh_token") if not secret.get(key)]
    if missing:
        raise ValueError(f"The Google Sheets OAuth2 credential is missing: {', '.join(missing)}.")
    return Credentials(
        token=secret.get("access_token") or None,
        refresh_token=secret["refresh_token"],
        token_uri=str(secret.get("token_uri") or "https://oauth2.googleapis.com/token"),
        client_id=secret["client_id"],
        client_secret=secret["client_secret"],
        scopes=scopes,
    )


def _document_id(value: Any) -> str:
    raw = str(value or "").strip()
    match = _DOCUMENT_ID.search(raw)
    document_id = match.group(1) if match else raw
    if not re.fullmatch(r"[A-Za-z0-9_-]{2,256}", document_id):
        raise ValueError("Document must be a valid Google Sheets URL or spreadsheet ID.")
    return document_id


def _quote_sheet(title: str) -> str:
    return "'" + title.replace("'", "''") + "'"


def _column_number(column: str) -> int:
    value = str(column).strip().upper()
    if not re.fullmatch(r"[A-Z]+", value):
        raise ValueError("Start Column must use A1 letter notation, such as A or BC.")
    number = 0
    for character in value:
        number = number * 26 + ord(character) - 64
    return number


def _column_name(number: int) -> str:
    result = ""
    while number:
        number, remainder = divmod(number - 1, 26)
        result = chr(65 + remainder) + result
    return result or "A"


def _hex_color(value: Any, fallback: str = "#FFFFFF") -> Dict[str, float]:
    """Convert a CSS-style hex color to the Google Sheets RGB color shape."""
    text = str(value or fallback).strip().lstrip("#")
    if len(text) == 3:
        text = "".join(character * 2 for character in text)
    if not re.fullmatch(r"[0-9a-fA-F]{6}", text):
        raise ValueError("Colors must be six-digit hex values such as #D9EAF7.")
    return {
        "red": int(text[0:2], 16) / 255,
        "green": int(text[2:4], 16) / 255,
        "blue": int(text[4:6], 16) / 255,
    }


def _a1_grid_range(value: Any, sheet_id: int, default_end_row: int, default_end_column: int) -> Dict[str, Any]:
    """Convert a simple A1 range (for example A1:D20) to a GridRange."""
    text = str(value or "").strip()
    if "!" in text:
        text = text.rsplit("!", 1)[1]
    match = re.fullmatch(r"([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?", text)
    if not match:
        raise ValueError("Chart Data Range must use A1 notation, such as A1:D20.")
    start_column = _column_number(match.group(1)) - 1
    start_row = max(0, int(match.group(2)) - 1)
    end_column = _column_number(match.group(3) or match.group(1))
    end_row = int(match.group(4)) if match.group(4) else default_end_row
    if end_row <= start_row or end_column <= start_column:
        raise ValueError("Chart Data Range must end after its starting cell.")
    if end_row > _MAX_READ_ROWS + 1 or end_column > _MAX_COLUMNS:
        raise ValueError(
            f"Chart Data Range may contain at most {_MAX_READ_ROWS} data rows "
            f"and {_MAX_COLUMNS} columns."
        )
    return {
        "sheetId": sheet_id,
        "startRowIndex": start_row,
        "endRowIndex": max(start_row + 1, end_row),
        "startColumnIndex": start_column,
        "endColumnIndex": max(start_column + 1, end_column),
    }


class GoogleSheetsNode(ProcessorNode):
    """Read and mutate Google Sheets documents through the Google API."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "GoogleSheets",
            "display_name": "Google Sheets",
            "description": "Read, update, and write data to Google Sheets.",
            "category": "Integration",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "google-sheets", "path": "icons/google-sheets.svg", "alt": "Google Sheets"},
            "colors": ["green-500", "emerald-700"],
            "version": "1.0.0",
            "documentation_url": "https://developers.google.com/workspace/sheets/api/guides/concepts",
            "inputs": [NodeInput(
                name="input", displayName="Input", type="any",
                description="Rows or values supplied by an upstream workflow node.",
                required=False, is_connection=True, direction=NodePosition.LEFT,
            )],
            "outputs": [NodeOutput(
                name="output", displayName="Output", type="any",
                description="Google Sheets rows or operation metadata.",
                is_connection=True, direction=NodePosition.RIGHT,
            )],
            "properties": self._properties(),
        }

    @staticmethod
    def _properties() -> List[NodeProperty]:
        def show(*operations: str) -> Dict[str, Any]:
            expected: Any = operations[0] if len(operations) == 1 else list(operations)
            return {"show": {"operation": expected}}

        document_operations = tuple(sorted(_SUPPORTED_OPERATIONS - {"create_document"}))
        sheet_operations = tuple(
            sorted(
                _SUPPORTED_OPERATIONS
                - {"create_document", "delete_document", "create_sheet"}
            )
        )
        row_write_operations = ("append", "append_or_update", "update")
        table_operations = (
            "append",
            "append_or_update",
            "format_sheet",
            "get_rows",
            "update",
        )
        return [
            NodeProperty(name="credential_id", displayName="Credential",
                         type=NodePropertyType.CREDENTIAL_SELECT, serviceType="google_sheets",
                         description="Google Sheets OAuth2 or Service Account credential.", required=True),
            NodeProperty(name="operation", displayName="Operation", type=NodePropertyType.SELECT,
                         description="Choose the Google Sheets action to execute.", default="get_rows", required=True,
                         options=[
                             {"label": "Document: Create", "value": "create_document"},
                             {"label": "Document: Delete", "value": "delete_document"},
                             {"label": "Sheet: Append or Update Row", "value": "append_or_update"},
                             {"label": "Sheet: Append Row", "value": "append"},
                             {"label": "Sheet: Add Columns", "value": "add_columns"},
                             {"label": "Sheet: Format", "value": "format_sheet"},
                             {"label": "Sheet: Create Chart", "value": "create_chart"},
                             {"label": "Sheet: Clear", "value": "clear"},
                             {"label": "Sheet: Create", "value": "create_sheet"},
                             {"label": "Sheet: Delete", "value": "delete_sheet"},
                             {"label": "Sheet: Delete Rows or Columns", "value": "delete_rows_columns"},
                             {"label": "Sheet: Get Row(s)", "value": "get_rows"},
                             {"label": "Sheet: Update Row", "value": "update"},
                         ]),
            NodeProperty(name="document_id", displayName="Document", type=NodePropertyType.TEXT,
                         description="Google spreadsheet URL or spreadsheet ID.",
                         placeholder="https://docs.google.com/spreadsheets/d/.../edit",
                         displayOptions=show(*document_operations), required=True),
            NodeProperty(name="document_title", displayName="Title", type=NodePropertyType.TEXT,
                         description="Title for the new spreadsheet.", default="Untitled spreadsheet",
                         displayOptions=show("create_document"), required=True),
            NodeProperty(name="sheet", displayName="Sheet", type=NodePropertyType.TEXT,
                         description="Sheet URL, numeric sheet ID, or exact sheet name.",
                         placeholder="Sheet1", displayOptions=show(*sheet_operations), required=True),
            NodeProperty(name="new_sheet_title", displayName="Title", type=NodePropertyType.TEXT,
                         description="Title for the new sheet.", default="Sheet1",
                         displayOptions=show("create_sheet"), required=True),
            NodeProperty(name="columns", displayName="Columns", type=NodePropertyType.JSON_EDITOR,
                         description="Column headings to append to the first row, for example [\"Name\", \"Status\"].",
                         default="[]", displayOptions=show("add_columns"), required=True),
            NodeProperty(name="header_background_color", displayName="Header Color", type=NodePropertyType.TEXT,
                         description="Header background as a six-digit hex color.", default="#D9EAF7",
                         displayOptions=show("format_sheet"), required=True),
            NodeProperty(name="header_text_color", displayName="Header Text Color", type=NodePropertyType.TEXT,
                         description="Header text color as a six-digit hex color.", default="#12355B",
                         displayOptions=show("format_sheet"), required=True),
            NodeProperty(name="body_background_color", displayName="Body Color", type=NodePropertyType.TEXT,
                         description="Optional body background as a six-digit hex color.", default="#FFFFFF",
                         displayOptions=show("format_sheet"), required=False),
            NodeProperty(name="body_text_color", displayName="Body Text Color", type=NodePropertyType.TEXT,
                         description="Optional body text color as a six-digit hex color.", default="#222222",
                         displayOptions=show("format_sheet"), required=False),
            NodeProperty(name="bold_headers", displayName="Bold Headers", type=NodePropertyType.CHECKBOX,
                         description="Make the first row bold.", default=True,
                         displayOptions=show("format_sheet"), required=False),
            NodeProperty(name="chart_type", displayName="Chart Type", type=NodePropertyType.SELECT,
                         description="Chart type for the selected data range.", default="PIE",
                         options=[
                             {"label": "Pie", "value": "PIE"},
                             {"label": "Column", "value": "COLUMN"},
                             {"label": "Bar", "value": "BAR"},
                             {"label": "Line", "value": "LINE"},
                         ], displayOptions=show("create_chart"), required=True),
            NodeProperty(name="chart_title", displayName="Chart Title", type=NodePropertyType.TEXT,
                         description="Title shown above the chart.", default="Chart",
                         displayOptions=show("create_chart"), required=True),
            NodeProperty(name="data_range", displayName="Chart Data Range", type=NodePropertyType.TEXT,
                         description="A1 range including the heading row, for example A1:D20.", default="A1:D20",
                         displayOptions=show("create_chart"), required=True),
            NodeProperty(name="chart_row", displayName="Chart Row", type=NodePropertyType.NUMBER,
                         description="Zero-based row where the chart is anchored.", default=1,
                         displayOptions=show("create_chart"), required=False),
            NodeProperty(name="chart_column", displayName="Chart Column", type=NodePropertyType.NUMBER,
                         description="Zero-based column where the chart is anchored.", default=6,
                         displayOptions=show("create_chart"), required=False),
            NodeProperty(name="data_mode", displayName="Mapping Column Mode", type=NodePropertyType.SELECT,
                         description="Map incoming object keys automatically or define rows below.", default="auto_map",
                         options=[
                             {"label": "Map Automatically", "value": "auto_map"},
                             {"label": "Use Values Below", "value": "manual"},
                         ], displayOptions=show(*row_write_operations), required=False),
            NodeProperty(name="values", displayName="Values to Send", type=NodePropertyType.JSON_EDITOR,
                         description="JSON object or array. Object keys map to the heading row.", default="[]",
                         displayOptions={"show": {"operation": list(row_write_operations), "data_mode": "manual"}},
                         required=False),
            NodeProperty(name="match_column", displayName="Column to Match On", type=NodePropertyType.TEXT,
                         description="Existing heading used to find rows for Update and Append or Update.",
                         displayOptions=show("append_or_update", "update"), required=True),
            NodeProperty(name="filters", displayName="Filters", type=NodePropertyType.JSON_EDITOR,
                         description='JSON object or array such as [{"column":"Status","value":"Open"}].',
                         default="[]", displayOptions=show("get_rows"), required=False),
            NodeProperty(name="combine_filters", displayName="Combine Filters", type=NodePropertyType.SELECT,
                         description="Require all filters or any filter to match.", default="AND",
                         options=[{"label": "AND", "value": "AND"}, {"label": "OR", "value": "OR"}],
                         displayOptions=show("get_rows"), required=False),
            NodeProperty(name="return_all", displayName="Return All", type=NodePropertyType.CHECKBOX,
                         description=f"Return every matching row within the {_MAX_READ_ROWS}-row scan ceiling.", default=False,
                         displayOptions=show("get_rows"), required=False),
            NodeProperty(name="limit", displayName="Limit", type=NodePropertyType.NUMBER,
                         description="Maximum rows returned when Return All is disabled.", default=100,
                         min=1, max=_MAX_READ_ROWS,
                         displayOptions={"show": {"operation": "get_rows", "return_all": False}}, required=False),
            NodeProperty(name="clear_mode", displayName="Clear", type=NodePropertyType.SELECT,
                         description="Choose which part of the sheet to clear.", default="whole_sheet",
                         options=[
                             {"label": "Whole Sheet", "value": "whole_sheet"},
                             {"label": "Specific Rows", "value": "rows"},
                             {"label": "Specific Columns", "value": "columns"},
                             {"label": "Specific Range", "value": "range"},
                         ], displayOptions=show("clear"), required=True),
            NodeProperty(name="keep_first_row", displayName="Keep First Row", type=NodePropertyType.CHECKBOX,
                         description="Keep the heading row when clearing the whole sheet.", default=False,
                         displayOptions={"show": {"operation": "clear", "clear_mode": "whole_sheet"}}, required=False),
            NodeProperty(name="start_row", displayName="Start Row Number", type=NodePropertyType.NUMBER,
                         description="First one-based row for clear/delete operations.", default=2, min=1,
                         displayOptions={"show": {
                             "operation": ["clear", "delete_rows_columns"],
                             "_any": {"clear_mode": "rows", "delete_dimension": "rows"},
                         }}, required=False),
            NodeProperty(name="row_count", displayName="Number of Rows", type=NodePropertyType.NUMBER,
                         description="Number of rows to clear or delete.", default=1, min=1, max=_MAX_READ_ROWS,
                         displayOptions={"show": {
                             "operation": ["clear", "delete_rows_columns"],
                             "_any": {"clear_mode": "rows", "delete_dimension": "rows"},
                         }}, required=False),
            NodeProperty(name="start_column", displayName="Start Column", type=NodePropertyType.TEXT,
                         description="First column in A1 letter notation.", default="A",
                         displayOptions={"show": {
                             "operation": ["add_columns", "clear", "delete_rows_columns"],
                             "_any": {"operation": "add_columns", "clear_mode": "columns", "delete_dimension": "columns"},
                         }}, required=False),
            NodeProperty(name="column_count", displayName="Number of Columns", type=NodePropertyType.NUMBER,
                         description="Number of columns to clear or delete.", default=1, min=1, max=_MAX_COLUMNS,
                         displayOptions={"show": {
                             "operation": ["clear", "delete_rows_columns"],
                             "_any": {"clear_mode": "columns", "delete_dimension": "columns"},
                         }}, required=False),
            NodeProperty(name="specific_range", displayName="Range", type=NodePropertyType.TEXT,
                         description="A1 range within the selected sheet.", placeholder="A2:D20",
                         displayOptions={"show": {"operation": "clear", "clear_mode": "range"}}, required=True),
            NodeProperty(name="delete_dimension", displayName="Delete", type=NodePropertyType.SELECT,
                         description="Delete rows or columns.", default="rows",
                         options=[{"label": "Rows", "value": "rows"}, {"label": "Columns", "value": "columns"}],
                         displayOptions=show("delete_rows_columns"), required=True),
            NodeProperty(name="range", displayName="Data Range", type=NodePropertyType.TEXT,
                         description="Optional A1 range within the selected sheet.", placeholder="A1:Z1000",
                         displayOptions=show(*table_operations), tabName="advanced", required=False),
            NodeProperty(name="value_input_mode", displayName="Value Input Mode", type=NodePropertyType.SELECT,
                         description="USER_ENTERED parses values as if typed in Sheets; RAW stores them unchanged.",
                         default="USER_ENTERED", options=[
                             {"label": "User Entered", "value": "USER_ENTERED"},
                             {"label": "Raw", "value": "RAW"},
                          ], displayOptions=show("append", "append_or_update", "update"),
                         tabName="advanced", required=False),
            NodeProperty(name="value_render_mode", displayName="Value Render Mode", type=NodePropertyType.SELECT,
                         description="How values are represented when rows are read.", default="UNFORMATTED_VALUE",
                         options=[
                             {"label": "Unformatted Value", "value": "UNFORMATTED_VALUE"},
                             {"label": "Formatted Value", "value": "FORMATTED_VALUE"},
                             {"label": "Formula", "value": "FORMULA"},
                          ], displayOptions=show(*table_operations), tabName="advanced", required=False),
            NodeProperty(name="max_scan_rows", displayName="Scan Row Ceiling", type=NodePropertyType.NUMBER,
                         description="Maximum data rows loaded from Google Sheets in one execution.",
                         default=1000, min=1, max=_MAX_READ_ROWS,
                         displayOptions=show(*table_operations), tabName="advanced", required=False),
            NodeProperty(name="request_timeout", displayName="Request Timeout", type=NodePropertyType.NUMBER,
                         description="Maximum wait time for each Google API request.", default=30,
                         min=5, max=120, unit="seconds", tabName="advanced", required=False),
        ]

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any] | None = None) -> Dict[str, Any]:
        config = _configuration(self.user_data, inputs)
        connected = _unwrap_connected((connected_nodes or {}).get("input"))
        operation = str(config.get("operation") or "get_rows")
        if operation not in _SUPPORTED_OPERATIONS:
            raise ValueError(f"Unsupported Google Sheets operation: {operation}")

        timeout = _bounded_int(
            config.get("request_timeout"),
            field_name="Request Timeout",
            default=30,
            minimum=5,
            maximum=120,
        )
        try:
            secret = _credential_secret(self, config.get("credential_id"))
            credentials = _google_credentials(secret)
            sheets = _build_google_service("sheets", "v4", credentials, timeout)

            if operation == "create_document":
                title = _required_text(
                    config.get("document_title") or "Untitled spreadsheet",
                    field_name="Title",
                    max_length=200,
                )
                response = sheets.spreadsheets().create(
                    body={"properties": {"title": title}},
                    fields="spreadsheetId,spreadsheetUrl,properties(title)",
                ).execute()
                result = {
                    "success": True,
                    "operation": operation,
                    "spreadsheet_id": response.get("spreadsheetId"),
                    "spreadsheet_url": response.get("spreadsheetUrl"),
                    "title": (response.get("properties") or {}).get("title", title),
                }
            else:
                document_id = _document_id(config.get("document_id"))
                if operation == "delete_document":
                    drive = _build_google_service("drive", "v3", credentials, timeout)
                    drive.files().delete(fileId=document_id).execute()
                    result = {
                        "success": True,
                        "operation": operation,
                        "spreadsheet_id": document_id,
                        "deleted": True,
                    }
                elif operation == "create_sheet":
                    result = self._create_sheet(sheets, document_id, config)
                else:
                    sheet = self._resolve_sheet(sheets, document_id, config.get("sheet"))
                    handlers = {
                        "append": self._append,
                        "append_or_update": self._append_or_update,
                        "add_columns": self._add_columns,
                        "format_sheet": self._format_sheet,
                        "create_chart": self._create_chart,
                        "clear": self._clear,
                        "delete_sheet": self._delete_sheet,
                        "delete_rows_columns": self._delete_rows_columns,
                        "get_rows": self._get_rows,
                        "update": self._update,
                    }
                    result = handlers[operation](sheets, document_id, sheet, config, connected)
                    result.setdefault("spreadsheet_id", document_id)
                    result.setdefault("sheet", {
                        "id": sheet.get("sheetId"),
                        "title": sheet.get("title"),
                    })
        except Exception as exc:
            message = _google_error(exc)
            logger.warning("Google Sheets operation %s failed: %s", operation, message)
            if isinstance(exc, ValueError):
                raise
            raise RuntimeError(message) from exc

        result.setdefault("success", True)
        result.setdefault("operation", operation)
        result["schema_version"] = _SCHEMA_VERSION
        return {"output": result}

    @staticmethod
    def _resolve_sheet(service: Any, document_id: str, selector: Any) -> Dict[str, Any]:
        raw = str(selector or "Sheet1").strip()
        gid_match = _SHEET_ID.search(raw)
        requested_id = int(gid_match.group(1)) if gid_match else (int(raw) if raw.isdigit() else None)
        response = service.spreadsheets().get(
            spreadsheetId=document_id, fields="sheets.properties(sheetId,title,index)"
        ).execute()
        sheets = [item.get("properties") or {} for item in response.get("sheets") or []]
        normalised_raw = re.sub(r"\s+", "", raw).casefold()
        for sheet in sheets:
            if requested_id is not None and int(sheet.get("sheetId", -1)) == requested_id:
                return sheet
            if requested_id is None and str(sheet.get("title")) == raw:
                return sheet
        # Accept the common chat spelling "Sheet 1" for a tab actually named "Sheet1";
        # exact titles above still win for tabs that intentionally contain spaces.
        for sheet in sheets:
            title = str(sheet.get("title") or "")
            if requested_id is None and re.sub(r"\s+", "", title).casefold() == normalised_raw:
                return sheet
        raise ValueError(f"Google Sheets tab was not found: {raw}")

    @staticmethod
    def _range(sheet: Mapping[str, Any], config: Mapping[str, Any]) -> str:
        data_range = str(config.get("range") or "").strip()
        if data_range:
            if "!" in data_range or not _A1_RANGE.fullmatch(data_range):
                raise ValueError(
                    "Data Range must be an A1 range within the selected sheet, such as A1:Z1000."
                )
            if re.fullmatch(r"[A-Za-z]+:[A-Za-z]+", data_range):
                raise ValueError(
                    "Data Range must include a row boundary to prevent unbounded reads."
                )
            ceiling = GoogleSheetsNode._scan_ceiling(config)
            cell_range = re.fullmatch(
                r"([A-Za-z]+)(\d+)(?::([A-Za-z]+)(\d+))?",
                data_range,
            )
            row_range = re.fullmatch(r"(\d+):(\d+)", data_range)
            if cell_range:
                start_column = _column_number(cell_range.group(1))
                end_column = _column_number(cell_range.group(3) or cell_range.group(1))
                start_row = int(cell_range.group(2))
                end_row = int(cell_range.group(4) or cell_range.group(2))
                if end_column < start_column or end_row < start_row:
                    raise ValueError("Data Range must end after its starting cell.")
                if end_column - start_column + 1 > _MAX_COLUMNS:
                    raise ValueError(f"Data Range may contain at most {_MAX_COLUMNS} columns.")
                if end_row - start_row + 1 > ceiling + 1:
                    raise ValueError(
                        "Data Range exceeds the configured Scan Row Ceiling."
                    )
            elif row_range:
                raise ValueError(
                    "Data Range must include column boundaries to prevent unbounded reads."
                )
        return f"{_quote_sheet(str(sheet['title']))}!{data_range}" if data_range else _quote_sheet(str(sheet["title"]))

    @staticmethod
    def _scan_ceiling(config: Mapping[str, Any]) -> int:
        return _bounded_int(
            config.get("max_scan_rows"),
            field_name="Scan Row Ceiling",
            default=1000,
            minimum=1,
            maximum=_MAX_READ_ROWS,
        )

    @staticmethod
    def _range_origin(config: Mapping[str, Any]) -> tuple[int, int]:
        """Return the one-based starting column and header row of Data Range."""
        data_range = str(config.get("range") or "").strip()
        cell_match = re.match(r"([A-Za-z]+)(\d+)", data_range)
        if cell_match:
            return _column_number(cell_match.group(1)), int(cell_match.group(2))
        row_match = re.match(r"(\d+):", data_range)
        if row_match:
            return 1, int(row_match.group(1))
        return 1, 1

    @staticmethod
    def _rows(config: Mapping[str, Any], connected: Any) -> List[Any]:
        manual = str(config.get("data_mode") or "auto_map") == "manual"
        source = _parse_json(config.get("values"), default=[], field_name="Values to Send") if manual else connected
        if source in (None, "", []):
            source = _parse_json(config.get("values"), default=[], field_name="Values to Send")
        if isinstance(source, dict) and isinstance(source.get("rows"), list):
            source = source["rows"]
        if isinstance(source, dict):
            source = [source]
        if isinstance(source, list):
            if not source:
                return []
            rows = source if isinstance(source[0], (dict, list, tuple)) else [source]
            if len(rows) > _MAX_WRITE_ROWS:
                raise ValueError(
                    f"A single execution may write at most {_MAX_WRITE_ROWS} rows."
                )
            if not all(isinstance(row, (Mapping, list, tuple)) for row in rows):
                raise ValueError("Every row must be a JSON object or array.")
            return list(rows)
        raise ValueError("Values to Send must be a JSON object or array of rows.")

    def _table(self, service: Any, document_id: str, sheet: Mapping[str, Any], config: Mapping[str, Any]):
        ceiling = self._scan_ceiling(config)
        configured_range = str(config.get("range") or "").strip()
        if configured_range:
            read_range = self._range(sheet, config)
        else:
            # Request one extra data row so the output can report truncation honestly.
            read_range = (
                f"{_quote_sheet(str(sheet['title']))}!"
                f"A1:{_column_name(_MAX_COLUMNS)}{ceiling + 2}"
            )
        response = service.spreadsheets().values().get(
            spreadsheetId=document_id,
            range=read_range,
            valueRenderOption=str(config.get("value_render_mode") or "UNFORMATTED_VALUE"),
            majorDimension="ROWS",
        ).execute()
        values = response.get("values") or []
        raw_headers = values[0] if values else []
        if len(raw_headers) > _MAX_COLUMNS:
            raise ValueError(f"A sheet may expose at most {_MAX_COLUMNS} columns per execution.")
        headers = [
            str(value).strip() if str(value).strip() else f"col_{index + 1}"
            for index, value in enumerate(raw_headers)
        ]
        if len(set(headers)) != len(headers):
            raise ValueError("The selected range contains duplicate column headings.")
        rows = values[1:] if values else []
        truncated = len(rows) > ceiling
        return headers, rows[:ceiling], truncated

    @staticmethod
    def _headers(service: Any, document_id: str, sheet: Mapping[str, Any]) -> List[str]:
        response = service.spreadsheets().values().get(
            spreadsheetId=document_id,
            range=f"{_quote_sheet(str(sheet['title']))}!1:1",
            valueRenderOption="UNFORMATTED_VALUE",
            majorDimension="ROWS",
        ).execute()
        rows = response.get("values") or []
        raw_headers = rows[0] if rows else []
        if len(raw_headers) > _MAX_COLUMNS:
            raise ValueError(f"A sheet may expose at most {_MAX_COLUMNS} columns per execution.")
        headers = [
            str(value).strip() if str(value).strip() else f"col_{index + 1}"
            for index, value in enumerate(raw_headers)
        ]
        if len(set(headers)) != len(headers):
            raise ValueError("The selected sheet contains duplicate column headings.")
        return headers

    @staticmethod
    def _mapped_values(rows: Sequence[Any], headers: Sequence[str]) -> List[List[Any]]:
        mapped: List[List[Any]] = []
        for row in rows:
            if isinstance(row, Mapping):
                if not headers:
                    raise ValueError("Object rows require a heading row in the selected sheet.")
                mapped.append([row.get(header, "") for header in headers])
            else:
                values = list(row)
                if len(values) > _MAX_COLUMNS:
                    raise ValueError(f"A row may contain at most {_MAX_COLUMNS} values.")
                mapped.append(values)
        return mapped

    def _append(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        rows = self._rows(config, connected)
        if not rows:
            raise ValueError("At least one row is required for Append Row.")
        headers = self._headers(service, document_id, sheet)
        if rows and isinstance(rows[0], Mapping) and not headers:
            headers = [str(key).strip() for key in rows[0].keys()]
            if any(not header for header in headers) or len(set(headers)) != len(headers):
                raise ValueError("Object row keys must be unique, non-empty column headings.")
            if len(headers) > _MAX_COLUMNS:
                raise ValueError(f"A sheet may contain at most {_MAX_COLUMNS} mapped columns.")
            service.spreadsheets().values().update(
                spreadsheetId=document_id, range=f"{_quote_sheet(str(sheet['title']))}!A1",
                valueInputOption="RAW", body={"values": [headers]},
            ).execute()
        values = self._mapped_values(rows, headers) if headers else self._mapped_values(rows, [])
        response = service.spreadsheets().values().append(
            spreadsheetId=document_id, range=self._range(sheet, config),
            valueInputOption=str(config.get("value_input_mode") or "USER_ENTERED"),
            insertDataOption="INSERT_ROWS", body={"values": values},
        ).execute()
        updates = response.get("updates") or {}
        return {
            "success": True,
            "operation": "append",
            "rows_affected": len(values),
            "updated_range": updates.get("updatedRange"),
        }

    def _update_rows(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                     config: Mapping[str, Any], rows: Sequence[Any], upsert: bool) -> Dict[str, Any]:
        if not rows:
            raise ValueError("At least one row is required for this operation.")
        headers, existing, scan_truncated = self._table(service, document_id, sheet, config)
        match_column = str(config.get("match_column") or "").strip()
        if not headers or match_column not in headers:
            raise ValueError("Column to Match On must name an existing heading row column.")
        if not all(isinstance(row, Mapping) for row in rows):
            raise ValueError("Update operations require JSON objects keyed by heading name.")
        match_index = headers.index(match_column)
        start_column, header_row_number = self._range_origin(config)
        lookup: Dict[str, int] = {}
        duplicate_values = set()
        for index, existing_row in enumerate(existing):
            value = str(existing_row[match_index]) if match_index < len(existing_row) else ""
            if not value:
                continue
            if value in lookup:
                duplicate_values.add(value)
            else:
                lookup[value] = header_row_number + index + 1
        if duplicate_values:
            raise ValueError(
                "Column to Match On contains duplicate values; update would be ambiguous."
            )
        updated: List[int] = []
        to_append: List[Mapping[str, Any]] = []
        updates: List[Dict[str, Any]] = []
        first_column = _column_name(start_column)
        last_column = _column_name(start_column + len(headers) - 1)
        for row in rows:
            if match_column not in row:
                raise ValueError(f"Every row must include the match column {match_column!r}.")
            match_value = str(row.get(match_column, "")).strip()
            if not match_value:
                raise ValueError("Match values cannot be empty.")
            row_number = lookup.get(match_value)
            if row_number is None:
                if scan_truncated:
                    raise ValueError(
                        "The matching row may be beyond the Scan Row Ceiling. "
                        "Increase the ceiling before updating or appending."
                    )
                if upsert:
                    to_append.append(row)
                    continue
                raise ValueError(f"No row matched {match_column}={match_value!r}.")
            existing_index = row_number - header_row_number - 1
            current = list(existing[existing_index]) + [""] * len(headers)
            values = [row.get(header, current[index]) for index, header in enumerate(headers)]
            updates.append({
                "range": (
                    f"{_quote_sheet(str(sheet['title']))}!"
                    f"{first_column}{row_number}:{last_column}{row_number}"
                ),
                "values": [values],
            })
            updated.append(row_number)
        if updates:
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=document_id,
                body={
                    "valueInputOption": str(config.get("value_input_mode") or "USER_ENTERED"),
                    "data": updates,
                },
            ).execute()
        appended = 0
        if to_append:
            response = service.spreadsheets().values().append(
                spreadsheetId=document_id, range=self._range(sheet, config),
                valueInputOption=str(config.get("value_input_mode") or "USER_ENTERED"),
                insertDataOption="INSERT_ROWS", body={"values": self._mapped_values(to_append, headers)},
            ).execute()
            appended = len(to_append)
        return {"success": True, "updated_rows": updated, "updated_count": len(updated), "appended_count": appended}

    def _update(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        rows = self._rows(config, connected)
        result = self._update_rows(service, document_id, sheet, config, rows, False)
        return {"operation": "update", **result}

    def _append_or_update(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                          config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        rows = self._rows(config, connected)
        result = self._update_rows(service, document_id, sheet, config, rows, True)
        return {"operation": "append_or_update", **result}

    def _add_columns(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                     config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        """Append heading columns to a sheet without requiring an existing row match."""
        raw_columns = config.get("columns")
        if raw_columns in (None, "", []):
            raw_columns = config.get("values")
        columns = _parse_json(raw_columns, default=[], field_name="Columns")
        if isinstance(columns, Mapping):
            columns = columns.get("columns") or columns.get("headers") or list(columns.keys())
        if isinstance(columns, str):
            columns = [item.strip() for item in columns.split(",") if item.strip()]
        if not isinstance(columns, list):
            raise ValueError("Columns must be a JSON array or comma-separated text.")
        headings = []
        for item in columns:
            if isinstance(item, Mapping):
                item = item.get("title") or item.get("name") or item.get("header")
            heading = str(item or "").strip()
            if heading:
                headings.append(heading)
        if not headings:
            raise ValueError("At least one column heading is required.")
        if len(headings) > _MAX_COLUMNS:
            raise ValueError(f"At most {_MAX_COLUMNS} columns can be added at once.")
        if len(set(headings)) != len(headings):
            raise ValueError("Column headings must be unique.")

        headers = self._headers(service, document_id, sheet)
        start_column = _column_number(str(config.get("start_column") or _column_name(len(headers) + 1)))
        end_column = start_column + len(headings) - 1
        if end_column > _MAX_COLUMNS:
            raise ValueError(f"The resulting column index may not exceed {_MAX_COLUMNS}.")
        service.spreadsheets().batchUpdate(
            spreadsheetId=document_id,
            body={"requests": [{"insertDimension": {"range": {
                "sheetId": int(sheet["sheetId"]), "dimension": "COLUMNS",
                "startIndex": start_column - 1, "endIndex": end_column,
            }, "inheritFromBefore": start_column > 1}}]},
        ).execute()
        header_range = (
            f"{_quote_sheet(str(sheet['title']))}!{_column_name(start_column)}1:"
            f"{_column_name(end_column)}1"
        )
        service.spreadsheets().values().update(
            spreadsheetId=document_id,
            range=header_range,
            valueInputOption=str(config.get("value_input_mode") or "USER_ENTERED"),
            body={"values": [headings]},
        ).execute()
        return {
            "success": True,
            "operation": "add_columns",
            "columns_added": headings,
            "range": header_range,
        }

    def _format_sheet(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                      config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        """Apply a simple, safe header/body color scheme to the selected sheet."""
        headers, existing, truncated = self._table(service, document_id, sheet, config)
        column_count = max(1, len(headers))
        row_count = max(1, len(existing) + 1)
        start_column, header_row = self._range_origin(config)
        start_column_index = start_column - 1
        header_row_index = header_row - 1
        sheet_id = int(sheet["sheetId"])
        requests = [{
            "repeatCell": {
                "range": {
                    "sheetId": sheet_id,
                    "startRowIndex": header_row_index,
                    "endRowIndex": header_row_index + 1,
                    "startColumnIndex": start_column_index,
                    "endColumnIndex": start_column_index + column_count,
                },
                "cell": {"userEnteredFormat": {
                    "backgroundColor": _hex_color(config.get("header_background_color"), "#D9EAF7"),
                    "textFormat": {
                        "foregroundColor": _hex_color(config.get("header_text_color"), "#12355B"),
                        "bold": _as_bool(config.get("bold_headers", True)),
                    },
                }},
                "fields": "userEnteredFormat(backgroundColor,textFormat)",
            }
        }]
        if row_count > 1:
            requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": sheet_id,
                        "startRowIndex": header_row_index + 1,
                        "endRowIndex": header_row_index + row_count,
                        "startColumnIndex": start_column_index,
                        "endColumnIndex": start_column_index + column_count,
                    },
                    "cell": {"userEnteredFormat": {
                        "backgroundColor": _hex_color(config.get("body_background_color"), "#FFFFFF"),
                        "textFormat": {"foregroundColor": _hex_color(config.get("body_text_color"), "#222222")},
                    }},
                    "fields": "userEnteredFormat(backgroundColor,textFormat)",
                }
            })
        service.spreadsheets().batchUpdate(
            spreadsheetId=document_id, body={"requests": requests}
        ).execute()
        return {
            "success": True,
            "operation": "format_sheet",
            "formatted_columns": column_count,
            "formatted_rows": row_count,
            "truncated": truncated,
        }

    def _create_chart(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                      config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        """Create a bounded chart using the first column as its domain."""
        source = _a1_grid_range(
            config.get("data_range") or "A1:B2",
            int(sheet["sheetId"]),
            2,
            2,
        )
        start_column = int(source.get("startColumnIndex", 0))
        end_column = int(source.get("endColumnIndex", 2))
        if end_column - start_column < 2:
            raise ValueError("Chart Data Range must include a label column and a value column.")

        domain_source = {
            **source,
            "startColumnIndex": start_column,
            "endColumnIndex": start_column + 1,
        }
        value_sources = [
            {
                **source,
                "startColumnIndex": column,
                "endColumnIndex": column + 1,
            }
            for column in range(start_column + 1, end_column)
        ]
        chart_type = str(config.get("chart_type") or "PIE").upper()
        if chart_type not in {"PIE", "COLUMN", "BAR", "LINE"}:
            raise ValueError("Chart Type must be Pie, Column, Bar, or Line.")

        title = _required_text(
            config.get("chart_title") or "Chart",
            field_name="Chart Title",
            max_length=200,
        )
        if chart_type == "PIE":
            chart_spec: Dict[str, Any] = {
                "title": title,
                "pieChart": {
                    "legendPosition": "RIGHT_LEGEND",
                    "domain": {"sourceRange": {"sources": [domain_source]}},
                    "series": {"sourceRange": {"sources": [value_sources[0]]}},
                    "threeDimensional": False,
                },
            }
        else:
            series = [
                {
                    "series": {"sourceRange": {"sources": [value_source]}},
                    "targetAxis": "LEFT_AXIS",
                }
                for value_source in value_sources
            ]
            chart_spec = {
                "title": title,
                "basicChart": {
                    "chartType": chart_type,
                    "legendPosition": "RIGHT_LEGEND",
                    "headerCount": 1,
                    "domains": [{"domain": {"sourceRange": {"sources": [domain_source]}}}],
                    "series": series,
                },
            }
        request = {
            "addChart": {
                "chart": {
                    "spec": chart_spec,
                    "position": {"overlayPosition": {
                        "anchorCell": {
                            "sheetId": int(sheet["sheetId"]),
                            "rowIndex": _bounded_int(
                                config.get("chart_row"), field_name="Chart Row",
                                default=1, minimum=0, maximum=_MAX_READ_ROWS,
                            ),
                            "columnIndex": _bounded_int(
                                config.get("chart_column"), field_name="Chart Column",
                                default=6, minimum=0, maximum=_MAX_COLUMNS - 1,
                            ),
                        }
                    }},
                }
            }
        }
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=document_id, body={"requests": [request]}
        ).execute()
        chart_id = None
        replies = response.get("replies") if isinstance(response, dict) else None
        if replies and isinstance(replies[0], dict):
            chart_id = (replies[0].get("addChart") or {}).get("chart", {}).get("chartId")
        return {"success": True, "operation": "create_chart", "chart_id": chart_id, "chart_type": chart_type}

    def _get_rows(self, service: Any, document_id: str, sheet: Mapping[str, Any],
                  config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        headers, values, scan_truncated = self._table(service, document_id, sheet, config)
        _, header_row_number = self._range_origin(config)
        rows = [
            {
                **{
                    header: (row[index] if index < len(row) else "")
                    for index, header in enumerate(headers)
                },
                "row_number": header_row_number + offset + 1,
            }
            for offset, row in enumerate(values)
        ]
        filters = _parse_json(config.get("filters"), default=[], field_name="Filters")
        if isinstance(filters, dict):
            filters = ([filters] if "column" in filters else [
                {"column": key, "value": value} for key, value in filters.items()
            ])
        if not isinstance(filters, list):
            raise ValueError("Filters must be a JSON object or array.")
        if len(filters) > 50:
            raise ValueError("At most 50 filters can be applied in one execution.")
        if filters:
            for rule in filters:
                if not isinstance(rule, Mapping):
                    raise ValueError("Every filter must be a JSON object.")
                column = str(rule.get("column") or "").strip()
                if not column or column not in headers:
                    raise ValueError(f"Filter column does not exist: {column or '<empty>'}")
            combine_mode = str(config.get("combine_filters") or "AND").upper()
            if combine_mode not in {"AND", "OR"}:
                raise ValueError("Combine Filters must be AND or OR.")
            combine_all = combine_mode == "AND"

            def matches(row: Mapping[str, Any]) -> bool:
                checks = [str(row.get(str(rule.get("column")), "")) == str(rule.get("value", "")) for rule in filters]
                return all(checks) if combine_all else any(checks)

            rows = [row for row in rows if matches(row)]
        matched_count = len(rows)
        limited = False
        if not _as_bool(config.get("return_all", False)):
            limit = _bounded_int(
                config.get("limit"), field_name="Limit", default=100,
                minimum=1, maximum=_MAX_READ_ROWS,
            )
            limited = matched_count > limit
            rows = rows[:limit]
        return {
            "success": True,
            "operation": "get_rows",
            "rows": rows,
            "row_count": len(rows),
            "rows_scanned": len(values),
            "matched_count": matched_count,
            "truncated": scan_truncated or limited,
            "complete": not scan_truncated and not limited,
        }

    @staticmethod
    def _create_sheet(service: Any, document_id: str, config: Mapping[str, Any]) -> Dict[str, Any]:
        title = _required_text(
            config.get("new_sheet_title") or "Sheet1",
            field_name="Title",
            max_length=100,
        )
        response = service.spreadsheets().batchUpdate(
            spreadsheetId=document_id, body={"requests": [{"addSheet": {"properties": {"title": title}}}]}
        ).execute()
        replies = response.get("replies") or []
        properties = ((replies[0].get("addSheet") or {}).get("properties") or {}) if replies else {}
        return {
            "success": True,
            "operation": "create_sheet",
            "spreadsheet_id": document_id,
            "sheet": {
                "id": properties.get("sheetId"),
                "title": properties.get("title", title),
                "index": properties.get("index"),
            },
        }

    @staticmethod
    def _delete_sheet(service: Any, document_id: str, sheet: Mapping[str, Any],
                      config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        service.spreadsheets().batchUpdate(
            spreadsheetId=document_id,
            body={"requests": [{"deleteSheet": {"sheetId": int(sheet["sheetId"])}}]},
        ).execute()
        return {
            "success": True,
            "operation": "delete_sheet",
            "sheet_id": sheet["sheetId"],
            "deleted": True,
        }

    @staticmethod
    def _delete_rows_columns(service: Any, document_id: str, sheet: Mapping[str, Any],
                             config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        dimension = str(config.get("delete_dimension") or "rows")
        if dimension not in {"rows", "columns"}:
            raise ValueError("Delete must be Rows or Columns.")
        if dimension == "columns":
            start = _column_number(str(config.get("start_column") or "A")) - 1
            count = _bounded_int(
                config.get("column_count"), field_name="Number of Columns",
                default=1, minimum=1, maximum=_MAX_COLUMNS,
            )
            if start + count > _MAX_COLUMNS:
                raise ValueError(f"The ending column may not exceed {_MAX_COLUMNS}.")
            api_dimension = "COLUMNS"
        else:
            start = _bounded_int(
                config.get("start_row"), field_name="Start Row Number",
                default=1, minimum=1, maximum=10_000_000,
            ) - 1
            count = _bounded_int(
                config.get("row_count"), field_name="Number of Rows",
                default=1, minimum=1, maximum=_MAX_READ_ROWS,
            )
            api_dimension = "ROWS"
        request = {"deleteDimension": {"range": {
            "sheetId": int(sheet["sheetId"]), "dimension": api_dimension,
            "startIndex": start, "endIndex": start + count,
        }}}
        service.spreadsheets().batchUpdate(
            spreadsheetId=document_id, body={"requests": [request]}
        ).execute()
        return {
            "success": True,
            "operation": "delete_rows_columns",
            "dimension": dimension,
            "start_index": start,
            "count": count,
        }

    def _clear(self, service: Any, document_id: str, sheet: Mapping[str, Any],
               config: Mapping[str, Any], connected: Any) -> Dict[str, Any]:
        mode = str(config.get("clear_mode") or "whole_sheet")
        if mode not in {"whole_sheet", "rows", "columns", "range"}:
            raise ValueError("Clear must target the whole sheet, rows, columns, or a range.")
        title = _quote_sheet(str(sheet["title"]))
        if mode == "rows":
            start = _bounded_int(
                config.get("start_row"), field_name="Start Row Number",
                default=1, minimum=1, maximum=10_000_000,
            )
            count = _bounded_int(
                config.get("row_count"), field_name="Number of Rows",
                default=1, minimum=1, maximum=_MAX_READ_ROWS,
            )
            clear_range = f"{title}!{start}:{start + count - 1}"
        elif mode == "columns":
            start_number = _column_number(str(config.get("start_column") or "A"))
            count = _bounded_int(
                config.get("column_count"), field_name="Number of Columns",
                default=1, minimum=1, maximum=_MAX_COLUMNS,
            )
            if start_number + count - 1 > _MAX_COLUMNS:
                raise ValueError(f"The ending column may not exceed {_MAX_COLUMNS}.")
            end = _column_name(start_number + count - 1)
            clear_range = f"{title}!{_column_name(start_number)}:{end}"
        elif mode == "range":
            specific = str(config.get("specific_range") or "").strip()
            if not specific or "!" in specific or not _A1_RANGE.fullmatch(specific):
                raise ValueError(
                    "Range must use A1 notation within the selected sheet, such as A2:D20."
                )
            clear_range = f"{title}!{specific}"
        elif _as_bool(config.get("keep_first_row")):
            clear_range = f"{title}!2:1000000"
        else:
            clear_range = title
        service.spreadsheets().values().clear(
            spreadsheetId=document_id, range=clear_range, body={}
        ).execute()
        return {"success": True, "operation": "clear", "cleared_range": clear_range}
