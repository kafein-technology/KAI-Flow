"""Portable process isolation primitives for model security scanners.

The web server must never execute parser-heavy security engines in its own
process.  This module owns the cross-platform multiprocessing policy and the
worker lifecycle shared by every scanner adapter.
"""

from __future__ import annotations

import importlib
import logging
import multiprocessing
import os
import re
import signal
import time
import unicodedata
from collections.abc import Callable, Mapping, Sequence
from typing import Any


logger = logging.getLogger(__name__)

_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_ERROR_TEXT = 320
_POSIX_START_METHODS = ("forkserver", "spawn")
_WINDOWS_START_METHODS = ("spawn",)


class IsolatedProcessError(RuntimeError):
    """Raised when an isolated worker cannot return a valid result."""


class IsolatedProcessTimeoutError(IsolatedProcessError):
    """Raised when an isolated worker exceeds its wall-clock deadline."""


class _WorkerBootstrapError(IsolatedProcessError):
    """Internal signal used to try the next safe process start method."""


def _safe_error_text(
    value: Any,
    *,
    artifact_path: str | None = None,
    artifact_name: str = "artifact",
) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    if artifact_path:
        text = text.replace(artifact_path, artifact_name)
    text = _CONTROL_CHARS.sub("", text)
    return " ".join(text.split())[:_MAX_ERROR_TEXT]


def _worker_exit_details(exit_code: int | None) -> str:
    if exit_code is None:
        return "exit_code=unavailable"
    if exit_code >= 0:
        return f"exit_code={exit_code}"
    try:
        signal_name = signal.Signals(-exit_code).name
    except (ValueError, OverflowError):
        signal_name = "unknown"
    return f"exit_code={exit_code} signal={signal_name}"


def scanner_process_start_methods(start_method: str | None = None) -> tuple[str, ...]:
    """Return an ordered, supported process policy for the current platform.

    ``fork`` is deliberately not selected automatically because forking a
    multithreaded ASGI process can inherit locks and partially initialized
    library state.  ``forkserver`` provides clean POSIX workers without
    re-running the web server entry point; Windows uses ``spawn``.
    """

    available = tuple(multiprocessing.get_all_start_methods())
    if start_method is not None:
        requested = str(start_method).strip().lower()
        if requested not in available:
            raise ValueError(
                f"Unsupported process start method {requested!r}; "
                f"available methods: {', '.join(available)}."
            )
        return (requested,)

    preferred = _WINDOWS_START_METHODS if os.name == "nt" else _POSIX_START_METHODS
    selected = tuple(method for method in preferred if method in available)
    if selected:
        return selected
    if not available:
        raise RuntimeError("No multiprocessing start method is available.")
    return (available[0],)


def _terminate_process(process: Any, *, started: bool) -> None:
    if not started:
        return
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
    if process.is_alive():
        process.kill()
        process.join(timeout=2)


def _resolve_worker_target(module_name: str, qualname: str) -> Callable[..., None]:
    """Resolve a scanner target inside the child after the process has started."""

    target: Any = importlib.import_module(module_name)
    for part in qualname.split("."):
        if part == "<locals>":
            raise TypeError("Scanner worker targets must be module-level callables.")
        target = getattr(target, part)
    if not callable(target):
        raise TypeError("Scanner worker target is not callable.")
    return target


def _scanner_worker_bootstrap(
    send_connection: Any,
    target_module: str,
    target_qualname: str,
    worker_args: tuple[Any, ...],
    artifact_path: str,
    artifact_name: str,
) -> None:
    """Import and dispatch a scanner target while preserving bootstrap errors."""

    try:
        target = _resolve_worker_target(target_module, target_qualname)
        target(send_connection, *worker_args)
    except BaseException as exc:
        try:
            send_connection.send(
                {
                    "ok": False,
                    "error_type": type(exc).__name__,
                    "error_message": _safe_error_text(
                        exc,
                        artifact_path=artifact_path,
                        artifact_name=artifact_name,
                    ),
                }
            )
        except BaseException:
            pass
    finally:
        try:
            send_connection.close()
        except OSError:
            pass


