"""
JSON Serialization Utilities - Best Practice Implementation
===========================================================

This module provides efficient JSON serialization utilities using orjson,
which is significantly faster than the standard library's json module and
includes built-in support for common non-serializable types.

Features:
• Fast serialization using orjson
• Automatic handling of datetime, UUID, date, Decimal
• Pydantic model support
• LangChain object support (BaseTool, Runnable, etc.)
• Agent result filtering (tools, memory, intermediate_steps)
• Fallback to standard json for unsupported types
• Recursive handling of nested structures

Best Practices:
• Use orjson.dumps() for fast serialization (3-5x faster than json)
• Use make_json_serializable() for complex objects before serialization
• Use make_json_serializable_with_langchain() for LangChain objects
• Prefer pydantic models for structured data with automatic validation

Usage:
    from app.core.json_utils import make_json_serializable, safe_json_dumps
    
    # Option 1: Convert then serialize
    serializable = make_json_serializable(data)
    json_str = json.dumps(serializable)
    
    # Option 2: Direct serialization (recommended)
    json_str = safe_json_dumps(data)
    
    # Option 3: Fast serialization with orjson (best performance)
    json_bytes = orjson.dumps(data, default=json_serializer_default)
    
    # Option 4: LangChain-aware serialization
    serializable = make_json_serializable_with_langchain(agent_result, filter_complex=True)
"""

from typing import Any, Optional, Dict
from datetime import datetime, date
from decimal import Decimal
import uuid
import json

try:
    import orjson
    ORJSON_AVAILABLE = True
except ImportError:
    ORJSON_AVAILABLE = False

# Lazy import for LangChain types (optional dependency)
_LANGCHAIN_AVAILABLE = False
_BaseTool = None
_Runnable = None

try:
    from langchain_core.tools import BaseTool
    from langchain_core.runnables import Runnable
    from langchain_core.vectorstores import VectorStore
    from langchain_core.retrievers import BaseRetriever
    
    _LANGCHAIN_AVAILABLE = True
    _BaseTool = BaseTool
    _Runnable = Runnable
    _VectorStore = VectorStore
    _BaseRetriever = BaseRetriever
except ImportError:
    _LANGCHAIN_AVAILABLE = False
    _BaseTool = None
    _Runnable = None
    _VectorStore = None
    _BaseRetriever = None


