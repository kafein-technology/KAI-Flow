"""Public service-layer exports without package-import side effects.

Service modules are loaded only when their exported class is requested.  This
keeps isolated workers from initializing the database, workflow engine, and
unrelated integrations merely because they import one scanner service.
"""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any


_EXPORTS = {
    "BaseService": (".base", "BaseService"),
    "UserService": (".user_service", "UserService"),
    "WorkflowService": (".workflow_service", "WorkflowService"),
    "ExecutionService": (".execution_service", "ExecutionService"),
    "CredentialService": (".credential_service", "CredentialService"),
    "VariableService": (".variable_service", "VariableService"),
    "NodeRegistryService": (".node_registry_service", "NodeRegistryService"),
    "NodeConfigurationService": (
        ".node_configuration_service",
        "NodeConfigurationService",
    ),
    "WebhookService": (".webhook_service", "WebhookService"),
}

if TYPE_CHECKING:
    from .base import BaseService
    from .credential_service import CredentialService
    from .execution_service import ExecutionService
    from .node_configuration_service import NodeConfigurationService
    from .node_registry_service import NodeRegistryService
    from .user_service import UserService
    from .variable_service import VariableService
    from .webhook_service import WebhookService
    from .workflow_service import WorkflowService


def __getattr__(name: str) -> Any:
    """Load one public service export on first access."""

    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(_EXPORTS))

__all__ = [
    "BaseService",
    "UserService",
    "WorkflowService",
    "ExecutionService",
    "CredentialService",
    "VariableService",
    "NodeRegistryService",
    "NodeConfigurationService",
    "WebhookService",
]
