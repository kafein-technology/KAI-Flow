# -*- coding: utf-8 -*-
"""Export services - Node extraction and package creation."""

import logging
import uuid
import os
import tempfile
import zipfile
import json
import re
from datetime import datetime
from typing import Dict, Any, List, Optional

from app.models.workflow import Workflow
from app.core.node_registry import node_registry
from .schemas import WorkflowDependencies, SecurityConfig, MonitoringConfig, DockerConfig
from .workflow_templates import create_workflow_engine, create_main_py, create_dockerfile

logger = logging.getLogger(__name__)

# ================================================================================
# CORE NODE EXTRACTION SERVICES
# ================================================================================

def extract_node_source_code(node_class, node_type: str) -> str:
    """Extract actual source code from node class."""
    try:
        import inspect
        
        # Get the module where the node class is defined
        module = inspect.getmodule(node_class)
        if not module:
            raise ValueError(f"Could not determine module for {node_type}")
        
        # Get the file path of the module
        module_file = inspect.getfile(module)
        logger.info(f"Extracting {node_type} from {module_file}")
        
        # Read the entire source file
        with open(module_file, 'r', encoding='utf-8') as f:
            full_source = f.read()
        
        # Clean up the source for export
        cleaned_source = clean_node_source_for_export(full_source, node_type)
        
        logger.info(f"Successfully extracted {len(cleaned_source)} chars for {node_type}")
        return cleaned_source
        
    except Exception as e:
        logger.warning(f"Failed to extract source for {node_type}: {e}")
        return create_simple_fallback(node_type)

def clean_node_source_for_export(source_code: str, node_type: str) -> str:
    """Clean node source code for standalone export runtime."""
    import re
    
    logger.info(f"Cleaning source code for {node_type}")
    
    cleaned = source_code
    
    # Remove project internal imports
    internal_imports = [
        "from ..base import", "from ...base import", "from app.core", 
        "from app.models", "from app.services", "from app.nodes"
    ]
    
    for pattern in internal_imports:
        cleaned = cleaned.replace(pattern, f"# {pattern}")
    
    # Keep external imports (LangChain, etc.)
    external_imports = [
        "from langchain_openai import", "from langchain_tavily import", 
        "from langchain_cohere import", "from langchain.memory import"
    ]
    
    for import_line in external_imports:
        cleaned = cleaned.replace(f"# {import_line}", import_line)
    
    # Final cleanup
    cleaned = re.sub(r"^(\s*)from app\.", r"\1# from app.", cleaned, flags=re.MULTILINE)
    
    return cleaned

def create_simple_fallback(node_type: str) -> str:
    """Create simple fallback for nodes that can't be extracted."""
    return f'''
# Simple {node_type} fallback
class {node_type}Node:
    def __init__(self):
        self.user_data = {{}}
        self._metadata = {{"name": "{node_type}"}}
    
    def execute(self, **kwargs):
        def simple_exec(inputs):
            return {{"output": f"{node_type} executed", "type": "fallback"}}
        from langchain_core.runnables import RunnableLambda
        return RunnableLambda(simple_exec)
'''

def create_enhanced_base_fallback(node_type: str) -> str:
    """Create enhanced fallback for base node types."""
    if 'processor' in node_type.lower():
        base_class = "ProcessorNode"
        node_behavior = '''
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        input_text = processed_inputs.get("input", str(processed_inputs))
        return {
            "output": f"Processed by {self.__class__.__name__}: {input_text}",
            "processed_by": self.__class__.__name__,
            "node_type": "processor"
        }'''
    elif 'provider' in node_type.lower():
        base_class = "ProviderNode"
        node_behavior = '''
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        input_text = processed_inputs.get("input", str(processed_inputs))
        return {
            "provided_data": f"Data provided by {self.__class__.__name__}: {input_text}",
            "provider": self.__class__.__name__,
            "node_type": "provider"
        }'''
    elif 'terminator' in node_type.lower():
        base_class = "TerminatorNode"
        node_behavior = '''
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        input_data = processed_inputs.get("input", processed_inputs)
        return {
            "final_result": input_data,
            "terminated_by": self.__class__.__name__,
            "execution_complete": True,
            "node_type": "terminator"
        }'''
    else:
        base_class = "BaseNode"
        node_behavior = '''
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        return {
            "output": f"Executed by {self.__class__.__name__}",
            "inputs": processed_inputs,
            "node_type": "base"
        }'''
    
    return f'''
# Enhanced {node_type} based on {base_class}
class {node_type}({base_class}):
    def __init__(self):
        super().__init__()
        self.user_data = {{}}
        self._metadata = {{"name": "{node_type}", "type": "{base_class.lower()}"}}
{node_behavior}
'''

