"""
MongoDB Node
============

Reads from and writes to a MongoDB database inside a workflow.

A document store asks for a different shape than a relational one. There are no
columns to map, so a filter is written as a document and the fields of a record
are whatever the record happens to carry. What the node can still do is read the
collection names from the server, and look at a sample of documents to work out
which fields exist, so neither has to be typed from memory.

Filters and update documents are passed to the driver as they are, never spliced
into a string, so a value coming from a form or an upstream node cannot change
what the operation does.
"""

from __future__ import annotations

import re
import json
import time
import logging
from itertools import islice
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Mapping, Optional, Set, Tuple
from urllib.parse import quote_plus, urlencode

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

# A collection name is passed to the driver rather than into a string, but it is
# still checked so a typo surfaces as a clear message instead of a driver error.
COLLECTION_PATTERN = re.compile(r"^[^$\x00.][^$\x00]*$")
FIELD_PATH_PATTERN = re.compile(r"^(?!\$)[^\x00.]+(?:\.(?!\$)[^\x00.]+)*$")

# Operations that change data. Refused while read-only mode is on.
WRITE_OPERATIONS = {
    "insert_one", "insert_many", "update_one", "update_many",
    "replace_one", "delete_one", "delete_many",
}

# Update operators the driver understands. An update document either uses these
# or is treated as a plain replacement, which is easy to write by accident.
UPDATE_OPERATORS = {
    "$set", "$unset", "$inc", "$mul", "$rename", "$min", "$max",
    "$currentDate", "$addToSet", "$pop", "$pull", "$push", "$pullAll",
    "$bit", "$setOnInsert",
}

# Stages that write or read outside the collection being aggregated. Refused so
# an aggregation cannot quietly turn into a write.
FORBIDDEN_OPERATORS = {
    "$accumulator", "$function", "$graphLookup", "$lookup", "$merge", "$out",
    "$unionWith", "$where",
}

MAX_SAMPLE_DOCUMENTS = 200
MAX_RESULT_DOCUMENTS = 10_000
MAX_WRITE_DOCUMENTS = 10_000
SUPPORTED_OPERATIONS = {
    "aggregate", "count", "delete_many", "delete_one", "distinct", "find",
    "find_one", "insert_many", "replace_one", "update_many", "update_one",
}
SENSITIVE_VALUE_PATTERN = re.compile(
    r"(?i)(password|passwd|pwd|token|secret|api[_-]?key)\s*[:=]\s*([^\s,;]+)"
)


def _as_bool(value: Any) -> bool:
    return value is True or str(value).strip().lower() in {"1", "true", "yes", "on"}


def _flatten_node_configuration(user_data: Any) -> Dict[str, Any]:
    """Return saved node settings regardless of their flat or nested form."""
    if not isinstance(user_data, dict):
        return {}
    configuration = dict(user_data)
    nested = user_data.get("inputs")
    if isinstance(nested, dict):
        configuration.update(nested)
    return configuration


def _unwrap_connected_value(value: Any) -> Any:
    """Remove the standard execution envelope while preserving document payloads."""
    if isinstance(value, dict) and {"nodeId", "success", "output"}.issubset(value):
        return value["output"]
    return value


def _build_mongodb_uri(secret: Mapping[str, Any]) -> str:
    """Build and validate a MongoDB URI without logging credential values."""
    configuration_type = str(secret.get("configuration_type") or "values").strip()
    connection_string = str(secret.get("connection_string") or "").strip()
    uses_connection_string = configuration_type == "connection_string" or (
        bool(connection_string) and not secret.get("host")
    )
    if uses_connection_string:
        if not connection_string:
            raise ValueError("MongoDB Connection String is required.")
        if not connection_string.lower().startswith(("mongodb://", "mongodb+srv://")):
            raise ValueError(
                "MongoDB Connection String must start with mongodb:// or mongodb+srv://."
            )
        return connection_string

    host = str(secret.get("host") or "").strip()
    if not host:
        raise ValueError("MongoDB Host is required.")
    if any(character in host for character in "/?#@"):
        raise ValueError(
            "MongoDB Host must be a hostname or IP address, not a connection string."
        )

    try:
        port = int(secret.get("port") or 27017)
    except (TypeError, ValueError) as exc:
        raise ValueError("MongoDB Port must be a whole number.") from exc
    if port < 1 or port > 65535:
        raise ValueError("MongoDB Port must be between 1 and 65535.")

    username = str(secret.get("username") or "").strip()
    password = str(secret.get("password") or "")
    if password and not username:
        raise ValueError("MongoDB Username is required when a password is provided.")
    credentials = (
        f"{quote_plus(username)}:{quote_plus(password)}@" if username else ""
    )
    uri = f"mongodb://{credentials}{host}:{port}"
    auth_source = str(secret.get("auth_source") or "").strip()
    if auth_source:
        uri += f"/?{urlencode({'authSource': auth_source})}"
    return uri