def _run_worker_once(
    *,
    start_method: str,
    target: Callable[..., None],
    worker_args: Sequence[Any],
    timeout_seconds: float,
    worker_name: str,
    memory_limit_bytes: int,
    artifact_path: str,
    artifact_name: str,
) -> dict[str, Any]:
    context = multiprocessing.get_context(start_method)
    receive_connection, send_connection = context.Pipe(duplex=False)
    process = context.Process(
        target=_scanner_worker_bootstrap,
        args=(
            send_connection,
            target.__module__,
            target.__qualname__,
            tuple(worker_args),
            artifact_path,
            artifact_name,
        ),
        daemon=True,
    )
    started = False
    try:
        try:
            process.start()
            started = True
        except BaseException as exc:
            raise IsolatedProcessError(
                f"{worker_name} worker could not start: "
                f"start_method={start_method} "
                f"parent_error_type={type(exc).__name__} "
                f"parent_error_message={_safe_error_text(exc)}."
            ) from exc
        finally:
            send_connection.close()

        if not receive_connection.poll(max(0.001, timeout_seconds)):
            _terminate_process(process, started=started)
            raise IsolatedProcessTimeoutError(
                f"{worker_name} scan timed out: start_method={start_method} "
                f"{_worker_exit_details(process.exitcode)} "
                f"memory_limit_bytes={memory_limit_bytes}."
            )

        try:
            message = receive_connection.recv()
        except EOFError as exc:
            process.join(timeout=2)
            raise _WorkerBootstrapError(
                f"start_method={start_method} {_worker_exit_details(process.exitcode)}"
            ) from exc

        process.join(timeout=2)
        payload = message if isinstance(message, Mapping) else {}
        if not payload.get("ok"):
            error_type = _safe_error_text(
                payload.get("error_type") or "UnknownWorkerError",
                artifact_path=artifact_path,
                artifact_name=artifact_name,
            )[:96]
            error_message = _safe_error_text(
                payload.get("error_message") or "No error message was returned.",
                artifact_path=artifact_path,
                artifact_name=artifact_name,
            )
            raise IsolatedProcessError(
                f"{worker_name} worker failed: "
                f"child_error_type={error_type} start_method={start_method} "
                f"{_worker_exit_details(process.exitcode)} "
                f"memory_limit_bytes={memory_limit_bytes} "
                f"child_error_message={error_message}."
            )

        result = payload.get("result")
        if not isinstance(result, dict):
            raise IsolatedProcessError(
                f"{worker_name} worker returned an invalid result: "
                f"start_method={start_method} "
                f"{_worker_exit_details(process.exitcode)}."
            )
        return result
    finally:
        receive_connection.close()
        try:
            send_connection.close()
        except OSError:
            pass
        _terminate_process(process, started=started)
        if started:
            try:
                process.close()
            except ValueError:
                pass


def run_in_isolated_process(
    *,
    target: Callable[..., None],
    worker_args: Sequence[Any],
    timeout_seconds: int,
    worker_name: str,
    memory_limit_bytes: int,
    artifact_path: str,
    artifact_name: str,
    start_method: str | None = None,
) -> dict[str, Any]:
    """Run one scanner with a killable deadline and portable bootstrap policy."""

    methods = scanner_process_start_methods(start_method)
    deadline = time.monotonic() + max(1, int(timeout_seconds))
    bootstrap_failures: list[str] = []

    for index, method in enumerate(methods):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise IsolatedProcessTimeoutError(
                f"{worker_name} scan timed out before a worker could complete: "
                f"start_method_attempts={','.join(methods[: index + 1])} "
                f"memory_limit_bytes={memory_limit_bytes}."
            )
        try:
            return _run_worker_once(
                start_method=method,
                target=target,
                worker_args=worker_args,
                timeout_seconds=remaining,
                worker_name=worker_name,
                memory_limit_bytes=memory_limit_bytes,
                artifact_path=artifact_path,
                artifact_name=artifact_name,
            )
        except _WorkerBootstrapError as exc:
            bootstrap_failures.append(str(exc))
            if index + 1 < len(methods):
                logger.warning(
                    "%s worker bootstrap failed; retrying with start_method=%s: %s",
                    worker_name,
                    methods[index + 1],
                    exc,
                )
                continue

    details = "; ".join(bootstrap_failures) or "no bootstrap details"
    raise IsolatedProcessError(
        f"{worker_name} worker exited without a result: "
        f"attempts=[{details}] memory_limit_bytes={memory_limit_bytes}."
    )


__all__ = [
    "IsolatedProcessError",
    "IsolatedProcessTimeoutError",
    "run_in_isolated_process",
    "scanner_process_start_methods",
]