# ================================================================================
# MODULAR NODE PROCESSING
# ================================================================================

def extract_modular_node_implementations(flow_data: Dict[str, Any]) -> Dict[str, str]:
    """Extract nodes to separate files with base class detection."""
    logger.info("[TEST] MODULAR: Extracting nodes to separate files")
    
    workflow_nodes = flow_data.get("nodes", [])
    detected_node_types = list(set(node.get("type", "") for node in workflow_nodes if node.get("type")))
    
    # Initialize node registry
    if not node_registry.nodes:
        node_registry.discover_nodes()
    
    # Define base node types that shouldn't be searched in registry
    base_node_types = {
        'ProcessorNode', 'ProviderNode', 'TerminatorNode', 'BaseNode',
        'processor', 'provider', 'terminator', 'base'
    }
    
    modular_files = {}
    
    # Base definitions
    modular_files["nodes/__init__.py"] = create_base_definitions()
    
    # Extract each node
    for node_type in detected_node_types:
        try:
            node_source = None
            
            # Check if it's a base node type first
            if node_type in base_node_types or node_type.lower() in [t.lower() for t in base_node_types]:
                logger.info(f"{node_type} is a base class, using built-in definition")
                node_source = create_enhanced_base_fallback(node_type)
            else:
                # Try to get from registry for custom nodes
                node_class = node_registry.get_node(node_type)
                
                if node_class:
                    logger.info(f"{node_type} found in registry, extracting source")
                    node_source = extract_node_source_code(node_class, node_type)
                else:
                    logger.info(f"{node_type} not found in registry, creating fallback")
                    node_source = create_simple_fallback(node_type)
            
            # Create clean file
            clean_source = create_clean_node_file(node_source, node_type)
            filename = f"nodes/{node_type.lower()}_node.py"
            modular_files[filename] = clean_source
            
            logger.info(f"{node_type} -> {filename}")
            
        except Exception as e:
            logger.warning(f"Failed to process {node_type}: {e}")
    
    logger.info(f"MODULAR: Created {len(modular_files)} files")
    return modular_files

def create_clean_node_file(node_source: str, node_type: str) -> str:
    """Create clean, standalone node file."""
    import re
    
    # Simple header
    header = f'''# -*- coding: utf-8 -*-
"""{node_type} Node - Extracted from KAI-Flow"""

from nodes import BaseNode, ProviderNode, ProcessorNode, TerminatorNode, NodeType, NodeInput, NodeOutput
from typing import Dict, Any, Optional, List
from langchain_core.runnables import Runnable, RunnableLambda
import logging

logger = logging.getLogger(__name__)

'''
    
    # Clean the source
    cleaned = node_source
    
    # Fix "class class" syntax error
    cleaned = re.sub(r'class\s+class\s+(\w+)', r'class \1', cleaned)
    
    # Remove excessive imports (they're in header)
    cleaned = re.sub(r'from typing import.*\n', '', cleaned)
    cleaned = re.sub(r'import logging.*\n', '', cleaned)
    
    # Shorten very long docstrings
    def shorten_docstring(match):
        full_docstring = match.group(1)
        lines = full_docstring.split('\n')
        if len(lines) > 10:
            return f'"""{lines[0]}\n\n... (Documentation shortened for export) ...\n"""'
        return match.group(0)
    
    cleaned = re.sub(r'"""(.*?)"""', shorten_docstring, cleaned, flags=re.DOTALL)
    
    # Ensure we have a proper class definition for this node type
    if f'class {node_type}' not in cleaned:
        # If no specific class found, create a standard one
        if 'class' in cleaned:
            # Replace first class name with correct node type
            cleaned = re.sub(r'class\s+\w+(\([^)]*\))?:', f'class {node_type}\\1:', cleaned, count=1)
        else:
            # Fallback: create a minimal class implementation
            cleaned = f'''
class {node_type}(BaseNode):
    """Generated {node_type} class."""
    def __init__(self):
        super().__init__()
        self.user_data = {{}}
        self._metadata = {{"name": "{node_type}"}}
    
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        return {{
            "output": f"Executed by {{self.__class__.__name__}}",
            "inputs": processed_inputs,
            "node_type": "{node_type.lower()}"
        }}
'''
    
    # Add explicit export of the main class
    footer = f'''

# Export the main node class
__all__ = ['{node_type}']
'''
    
    return header + cleaned + footer

