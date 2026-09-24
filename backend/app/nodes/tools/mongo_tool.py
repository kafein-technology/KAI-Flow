"""Agent-callable MongoDB tool with explicit permissions and database scope."""

from __future__ import annotations

import json
import logging
import re
from datetime import date, datetime
from decimal import Decimal
from itertools import islice
from typing import Any, Dict, List, Mapping, Optional, Set, Tuple

from langchain_core.tools import Tool, ToolException

from ..base import (
    NodeOutput,
    NodePosition,
    NodeProperty,
    NodePropertyType,
    NodeType,
    ProviderNode,
)
from ..databases.mongo_node import MongoNode, _build_mongodb_uri

logger = logging.getLogger(__name__)

IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
COLLECTION_PATTERN = re.compile(r"^[^$\x00.][^$\x00]*$")
FIELD_PATH_PATTERN = re.compile(r"^(?!\$)[^\x00.]+(?:\.(?!\$)[^\x00.]+)*$")

READ_ACTIONS = {"find", "find_one", "count", "distinct", "aggregate"}
INSERT_ACTIONS = {"insert"}
UPDATE_ACTIONS = {"update", "update_one", "replace_one"}
DELETE_ACTIONS = {"delete", "delete_one"}
ALL_ACTIONS = READ_ACTIONS | INSERT_ACTIONS | UPDATE_ACTIONS | DELETE_ACTIONS

UPDATE_OPERATORS = {
    "$set",
    "$unset",
    "$inc",
    "$mul",
    "$rename",
    "$min",
    "$max",
    "$currentDate",
    "$addToSet",
    "$pop",
    "$pull",
    "$push",
    "$pullAll",
    "$bit",
    "$setOnInsert",
}

# Cross-collection access, writes from aggregation, and server-side JavaScript
# are outside the scope granted by this tool.
FORBIDDEN_OPERATORS = {
    "$accumulator",
    "$function",
    "$graphLookup",
    "$lookup",
    "$merge",
    "$out",
    "$unionWith",
    "$where",
}

MAX_CONFIGURED_DOCUMENTS = 200
MAX_RETURN_ALL_DOCUMENTS = 5000
MAX_WRITE_DOCUMENTS = 1000
MAX_OPERATION_TIMEOUT = 120
MAX_ALLOWED_COLLECTIONS = 500
MAX_TOOL_NAME_CHARACTERS = 64
MAX_CUSTOM_DESCRIPTION_CHARACTERS = 10000
MAX_REQUEST_CHARACTERS = 1_000_000
MAX_VALUE_CHARACTERS = 4000
MAX_OUTPUT_CHARACTERS = 50000
MAX_SCHEMA_COLLECTIONS = 50
MAX_SCHEMA_FIELDS = 100
MAX_SCHEMA_DESCRIPTION_CHARACTERS = 20000
MAX_SAMPLE_DOCUMENTS = 100