class MongoNode(ProcessorNode):
    """Runs a MongoDB operation and returns the documents it produced."""

    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "MongoNode",
            "display_name": "MongoDB",
            "description": (
                "Read and write documents in a MongoDB database. Covers find, insert, update, "
                "replace, delete, count, distinct and aggregate."
            ),
            "category": "Databases",
            "node_type": NodeType.PROCESSOR,
            "icon": {
                "name": "mongodb",
                "path": "icons/mongodb.svg",
                "alt": "MongoDB",
            },
            "colors": ["sky-700", "blue-800"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description=(
                        "Documents to write. Used when the Documents field is left empty."
                    ),
                    required=False,
                    is_connection=True,
                    direction=NodePosition.LEFT,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="dict",
                    description=(
                        "Result of the operation: the documents it returned, how many were "
                        "affected and how long it took."
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
                    description="MongoDB connection to use.",
                    placeholder="Select Credential",
                    required=True,
                    serviceType="mongodb",
                    tabName="basic",
                ),
                NodeProperty(
                    name="operation",
                    displayName="Operation",
                    type=NodePropertyType.SELECT,
                    description="What to do with the collection.",
                    required=True,
                    default="find",
                    options=[
                        {"label": "Find - read documents", "value": "find"},
                        {"label": "Find One - read a single document", "value": "find_one"},
                        {"label": "Count - how many documents match", "value": "count"},
                        {"label": "Distinct - the values a field holds", "value": "distinct"},
                        {"label": "Insert - add documents", "value": "insert_many"},
                        {"label": "Update - change matching documents", "value": "update_many"},
                        {"label": "Update One - change the first match", "value": "update_one"},
                        {"label": "Replace One - swap a whole document", "value": "replace_one"},
                        {"label": "Delete - remove matching documents", "value": "delete_many"},
                        {"label": "Delete One - remove the first match", "value": "delete_one"},
                        {"label": "Aggregate - run a pipeline", "value": "aggregate"},
                    ],
                    tabName="basic",
                ),
                NodeProperty(
                    name="collection",
                    displayName="Collection",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Collection to work in.",
                    placeholder="Select or type a collection",
                    required=True,
                    default="",
                    optionsMethod="load_collections",
                    optionsDependsOn=["credential_id"],
                    tabName="basic",
                ),

                # --- Filter -----------------------------------------------
                NodeProperty(
                    name="distinct_field",
                    displayName="Field",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Field whose distinct values are returned.",
                    placeholder="Select a field",
                    required=True,
                    default="",
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={"show": {"operation": "distinct", "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="documents",
                    displayName="Document",
                    type=NodePropertyType.DOCUMENT_EDITOR,
                    description=(
                        "Fields of the document to insert. The names come from the documents "
                        "already stored; one the collection does not yet have can be added."
                    ),
                    required=False,
                    default="",
                    optionsMethod="load_field_schema",
                    optionsDependsOn=["credential_id", "collection"],
                    hint=(
                        "Leave every field empty to take the documents from the input "
                        "connection instead."
                    ),
                    displayOptions={"show": {"operation": "insert_many", "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="pipeline",
                    displayName="Pipeline",
                    type=NodePropertyType.JSON_EDITOR,
                    description="Aggregation pipeline, as an array of stages.",
                    required=True,
                    placeholder=(
                        '[{"$group": {"_id": "$status", "count": {"$sum": 1}}}]'
                    ),
                    default="[]",
                    hint=(
                        "Stages that write or read another collection, such as $out, $merge and "
                        "$lookup, are not allowed."
                    ),
                    displayOptions={"show": {"operation": "aggregate", "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_field",
                    displayName="Filter Field",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Field the documents are matched on. Leave empty to match every "
                        "document, which for Delete means the whole collection."
                    ),
                    placeholder="No filter, match every document",
                    required=False,
                    default="",
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={
                        "show": {
                            "operation": [
                                "find", "find_one", "count", "distinct",
                                "update_one", "update_many", "replace_one",
                                "delete_one", "delete_many",
                            ],
                            "collection": "*",
                        }
                    },
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_operator",
                    displayName="Filter Operator",
                    type=NodePropertyType.SELECT,
                    description="How the field is compared to the value.",
                    required=False,
                    default="equals",
                    options=[
                        {"label": "is equal to", "value": "equals"},
                        {"label": "is not equal to", "value": "not_equals"},
                        {"label": "is greater than", "value": "greater_than"},
                        {"label": "is greater than or equal to", "value": "greater_or_equal"},
                        {"label": "is less than", "value": "less_than"},
                        {"label": "is less than or equal to", "value": "less_or_equal"},
                        {"label": "contains", "value": "contains"},
                        {"label": "starts with", "value": "starts_with"},
                        {"label": "is one of", "value": "in"},
                        {"label": "is not one of", "value": "not_in"},
                        {"label": "exists", "value": "exists"},
                        {"label": "does not exist", "value": "not_exists"},
                    ],
                    displayOptions={
                        "show": {
                            "operation": [
                                "find", "find_one", "count", "distinct",
                                "update_one", "update_many", "replace_one",
                                "delete_one", "delete_many",
                            ],
                            "filter_field": "*",
                        }
                    },
                    tabName="basic",
                ),
                NodeProperty(
                    name="filter_value",
                    displayName="Filter Value",
                    type=NodePropertyType.TEXT,
                    description=(
                        "Value the field is compared to. Separate several values with commas "
                        "for the one-of operators."
                    ),
                    placeholder="Value to match",
                    required=False,
                    default="",
                    displayOptions={
                        "show": {
                            "operation": [
                                "find", "find_one", "count", "distinct",
                                "update_one", "update_many", "replace_one",
                                "delete_one", "delete_many",
                            ],
                            "filter_field": "*",
                            "filter_operator": [
                                "equals", "not_equals", "greater_than", "greater_or_equal",
                                "less_than", "less_or_equal", "contains", "starts_with",
                                "in", "not_in",
                            ],
                        }
                    },
                    tabName="basic",
                ),

                # --- Read options -----------------------------------------
                NodeProperty(
                    name="update_document",
                    displayName="Fields to Change",
                    type=NodePropertyType.DOCUMENT_EDITOR,
                    description=(
                        "Fields to change on the matching documents. Only the ones filled in "
                        "are written; the rest are left as they are."
                    ),
                    required=False,
                    default="",
                    optionsMethod="load_field_schema",
                    optionsDependsOn=["credential_id", "collection"],
                    hint=(
                        "For anything an operator is needed for, such as $inc or $push, use "
                        "Advanced Update in the Advanced tab."
                    ),
                    displayOptions={
                        "show": {"operation": ["update_one", "update_many"], "collection": "*"}
                    },
                    tabName="basic",
                ),
                NodeProperty(
                    name="replacement_document",
                    displayName="Replacement Document",
                    type=NodePropertyType.DOCUMENT_EDITOR,
                    description=(
                        "Document that takes the place of the match. Every field not filled in "
                        "here is dropped from the stored document."
                    ),
                    required=False,
                    default="",
                    optionsMethod="load_field_schema",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={"show": {"operation": "replace_one", "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="projection",
                    displayName="Fields to Return",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Fields to include in the result. Leave empty to return all.",
                    placeholder="All fields",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={"show": {"operation": ["find", "find_one"], "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="return_all",
                    displayName="Return All",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Return matching documents up to the platform safety limit, ignoring "
                        "the configurable limit below."
                    ),
                    required=False,
                    default=False,
                    displayOptions={"show": {"operation": "find", "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="limit",
                    displayName="Limit",
                    type=NodePropertyType.NUMBER,
                    description="Largest number of documents to return.",
                    required=False,
                    default=50,
                    min=1,
                    max=10000,
                    displayOptions={"show": {"operation": "find", "return_all": False}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_field",
                    displayName="Sort Field",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description="Field the results are ordered by.",
                    placeholder="No ordering",
                    required=False,
                    default="",
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={"show": {"operation": ["find", "find_one"], "collection": "*"}},
                    tabName="basic",
                ),
                NodeProperty(
                    name="sort_direction",
                    displayName="Sort Direction",
                    type=NodePropertyType.SELECT,
                    description="Order the results are returned in.",
                    required=False,
                    default="asc",
                    options=[
                        {"label": "Ascending", "value": "asc"},
                        {"label": "Descending", "value": "desc"},
                    ],
                    displayOptions={
                        "show": {"operation": ["find", "find_one"], "sort_field": "*"}
                    },
                    tabName="basic",
                ),

                # --- Write ------------------------------------------------
                NodeProperty(
                    name="write_fields",
                    displayName="Fields to Write",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Fields to take from the incoming documents. Leave empty to write every "
                        "field they carry."
                    ),
                    placeholder="All fields",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    hint=(
                        "A trigger usually sends more than the document itself. Naming the "
                        "fields keeps the extras out. A name that is not in the list can be "
                        "typed."
                    ),
                    displayOptions={"show": {"operation": "insert_many", "collection": "*"}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="update_fields",
                    displayName="Fields to Update",
                    type=NodePropertyType.DYNAMIC_SELECT,
                    description=(
                        "Fields to take from the incoming documents when the Update field is "
                        "left empty. Leave both empty to write every field they carry."
                    ),
                    placeholder="All fields",
                    required=False,
                    default="",
                    multiple=True,
                    optionsMethod="load_fields",
                    optionsDependsOn=["credential_id", "collection"],
                    displayOptions={
                        "show": {"operation": ["update_one", "update_many"], "collection": "*"}
                    },
                    tabName="advanced",
                ),
                NodeProperty(
                    name="upsert",
                    displayName="Insert if Missing",
                    type=NodePropertyType.CHECKBOX,
                    description="Insert the document when nothing matches the filter.",
                    required=False,
                    default=False,
                    displayOptions={
                        "show": {
                            "operation": ["update_one", "update_many", "replace_one"],
                            "collection": "*",
                        }
                    },
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
                        "Refuse any operation that would change data. Useful when the node runs "
                        "on data you cannot afford to lose."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="allow_empty_filter",
                    displayName="Allow Empty Filter",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Allow update, replace, or delete operations without a filter. This can "
                        "change or remove arbitrary documents and should be enabled deliberately."
                    ),
                    required=False,
                    default=False,
                    displayOptions={
                        "show": {
                            "operation": [
                                "update_one", "update_many", "replace_one",
                                "delete_one", "delete_many",
                            ]
                        }
                    },
                    tabName="advanced",
                ),
                NodeProperty(
                    name="advanced_update",
                    type=NodePropertyType.JSON_EDITOR,
                    displayName="Advanced Update",
                    description=(
                        "Update document written by hand, for what an operator is needed for. "
                        "Takes the place of Fields to Change when filled in."
                    ),
                    placeholder='{"$inc": {"stock": -1}}',
                    required=False,
                    default="",
                    hint=(
                        "Operators: $set, $unset, $inc, $push, $pull, $addToSet, $rename, "
                        "$currentDate"
                    ),
                    displayOptions={"show": {"operation": ["update_one", "update_many"]}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="extra_filter",
                    displayName="Extra Filter",
                    type=NodePropertyType.JSON_EDITOR,
                    description=(
                        "Further conditions as a MongoDB filter document, for cases the single "
                        "filter above cannot express. Merged with it."
                    ),
                    placeholder='{"balance": {"$gt": 1000}}',
                    required=False,
                    default="",
                    displayOptions={
                        "show": {
                            "operation": [
                                "find", "find_one", "count", "distinct",
                                "update_one", "update_many", "replace_one",
                                "delete_one", "delete_many",
                            ]
                        }
                    },
                    tabName="advanced",
                ),
                NodeProperty(
                    name="case_insensitive",
                    displayName="Ignore Capitalisation",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Match text without regard to case, so a value typed in lower case still "
                        "finds documents stored with capitals."
                    ),
                    required=False,
                    default=True,
                    displayOptions={"show": {"filter_field": "*"}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="skip",
                    displayName="Skip",
                    type=NodePropertyType.NUMBER,
                    description="Number of documents to pass over before returning any.",
                    required=False,
                    default=0,
                    min=0,
                    max=10000000,
                    displayOptions={"show": {"operation": ["find", "find_one"]}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="ordered_insert",
                    displayName="Stop on First Error",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Stop inserting at the first document that fails. Turn off to keep going "
                        "and insert the rest."
                    ),
                    required=False,
                    default=True,
                    displayOptions={"show": {"operation": "insert_many"}},
                    tabName="advanced",
                ),
                NodeProperty(
                    name="connection_timeout",
                    displayName="Connection Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="How long to wait for the server to answer.",
                    required=False,
                    default=10,
                    min=1,
                    max=120,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="operation_timeout",
                    displayName="Operation Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Cancel an operation that runs longer than this.",
                    required=False,
                    default=30,
                    min=1,
                    max=300,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="continue_on_error",
                    displayName="Continue on Error",
                    type=NodePropertyType.CHECKBOX,
                    description=(
                        "Carry the error in the output instead of stopping the workflow."
                    ),
                    required=False,
                    default=False,
                    tabName="advanced",
                ),
            ],
        }

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    def _connection_details(self, credential_id: Optional[str]) -> Tuple[str, str]:
        """Read the credential and return the URI and the database name."""
        if not credential_id:
            raise ValueError("A MongoDB credential must be selected.")

        credential = self.get_credential(credential_id)
        if not credential:
            raise ValueError("The selected MongoDB credential could not be found.")
        if credential.get("service_type") != "mongodb":
            raise ValueError("The selected credential is not a MongoDB credential.")

        secret = credential.get("secret") or {}
        if not isinstance(secret, dict):
            raise ValueError("The selected MongoDB credential has an invalid secret payload.")
        database = str(secret.get("database") or "").strip()
        if not database:
            raise ValueError("MongoDB Database Name is required.")
        if "\x00" in database:
            raise ValueError("MongoDB Database Name contains an invalid character.")

        return _build_mongodb_uri(secret), database

    def _open_client(
        self,
        credential_id: Optional[str],
        connection_timeout: int = 10,
        operation_timeout: int = 30,
    ):
        """Open a client and the database it points at."""
        try:
            from pymongo import MongoClient
        except ImportError as exc:
            raise ValueError(
                "The pymongo package is not installed on the server."
            ) from exc

        uri, database_name = self._connection_details(credential_id)
        client = MongoClient(
            uri,
            serverSelectionTimeoutMS=connection_timeout * 1000,
            connectTimeoutMS=connection_timeout * 1000,
            socketTimeoutMS=operation_timeout * 1000,
        )
        try:
            client.admin.command("ping")
            return client, client[database_name]
        except Exception:
            client.close()
            raise

    # ------------------------------------------------------------------
    # Option loaders
    # ------------------------------------------------------------------

    def load_collections(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """Fill the collection dropdown."""
        client = None
        try:
            client, database = self._open_client(values.get("credential_id"))
            names = sorted(database.list_collection_names())
            return [{"label": name, "value": name} for name in names]
        except Exception as exc:
            raise ValueError(self._database_error(exc)) from exc
        finally:
            if client is not None:
                client.close()

    def load_fields(self, values: Dict[str, Any]) -> List[Dict[str, str]]:
        """
        Fill a field dropdown.

        A collection has no declared shape, so the field names are worked out
        from a sample of documents. Nested objects are walked so a filter can be
        written against something like address.city, which is how a document
        store is usually laid out.
        """
        collection_name = str(values.get("collection") or "").strip()
        if not collection_name:
            return []
        collection_name = self._validate_collection(collection_name)

        client = None
        try:
            client, database = self._open_client(values.get("credential_id"))
            documents = list(
                database[collection_name].find({}, limit=MAX_SAMPLE_DOCUMENTS)
            )
        except Exception as exc:
            raise ValueError(self._database_error(exc)) from exc
        finally:
            if client is not None:
                client.close()

        fields: Set[str] = set()

        def walk(document: Any, prefix: str = "", depth: int = 0) -> None:
            if depth > 3 or not isinstance(document, dict):
                return
            for key, value in document.items():
                path = f"{prefix}{key}"
                fields.add(path)
                if isinstance(value, dict):
                    walk(value, f"{path}.", depth + 1)

        for document in documents:
            walk(document)

        return [{"label": name, "value": name} for name in sorted(fields)]

    def load_field_schema(self, values: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Describe the fields a collection habitually carries.

        There is no schema to read, so a sample of the documents is examined and
        the widget for each field is chosen from the values found there.

        Nested objects are walked and their leaves listed under a dotted path,
        so address.city gets an input of its own rather than the whole address
        arriving as one block of JSON. A field that appears in only a handful of
        documents is still listed, since a document store is often chosen
        precisely because records differ.
        """
        collection_name = str(values.get("collection") or "").strip()
        if not collection_name:
            return []
        collection_name = self._validate_collection(collection_name)

        client = None
        try:
            client, database = self._open_client(values.get("credential_id"))
            documents = list(
                database[collection_name].find({}, limit=MAX_SAMPLE_DOCUMENTS)
            )
        except Exception as exc:
            raise ValueError(self._database_error(exc)) from exc
        finally:
            if client is not None:
                client.close()

        seen: Dict[str, int] = {}
        types: Dict[str, Set[str]] = {}

        def widget_for(value: Any) -> str:
            if isinstance(value, bool):
                return "checkbox"
            if isinstance(value, (int, float, Decimal)):
                return "number"
            if isinstance(value, (datetime, date)):
                return "datetime"
            if isinstance(value, (dict, list)):
                return "json"
            return "text"

        def walk(document: Any, prefix: str = "", depth: int = 0) -> None:
            if not isinstance(document, dict):
                return
            for key, value in document.items():
                if not prefix and key == "_id":
                    continue
                path = f"{prefix}{key}"

                # An object is opened up rather than listed, so its leaves each
                # get their own input. A list is left whole, since its entries
                # have no names to draw.
                if isinstance(value, dict) and value and depth < 3:
                    walk(value, f"{path}.", depth + 1)
                    continue

                seen[path] = seen.get(path, 0) + 1
                types.setdefault(path, set()).add(widget_for(value))

        for document in documents:
            walk(document)

        fields = []
        for name in sorted(seen):
            found = types[name]
            # One kind of value means the widget is certain; a mix falls back to
            # text, which accepts anything.
            widget = next(iter(found)) if len(found) == 1 else "text"
            fields.append({"name": name, "widget": widget, "seen": seen[name]})
        return fields

    # ------------------------------------------------------------------
    # Value handling
    # ------------------------------------------------------------------

    @staticmethod
    def _coerce_json(raw: Any, fallback: Any = None) -> Any:
        """Read a JSON field that may arrive as text or as a parsed value."""
        if raw is None or raw == "":
            return fallback
        if isinstance(raw, (dict, list)):
            return raw
        if isinstance(raw, str):
            try:
                return json.loads(raw)
            except json.JSONDecodeError as exc:
                raise ValueError(f"The JSON could not be read: {exc}") from exc
        return fallback

    @staticmethod
    def _guess_type(text: str) -> Any:
        """
        Read a typed value out of the text a filter field carries.

        A form hands over a string, but a filter on a number or a flag has to
        compare against the same type the document stores, or it matches nothing.
        """
        value = text.strip()
        if not value:
            return value

        lowered = value.lower()
        if lowered == "true":
            return True
        if lowered == "false":
            return False
        if lowered in ("null", "none"):
            return None

        try:
            return int(value)
        except ValueError:
            pass
        try:
            return float(value)
        except ValueError:
            pass

        # An ISO date is recognised so a range filter on a timestamp works.
        if re.match(r"^\d{4}-\d{2}-\d{2}([T ]\d{2}:\d{2}(:\d{2})?)?", value):
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    parsed = parsed.replace(tzinfo=timezone.utc)
                return parsed
            except ValueError:
                pass

        return value

    @classmethod
    def _to_object_id(cls, value: Any) -> Any:
        """Turn a 24 character hex string into an ObjectId when it looks like one."""
        if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{24}", value):
            try:
                from bson import ObjectId

                return ObjectId(value)
            except Exception:
                return value
        return value

    @classmethod
    def _serialize(cls, value: Any) -> Any:
        """Turn driver types into something that survives being written as JSON."""
        if value is None or isinstance(value, (str, int, float, bool)):
            return value
        if isinstance(value, Decimal):
            return float(value)
        if isinstance(value, (datetime, date)):
            return value.isoformat()
        if isinstance(value, (bytes, bytearray)):
            return "<binary>"
        if isinstance(value, dict):
            return {key: cls._serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple, set)):
            return [cls._serialize(item) for item in value]
        # ObjectId, Decimal128 and the rest render as text.
        return str(value)

    # ------------------------------------------------------------------
    # Filter building
    # ------------------------------------------------------------------

    def _build_filter(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """
        Assemble the filter document.

        The three filter fields cover the common case of a single comparison and
        are picked from lists rather than typed. Anything more involved goes in
        Extra Filter as a MongoDB document, and the two are merged.
        """
        conditions: List[Dict[str, Any]] = []

        field = str(inputs.get("filter_field") or "").strip()
        if field:
            field = self._validate_field_path(field, "Filter Field")
            operator = (inputs.get("filter_operator") or "equals").strip()
            raw_value = inputs.get("filter_value", "")
            ignore_case = _as_bool(inputs.get("case_insensitive", True))

            if operator == "exists":
                conditions.append({field: {"$exists": True}})
            elif operator == "not_exists":
                conditions.append({field: {"$exists": False}})
            elif operator in ("in", "not_in"):
                parts = [
                    self._guess_type(part)
                    for part in str(raw_value).split(",")
                    if part.strip()
                ]
                if field == "_id":
                    parts = [self._to_object_id(part) for part in parts]
                conditions.append(
                    {field: {"$in" if operator == "in" else "$nin": parts}}
                )
            elif operator in ("contains", "starts_with"):
                pattern = re.escape(str(raw_value))
                if operator == "starts_with":
                    pattern = f"^{pattern}"
                regex = {"$regex": pattern}
                if ignore_case:
                    regex["$options"] = "i"
                conditions.append({field: regex})
            else:
                value = self._guess_type(str(raw_value))
                if field == "_id":
                    value = self._to_object_id(value)

                if operator == "equals":
                    # An exact match on text ignores case when asked to, so a
                    # value typed as "bursa" still finds "Bursa" and "BURSA".
                    if ignore_case and isinstance(value, str) and value:
                        conditions.append(
                            {
                                field: {
                                    "$regex": f"^{re.escape(value)}$",
                                    "$options": "i",
                                }
                            }
                        )
                    else:
                        conditions.append({field: value})
                elif operator == "not_equals":
                    if ignore_case and isinstance(value, str) and value:
                        conditions.append(
                            {
                                field: {
                                    "$not": {
                                        "$regex": f"^{re.escape(value)}$",
                                        "$options": "i",
                                    }
                                }
                            }
                        )
                    else:
                        conditions.append({field: {"$ne": value}})
                else:
                    mongo_operator = {
                        "greater_than": "$gt",
                        "greater_or_equal": "$gte",
                        "less_than": "$lt",
                        "less_or_equal": "$lte",
                    }.get(operator)
                    if not mongo_operator:
                        raise ValueError(f"Unknown filter operator: {operator}")
                    conditions.append({field: {mongo_operator: value}})

        extra = self._coerce_json(inputs.get("extra_filter"), None)
        if extra:
            if not isinstance(extra, dict):
                raise ValueError("Extra Filter has to be a JSON object.")
            self._guard_document_operators(extra)
            conditions.append(extra)

        if not conditions:
            return {}
        if len(conditions) == 1:
            return conditions[0]
        return {"$and": conditions}

    # ------------------------------------------------------------------
    # Guards
    # ------------------------------------------------------------------

    @staticmethod
    def _validate_collection(name: str) -> str:
        """Refuse a collection name the server would reject anyway."""
        name = (name or "").strip()
        if not name:
            raise ValueError("A collection is required.")
        if not COLLECTION_PATTERN.match(name):
            raise ValueError(
                f"Collection '{name}' is not a usable name. It cannot be empty, start with a "
                "dot, or hold a dollar sign."
            )
        return name

    @staticmethod
    def _validate_field_path(name: Any, label: str = "Field") -> str:
        path = str(name or "").strip()
        if not path or not FIELD_PATH_PATTERN.fullmatch(path):
            raise ValueError(
                f"{label} must contain valid MongoDB field names separated by dots and "
                "must not start a segment with '$'."
            )
        return path

    @staticmethod
    def _guard_read_only(operation: str) -> None:
        """Refuse anything that would change data while read-only mode is on."""
        if operation in WRITE_OPERATIONS:
            raise ValueError(
                f"Read Only is enabled, so the '{operation}' operation is not allowed. "
                "Turn Read Only off in the Advanced tab to write to the database."
            )

    @classmethod
    def _guard_document_operators(cls, value: Any) -> None:
        """Reject cross-collection, write, and server-side JavaScript operators."""
        if isinstance(value, dict):
            for name, nested in value.items():
                if name in FORBIDDEN_OPERATORS:
                    raise ValueError(
                        f"The {name} operator is not allowed in this node."
                    )
                cls._guard_document_operators(nested)
        elif isinstance(value, list):
            for nested in value:
                cls._guard_document_operators(nested)

    @classmethod
    def _guard_pipeline(cls, pipeline: List[Any]) -> None:
        """Validate every stage and recursively reject unsafe operators."""
        if not pipeline:
            raise ValueError("The aggregation pipeline cannot be empty.")
        for stage in pipeline:
            if not isinstance(stage, dict) or len(stage) != 1:
                raise ValueError(
                    "Every aggregation pipeline stage must be an object with one operator."
                )
        cls._guard_document_operators(pipeline)

    @staticmethod
    def _guard_scoped_write(
        operation: str,
        query: Mapping[str, Any],
        allow_empty_filter: bool,
    ) -> None:
        if operation in {
            "delete_many", "delete_one", "replace_one", "update_many", "update_one"
        } and not query and not allow_empty_filter:
            raise ValueError(
                f"The '{operation}' operation requires a filter. Enable Allow Empty Filter "
                "only when intentionally targeting documents without a filter."
            )

    @classmethod
    def _bounded_documents(
        cls,
        documents: Iterable[Any],
        limit: int,
    ) -> Tuple[List[Any], bool]:
        values = list(islice(documents, limit + 1))
        truncated = len(values) > limit
        return values[:limit], truncated

    @staticmethod
    def _bounded_int(value: Any, label: str, minimum: int, maximum: int) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{label} must be a whole number.") from exc
        if parsed < minimum or parsed > maximum:
            raise ValueError(f"{label} must be between {minimum} and {maximum}.")
        return parsed

    def _prepare_update(self, raw: Any) -> Dict[str, Any]:
        """
        Read the update document.

        A plain object is wrapped in $set, which is what someone writing
        {"status": "shipped"} means. Left as it was, the driver would take it for
        a replacement and drop every other field.
        """
        update = self._coerce_json(raw, None)
        if not update:
            raise ValueError("An update document is required.")
        if not isinstance(update, dict):
            raise ValueError("The update has to be a JSON object.")

        if any(key.startswith("$") for key in update):
            plain_keys = [key for key in update if not key.startswith("$")]
            if plain_keys:
                raise ValueError(
                    "An advanced update cannot mix update operators with plain field names."
                )
            unknown = [
                key
                for key in update
                if key.startswith("$") and key not in UPDATE_OPERATORS
            ]
            if unknown:
                raise ValueError(
                    f"Unknown update operator: {', '.join(unknown)}. "
                    f"Supported: {', '.join(sorted(UPDATE_OPERATORS))}"
                )
            return update

        return {"$set": update}

    # ------------------------------------------------------------------
    # Documents to write
    # ------------------------------------------------------------------

    ENVELOPE_KEYS = (
        "webhook_data", "payload", "body", "json", "data", "result", "rows",
        "documents",
    )

    @classmethod
    def _unwrap_payload(cls, value: Any, depth: int = 4) -> Any:
        """Reach the documents inside a trigger's envelope."""
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
    def _clean_document(cls, document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Drop the fields left empty and keep the rest as they were entered.

        The editor hands over a value for every field it drew, so the ones the
        author did not touch have to be dropped rather than stored as empty
        strings.

        Nothing else is converted. The widget has already settled the type: a
        number input returns a number, a checkbox a boolean, a date picker a
        date. Guessing again over a text input would turn a phone number or a
        postal code into a number and lose its leading zero, so what was typed
        is what is stored. A field drawn as JSON is the one exception, since it
        arrives as text and has to be parsed back.
        """
        cleaned: Dict[str, Any] = {}
        for key, value in document.items():
            if value is None or value == "":
                continue

            if isinstance(value, str):
                stripped = value.strip()
                if not stripped:
                    continue
                if stripped[0] in "[{":
                    try:
                        cleaned[key] = json.loads(stripped)
                        continue
                    except json.JSONDecodeError:
                        pass
                cleaned[key] = stripped
            else:
                cleaned[key] = value

        return cleaned

    @staticmethod
    def _nest_dotted(document: Dict[str, Any]) -> Dict[str, Any]:
        """
        Turn dotted names back into the nested objects they describe.

        The editor draws address.city as an input of its own, but a document
        holding a field literally called "address.city" is not what was meant,
        and MongoDB would refuse it besides. The path is walked back into place
        so the document comes out the shape it was drawn from.
        """
        nested: Dict[str, Any] = {}

        for key, value in document.items():
            if "." not in key:
                nested[key] = value
                continue

            parts = key.split(".")
            cursor = nested
            for part in parts[:-1]:
                existing = cursor.get(part)
                if not isinstance(existing, dict):
                    existing = {}
                    cursor[part] = existing
                cursor = existing
            cursor[parts[-1]] = value

        return nested

    @classmethod
    def _pick_fields(
        cls, document: Dict[str, Any], wanted: List[str]
    ) -> Dict[str, Any]:
        """
        Keep only the named fields of a document.

        A dotted name reaches into a nested object, so address.city can be taken
        without the rest of the address coming with it.
        """
        if not wanted:
            return document

        picked: Dict[str, Any] = {}
        for name in wanted:
            if "." not in name:
                if name in document:
                    picked[name] = document[name]
                continue

            head, _, tail = name.partition(".")
            source = document.get(head)
            if not isinstance(source, dict):
                continue
            nested = cls._pick_fields(source, [tail])
            if nested:
                picked.setdefault(head, {}).update(nested)

        return picked

    def _resolve_documents(
        self,
        raw: Any,
        connected_nodes: Dict[str, Any],
        wanted_fields: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Collect the documents to write.

        They come either from the field or from the input connection. Data
        arriving on the connection is narrowed to the named fields, since a
        trigger sends its own context alongside the document and those extras
        have no business being stored.
        """
        data = self._coerce_json(raw, None)
        from_connection = False

        if not data:
            data = self._unwrap_payload(connected_nodes.get("input"))
            from_connection = True

        if isinstance(data, dict):
            documents = [data]
        elif isinstance(data, list):
            documents = [item for item in data if isinstance(item, dict) and item]
        else:
            documents = []

        if not documents:
            raise ValueError(
                "No documents were supplied. Fill in the Documents field or connect a node that "
                "produces an object or a list of objects."
            )

        # The field list narrows what is written, whichever way the data arrived.
        if wanted_fields:
            narrowed = [self._pick_fields(document, wanted_fields) for document in documents]
            narrowed = [document for document in narrowed if document]
            if not narrowed:
                raise ValueError(
                    "None of the named fields were found in the incoming documents. "
                    "Check the field names, or leave Fields to Write empty to write everything."
                )
            documents = narrowed
        elif from_connection:
            # Nothing was named, so anything the trigger wrapped around the
            # document is dropped rather than stored alongside it.
            documents = [
                {
                    key: value
                    for key, value in document.items()
                    if key not in self.ENVELOPE_KEYS
                }
                for document in documents
            ]

        return documents

    @staticmethod
    def _database_error(error: Exception) -> str:
        """Return a stable message without leaking connection-string credentials."""
        try:
            from pymongo.errors import (
                ConfigurationError,
                DuplicateKeyError,
                ExecutionTimeout,
                OperationFailure,
                ServerSelectionTimeoutError,
            )

            if isinstance(error, ServerSelectionTimeoutError):
                return "Could not reach the configured MongoDB server before the timeout."
            if isinstance(error, ExecutionTimeout):
                return "The MongoDB operation exceeded its configured timeout."
            if isinstance(error, DuplicateKeyError):
                return "The operation conflicts with an existing unique value."
            if isinstance(error, ConfigurationError):
                return "The MongoDB connection configuration is invalid."
            if isinstance(error, OperationFailure):
                if getattr(error, "code", None) in {13, 18}:
                    return "MongoDB authentication or authorization failed."
                return "MongoDB rejected the requested operation."
        except ImportError:
            pass

        message = str(error).strip() or "The MongoDB operation could not be completed."
        message = re.sub(
            r"mongodb(?:\+srv)?://[^\s]+",
            "[redacted MongoDB connection string]",
            message,
            flags=re.IGNORECASE,
        )
        return SENSITIVE_VALUE_PATTERN.sub(r"\1=[redacted]", message)[:500]

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def execute(
        self,
        inputs: Dict[str, Any],
        connected_nodes: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Run one bounded MongoDB operation and return a stable result envelope."""
        started_at = time.time()
        configuration = {**_flatten_node_configuration(self.user_data), **inputs}
        operation = str(configuration.get("operation") or "find").strip().lower()
        continue_on_error = _as_bool(configuration.get("continue_on_error"))
        client = None
        collection_name = str(configuration.get("collection") or "").strip()
        attempted = 0
        written = 0
        truncated = False
        errors: List[Dict[str, Any]] = []

        try:
            if operation not in SUPPORTED_OPERATIONS:
                raise ValueError(f"Unsupported MongoDB operation: {operation}")
            if _as_bool(configuration.get("read_only")):
                self._guard_read_only(operation)

            collection_name = self._validate_collection(collection_name)
            connection_timeout = self._bounded_int(
                configuration.get("connection_timeout") or 10,
                "Connection Timeout",
                1,
                120,
            )
            operation_timeout_seconds = self._bounded_int(
                configuration.get("operation_timeout") or 30,
                "Operation Timeout",
                1,
                300,
            )
            operation_timeout = operation_timeout_seconds * 1000

            client, database = self._open_client(
                configuration.get("credential_id"),
                connection_timeout,
                operation_timeout_seconds,
            )
            collection = database[collection_name]
            documents: List[Any] = []
            affected = 0

            if operation in {"find", "find_one"}:
                query = self._build_filter(configuration)
                fields = self._build_projection(configuration.get("projection"))
                sort_field = str(configuration.get("sort_field") or "").strip()
                sort = None
                if sort_field:
                    sort_field = self._validate_field_path(sort_field, "Sort Field")
                    sort = [
                        (
                            sort_field,
                            -1 if configuration.get("sort_direction") == "desc" else 1,
                        )
                    ]
                skip = self._bounded_int(
                    configuration.get("skip") or 0,
                    "Skip",
                    0,
                    10_000_000,
                )

                if operation == "find_one":
                    found = collection.find_one(
                        query,
                        fields,
                        sort=sort,
                        skip=skip,
                        max_time_ms=operation_timeout,
                    )
                    documents = [found] if found is not None else []
                else:
                    result_limit = (
                        MAX_RESULT_DOCUMENTS
                        if _as_bool(configuration.get("return_all"))
                        else self._bounded_int(
                            configuration.get("limit") or 50,
                            "Limit",
                            1,
                            MAX_RESULT_DOCUMENTS,
                        )
                    )
                    cursor = collection.find(
                        query, fields, max_time_ms=operation_timeout
                    )
                    if sort:
                        cursor = cursor.sort(sort)
                    if skip:
                        cursor = cursor.skip(skip)
                    cursor = cursor.limit(result_limit + 1)
                    documents, truncated = self._bounded_documents(
                        cursor, result_limit
                    )
                affected = len(documents)

            elif operation == "count":
                query = self._build_filter(configuration)
                affected = collection.count_documents(
                    query, maxTimeMS=operation_timeout
                )
                documents = [{"count": affected}]

            elif operation == "distinct":
                field = self._validate_field_path(
                    configuration.get("distinct_field"), "Distinct Field"
                )
                query = self._build_filter(configuration)
                pipeline: List[Dict[str, Any]] = []
                if query:
                    pipeline.append({"$match": query})
                pipeline.extend(
                    [
                        {"$group": {"_id": f"${field}"}},
                        {"$limit": MAX_RESULT_DOCUMENTS + 1},
                    ]
                )
                values, truncated = self._bounded_documents(
                    collection.aggregate(pipeline, maxTimeMS=operation_timeout),
                    MAX_RESULT_DOCUMENTS,
                )
                documents = [{field: value.get("_id")} for value in values]
                affected = len(documents)

            elif operation == "aggregate":
                pipeline = self._coerce_json(configuration.get("pipeline"), [])
                if not isinstance(pipeline, list):
                    raise ValueError("Pipeline must be a JSON array of stages.")
                self._guard_pipeline(pipeline)
                documents, truncated = self._bounded_documents(
                    collection.aggregate(pipeline, maxTimeMS=operation_timeout),
                    MAX_RESULT_DOCUMENTS,
                )
                affected = len(documents)

            elif operation == "insert_many":
                written_by_hand = self._coerce_json(
                    configuration.get("documents"), None
                )
                if isinstance(written_by_hand, dict):
                    written_by_hand = self._nest_dotted(
                        self._clean_document(written_by_hand)
                    ) or None

                connected = dict(connected_nodes or {})
                connected["input"] = _unwrap_connected_value(connected.get("input"))
                to_insert = self._resolve_documents(
                    written_by_hand,
                    connected,
                    self._parse_list(configuration.get("write_fields")),
                )
                attempted = len(to_insert)
                if attempted > MAX_WRITE_DOCUMENTS:
                    raise ValueError(
                        f"A single execution can insert at most {MAX_WRITE_DOCUMENTS} documents."
                    )

                ordered = _as_bool(configuration.get("ordered_insert", True))
                try:
                    result = collection.insert_many(to_insert, ordered=ordered)
                    written = len(result.inserted_ids)
                    affected = written
                    documents = [
                        {**document, "_id": inserted}
                        for document, inserted in zip(to_insert, result.inserted_ids)
                    ]
                except Exception as exc:
                    from pymongo.errors import BulkWriteError

                    if not isinstance(exc, BulkWriteError) or ordered or not continue_on_error:
                        raise
                    details = exc.details or {}
                    written = max(0, int(details.get("nInserted") or 0))
                    affected = written
                    errors = [
                        {
                            "success": False,
                            "item_index": item.get("index"),
                            "code": item.get("code"),
                            "message": self._database_error(
                                ValueError(str(item.get("errmsg") or "Insert failed."))
                            ),
                        }
                        for item in details.get("writeErrors", [])
                    ]
                    documents = [{"inserted_count": written}]

            elif operation in {"update_one", "update_many"}:
                query = self._build_filter(configuration)
                self._guard_scoped_write(
                    operation,
                    query,
                    _as_bool(configuration.get("allow_empty_filter")),
                )
                raw_update = self._coerce_json(
                    configuration.get("advanced_update"), None
                )
                if not raw_update:
                    edited = self._coerce_json(
                        configuration.get("update_document"), None
                    )
                    if isinstance(edited, dict):
                        raw_update = self._clean_document(edited) or None
                if not raw_update:
                    connected = dict(connected_nodes or {})
                    connected["input"] = _unwrap_connected_value(
                        connected.get("input")
                    )
                    incoming = self._resolve_documents(
                        None,
                        connected,
                        self._parse_list(configuration.get("update_fields")),
                    )
                    raw_update = incoming[0]

                update = self._prepare_update(raw_update)
                self._guard_document_operators(update)
                attempted = 1
                upsert = _as_bool(configuration.get("upsert"))
                result = (
                    collection.update_one(query, update, upsert=upsert)
                    if operation == "update_one"
                    else collection.update_many(query, update, upsert=upsert)
                )
                written = result.modified_count + int(result.upserted_id is not None)
                affected = written
                documents = [
                    {
                        "matched_count": result.matched_count,
                        "modified_count": result.modified_count,
                        "upserted_id": result.upserted_id,
                    }
                ]

            elif operation == "replace_one":
                query = self._build_filter(configuration)
                self._guard_scoped_write(
                    operation,
                    query,
                    _as_bool(configuration.get("allow_empty_filter")),
                )
                replacement = self._coerce_json(
                    configuration.get("replacement_document"), None
                )
                if isinstance(replacement, dict):
                    replacement = self._nest_dotted(
                        self._clean_document(replacement)
                    )
                if not replacement:
                    connected = dict(connected_nodes or {})
                    connected["input"] = _unwrap_connected_value(
                        connected.get("input")
                    )
                    replacement = self._resolve_documents(None, connected)[0]
                if not isinstance(replacement, dict):
                    raise ValueError("A replacement document is required.")
                if any(str(key).startswith("$") for key in replacement):
                    raise ValueError(
                        "A replacement document cannot contain update operators."
                    )
                attempted = 1
                result = collection.replace_one(
                    query,
                    replacement,
                    upsert=_as_bool(configuration.get("upsert")),
                )
                written = result.modified_count + int(result.upserted_id is not None)
                affected = written
                documents = [
                    {
                        "matched_count": result.matched_count,
                        "modified_count": result.modified_count,
                        "upserted_id": result.upserted_id,
                    }
                ]

            elif operation in {"delete_one", "delete_many"}:
                query = self._build_filter(configuration)
                self._guard_scoped_write(
                    operation,
                    query,
                    _as_bool(configuration.get("allow_empty_filter")),
                )
                result = (
                    collection.delete_one(query)
                    if operation == "delete_one"
                    else collection.delete_many(query)
                )
                written = result.deleted_count
                affected = written
                documents = [{"deleted_count": written}]

            serialized = [self._serialize(document) for document in documents]
            error_message = "; ".join(
                str(error.get("message") or "MongoDB operation failed.")
                for error in errors
            ) or None
            duration_ms = round((time.time() - started_at) * 1000, 2)
            logger.info(
                "MongoNode completed operation=%s collection=%s affected=%s "
                "truncated=%s duration_ms=%s",
                operation,
                collection_name,
                affected,
                truncated,
                duration_ms,
            )
            return {
                "output": {
                    "documents": serialized,
                    "document_count": affected,
                    "documents_returned": len(serialized),
                    "documents_written": written,
                    "documents_attempted": attempted,
                    "operation": operation,
                    "collection": collection_name,
                    "duration_ms": duration_ms,
                    "truncated": truncated,
                    "errors": errors,
                },
                "success": not errors,
                "error": error_message,
            }

        except Exception as exc:
            message = self._database_error(exc)
            logger.error("MongoNode failed operation=%s: %s", operation, message)
            if not continue_on_error:
                try:
                    from pymongo.errors import PyMongoError
                except ImportError:
                    PyMongoError = ()  # type: ignore[assignment]
                if PyMongoError and isinstance(exc, PyMongoError):
                    raise ValueError(f"MongoDB error: {message}") from exc
                raise

            return {
                "output": {
                    "documents": [],
                    "document_count": 0,
                    "documents_returned": 0,
                    "documents_written": written,
                    "documents_attempted": attempted,
                    "operation": operation,
                    "collection": collection_name,
                    "duration_ms": round((time.time() - started_at) * 1000, 2),
                    "truncated": False,
                    "errors": [{"success": False, "message": message}],
                },
                "success": False,
                "error": message,
            }

        finally:
            if client is not None:
                client.close()

    @classmethod
    def _build_projection(cls, raw: Any) -> Optional[Dict[str, int]]:
        """
        Work out which fields to return.

        Naming both a parent and one of its children, such as address together
        with address.city, is a collision the server refuses. The parent already
        carries the child, so the narrower path is dropped and the parent kept.
        """
        names = cls._parse_list(raw)
        if not names:
            return None

        names = [cls._validate_field_path(name, "Projection Field") for name in names]

        kept: List[str] = []
        for name in sorted(set(names), key=len):
            # A path is skipped when something already selected covers it.
            if any(name.startswith(f"{existing}.") for existing in kept):
                continue
            kept.append(name)

        return {name: 1 for name in kept}

    @staticmethod
    def _parse_list(raw: Any) -> List[str]:
        """Read a comma separated selection into a list of names."""
        if not raw:
            return []
        parts = raw if isinstance(raw, (list, tuple)) else str(raw).split(",")
        return [str(part).strip() for part in parts if str(part).strip()]

    def get_required_packages(self) -> List[str]:
        """Packages this node needs."""
        return ["pymongo==4.18.1"]


__all__ = ["MongoNode"]