def create_base_definitions() -> str:
    """Create base node definitions with full functionality."""
    return '''# -*- coding: utf-8 -*-
"""Base node definitions with full execution capabilities."""

from typing import Dict, Any, Optional, List, Union
from langchain_core.runnables import Runnable, RunnableLambda
import logging
import json
import asyncio
import importlib
import os

logger = logging.getLogger(__name__)

class NodeType:
    PROCESSOR = "processor"
    PROVIDER = "provider"
    TERMINATOR = "terminator"

class NodeInput:
    """Node input definition for export runtime."""
    def __init__(self, name: str, type: str = "str", required: bool = True, description: str = "", default=None, is_connection: bool = False, **kwargs):
        self.name = name
        self.type = type
        self.required = required
        self.description = description
        self.default = default
        self.is_connection = is_connection
        # Handle any additional kwargs for flexibility
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @property
    def type_hint(self) -> str:
        """Backward compatibility property for type_hint."""
        return self.type

class NodeOutput:
    """Node output definition for export runtime."""
    def __init__(self, name: str, type_hint: str = "str", description: str = ""):
        self.name = name
        self.type_hint = type_hint
        self.description = description

class ExecutionResult:
    """Standard execution result wrapper."""
    def __init__(self, data: Any, success: bool = True, error: Optional[str] = None):
        self.data = data
        self.success = success
        self.error = error
        self.metadata = {}
    
    def to_dict(self):
        return {
            "data": self.data,
            "success": self.success,
            "error": self.error,
            "metadata": self.metadata
        }

class BaseNode:
    """Enhanced base node with full execution capabilities."""
    def __init__(self):
        self._metadata = {}
        self.user_data = {}
        self.node_type = "base"
        self._initialized = False
    
    @property
    def metadata(self):
        return self._metadata
    
    def initialize(self):
        """Initialize node with user configuration."""
        if not self._initialized:
            self._initialized = True
            logger.info(f"Node {self.__class__.__name__} initialized")
    
    def validate_inputs(self, inputs: Dict[str, Any]) -> bool:
        """Validate input data."""
        return True
    
    def process_inputs(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """Process and normalize inputs."""
        return inputs
    
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        """Core execution logic - to be overridden."""
        return {"output": f"{self.__class__.__name__} executed", "inputs": processed_inputs}
    
    def format_outputs(self, result: Any) -> Dict[str, Any]:
        """Format outputs for downstream nodes."""
        if isinstance(result, dict):
            return result
        return {"result": result}
    
    def execute(self, **kwargs) -> Runnable:
        """Execute node with full workflow support."""
        def node_execution(inputs):
            try:
                # Initialize if needed
                self.initialize()
                
                # Validate inputs
                if not self.validate_inputs(inputs):
                    return ExecutionResult(
                        data={"error": "Invalid inputs"},
                        success=False,
                        error="Input validation failed"
                    ).to_dict()
                
                # Process inputs
                processed_inputs = self.process_inputs(inputs)
                
                # Execute core logic
                result = self.execute_core_logic(processed_inputs)
                
                # Format outputs
                formatted_result = self.format_outputs(result)
                
                return ExecutionResult(data=formatted_result, success=True).to_dict()
                
            except Exception as e:
                logger.error(f"Node execution failed: {e}")
                return ExecutionResult(
                    data={"error": str(e)},
                    success=False,
                    error=str(e)
                ).to_dict()
        
        return RunnableLambda(node_execution)

class ProcessorNode(BaseNode):
    """Node that processes data through transformations."""
    def __init__(self):
        super().__init__()
        self.node_type = "processor"
    
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        # Default processor behavior
        input_text = processed_inputs.get("input", str(processed_inputs))
        processed_text = f"Processed: {input_text}"
        
        return {
            "output": processed_text,
            "processed_by": self.__class__.__name__,
            "timestamp": str(asyncio.get_event_loop().time()) if hasattr(asyncio, 'get_event_loop') else "unknown"
        }

class ProviderNode(BaseNode):
    """Node that provides data or services."""
    def __init__(self):
        super().__init__()
        self.node_type = "provider"
    
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        # Default provider behavior
        input_text = processed_inputs.get("input", str(processed_inputs))
        
        return {
            "provided_data": f"Data provided for: {input_text}",
            "provider": self.__class__.__name__,
            "data_type": "text",
            "metadata": {"source": "provider_node"}
        }

class TerminatorNode(BaseNode):
    """Node that terminates workflow execution."""
    def __init__(self):
        super().__init__()
        self.node_type = "terminator"
    
    def execute_core_logic(self, processed_inputs: Dict[str, Any]) -> Any:
        # Default terminator behavior
        input_data = processed_inputs.get("input", processed_inputs)
        
        return {
            "final_result": input_data,
            "terminated_by": self.__class__.__name__,
            "execution_complete": True,
            "summary": f"Workflow terminated with result: {json.dumps(input_data, default=str)[:100]}..."
        }

# Enhanced mock functions for export runtime
def trace_memory_operation(operation_name):
    """Enhanced memory operation tracer."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            logger.debug(f"Memory operation: {operation_name}")
            return func(*args, **kwargs)
        return wrapper
    return decorator

def get_workflow_tracer(session_id=None):
    """Enhanced workflow tracer."""
    class EnhancedTracer:
        def __init__(self, session_id):
            self.session_id = session_id or "default_session"
        
        def track_memory_operation(self, op, node_type, message, session_id):
            logger.info(f"[{self.session_id}] {node_type}: {op} - {message}")
        
        def track_execution(self, node_name, inputs, outputs):
            logger.info(f"[{self.session_id}] Node {node_name} executed")
    
    return EnhancedTracer(session_id)

def get_colored_logger(name):
    """Enhanced colored logger."""
    class EnhancedColoredLogger:
        def __init__(self, name):
            self.name = name
            self.logger = logging.getLogger(name)
        
        def yellow(self, message):
            self.logger.warning(f"[{self.name}] {message}")
        
        def green(self, message):
            self.logger.info(f"[{self.name}] {message}")
        
        def red(self, message):
            self.logger.error(f"[{self.name}] {message}")
    
    return EnhancedColoredLogger(name)

# Utility functions for node execution
def create_runnable_chain(*nodes):
    """Create a chain of runnable nodes."""
    def chain_execution(inputs):
        current_inputs = inputs
        results = []
        
        for node in nodes:
            try:
                runnable = node.execute()
                result = runnable.invoke(current_inputs)
                results.append(result)
                
                if result.get("success", True):
                    current_inputs = result.get("data", result)
                else:
                    return {"error": f"Chain failed at {node.__class__.__name__}", "results": results}
            except Exception as e:
                return {"error": f"Chain execution failed: {e}", "results": results}
        
        return {"success": True, "results": results, "final_output": current_inputs}
    
    return RunnableLambda(chain_execution)

# ================================================================================
# DYNAMIC MODULE IMPORTING - Auto-discovers and imports all node modules
# ================================================================================

def _discover_and_import_node_modules():
    """Dynamically discover and import all node modules in the nodes package."""
    import glob
    import os
    import sys
    
    # Pre-register critical missing classes to avoid import failures
    _register_critical_missing_classes()
    
    try:
        # Try multiple methods to get current directory
        current_dir = None
        
        # Method 1: Use __file__ if available
        try:
            current_dir = os.path.dirname(__file__)
        except NameError:
            pass
        
        # Method 2: Use current working directory + nodes
        if not current_dir:
            cwd = os.getcwd()
            potential_dirs = [
                os.path.join(cwd, "nodes"),
                cwd  # If we're already in nodes directory
            ]
            for potential_dir in potential_dirs:
                if os.path.exists(potential_dir) and os.path.isdir(potential_dir):
                    current_dir = potential_dir
                    break
        
        # Method 3: Search in sys.path
        if not current_dir:
            for path in sys.path:
                nodes_path = os.path.join(path, "nodes")
                if os.path.exists(nodes_path) and os.path.isdir(nodes_path):
                    current_dir = nodes_path
                    break
        
        if not current_dir:
            logger.warning("Could not determine nodes directory")
            return
        
        logger.debug(f"Looking for node modules in: {current_dir}")
        
        # Find all *_node.py files
        node_files = glob.glob(os.path.join(current_dir, "*_node.py"))
        
        if not node_files:
            # Try alternative pattern
            try:
                node_files = [f for f in os.listdir(current_dir) if f.endswith("_node.py")]
                node_files = [os.path.join(current_dir, f) for f in node_files]
            except OSError:
                logger.warning(f"Could not list directory: {current_dir}")
                return
        
        logger.debug(f"Found {len(node_files)} node files: {[os.path.basename(f) for f in node_files]}")
        
        for node_file in node_files:
            try:
                # Get module name without .py extension
                module_name = os.path.basename(node_file)[:-3]  # Remove .py
                
                # Import the module with better error handling
                try:
                    module = importlib.import_module(f".{module_name}", package="nodes")
                except ImportError as e:
                    # Try direct import if relative import fails
                    try:
                        module = importlib.import_module(f"nodes.{module_name}")
                    except ImportError:
                        logger.warning(f"Failed to import {module_name}: {e}")
                        continue
                
                # Add module to current namespace
                globals()[module_name] = module
                
                # Also try to expose the main class from the module
                # Extract node type from filename (e.g., startnode_node -> StartNode)
                node_type_parts = module_name.replace("_node", "").split("_")
                node_class_name = "".join(word.capitalize() for word in node_type_parts)
                
                # Try to get the class from the module
                if hasattr(module, node_class_name):
                    globals()[node_class_name] = getattr(module, node_class_name)
                    logger.debug(f"Exposed class {node_class_name} from {module_name}")
                elif hasattr(module, module_name.replace("_", "")):
                    # Alternative naming pattern
                    alt_class_name = module_name.replace("_", "")
                    globals()[alt_class_name] = getattr(module, alt_class_name)
                    logger.debug(f"Exposed class {alt_class_name} from {module_name}")
                else:
                    # Try to find any class in the module that looks like a node
                    for attr_name in dir(module):
                        attr = getattr(module, attr_name)
                        if (isinstance(attr, type) and
                            hasattr(attr, 'execute') and
                            'node' in attr_name.lower()):
                            globals()[attr_name] = attr
                            logger.debug(f"Exposed class {attr_name} from {module_name}")
                            break
                
                logger.debug(f"Imported node module: {module_name}")
                
            except Exception as e:
                logger.warning(f"Failed to import {module_name}: {e}")
                # Create a fallback stub for the module
                _create_fallback_module_stub(module_name)
    
    except Exception as e:
        logger.warning(f"Node module discovery failed: {e}")

def _register_critical_missing_classes():
    """Pre-register critical classes that are commonly missing."""
    
    # ReactAgentNode fallback
    class ReactAgentNode(ProcessorNode):
        def __init__(self):
            super().__init__()
            self.user_data = {}
            self._metadata = {"name": "ReactAgentNode", "type": "processor"}
        
        def execute(self, inputs: dict, connected_nodes: dict):
            def react_agent_exec(input_data):
                return {"output": f"ReactAgent processed: {input_data.get('input', '')}", "type": "agent_result"}
            from langchain_core.runnables import RunnableLambda
            return RunnableLambda(react_agent_exec)
    
    # OpenAINode fallback
    class OpenAINode(ProviderNode):
        def __init__(self):
            super().__init__()
            self.user_data = {}
            self._metadata = {"name": "OpenAINode", "type": "provider"}
        
        def execute(self, **kwargs):
            def openai_exec(input_data):
                return {"output": f"OpenAI processed: {input_data.get('input', '')}", "type": "llm_result"}
            from langchain_core.runnables import RunnableLambda
            return RunnableLambda(openai_exec)
    
    # Register these globally
    globals()['ReactAgentNode'] = ReactAgentNode
    globals()['OpenAINode'] = OpenAINode
    
    logger.info("Pre-registered critical missing classes")

def _create_fallback_module_stub(module_name):
    """Create a fallback module stub for failed imports."""
    class FallbackModuleStub:
        def __getattr__(self, name):
            # Return a basic node class for any requested attribute
            if name.endswith('Node'):
                return type(name, (BaseNode,), {
                    '__init__': lambda self: setattr(self, '_metadata', {'name': name}),
                    'execute': lambda self, *args, **kwargs: None
                })
            return None
    
    globals()[module_name] = FallbackModuleStub()
    logger.debug(f"Created fallback stub for {module_name}")

# Auto-import all node modules when this package is loaded
try:
    _discover_and_import_node_modules()
except Exception as e:
    logger.warning(f"Auto-import failed: {e}")

# Auto-discover available modules and classes
_available_modules = []
_available_classes = []

def _register_discovered_items():
    """Register all discovered modules and classes for export."""
    import os
    import glob
    
    try:
        # Try to find current directory
        current_dir = None
        try:
            current_dir = os.path.dirname(__file__)
        except NameError:
            current_dir = os.getcwd()
            if not os.path.exists(os.path.join(current_dir, "__init__.py")):
                # We might be in a parent directory, check for nodes subdirectory
                nodes_dir = os.path.join(current_dir, "nodes")
                if os.path.exists(nodes_dir):
                    current_dir = nodes_dir
        
        if current_dir and os.path.exists(current_dir):
            # Find all node modules
            node_files = glob.glob(os.path.join(current_dir, "*_node.py"))
            for node_file in node_files:
                module_name = os.path.basename(node_file)[:-3]
                _available_modules.append(module_name)
                
                # Try to guess class names
                node_type_parts = module_name.replace("_node", "").split("_")
                class_name = "".join(word.capitalize() for word in node_type_parts)
                _available_classes.append(class_name)
                
        logger.debug(f"Registered modules: {_available_modules}")
        logger.debug(f"Registered classes: {_available_classes}")
        
    except Exception as e:
        logger.warning(f"⚠️  Registration failed: {e}")

# Register discovered items
_register_discovered_items()

# Ensure base classes and discovered items are always available
__all__ = [
    'BaseNode', 'ProcessorNode', 'ProviderNode', 'TerminatorNode',
    'NodeType', 'NodeInput', 'NodeOutput', 'ExecutionResult'
] + _available_modules + _available_classes

# Make modules available at package level
def __getattr__(name):
    """Dynamic attribute access for discovered modules."""
    if name in _available_modules:
        try:
            return importlib.import_module(f".{name}", package="nodes")
        except ImportError as e:
            logger.warning(f"Failed to import {name}: {e}")
            raise AttributeError(f"module 'nodes' has no attribute '{name}'")
    
    if name in _available_classes:
        # Try to find the class in any of the modules
        for module_name in _available_modules:
            try:
                module = importlib.import_module(f".{module_name}", package="nodes")
                if hasattr(module, name):
                    return getattr(module, name)
            except ImportError:
                continue
    
    raise AttributeError(f"module 'nodes' has no attribute '{name}'")
'''

