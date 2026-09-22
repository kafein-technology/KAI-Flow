"""Small, side-effect-free helpers for environment backed feature flags."""

from __future__ import annotations

import os


_TRUE_VALUES = frozenset({"1", "true", "t", "yes", "y", "on"})
_FALSE_VALUES = frozenset({"0", "false", "f", "no", "n", "off", ""})


def env_flag(name: str, default: bool = False) -> bool:
    """Read a boolean environment variable without Python string truthiness."""

    raw = os.getenv(name)
    if raw is None:
        return default
    normalized = raw.strip().lower()
    if normalized in _TRUE_VALUES:
        return True
    if normalized in _FALSE_VALUES:
        return False
    return default


def external_tracing_enabled() -> bool:
    """Return the LangSmith tracing decision with legacy-name compatibility."""

    modern_value = os.getenv("LANGSMITH_TRACING")
    if modern_value is not None and modern_value.strip():
        return env_flag("LANGSMITH_TRACING", False)
    return env_flag("LANGCHAIN_TRACING_V2", False)


__all__ = ["env_flag", "external_tracing_enabled"]