def json_serializer_default(obj: Any) -> Any:
    """
    Default serializer function for orjson that handles common non-serializable types.
    
    This function is used as the 'default' parameter for orjson.dumps() and
    handles datetime, UUID, date, Decimal, LangChain objects, and other common types.
    
    Args:
        obj: Object to serialize
        
    Returns:
        JSON-serializable representation of the object
        
    Examples:
        >>> import orjson
        >>> from app.core.json_utils import json_serializer_default
        >>> data = {"created_at": datetime.now(), "id": uuid.uuid4()}
        >>> orjson.dumps(data, default=json_serializer_default)
        b'{"created_at":"2025-01-13T12:00:00","id":"..."}'
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    # LangChain LLMs, ChatModels, Embeddings
    class_name = obj.__class__.__name__
    module_name = obj.__class__.__module__.lower()
    if "langchain" in module_name:
        is_llm_or_embed = any(kw in module_name for kw in ("language_models", "chat_models", "llms", "embeddings")) or class_name.endswith("Embeddings")
        if is_llm_or_embed:
            if hasattr(obj, 'model_name') and getattr(obj, 'model_name'):
                return f"<{class_name} model={getattr(obj, 'model_name')}>"
            if hasattr(obj, 'model') and getattr(obj, 'model'):
                return f"<{class_name} model={getattr(obj, 'model')}>"
            return f"<{class_name}>"
    # LangChain objects (if available)
    elif _LANGCHAIN_AVAILABLE and (_BaseTool and isinstance(obj, _BaseTool) or 
                                   _Runnable and isinstance(obj, _Runnable)):
        return f"<{obj.__class__.__name__}>"
    elif _LANGCHAIN_AVAILABLE and callable(obj):
        return f"<{obj.__class__.__name__}>"
    # Pydantic v2 models
    elif hasattr(obj, 'model_dump'):
        try:
            return obj.model_dump()
        except Exception:
            pass
    # Pydantic v1 models (legacy)
    elif hasattr(obj, 'dict'):
        try:
            return obj.dict()
        except Exception:
            pass
    # Objects with __dict__ attribute
    elif hasattr(obj, '__dict__'):
        return obj.__dict__
    # Raise TypeError to let orjson handle it with default fallback
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")


def _contains_langchain_complex_objects(obj: Any) -> bool:
    """
    Check if object contains complex LangChain objects that can't be serialized.
    
    Args:
        obj: Object to check
        
    Returns:
        True if object contains complex LangChain objects
    """
    if not isinstance(obj, dict):
        return False
    complex_keys = ['tools', 'tool_names', 'intermediate_steps', 'memory']
    return any(key in obj for key in complex_keys)


def make_json_serializable(obj: Any, filter_langchain_complex: bool = False) -> Any:
    """
    Recursively convert non-JSON-serializable objects to serializable format.
    
    This is a comprehensive utility that handles:
    - datetime, date objects → ISO format strings
    - UUID objects → string representation
    - Decimal → float
    - Pydantic models → dictionaries via model_dump()
    - LangChain objects (BaseTool, Runnable) → string representation
    - Custom objects → dictionaries via __dict__
    - Nested structures (dict, list, tuple)
    
    Args:
        obj: Object to make JSON-serializable (can be any type)
        filter_langchain_complex: If True, filters out complex LangChain objects
                                 (tools, intermediate_steps, memory) from dicts
        
    Returns:
        JSON-serializable version of the object
        
    Examples:
        >>> from datetime import datetime
        >>> import uuid
        >>> data = {
        ...     "timestamp": datetime.now(),
        ...     "id": uuid.uuid4(),
        ...     "nested": {"value": datetime.now()}
        ... }
        >>> serializable = make_json_serializable(data)
        >>> json.dumps(serializable)  # Works without errors
    """
    if obj is None or isinstance(obj, (bool, int, float, str)):
        return obj
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, uuid.UUID):
        return str(obj)
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, dict):
        # Filter complex LangChain objects if requested
        if filter_langchain_complex and _contains_langchain_complex_objects(obj):
            return _filter_langchain_complex_objects(obj, filter_langchain_complex)
        return {key: make_json_serializable(value, filter_langchain_complex) 
                for key, value in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [make_json_serializable(item, filter_langchain_complex) 
                for item in obj]
    # LangChain LLMs, ChatModels, Embeddings
    class_name = obj.__class__.__name__
    module_name = obj.__class__.__module__.lower()
    if "langchain" in module_name:
        is_llm_or_embed = any(kw in module_name for kw in ("language_models", "chat_models", "llms", "embeddings")) or class_name.endswith("Embeddings")
        if is_llm_or_embed:
            if hasattr(obj, 'model_name') and getattr(obj, 'model_name'):
                return f"<{class_name} model={getattr(obj, 'model_name')}>"
            if hasattr(obj, 'model') and getattr(obj, 'model'):
                return f"<{class_name} model={getattr(obj, 'model')}>"
            return f"<{class_name}>"

    # LangChain complex objects (BaseTool, Runnable, callable) - convert to string representation
    # Note: We use 'if' here instead of 'elif' to allow fallthrough to Pydantic handling for other LangChain objects like Document
    if _LANGCHAIN_AVAILABLE:
        if (_BaseTool and isinstance(obj, _BaseTool)) or \
           (_Runnable and isinstance(obj, _Runnable)) or \
           (_VectorStore and isinstance(obj, _VectorStore)) or \
           (_BaseRetriever and isinstance(obj, _BaseRetriever)):
            return f"<{obj.__class__.__name__}>"
        # Check callable ONLY for things that don't have model_dump (Pydantic models)
        # This prevents treating Document and other Pydantic models as callables
        if callable(obj) and not hasattr(obj, 'model_dump') and not hasattr(obj, 'dict'):
            return f"<{obj.__class__.__name__}>"
    # Pydantic v2 models (includes LangChain Document)
    if hasattr(obj, 'model_dump'):
        try:
            return make_json_serializable(obj.model_dump(), filter_langchain_complex)
        except Exception:
            return str(obj)
    # Pydantic v1 models (legacy)
    elif hasattr(obj, 'dict'):
        try:
            return make_json_serializable(obj.dict(), filter_langchain_complex)
        except Exception:
            return str(obj)
    # Objects with __dict__ attribute
    elif hasattr(obj, '__dict__'):
        return make_json_serializable(obj.__dict__, filter_langchain_complex)
    else:
        # Try to check if it's already JSON serializable
        try:
            json.dumps(obj)
            return obj
        except (TypeError, ValueError):
            return str(obj)


def _filter_langchain_complex_objects(obj: Any, filter_complex: bool = True) -> Any:
    """
    Filter out complex LangChain objects from Agent results, keeping only serializable data.
    
    This function specifically handles LangChain agent results by:
    - Removing 'tools' and 'intermediate_steps' completely
    - Converting 'tool_names' to list of strings
    - Extracting messages from 'memory' if available
    - Recursively processing other values
    
    Args:
        obj: Object to filter (should be dict containing LangChain complex objects)
        filter_complex: If True, filters complex objects (used for nested calls)
        
    Returns:
        Filtered object with only serializable data
    """
    if not isinstance(obj, dict):
        # For non-dict objects, just make serializable without filtering
        return make_json_serializable(obj, filter_langchain_complex=False)
    
    filtered = {}
    for key, value in obj.items():
        if key in ['tools', 'intermediate_steps']:
            # Skip these complex objects completely
            continue
        elif key == 'tool_names':
            # Convert tool names to list of strings
            if isinstance(value, list):
                filtered[key] = [str(name) for name in value]
            else:
                filtered[key] = str(value)
        elif key == 'memory':
            # Extract messages from memory if available
            if hasattr(value, 'chat_memory') and hasattr(value.chat_memory, 'messages'):
                filtered[key] = [
                    msg.content if hasattr(msg, 'content') else str(msg)
                    for msg in value.chat_memory.messages
                ]
            else:
                filtered[key] = str(value)
        else:
            # Recursively process other values without filtering again
            # (already filtered at top level, just serialize nested values)
            filtered[key] = make_json_serializable(value, filter_langchain_complex=False)
    
    return filtered


def make_json_serializable_with_langchain(obj: Any, filter_complex: bool = True) -> Any:
    """
    Make object JSON-serializable with LangChain-specific handling.
    
    This is a convenience wrapper around make_json_serializable() that automatically
    enables LangChain complex object filtering. Use this when working with LangChain
    agent results or other LangChain objects.
    
    Args:
        obj: Object to make JSON-serializable
        filter_complex: If True, filters out complex LangChain objects (tools, memory, etc.)
        
    Returns:
        JSON-serializable version of the object
        
    Examples:
        >>> agent_result = {"output": "Hello", "tools": [...], "memory": ...}
        >>> serializable = make_json_serializable_with_langchain(agent_result)
        >>> # tools and memory are filtered out, output is preserved
    """
    return make_json_serializable(obj, filter_langchain_complex=filter_complex)


def format_standard_node_output(
    node_id: str,
    node_type: str,
    success: bool,
    status_code: int,
    execution_time_ms: float,
    inputs: Any,
    output: Any,
    error: Optional[Dict[str, Any]] = None,
    node_instance: Optional[Any] = None
) -> Dict[str, Any]:
    """
    Format node execution result into a standardized JSON structure.
    Also copies keys from the output payload to the top-level (if output is a dict)
    to maintain backward compatibility with routing and direct key access.
    
    If node_instance is provided, metadata.outputs definitions are dynamically inspected
    and mapped to the root of the output dictionary.
    """
    serializable_inputs = make_json_serializable_with_langchain(inputs, filter_complex=True)
    serializable_output = make_json_serializable_with_langchain(output, filter_complex=False)
    
    # Dynamically resolve success status and status code from the output payload if present
    dynamic_success = success
    dynamic_status_code = status_code
    
    if isinstance(serializable_output, dict):
        # Resolve dynamic success
        if "success" in serializable_output:
            val = serializable_output["success"]
            if isinstance(val, bool):
                dynamic_success = val
            elif str(val).lower() in ("true", "1"):
                dynamic_success = True
            elif str(val).lower() in ("false", "0"):
                dynamic_success = False
                
        # Resolve dynamic status code (supports both status_code and statusCode)
        if "status_code" in serializable_output:
            try:
                dynamic_status_code = int(serializable_output["status_code"])
            except (ValueError, TypeError):
                pass
        elif "statusCode" in serializable_output:
            try:
                dynamic_status_code = int(serializable_output["statusCode"])
            except (ValueError, TypeError):
                pass
                
    result = {
        "success": dynamic_success,
        "statusCode": dynamic_status_code,
        "nodeId": node_id,
        "nodeType": node_type,
        "timestamp": datetime.now().isoformat(),
        "executionTimeMs": execution_time_ms,
        "inputs": serializable_inputs,
        "output": serializable_output,
        "error": error
    }
    
    if isinstance(serializable_output, dict):
        reserved_keys = set(result.keys())
        for k, v in serializable_output.items():
            if k not in reserved_keys:
                result[k] = v
                
    # Dynamic metadata-based mapping if node_instance or its outputs metadata is available
    mapped_dynamically = False
    outputs_list = []
    if node_instance is not None:
        if hasattr(node_instance, "metadata") and node_instance.metadata is not None:
            outputs_list = getattr(node_instance.metadata, "outputs", [])
        elif hasattr(node_instance, "outputs") and node_instance.outputs is not None:
            outputs_list = node_instance.outputs
        elif isinstance(node_instance, dict):
            outputs_list = node_instance.get("outputs") or node_instance.get("metadata", {}).get("outputs", [])
            
    if outputs_list:
        output_names = []
        connection_outputs = []
        for out in outputs_list:
            if isinstance(out, dict):
                name = out.get("name")
                is_conn = out.get("is_connection", False)
            else:
                name = getattr(out, "name", None)
                is_conn = getattr(out, "is_connection", False)
            if name:
                output_names.append(name)
                if is_conn:
                    connection_outputs.append(name)
                    
        # 1. If output is a dict, copy matching keys from output to result
        if isinstance(serializable_output, dict):
            for name in output_names:
                if name in serializable_output:
                    result[name] = serializable_output[name]
                    mapped_dynamically = True
                    
        # 2. If output is not mapped, and there is exactly one output defined in metadata
        if not mapped_dynamically and len(output_names) == 1:
            name = output_names[0]
            result[name] = serializable_output
            mapped_dynamically = True
            
        # 3. If output is not mapped, and there is exactly one connection output defined in metadata
        if not mapped_dynamically and len(connection_outputs) == 1:
            result[connection_outputs[0]] = serializable_output
            mapped_dynamically = True

    # Fallback to static mapping for legacy/backward compatibility
    if not mapped_dynamically:
        node_type_lower = node_type.lower()
        if "openai" in node_type_lower or "openrouter" in node_type_lower or "llm" in node_type_lower:
            result["llm"] = serializable_output
        elif "embeddings" in node_type_lower or "embedder" in node_type_lower:
            result["embedder"] = serializable_output
        elif "reranker" in node_type_lower or "cohere" in node_type_lower:
            result["reranker"] = serializable_output
        elif "memory" in node_type_lower:
            result["memory"] = serializable_output
        elif "tavily" in node_type_lower or "search" in node_type_lower:
            result["search_tool"] = serializable_output
        elif "retriever" in node_type_lower:
            result["retriever_tool"] = serializable_output
        elif "loader" in node_type_lower or "scraper" in node_type_lower or "crawler" in node_type_lower:
            result["documents"] = serializable_output
        elif "webhook" in node_type_lower:
            if isinstance(serializable_output, dict):
                result["webhook_data"] = serializable_output.get("webhook_data")
                result["webhook_endpoint"] = serializable_output.get("webhook_endpoint")
                result["webhook_config"] = serializable_output.get("webhook_config")
        elif "kafka" in node_type_lower or "consumer" in node_type_lower:
            if isinstance(serializable_output, dict):
                result["kafka_data"] = serializable_output.get("kafka_data")
        elif "timer" in node_type_lower:
            if isinstance(serializable_output, dict):
                result["timer_data"] = serializable_output.get("timer_data")
        elif "errortrigger" in node_type_lower:
            if isinstance(serializable_output, dict):
                result["error_data"] = serializable_output.get("error_data")

    return result


def safe_json_dumps(obj: Any, **kwargs) -> str:
    """
    Safely serialize object to JSON string with automatic type handling.
    
    Uses orjson if available for better performance, otherwise falls back
    to standard json with make_json_serializable preprocessing.
    
    Args:
        obj: Object to serialize
        **kwargs: Additional arguments for json.dumps() or orjson.dumps()
        
    Returns:
        JSON string representation
        
    Examples:
        >>> from datetime import datetime
        >>> data = {"timestamp": datetime.now()}
        >>> json_str = safe_json_dumps(data)
        >>> print(json_str)
        '{"timestamp":"2025-01-13T12:00:00"}'
    """
    if ORJSON_AVAILABLE:
        try:
            # orjson returns bytes, decode to string
            result = orjson.dumps(obj, default=json_serializer_default, **kwargs)
            return result.decode('utf-8')
        except (TypeError, ValueError):
            # Fallback to recursive conversion if orjson fails
            serializable = make_json_serializable(obj)
            return orjson.dumps(serializable).decode('utf-8')
    else:
        # Fallback to standard json with preprocessing
        serializable = make_json_serializable(obj)
        return json.dumps(serializable, **kwargs)


def safe_json_loads(s: str | bytes, **kwargs) -> Any:
    """
    Safely deserialize JSON string/bytes to Python object.
    
    Uses orjson if available for better performance, otherwise falls back
    to standard json.loads().
    
    Args:
        s: JSON string or bytes to deserialize
        **kwargs: Additional arguments for json.loads() or orjson.loads()
        
    Returns:
        Deserialized Python object
    """
    if ORJSON_AVAILABLE:
        if isinstance(s, str):
            s = s.encode('utf-8')
        return orjson.loads(s, **kwargs)
    else:
        if isinstance(s, bytes):
            s = s.decode('utf-8')
        return json.loads(s, **kwargs)