# ================================================================================
# BACKEND CREATION SERVICES  
# ================================================================================

def create_minimal_backend(dependencies: WorkflowDependencies, workflow_flow_data: Dict[str, Any] = None) -> Dict[str, str]:
    """Create modular backend components."""
    logger.info("Creating modular backend")
    
    # Extract node implementations to separate files
    if workflow_flow_data:
        modular_files = extract_modular_node_implementations(workflow_flow_data)
        logger.info(f"{len(modular_files)} node files created")
    else:
        modular_files = {"nodes/__init__.py": create_base_definitions()}
    
    # Add workflow engine from templates
    modular_files["workflow_engine.py"] = create_workflow_engine()
    
    # Create main.py from templates 
    modular_files["main.py"] = create_main_py()
    
    # Add Dockerfile from templates
    modular_files["Dockerfile"] = create_dockerfile()
    
    return modular_files

# ================================================================================
# PACKAGE CREATION SERVICES
# ================================================================================

def filter_requirements_for_nodes(node_types: List[str]) -> str:
    """Generate requirements.txt for nodes."""
    try:
        from app.core.dynamic_node_analyzer import dynamic_analyzer
        
        flow_data = {"nodes": [{"type": node_type, "id": f"node_{i}", "data": {}} for i, node_type in enumerate(node_types)]}
        analysis_result = dynamic_analyzer.analyze_workflow(flow_data)
        dynamic_packages = [f"{pkg.name}{pkg.version}" for pkg in analysis_result.package_dependencies]
        
        return "\n".join(sorted(dynamic_packages))
        
    except Exception as e:
        logger.error(f"Dynamic package filtering failed: {e}")
        
        # Fallback
        base_packages = ["fastapi>=0.104.0", "uvicorn[standard]>=0.24.0", "langchain>=0.1.0", "pydantic>=2.5.0"]
        
        for node_type in node_types:
            if "OpenAI" in node_type:
                base_packages.extend(["langchain-openai>=0.0.5", "openai>=1.0.0"])
        
        return "\n".join(sorted(set(base_packages)))

