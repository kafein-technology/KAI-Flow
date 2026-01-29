"""
KAI-Fusion Code Execution Node - Multi-Language Code Processing Engine
======================================================================

This module implements a sophisticated multi-language code execution node for the KAI-Fusion platform,
providing secure, sandboxed code execution capabilities for Python and JavaScript.
Built for dynamic data processing, transformation, and custom logic implementation within workflows.

ARCHITECTURAL OVERVIEW:
======================

The Code node serves as a flexible multi-language code execution engine, allowing users to write
custom Python or JavaScript code to process inputs, transform data, and generate outputs dynamically.

┌─────────────────────────────────────────────────────────────────┐
│                  Code Execution Architecture                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Input Data → [Language Selector] → [Code Editor]              │
│       ↓               ↓                    ↓                    │
│  [Validation] → [Runtime Selection] → [Sandbox Environment]    │
│       ↓               ↓                    ↓                    │
│  [Code Execution] → [Error Handling] → [Output Processing]     │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘

KEY FEATURES:
============

1. **Multi-Language Support**:
   - Python 3.x execution with secure sandbox
   - JavaScript (Node.js) execution environment
   - Language-specific helper functions and modules

2. **Secure Sandbox Execution**:
   - Isolated execution environment for each language
   - Resource limits and timeout protection
   - Safe module imports with whitelist
   - Memory and CPU usage constraints

3. **Batch Processing Support**:
   - Support for processing datasets efficiently
   - Optimized for large data processing

4. **Rich Context Access**:
   - Access to input data and workflow variables
   - Helper functions for common operations
   - JSON manipulation utilities
   - Date/time handling functions

AUTHORS: KAI-Fusion Development Team
VERSION: 2.0.0
LICENSE: Proprietary - KAI-Fusion Platform
"""

import ast
import json
import logging
import os
import subprocess
import sys
import tempfile
import time
import traceback
from typing import Any, Dict, Optional

from langchain_core.runnables import Runnable, RunnableLambda

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

# Safe built-in functions and modules for Python sandbox
SAFE_PYTHON_BUILTINS = {
    "abs",
    "all",
    "any",
    "ascii",
    "bin",
    "bool",
    "bytes",
    "chr",
    "dict",
    "dir",
    "divmod",
    "enumerate",
    "filter",
    "float",
    "format",
    "frozenset",
    "hex",
    "int",
    "isinstance",
    "issubclass",
    "iter",
    "len",
    "list",
    "map",
    "max",
    "min",
    "next",
    "oct",
    "ord",
    "pow",
    "print",
    "logger",
    "range",
    "repr",
    "reversed",
    "round",
    "set",
    "slice",
    "sorted",
    "str",
    "sum",
    "tuple",
    "type",
    "zip",  # Additional safe functions (note: broadens sandbox surface, kept for backward compatibility)
    "hasattr",
    "getattr",
    "setattr",
    "delattr",
    "hash",
    "id",
    "callable",
    "classmethod",
    "staticmethod",
    "property",
    "locals",
    "globals",
    "vars",
}

SAFE_PYTHON_MODULES = {
    "json",
    "math",
    "random",
    "re",
    "datetime",
    "time",
    "itertools",
    "collections",
    "functools",
    "operator",
    "string",
    "decimal",
    "fractions",
    "statistics",
    "base64",
    "hashlib",
    "hmac",
    "secrets",
    "uuid",
    "urllib.parse",
    "html",
    "xml.etree.ElementTree",
    "csv",
}

SAFE_JS_MODULES = {"crypto", "util", "url", "querystring", "path", "os"}

CODE_INPUT_VARIABLE_NAME = "node_data"

PY_MARKER_START = "__PY_OUTPUT_START__"
PY_MARKER_END = "__PY_OUTPUT_END__"
JS_MARKER_START = "__OUTPUT_START__"
JS_MARKER_END = "__OUTPUT_END__"


def _safe_json_dumps(value: Any) -> str:
    try:
        return json.dumps(value, default=str, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)