class MongoToolNode(ProviderNode):
    """Expose a bounded MongoDB tool to an agent."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "MongoTool",
            "display_name": "MongoDB Tool",
            "description": (
                "Let an agent use MongoDB through explicit operation permissions and an "
                "explicit collection scope."
            ),
            "category": "Tool",
            "node_type": NodeType.PROVIDER,
            "icon": {
                "name": "mongodb",
                "path": "icons/mongodb.svg",
                "alt": "MongoDB",
            },
            "colors": ["sky-700", "blue-800"],
            "inputs": [],
            "outputs": [
                NodeOutput(
                    name="mongo_tool",
                    displayName="MongoDB Tool",
                    type="BaseTool",
                    description="A policy-controlled MongoDB tool an agent can call.",
                    is_connection=True,
                    direction=NodePosition.TOP,
                )
            ],
            "properties": [
                NodeProperty(
                    name="credential_id",
                    displayName="Credential",
                    type=NodePropertyType.CREDENTIAL_SELECT,
                    description="MongoDB connection the tool will use.",
                    placeholder="Select Credential",
                    required=True,
                    serviceType="mongodb",
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_all_collections",
                    displayName="Allow All Collections",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Grant access to every collection visible to the credential. Leave "
                        "disabled to require an explicit allowlist."
                    ),
                    required=True,
                    default=False,
                    hint="Enable only when database-wide access is intentional.",
                    tabName="basic",
                ),
                NodeProperty(
                    name="allowed_collections",
                    displayName="Allowed Collections",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Collections the tool may access.",
                    placeholder="Select one or more collections",
                    required=True,
                    default="",
                    multiple=True,
                    optionsMethod="load_collections",
                    optionsDependsOn=["credential_id"],
                    displayOptions={"show": {"allow_all_collections": False}},
                    hint=(
                        "An empty selection is rejected instead of silently granting access "
                        "to the whole database."
                    ),
                    tabName="basic",
                ),
                NodeProperty(
                    name="return_all",
                    displayName="Return All Documents",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return documents up to the tool safety ceiling. Leave disabled to "
                        "configure a smaller limit."
                    ),
                    required=True,
                    default=False,
                    hint="Leaving this disabled protects the agent context and backend memory.",
                    tabName="basic",
                ),
                NodeProperty(
                    name="max_documents",
                    displayName="Maximum Documents",
                    type=NodePropertyType.NUMBER,
                    description="Largest number of documents returned by one read.",
                    required=True,
                    default=20,
                    min=1,
                    max=MAX_CONFIGURED_DOCUMENTS,
                    displayOptions={"show": {"return_all": False}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="permissions_title",
                    displayName="Permissions",
                    type=NodePropertyType.TITLE,
                    description="Operations the agent is allowed to perform.",
                    required=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_read",
                    displayName="Allow Read",
                    type=NodePropertyType.CHECKBOX,
                    description="Allow find, count, distinct, and aggregate operations.",
                    required=True,
                    default=True,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_insert",
                    displayName="Allow Insert",
                    type=NodePropertyType.CHECKBOX,
                    description="Allow the agent to insert documents.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_update",
                    displayName="Allow Update",
                    type=NodePropertyType.CHECKBOX,
                    description="Allow filtered updates and replacements.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="allow_delete",
                    displayName="Allow Delete",
                    type=NodePropertyType.CHECKBOX,
                    description="Allow filtered delete operations.",
                    required=True,
                    default=False,
                    tabName="basic",
                ),
                NodeProperty(
                    name="describe_collections",
                    displayName="Describe Collections to the Agent",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Sample the permitted collections and include discovered field names "
                        "in the tool description."
                    ),
                    required=False,
                    default=True,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="tool_name",
                    displayName="Tool Name",
                    type=NodePropertyType.TEXT,
                    description="Name shown to the agent. Use letters, digits, and underscores.",
                    placeholder="mongo_database",
                    required=False,
                    default="mongo_database",
                    tabName="advanced",
                ),
                NodeProperty(
                    name="tool_description",
                    displayName="Tool Description",
                    type=NodePropertyType.TEXT_AREA,
                    description="Optional replacement for the generated tool description.",
                    required=False,
                    default="",
                    rows=4,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="operation_timeout",
                    displayName="Operation Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Maximum time allowed for one database operation.",
                    required=False,
                    default=15,
                    min=1,
                    max=MAX_OPERATION_TIMEOUT,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="case_insensitive",
                    displayName="Case-Insensitive Text Equality",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Rewrite plain string equality filters as escaped case-insensitive "
                        "regular expressions. This can reduce index efficiency."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
            ],
        }

    # ------------------------------------------------------------------
    # Configuration and connection
    # ------------------------------------------------------------------

    def _setting(self, kwargs: Dict[str, Any], name: str, fallback: Any) -> Any:
        if name in kwargs and kwargs[name] is not None:
            return kwargs[name]
        stored = getattr(self, "user_data", {}) or {}
        nested = stored.get("inputs") if isinstance(stored, dict) else None
        if isinstance(nested, dict) and name in nested and nested[name] is not None:
            return nested[name]
        if isinstance(stored, dict) and name in stored and stored[name] is not None:
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
        if isinstance(value, bool):
            raise ValueError(f"{name} must be a whole number.")
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{name} must be a whole number.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{name} must be between {minimum} and {maximum}.")
        return parsed

    def _connection_details(self, credential_id: Optional[str]) -> Tuple[str, str]:
        if not credential_id:
            raise ValueError("A MongoDB credential must be selected.")
        credential = self.get_credential(credential_id)
        if not credential:
            raise ValueError("The selected MongoDB credential could not be found.")
        if credential.get("service_type") != "mongodb":
            raise ValueError("The selected credential is not a MongoDB credential.")

        secret = credential.get("secret") or {}
        if not isinstance(secret, Mapping):
            raise ValueError("The selected MongoDB credential has an invalid secret payload.")
        database = str(secret.get("database") or "").strip()
        if not database:
            raise ValueError("MongoDB Database Name is required.")
        if any(character in database for character in '\x00/\\."$*<>:|?'):
            raise ValueError("MongoDB Database Name contains an invalid character.")
        return _build_mongodb_uri(secret), database

    def _open_client(
        self,
        credential_id: Optional[str],
        operation_timeout: int = 15,
    ):
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ValueError("The pymongo package is not installed on the server.") from exc

        uri, database_name = self._connection_details(credential_id)
        milliseconds = operation_timeout * 1000
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=min(milliseconds, 10_000),
            connectTimeoutMS=min(milliseconds, 10_000),
            socketTimeoutMS=milliseconds,
        )
        try:
            client.admin.command("ping")
            return client, client[database_name]
        except Exception:
            client.close()
            raise

    def _load_database_collections(
        self, credential_id: Optional[str], timeout: int = 15
    ) -> List[str]:
        client = None
        try:
            client, database = self._open_client(credential_id, timeout)
            return sorted(database.list_collection_names())
        finally:
            if client is not None:
                client.close()

    def load_collections(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        try:
            names = self._load_database_collections(values.get("credential_id"))
            return [{"label": name, "value": name} for name in names]
        except Exception as exc:
            raise ValueError(self._database_error(exc)) from exc

    # ------------------------------------------------------------------
    # Policy validation
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_list(raw: Any) -> List[str]:
        if not raw:
            return []
        parts = raw if isinstance(raw, (list, tuple, set)) else str(raw).split(",")
        values: List[str] = []
        seen: Set[str] = set()
        for part in parts:
            value = str(part).strip()
            if value and value not in seen:
                seen.add(value)
                values.append(value)
        return values

    @staticmethod
    def _validate_collection(name: Any) -> str:
        value = str(name or "").strip()
        if not value or not COLLECTION_PATTERN.fullmatch(value):
            raise ValueError(
                "Collection names cannot be empty, start with '$', contain a dot, or "
                "contain a null character."
            )
        return value

    @staticmethod
    def _validate_field_path(name: Any, label: str = "Field") -> str:
        value = str(name or "").strip()
        if not value or not FIELD_PATH_PATTERN.fullmatch(value):
            raise ValueError(
                f"{label} must contain valid MongoDB field names separated by dots and "
                "must not start a segment with '$'."
            )
        return value

    @classmethod
    def _resolve_allowed_collections(
        cls, raw: Any, allow_all_collections: Any
    ) -> List[str]:
        allow_all = cls._coerce_bool(allow_all_collections, "Allow All Collections")
        names = [cls._validate_collection(name) for name in cls._parse_list(raw)]
        if len(names) > MAX_ALLOWED_COLLECTIONS:
            raise ValueError(
                f"Allowed Collections may contain at most {MAX_ALLOWED_COLLECTIONS} names."
            )
        if allow_all:
            return []
        if not names:
            raise ValueError(
                "Select at least one Allowed Collection or explicitly enable Allow All "
                "Collections."
            )
        return names

    @classmethod
    def _guard_collection(cls, name: Any, allowed: List[str]) -> str:
        collection = cls._validate_collection(name)
        if allowed and collection not in allowed:
            raise ValueError(
                f"Collection '{collection}' is outside this tool's allowlist: "
                f"{', '.join(allowed)}."
            )
        return collection

    @staticmethod
    def _guard_permission(action: str, granted: Set[str]) -> None:
        if action in READ_ACTIONS:
            required = "read"
        elif action in INSERT_ACTIONS:
            required = "insert"
        elif action in UPDATE_ACTIONS:
            required = "update"
        elif action in DELETE_ACTIONS:
            required = "delete"
        else:
            raise ValueError(
                f"Unsupported action '{action}'. Use one of: {', '.join(sorted(ALL_ACTIONS))}."
            )
        if required not in granted:
            raise ValueError(f"This tool is not allowed to {required}.")

    @classmethod
    def _guard_document_operators(cls, value: Any) -> None:
        if isinstance(value, Mapping):
            for name, nested in value.items():
                if name in FORBIDDEN_OPERATORS:
                    raise ValueError(f"The {name} operator is not allowed in this tool.")
                cls._guard_document_operators(nested)
        elif isinstance(value, list):
            for nested in value:
                cls._guard_document_operators(nested)

    @classmethod
    def _guard_filter(cls, action: str, query: Any) -> Dict[str, Any]:
        if query is None:
            query = {}
        if not isinstance(query, dict):
            raise ValueError("The filter must be a JSON object.")
        cls._guard_document_operators(query)
        if action in (UPDATE_ACTIONS | DELETE_ACTIONS) and not query:
            raise ValueError(
                f"A {action} without a filter would affect the whole collection. "
                "Supply a filter that selects the intended documents."
            )
        return query

    @classmethod
    def _guard_pipeline(cls, pipeline: Any) -> List[Dict[str, Any]]:
        if not isinstance(pipeline, list) or not pipeline:
            raise ValueError("The aggregation pipeline must be a non-empty array.")
        for stage in pipeline:
            if not isinstance(stage, dict) or len(stage) != 1:
                raise ValueError(
                    "Every aggregation stage must be an object containing one operator."
                )
            operator = next(iter(stage))
            if not str(operator).startswith("$"):
                raise ValueError("Every aggregation stage must start with a MongoDB operator.")
        cls._guard_document_operators(pipeline)
        return pipeline

    @classmethod
    def _guard_update(cls, update: Any) -> Dict[str, Any]:
        if not isinstance(update, dict) or not update:
            raise ValueError("An update document is required.")
        cls._guard_document_operators(update)
        operator_keys = [key for key in update if str(key).startswith("$")]
        plain_keys = [key for key in update if not str(key).startswith("$")]
        if operator_keys and plain_keys:
            raise ValueError(
                "An update cannot mix update operators with plain field names."
            )
        if operator_keys:
            unknown = [key for key in operator_keys if key not in UPDATE_OPERATORS]
            if unknown:
                raise ValueError(
                    f"Unknown update operator: {', '.join(unknown)}. Supported operators: "
                    f"{', '.join(sorted(UPDATE_OPERATORS))}."
                )
            return update
        return {"$set": update}

    @classmethod
    def _guard_documents(cls, raw: Any) -> List[Dict[str, Any]]:
        documents = [raw] if isinstance(raw, dict) else raw
        if not isinstance(documents, list) or not documents:
            raise ValueError("Insert requires a document or a non-empty list of documents.")
        if len(documents) > MAX_WRITE_DOCUMENTS:
            raise ValueError(
                f"One insert call may contain at most {MAX_WRITE_DOCUMENTS} documents."
            )
        normalized: List[Dict[str, Any]] = []
        for document in documents:
            if not isinstance(document, dict) or not document:
                raise ValueError("Every inserted document must be a non-empty JSON object.")
            cls._guard_document_operators(document)
            normalized.append(dict(document))
        return normalized

    @classmethod
    def _fold_case(cls, query: Any, depth: int = 0) -> Any:
        if depth > 8 or not isinstance(query, dict):
            return query
        folded: Dict[str, Any] = {}
        for key, value in query.items():
            if key in {"$and", "$or", "$nor"} and isinstance(value, list):
                folded[key] = [cls._fold_case(item, depth + 1) for item in value]
            elif key == "$not" and isinstance(value, dict):
                folded[key] = cls._fold_case(value, depth + 1)
            elif str(key).startswith("$"):
                folded[key] = value
            elif isinstance(value, str) and value:
                folded[key] = {"$regex": f"^{re.escape(value)}$", "$options": "i"}
            elif isinstance(value, dict):
                folded[key] = cls._fold_case(value, depth + 1)
            else:
                folded[key] = value
        return folded

    # ------------------------------------------------------------------
    # Result shaping
    # ------------------------------------------------------------------

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return str(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray, memoryview)):
            return "<binary>"
        if isinstance(value, Mapping):
            return {str(key): cls._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize(item) for item in value]
        return str(value)

    @classmethod
    def _format_documents(
        cls,
        action: str,
        collection: str,
        documents: List[Any],
        database_limit_reached: bool,
    ) -> str:
        rendered: List[Any] = []
        rendered_size = 0
        output_limit_reached = False
        for document in documents:
            value = cls._serialize(document)
            encoded = json.dumps(value, ensure_ascii=False, default=str)
            if len(encoded) > MAX_VALUE_CHARACTERS:
                value = encoded[: MAX_VALUE_CHARACTERS - 16] + "...[truncated]"
                output_limit_reached = True
                encoded = json.dumps(value, ensure_ascii=False)
            if rendered_size + len(encoded) > MAX_OUTPUT_CHARACTERS - 1500:
                output_limit_reached = True
                break
            rendered.append(value)
            rendered_size += len(encoded)

        complete = not database_limit_reached and not output_limit_reached
        if not documents:
            guidance = (
                "This operation matched no documents. Do not describe the collection as "
                "empty unless the request examined the whole collection."
            )
        elif complete:
            guidance = "Base the answer on the returned values exactly as provided."
        else:
            guidance = (
                "This is a partial result. Narrow, aggregate, or paginate before presenting "
                "it as exhaustive."
            )
        payload = {
            "status": "success",
            "action": action,
            "collection": collection,
            "documents_fetched": len(documents),
            "documents_in_output": len(rendered),
            "result_complete": complete,
            "database_document_limit_reached": database_limit_reached,
            "output_limit_reached": output_limit_reached,
            "documents": rendered,
            "guidance": guidance,
        }
        result = json.dumps(payload, ensure_ascii=False, default=str)
        while len(result) > MAX_OUTPUT_CHARACTERS and rendered:
            rendered.pop()
            payload["documents_in_output"] = len(rendered)
            payload["result_complete"] = False
            payload["output_limit_reached"] = True
            result = json.dumps(payload, ensure_ascii=False, default=str)
        return result

    @staticmethod
    def _format_count(collection: str, count: int) -> str:
        return json.dumps(
            {
                "status": "success",
                "action": "count",
                "collection": collection,
                "count": count,
                "result_complete": True,
                "guidance": "Report this count only for the supplied filter.",
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _format_write_result(action: str, collection: str, **counts: Any) -> str:
        changed = counts.get(
            "modified_count",
            counts.get("inserted_count", counts.get("deleted_count", 0)),
        )
        matched = counts.get("matched_count", 0)
        if changed:
            guidance = (
                "Report the affected counts without inferring changes beyond this operation."
            )
        elif matched:
            guidance = (
                "The filter matched a document, but its stored value did not change. It may "
                "already contain the requested value."
            )
        else:
            guidance = (
                "No documents were changed. This means the supplied filter matched no "
                "writable document; it does not prove that the collection is empty."
            )
        return json.dumps(
            {
                "status": "success",
                "action": action,
                "collection": collection,
                **counts,
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
                    "Do not interpret this error as an empty result or claim a database fact. "
                    "Correct the request or explain the limitation before retrying."
                ),
            },
            ensure_ascii=False,
        )

    @staticmethod
    def _database_error(error: Exception) -> str:
        return MongoNode._database_error(error)

    # ------------------------------------------------------------------
    # Tool description
    # ------------------------------------------------------------------

    def _describe(
        self,
        credential_id: str,
        allowed: List[str],
        timeout: int,
    ) -> str:
        client = None
        try:
            client, database = self._open_client(credential_id, timeout)
            names = allowed or sorted(database.list_collection_names())
            lines = ["\nCollections and sampled fields:"]
            for name in names[:MAX_SCHEMA_COLLECTIONS]:
                cursor = database[name].find({}).limit(MAX_SAMPLE_DOCUMENTS)
                fields: Set[str] = set()

                def walk(document: Any, prefix: str = "", depth: int = 0) -> None:
                    if depth > 3 or not isinstance(document, Mapping):
                        return
                    for key, value in document.items():
                        field = f"{prefix}{key}"
                        fields.add(field)
                        if isinstance(value, Mapping):
                            walk(value, f"{field}.", depth + 1)

                for document in cursor:
                    walk(document)
                shown = sorted(fields)[:MAX_SCHEMA_FIELDS]
                lines.append(f"  {name}: {', '.join(shown) if shown else 'empty'}")
                if sum(len(line) for line in lines) >= MAX_SCHEMA_DESCRIPTION_CHARACTERS:
                    lines.append("  ... schema description truncated")
                    break
            return "\n".join(lines)
        except Exception as exc:
            logger.warning(
                "MongoDB tool could not build collection metadata: %s",
                type(exc).__name__,
            )
            return ""
        finally:
            if client is not None:
                client.close()

    def _build_description(
        self,
        custom: str,
        allowed: List[str],
        granted: Set[str],
        max_documents: int,
        case_insensitive: bool,
        layout: str,
    ) -> str:
        if custom.strip():
            return custom.strip()

        verbs = {
            "read": "find, count, distinct, and aggregate",
            "insert": "insert",
            "update": "filtered update and replace_one",
            "delete": "filtered delete",
        }
        capabilities = [
            verbs[name] for name in ("read", "insert", "update", "delete") if name in granted
        ]
        scope = ", ".join(allowed) if allowed else "all collections in the selected database"
        parts = [
            "Use MongoDB through one JSON object containing action, collection, and the "
            "fields needed by that action.",
            f"Allowed operations: {'; '.join(capabilities)}.",
            f"Collection scope: {scope}.",
            f"Read results contain at most {max_documents} documents.",
            "Updates and deletes require a non-empty filter.",
            "Cross-collection aggregation, aggregation writes, and server-side JavaScript "
            "operators are refused.",
        ]
        if case_insensitive:
            parts.append(
                "Plain string equality filters are rewritten as escaped case-insensitive "
                "matches; explicit operators retain their original semantics."
            )
        parts.append(
            'Examples: {"action":"find","collection":"customers","filter":'
            '{"address.city":"Istanbul"},"limit":5} · '
            '{"action":"count","collection":"orders","filter":{"status":"pending"}} · '
            '{"action":"update_one","collection":"customers","filter":'
            '{"email":"a@b.com"},"update":{"is_active":false}}'
        )
        return " ".join(parts) + layout

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def validate_configuration(self, **inputs: Any) -> None:
        credential_id = self._setting(inputs, "credential_id", None)
        self._connection_details(credential_id)
        self._resolve_allowed_collections(
            self._setting(inputs, "allowed_collections", ""),
            self._setting(inputs, "allow_all_collections", False),
        )
        self._bounded_int(
            self._setting(inputs, "max_documents", 20),
            "Maximum Documents",
            1,
            MAX_CONFIGURED_DOCUMENTS,
        )
        self._bounded_int(
            self._setting(inputs, "operation_timeout", 15),
            "Operation Timeout",
            1,
            MAX_OPERATION_TIMEOUT,
        )
        for setting, label, fallback in (
            ("allow_all_collections", "Allow All Collections", False),
            ("return_all", "Return All Documents", False),
            ("allow_read", "Allow Read", True),
            ("allow_insert", "Allow Insert", False),
            ("allow_update", "Allow Update", False),
            ("allow_delete", "Allow Delete", False),
            ("describe_collections", "Describe Collections to the Agent", True),
            ("case_insensitive", "Case-Insensitive Text Equality", False),
        ):
            self._coerce_bool(self._setting(inputs, setting, fallback), label)

        tool_name = str(self._setting(inputs, "tool_name", "mongo_database")).strip()
        if (
            not IDENTIFIER_PATTERN.fullmatch(tool_name)
            or len(tool_name) > MAX_TOOL_NAME_CHARACTERS
        ):
            raise ValueError(
                "Tool Name must start with a letter or underscore and contain only letters, "
                f"digits, and underscores, with a maximum of {MAX_TOOL_NAME_CHARACTERS} "
                "characters."
            )
        description = str(self._setting(inputs, "tool_description", "") or "")
        if len(description) > MAX_CUSTOM_DESCRIPTION_CHARACTERS:
            raise ValueError(
                "Tool Description may contain at most "
                f"{MAX_CUSTOM_DESCRIPTION_CHARACTERS} characters."
            )

    @staticmethod
    def _parse_request(request: Any) -> Dict[str, Any]:
        if isinstance(request, Mapping):
            return dict(request)
        text = str(request or "").strip()
        if not text:
            raise ValueError("No MongoDB request was supplied.")
        if len(text) > MAX_REQUEST_CHARACTERS:
            raise ValueError(
                f"The MongoDB request exceeds {MAX_REQUEST_CHARACTERS} characters."
            )
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError("The tool input must be a valid JSON object.") from exc
        if not isinstance(payload, dict):
            raise ValueError("The tool input must be a JSON object naming an action.")
        return payload

    @classmethod
    def _projection(cls, raw: Any) -> Optional[Dict[str, int]]:
        fields = cls._parse_list(raw)
        if not fields:
            return None
        if len(fields) > 200:
            raise ValueError("Fields may contain at most 200 names.")
        return {cls._validate_field_path(field, "Projection Field"): 1 for field in fields}

    @classmethod
    def _sort(cls, raw: Any) -> Optional[List[Tuple[str, int]]]:
        if raw in (None, "", {}):
            return None
        if not isinstance(raw, Mapping) or len(raw) > 20:
            raise ValueError("Sort must be an object containing at most 20 field directions.")
        result: List[Tuple[str, int]] = []
        for field, direction in raw.items():
            name = cls._validate_field_path(field, "Sort Field")
            normalized = str(direction).strip().lower()
            if normalized in {"1", "asc", "ascending"}:
                result.append((name, 1))
            elif normalized in {"-1", "desc", "descending"}:
                result.append((name, -1))
            else:
                raise ValueError(
                    f"Sort direction for '{name}' must be asc, desc, 1, or -1."
                )
        return result

    def execute(self, **kwargs: Any) -> Dict[str, Any]:
        """Build the bounded MongoDB tool an agent will call."""
        self.validate_configuration(**kwargs)
        credential_id = self._setting(kwargs, "credential_id", None)
        allow_all = self._coerce_bool(
            self._setting(kwargs, "allow_all_collections", False),
            "Allow All Collections",
        )
        allowed = self._resolve_allowed_collections(
            self._setting(kwargs, "allowed_collections", ""), allow_all
        )
        return_all = self._coerce_bool(
            self._setting(kwargs, "return_all", False), "Return All Documents"
        )
        configured_limit = self._bounded_int(
            self._setting(kwargs, "max_documents", 20),
            "Maximum Documents",
            1,
            MAX_CONFIGURED_DOCUMENTS,
        )
        max_documents = MAX_RETURN_ALL_DOCUMENTS if return_all else configured_limit
        timeout = self._bounded_int(
            self._setting(kwargs, "operation_timeout", 15),
            "Operation Timeout",
            1,
            MAX_OPERATION_TIMEOUT,
        )
        describe = self._coerce_bool(
            self._setting(kwargs, "describe_collections", True),
            "Describe Collections to the Agent",
        )
        case_insensitive = self._coerce_bool(
            self._setting(kwargs, "case_insensitive", False),
            "Case-Insensitive Text Equality",
        )
        tool_name = str(self._setting(kwargs, "tool_name", "mongo_database")).strip()
        custom_description = str(self._setting(kwargs, "tool_description", "") or "")

        granted: Set[str] = set()
        for setting, operation, fallback, label in (
            ("allow_read", "read", True, "Allow Read"),
            ("allow_insert", "insert", False, "Allow Insert"),
            ("allow_update", "update", False, "Allow Update"),
            ("allow_delete", "delete", False, "Allow Delete"),
        ):
            if self._coerce_bool(self._setting(kwargs, setting, fallback), label):
                granted.add(operation)
        if not granted:
            raise ValueError(
                "No permission is granted, so the tool would refuse every call. "
                "Enable at least one permission."
            )

        try:
            available_collections = self._load_database_collections(credential_id, timeout)
        except Exception as exc:
            raise ValueError(self._database_error(exc)) from exc
        missing = sorted(set(allowed) - set(available_collections))
        if missing:
            raise ValueError(
                "Allowed Collections contains names that do not exist or are not visible: "
                f"{', '.join(missing)}."
            )

        logger.info(
            "MongoTool ready: collections=%s granted=%s max_documents=%s",
            allowed or "all",
            sorted(granted),
            max_documents,
        )

        def run(request: str) -> str:
            try:
                payload = self._parse_request(request)
                action = str(payload.get("action") or "").strip().lower()
                self._guard_permission(action, granted)
                collection_name = self._guard_collection(
                    payload.get("collection"), allowed
                )
                query = self._guard_filter(action, payload.get("filter"))
                if case_insensitive:
                    query = self._fold_case(query)
            except ValueError as exc:
                raise ToolException(
                    self._format_tool_error("policy_refusal", str(exc))
                ) from exc

            client = None
            try:
                client, database = self._open_client(credential_id, timeout)
                collection = database[collection_name]
                milliseconds = timeout * 1000

                if action in {"find", "find_one"}:
                    projection = self._projection(payload.get("fields"))
                    sort = self._sort(payload.get("sort"))
                    skip = self._bounded_int(
                        payload.get("skip", 0), "Skip", 0, 10_000_000
                    )
                    if action == "find_one":
                        found = collection.find_one(
                            query,
                            projection,
                            sort=sort,
                            skip=skip,
                            max_time_ms=milliseconds,
                        )
                        return self._format_documents(
                            action, collection_name, [found] if found is not None else [], False
                        )

                    requested_limit = payload.get("limit", max_documents)
                    limit = self._bounded_int(
                        requested_limit, "Limit", 1, max_documents
                    )
                    cursor = collection.find(
                        query, projection, max_time_ms=milliseconds
                    )
                    if sort:
                        cursor = cursor.sort(sort)
                    if skip:
                        cursor = cursor.skip(skip)
                    values = list(islice(cursor, limit + 1))
                    limit_reached = len(values) > limit
                    return self._format_documents(
                        action, collection_name, values[:limit], limit_reached
                    )

                if action == "count":
                    count = collection.count_documents(query, maxTimeMS=milliseconds)
                    return self._format_count(collection_name, count)

                if action == "distinct":
                    field = self._validate_field_path(payload.get("field"), "Distinct Field")
                    # Collection.distinct() materializes every unique value before the
                    # client can apply a limit. Build an equivalent bounded pipeline so
                    # a high-cardinality field cannot exhaust backend memory.
                    scoped_query = (
                        {"$and": [query, {field: {"$exists": True}}]}
                        if query
                        else {field: {"$exists": True}}
                    )
                    distinct_pipeline = [
                        {"$match": scoped_query},
                        {
                            "$project": {
                                "_values": {
                                    "$cond": [
                                        {"$isArray": f"${field}"},
                                        f"${field}",
                                        [f"${field}"],
                                    ]
                                }
                            }
                        },
                        {"$unwind": "$_values"},
                        {"$group": {"_id": "$_values"}},
                        {"$limit": max_documents + 1},
                    ]
                    cursor = collection.aggregate(
                        distinct_pipeline, maxTimeMS=milliseconds
                    )
                    values = list(islice(cursor, max_documents + 1))
                    limit_reached = len(values) > max_documents
                    documents = [
                        {field: item.get("_id")}
                        for item in values[:max_documents]
                    ]
                    return self._format_documents(
                        action, collection_name, documents, limit_reached
                    )

                if action == "aggregate":
                    pipeline = self._guard_pipeline(payload.get("pipeline"))
                    cursor = collection.aggregate(pipeline, maxTimeMS=milliseconds)
                    values = list(islice(cursor, max_documents + 1))
                    limit_reached = len(values) > max_documents
                    return self._format_documents(
                        action, collection_name, values[:max_documents], limit_reached
                    )

                if action == "insert":
                    documents = self._guard_documents(
                        payload.get("documents", payload.get("document"))
                    )
                    result = collection.insert_many(documents, ordered=True)
                    return self._format_write_result(
                        action,
                        collection_name,
                        inserted_count=len(result.inserted_ids),
                    )

                if action in {"update", "update_one"}:
                    update = self._guard_update(payload.get("update"))
                    result = (
                        collection.update_one(query, update)
                        if action == "update_one"
                        else collection.update_many(query, update)
                    )
                    return self._format_write_result(
                        action,
                        collection_name,
                        matched_count=result.matched_count,
                        modified_count=result.modified_count,
                    )

                if action == "replace_one":
                    replacement = payload.get("document")
                    if not isinstance(replacement, dict) or not replacement:
                        raise ValueError(
                            "replace_one requires a non-empty replacement document."
                        )
                    if any(str(key).startswith("$") for key in replacement):
                        raise ValueError(
                            "A replacement document cannot contain update operators."
                        )
                    self._guard_document_operators(replacement)
                    result = collection.replace_one(query, dict(replacement))
                    return self._format_write_result(
                        action,
                        collection_name,
                        matched_count=result.matched_count,
                        modified_count=result.modified_count,
                    )

                if action in {"delete", "delete_one"}:
                    result = (
                        collection.delete_one(query)
                        if action == "delete_one"
                        else collection.delete_many(query)
                    )
                    return self._format_write_result(
                        action,
                        collection_name,
                        deleted_count=result.deleted_count,
                    )

                raise ValueError(f"Unsupported action '{action}'.")
            except ValueError as exc:
                raise ToolException(
                    self._format_tool_error("invalid_input", str(exc))
                ) from exc
            except ToolException:
                raise
            except Exception as exc:
                logger.warning(
                    "MongoDB tool operation failed: action=%s error_type=%s",
                    action,
                    type(exc).__name__,
                )
                raise ToolException(
                    self._format_tool_error("database_error", self._database_error(exc))
                ) from exc
            finally:
                if client is not None:
                    client.close()

        layout = (
            self._describe(credential_id, allowed, timeout)
            if describe and not custom_description.strip()
            else ""
        )
        description = self._build_description(
            custom_description,
            allowed,
            granted,
            max_documents,
            case_insensitive,
            layout,
        )
        return {
            "mongo_tool": {
                "tool": Tool(
                    name=tool_name,
                    description=description,
                    func=run,
                    handle_tool_error=True,
                )
            }
        }

    def get_required_packages(self) -> List[str]:
        return ["pymongo==4.18.1", "langchain-core==1.6.1"]


__all__ = ["MongoToolNode"]