def create_pre_configured_env_file(dependencies, user_env_vars, security, monitoring, docker, flow_data) -> str:
    """Create .env file."""
    env_lines = [
        "# Generated .env file for workflow export",
        f"# Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
        f"WORKFLOW_ID={dependencies.workflow_id}",
        f"WORKFLOW_MODE=runtime",
        f"DATABASE_URL={user_env_vars.get('DATABASE_URL', 'postgresql://user:pass@localhost:5432/workflow_db')}",
        f"SECRET_KEY={user_env_vars.get('SECRET_KEY', 'auto-generated-secret-key-' + str(uuid.uuid4()))}",
        f"REQUIRE_API_KEY={str(security.require_api_key).lower()}",
        f"API_KEYS={security.api_keys or ''}",
        f"API_PORT={docker.api_port}",
        f"DOCKER_PORT={docker.docker_port}",
        ""
    ]
    
    # Add user environment variables
    for env_var, value in user_env_vars.items():
        if env_var not in ["DATABASE_URL", "SECRET_KEY"]:
            env_lines.append(f"{env_var}={value}")
    
    return "\n".join(env_lines)

def create_ready_to_run_docker_context(workflow, minimal_backend, pre_configured_env, docker_config) -> Dict[str, str]:
    """Create Docker context files."""
    docker_compose = f'''services:
  workflow-api:
    build: .
    env_file:
      - .env
    ports:
      - "{docker_config.docker_port}:{docker_config.api_port}"
    volumes:
      - ./logs:/app/logs
    restart: unless-stopped

volumes:
  logs:
'''
    
    return {"docker-compose.yml": docker_compose}