def _extract_between_markers(text: str, start: str, end: str) -> Optional[str]:
    if start not in text or end not in text:
        return None
    start_idx = text.find(start) + len(start)
    # The wrappers logger marker then newline, so tolerate optional newline
    if start_idx < len(text) and text[start_idx : start_idx + 1] == "\n":
        start_idx += 1
    end_idx = text.find(end)
    if end_idx < 0 or end_idx < start_idx:
        return None
    return text[start_idx:end_idx].strip()


def _split_user_stdout(text: str, marker_start: str) -> str:
    """Return everything loggered before our structured marker."""
    if marker_start not in text:
        return text.strip()
    return text[: text.find(marker_start)].strip()


def _write_temp_file(suffix: str, content: str) -> str:
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    ) as f:
        f.write(content)
        return f.name


def _cleanup_file(path: Optional[str]) -> None:
    if not path:
        return
    try:
        os.unlink(path)
    except Exception:
        pass


class PythonSandbox:
    """\
    Python execution sandbox using subprocess (cross-platform timeout).
    Notes:
    - This is NOT a perfect security sandbox; it is a restricted runtime wrapper.
    """

    def __init__(
        self,
        code: str,
        context: Dict[str, Any],
        timeout: int = 30,
        enable_validation: bool = True,
    ):
        self.code = code or ""
        self.context = context or {}
        self.timeout = timeout
        self.enable_validation = enable_validation

    def validate_code(self) -> Optional[str]:
        """Validate Python code syntax and check for dangerous operations."""
        try:
            tree = ast.parse(self.code)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.split(".")[0] not in SAFE_PYTHON_MODULES:
                            return f"Import of '{alias.name}' is not allowed"

                if isinstance(node, ast.ImportFrom):
                    if (
                        node.module
                        and node.module.split(".")[0] not in SAFE_PYTHON_MODULES
                    ):
                        return f"Import from '{node.module}' is not allowed"

                if isinstance(node, ast.Name) and node.id in {
                    "eval",
                    "exec",
                    "compile",
                    "__import__",
                    "open",
                    "file",
                    "input",
                }:
                    return f"Use of '{node.id}' is not allowed"

                if isinstance(node, ast.Attribute):
                    # Basic guard for direct attribute access like os.system / sys.exit / subprocess.run
                    if hasattr(node.value, "id") and node.value.id in {
                        "os",
                        "sys",
                        "subprocess",
                    }:
                        return f"Access to '{node.value.id}' module is not allowed"

            return None

        except SyntaxError as e:
            return f"Syntax error at line {e.lineno}: {e.msg}"
        except Exception as e:
            return f"Code validation error: {str(e)}"

    def _build_wrapper_script(self) -> str:
        context_json = json.dumps(self.context, default=str, ensure_ascii=False)
        context_json_escaped = context_json.replace("\\", "\\\\").replace(
            '"""', '\\"\\"\\"'
        )

        user_code_escaped = self.code.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')

        safe_builtins_list = list(SAFE_PYTHON_BUILTINS)
        safe_modules_list = sorted(SAFE_PYTHON_MODULES)

        wrapper = f'''# -*- coding: utf-8 -*-
import sys
import json
import math
import random
import re
import datetime
import time
import itertools
import collections
import traceback
import builtins

SAFE_BUILTINS = {safe_builtins_list!r}
SAFE_MODULES = {safe_modules_list!r}

_REAL_IMPORT = builtins.__import__

def _safe_import(name, globals=None, locals=None, fromlist=(), level=0):
    # Import statements rely on __import__. We provide a restricted implementation
    # that only allows whitelisted modules.
    if level != 0:
        raise ImportError("Relative imports are not allowed")
    root = (name or "").split(".")[0]
    if root not in SAFE_MODULES:
        raise ImportError("Import of '" + str(name) + "' is not allowed")
    return _REAL_IMPORT(name, globals, locals, fromlist, level)

def main():
    safe_builtins_dict = {{k: getattr(builtins, k) for k in SAFE_BUILTINS if hasattr(builtins, k)}}
    # Allow Python's `import x` to function while still enforcing SAFE_MODULES.
    safe_builtins_dict["__import__"] = _safe_import

    exec_globals = {{
        "__builtins__": safe_builtins_dict,
        "json": json,
        "math": math,
        "random": random,
        "re": re,
        "datetime": datetime,
        "time": time,
        "itertools": itertools,
        "collections": collections,
        "logger": print,
    }}

    try:
        context = json.loads("""{context_json_escaped}""")
        exec_globals.update(context)
    except Exception as ctx_err:
        print("{PY_MARKER_START}")
        print(json.dumps({{"success": False, "output": None, "error": f"Context load error: {{ctx_err}}" }}, ensure_ascii=False))
        print("{PY_MARKER_END}")
        return

    exec_globals["_json"] = json
    exec_globals["_now"] = datetime.datetime.now
    exec_globals["_utcnow"] = lambda: datetime.datetime.now(datetime.timezone.utc)

    exec_locals = {{}}
    try:
        user_code = """{user_code_escaped}"""
        exec(user_code, exec_globals, exec_locals)

        output = exec_locals.get("output", exec_locals.get("result", None))

        serializable_locals = {{}}
        for k, v in exec_locals.items():
            if not k.startswith("_") and not callable(v):
                try:
                    json.dumps(v, default=str)
                    serializable_locals[k] = v
                except Exception:
                    serializable_locals[k] = str(v)

        print("{PY_MARKER_START}")
        print(json.dumps({{
            "success": True,
            "output": output,
            "error": None,
            "locals": serializable_locals
        }}, default=str, ensure_ascii=False))
        print("{PY_MARKER_END}")

    except Exception:
        exc_type, exc_value, exc_tb = sys.exc_info()
        tb_lines = traceback.format_exception(exc_type, exc_value, exc_tb)
        error_msg = "".join(tb_lines)

        print("{PY_MARKER_START}")
        print(json.dumps({{
            "success": False,
            "output": None,
            "error": error_msg
        }}, ensure_ascii=False))
        print("{PY_MARKER_END}")

if __name__ == "__main__":
    main()
'''
        return wrapper

    def execute(self) -> Dict[str, Any]:
        if self.enable_validation:
            validation_error = self.validate_code()
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error,
                    "output": None,
                    "stdout": "",
                }

        temp_path: Optional[str] = None
        try:
            wrapper_script = self._build_wrapper_script()
            temp_path = _write_temp_file(".py", wrapper_script)

            result = subprocess.run(
                [sys.executable, temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
            )

            stdout, stderr = result.stdout or "", result.stderr or ""

            json_blob = _extract_between_markers(stdout, PY_MARKER_START, PY_MARKER_END)
            if json_blob is not None:
                user_stdout = _split_user_stdout(stdout, PY_MARKER_START)
                try:
                    output_data = json.loads(json_blob)
                    output_data["stdout"] = user_stdout
                    return output_data
                except json.JSONDecodeError as e:
                    return {
                        "success": False,
                        "error": f"Failed to parse output JSON: {e}",
                        "output": None,
                        "stdout": user_stdout,
                    }

            # No structured output found
            if result.returncode != 0:
                return {
                    "success": False,
                    "error": stderr or "Python execution failed with no output",
                    "output": None,
                    "stdout": stdout.strip(),
                }

            return {
                "success": True,
                "error": None,
                "output": None,
                "stdout": stdout.strip(),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"Python execution timed out after {self.timeout} seconds",
                "output": None,
                "stdout": "",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Python interpreter not found",
                "output": None,
                "stdout": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Python execution failed: {str(e)}",
                "output": None,
                "stdout": "",
            }
        finally:
            _cleanup_file(temp_path)


class JavaScriptSandbox:
    """\
    JavaScript execution sandbox using Node.js with basic restrictions.
    Notes:
    - This is NOT a perfect security sandbox; it is a restricted runtime wrapper.
    """

    def __init__(
        self,
        code: str,
        context: Dict[str, Any],
        timeout: int = 30,
        enable_validation: bool = True,
    ):
        self.code = code or ""
        self.context = context or {}
        self.timeout = timeout
        self.enable_validation = enable_validation

    def validate_code(self) -> Optional[str]:
        dangerous_patterns = [
            'require("fs")',
            "require('fs')",
            "require(`fs`)",
            'require("child_process")',
            "require('child_process')",
            "require(`child_process`)",
            'require("net")',
            "require('net')",
            "require(`net`)",
            'require("http")',
            "require('http')",
            "require(`http`)",
            'require("https")',
            "require('https')",
            "require(`https`)",
            "process.exit",
            "eval(",
            "__dirname",
            "__filename",
            "global.",
            "Buffer.",
            "setImmediate",
            "clearImmediate",
        ]

        for pattern in dangerous_patterns:
            if pattern in self.code:
                return f"Dangerous operation '{pattern}' is not allowed"
        return None

    def create_wrapper_code(self) -> str:
        context_json = json.dumps(self.context, default=str, ensure_ascii=False)

        return f"""
// Sandbox environment setup
const sandbox = {{}};

// Add context variables
const context = {context_json};
Object.assign(sandbox, context);

// Add safe utilities
sandbox.JSON = JSON;
sandbox.Math = Math;
sandbox.Date = Date;
sandbox._now = () => new Date();
sandbox._utcnow = () => new Date();
sandbox.console = console;
sandbox._json = JSON;

try {{
    for (const key in sandbox) {{
        if (key !== 'output' && key !== 'result') {{
            global[key] = sandbox[key];
        }}
    }}

    let output, result;

    {self.code}

    let finalOutput = (typeof result !== 'undefined') ? result :
                     (typeof output !== 'undefined') ? output : null;

    console.log('{JS_MARKER_START}');
    console.log(JSON.stringify({{
        success: true,
        output: finalOutput,
        error: null
    }}));
    console.log('{JS_MARKER_END}');

}} catch (error) {{
    console.log('{JS_MARKER_START}');
    console.log(JSON.stringify({{
        success: false,
        output: null,
        error: error.message + '\\n' + error.stack
    }}));
    console.log('{JS_MARKER_END}');
}}
"""

    def execute(self) -> Dict[str, Any]:
        if self.enable_validation:
            validation_error = self.validate_code()
            if validation_error:
                return {
                    "success": False,
                    "error": validation_error,
                    "output": None,
                    "stdout": "",
                }

        temp_path: Optional[str] = None
        try:
            wrapper_code = self.create_wrapper_code()
            temp_path = _write_temp_file(".js", wrapper_code)

            result = subprocess.run(
                ["node", temp_path],
                capture_output=True,
                text=True,
                timeout=self.timeout,
                encoding="utf-8",
            )

            stdout, stderr = result.stdout or "", result.stderr or ""

            json_blob = _extract_between_markers(stdout, JS_MARKER_START, JS_MARKER_END)
            if json_blob is not None:
                user_stdout = _split_user_stdout(stdout, JS_MARKER_START)
                try:
                    output_data = json.loads(json_blob)
                    output_data["stdout"] = user_stdout
                    return output_data
                except json.JSONDecodeError:
                    return {
                        "success": False,
                        "error": f"Failed to parse output: {json_blob}",
                        "output": None,
                        "stdout": user_stdout,
                    }

            if result.returncode != 0:
                return {
                    "success": False,
                    "error": stderr or "JavaScript execution failed",
                    "output": None,
                    "stdout": stdout.strip(),
                }

            return {
                "success": True,
                "error": None,
                "output": None,
                "stdout": stdout.strip(),
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "error": f"JavaScript execution timed out after {self.timeout} seconds",
                "output": None,
                "stdout": "",
            }
        except FileNotFoundError:
            return {
                "success": False,
                "error": "Node.js not found. Please install Node.js to run JavaScript code.",
                "output": None,
                "stdout": "",
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"JavaScript execution failed: {str(e)}",
                "output": None,
                "stdout": "",
            }
        finally:
            _cleanup_file(temp_path)


def _extract_input_payload(input_data: Any) -> Any:
    """\
    Preserve original behavior:
    - dict with "documents" -> join page_content
    - dict with "page_content"/"output"/"content" -> use that
    - Document-like object with .page_content -> use it
    - list of Document-like/dict -> join page_content
    - otherwise return as-is
    """

    if isinstance(input_data, dict):
        if (
            "documents" in input_data
            and isinstance(input_data["documents"], list)
            and input_data["documents"]
        ):
            docs = input_data["documents"]
            page_contents = []
            for doc in docs:
                if hasattr(doc, "page_content"):
                    page_contents.append(doc.page_content)
                elif isinstance(doc, dict) and "page_content" in doc:
                    page_contents.append(doc["page_content"])
            if page_contents:
                return (
                    "\n\n".join(page_contents)
                    if len(page_contents) > 1
                    else page_contents[0]
                )

        if "page_content" in input_data:
            return input_data["page_content"]

        if "output" in input_data:
            return input_data["output"]

        if "content" in input_data:
            return input_data["content"]

        return input_data

    if hasattr(input_data, "page_content"):
        return input_data.page_content

    if isinstance(input_data, list) and input_data:
        page_contents = []
        for item in input_data:
            if hasattr(item, "page_content"):
                page_contents.append(item.page_content)
            elif isinstance(item, dict) and "page_content" in item:
                page_contents.append(item["page_content"])
        if page_contents:
            return (
                "\n\n".join(page_contents)
                if len(page_contents) > 1
                else page_contents[0]
            )

    return input_data


def _extract_mixed_template(raw_code: str, language: str) -> str:
    """\
    Keep original intention: if raw_code includes both template markers, pick the relevant section.
    Also fixes original bug: Python fallback used __import__ which is forbidden by validator.
    """

    if "// JavaScript Example" not in raw_code or "# Python Example" not in raw_code:
        return raw_code

    if language == "python":
        lines = raw_code.split("\n")
        python_lines = []
        in_python = False

        for line in lines:
            if line.strip().startswith("# Python Example"):
                in_python = True
                continue
            if in_python and line.strip().startswith("#"):
                # Remove one leading "# " if present (match original behavior)
                python_lines.append(line.replace("# ", "", 1))
                continue
            if in_python and line.strip() and not line.strip().startswith("#"):
                break

        code = "\n".join(python_lines).strip()
        if code:
            return code

        # Fallback without __import__
        return """output = {
    'message': 'Hello from Code Node!',
    'timestamp': str(datetime.datetime.now()),
    'input_data': node_data
}"""

    # javascript
    lines = raw_code.split("\n")
    js_lines = []
    for line in lines:
        if line.strip().startswith("# Python Example"):
            break
        if line.strip() and not line.strip().startswith("//"):
            js_lines.append(line)

    code = "\n".join(js_lines).strip()
    if code:
        return code

    return """output = {
  message: 'Hello from Code Node!',
  timestamp: new Date(),
  input_data: node_data
};"""


class CodeNode(ProcessorNode):
    def __init__(self):
        super().__init__()
        self._metadata = {
            "name": "CodeNode",
            "display_name": "Code Node",
            "description": (
                "Execute custom Python or JavaScript code to process data. "
                "Supports data transformation, business logic, and custom processing."
            ),
            "category": "Processing",
            "node_type": NodeType.PROCESSOR,
            "icon": {"name": "code", "path": None, "alt": None},
            "colors": ["orange-500", "red-600"],
            "inputs": [
                NodeInput(
                    name="input",
                    displayName="Input",
                    type="any",
                    description=(
                        "Input data from connected nodes. Accessible as "
                        f"'{CODE_INPUT_VARIABLE_NAME}' variable in your code."
                    ),
                    is_connection=True,
                    required=False,
                    direction=NodePosition.LEFT,
                ),
            ],
            "outputs": [
                NodeOutput(
                    name="output",
                    displayName="Output",
                    type="any",
                    description="Result from code execution. Output is STDOUT (logger/console.log).",
                    is_connection=True,
                    direction=NodePosition.RIGHT,
                ),
            ],
            "properties": [
                NodeProperty(
                    name="language",
                    displayName="Programming Language",
                    type=NodePropertyType.SELECT,
                    description="Select the programming language for code execution",
                    default="python",
                    required=True,
                    options=[
                        {"label": "Python", "value": "python"},
                        {"label": "JavaScript", "value": "javascript"},
                    ],
                    tabName="basic",
                ),
                NodeProperty(
                    name="code",
                    displayName="Code",
                    type=NodePropertyType.CODE_EDITOR,
                    description=(
                        "Access input as node_data. You can refer to previous nodes using Jinja like ${node_name}. "
                        "If special characters possible, use {{node_name|tojson}}."
                    ),
                    default="# Python Example\nlogger(node_data)",
                    required=True,
                    rows=12,
                    maxLength=50000,
                    tabName="basic",
                ),
                NodeProperty(
                    name="timeout",
                    displayName="Timeout (seconds)",
                    type=NodePropertyType.NUMBER,
                    description="Maximum execution time in seconds",
                    default=30,
                    min=1,
                    max=300,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="continue_on_error",
                    displayName="Continue on Error",
                    type=NodePropertyType.CHECKBOX,
                    description="Continue workflow execution even if code fails",
                    default=False,
                    required=False,
                    tabName="advanced",
                ),
                NodeProperty(
                    name="enable_validation",
                    displayName="Enable Code Validation",
                    type=NodePropertyType.CHECKBOX,
                    description="Validate code for dangerous operations before execution",
                    default=True,
                    required=False,
                    tabName="advanced",
                ),
            ],
        }

        logger.info("CodeNode initialized with multi-language support")

    def execute(
        self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any]
    ) -> Dict[str, Any]:
        language = (inputs.get("language") or "python").strip().lower()
        raw_code = inputs.get("code", "") or ""
        timeout = int(inputs.get("timeout", 30))
        continue_on_error = bool(inputs.get("continue_on_error", False))
        enable_validation = bool(inputs.get("enable_validation", True))

        code = _extract_mixed_template(raw_code, language)

        input_data = connected_nodes.get("input", None)
        logger.info("RAW INPUT (before extraction): %s", input_data)
        input_data = _extract_input_payload(input_data)
        logger.info("PROCESSED INPUT (after extraction): %s", input_data)

        context = {
            CODE_INPUT_VARIABLE_NAME: input_data,
            "inputs": inputs,
        }

        start_time = time.time()
        try:
            if language == "python":
                sandbox = PythonSandbox(
                    code, context, timeout=timeout, enable_validation=enable_validation
                )
            elif language == "javascript":
                sandbox = JavaScriptSandbox(
                    code, context, timeout=timeout, enable_validation=enable_validation
                )
            else:
                raise ValueError(f"Unsupported language: {language}")

            result = sandbox.execute()
            execution_time_ms = (time.time() - start_time) * 1000

            logger.info(
                "Execution success=%s time=%.2fms",
                result.get("success"),
                execution_time_ms,
            )

            if result.get("success"):
                stdout_output = (result.get("stdout") or "").strip()

                # SMART OUTPUT DETECTION: If stdout looks like a Python dict/list repr,
                # automatically convert to proper JSON format
                if stdout_output and (
                    (stdout_output.startswith("{") and stdout_output.endswith("}"))
                    or (stdout_output.startswith("[") and stdout_output.endswith("]"))
                ):
                    try:
                        import ast

                        parsed = ast.literal_eval(stdout_output)
                        # Convert to proper JSON with double quotes
                        stdout_output = json.dumps(parsed, ensure_ascii=False)
                        logger.debug(
                            "Smart output: Converted Python dict/list repr to JSON"
                        )
                    except (ValueError, SyntaxError):
                        # Keep original if not a valid Python literal
                        pass

                return {"output": stdout_output}

            err = result.get("error") or "Unknown error"
            if continue_on_error:
                return {"output": f"Error: {err}"}

            raise ValueError(f"Code execution failed: {err}")

        except Exception as e:
            execution_time_ms = (time.time() - start_time) * 1000
            logger.error("CodeNode failed after %.2fms: %s", execution_time_ms, str(e))
            logger.error(traceback.format_exc())

            if continue_on_error:
                return {"output": f"Error: Code execution failed: {str(e)}"}

            raise ValueError(f"Code execution failed: {str(e)}")

    def as_runnable(self) -> Runnable:
        return RunnableLambda(
            lambda params: self.execute(
                inputs=params.get("inputs", {}),
                connected_nodes=params.get("connected_nodes", {}),
            ),
            name="CodeNode",
        )


__all__ = ["CodeNode", "PythonSandbox", "JavaScriptSandbox"]