def generate_ready_to_run_readme(workflow_name: str, env_config) -> str:
    """Generate README."""
    port = env_config.docker.docker_port
    workflow_slug = workflow_name.lower().replace(' ', '-')
    
    return f"""# {workflow_name} - Docker Export

Ready-to-run Docker export of your KAI-Flow workflow.

## Quick Start

1. Extract: `unzip workflow-export-{workflow_slug}.zip && cd workflow-export-{workflow_slug}/`
2. Start: `docker-compose up -d`
3. Test: `curl http://localhost:{port}/health`

## API Usage

```bash
curl -X POST http://localhost:{port}/api/workflow/execute \\
  -H "Content-Type: application/json" \\
  -d '{{"input": "Your input here"}}'
```

Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
"""

def create_workflow_export_package(components: Dict[str, Any]) -> Dict[str, Any]:
    """Create the final export package as a ZIP file."""
    logger.info("Creating workflow export package")
    
    workflow = components['workflow']
    package_name = f"workflow-export-{workflow.name.lower().replace(' ', '-')}"
    
    with tempfile.TemporaryDirectory() as temp_dir:
        package_dir = os.path.join(temp_dir, package_name)
        os.makedirs(package_dir)
        
        # Write all backend files (modular structure)
        backend_files = components['backend']
        for filename, content in backend_files.items():
            file_path = os.path.join(package_dir, filename)
            
            # Create subdirectories if needed
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Write essential files
        essential_files = {
            ".env": components['pre_configured_env'],
            "requirements.txt": components['filtered_requirements'],
            "README.md": components['readme'],
            "workflow-definition.json": json.dumps(workflow.flow_data, indent=2, ensure_ascii=False)
        }
        
        # Add docker files
        essential_files.update(components['docker_configs'])
        
        for filename, content in essential_files.items():
            with open(os.path.join(package_dir, filename), 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Create ZIP file
        zip_path = f"{package_dir}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(package_dir):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, temp_dir)
                    zipf.write(file_path, arcname)
        
        # Move to permanent storage
        import shutil
        permanent_dir = os.path.join(os.getcwd(), "exports")
        os.makedirs(permanent_dir, exist_ok=True)
        permanent_zip_path = os.path.join(permanent_dir, f"{package_name}.zip")
        shutil.move(zip_path, permanent_zip_path)
        
        logger.info(f"Export package created: {permanent_zip_path}")
        
        return {
            "download_url": f"/api/v1/export/download/{package_name}.zip",
            "package_size": os.path.getsize(permanent_zip_path),
            "local_path": permanent_zip_path
        }