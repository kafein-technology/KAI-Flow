# -*- coding: utf-8 -*-
"""Workflow template generation services."""

import logging
import uuid
import os
import tempfile
import zipfile
import json
from datetime import datetime
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

def create_workflow_engine() -> str:
    """Create full-featured workflow execution engine."""
    return '''# -*- coding: utf-8 -*-
"""Advanced Workflow Execution Engine - Full Implementation"""

from typing import Dict, Any, List, Optional, Set
import logging
import json
import uuid
import importlib
import traceback
from datetime import datetime
from collections import defaultdict, deque

logger = logging.getLogger(__name__)

class WorkflowExecutionContext:
    """Execution context for workflow runs."""
    def __init__(self, session_id: str = None):
        self.session_id = session_id or str(uuid.uuid4())
        self.execution_id = str(uuid.uuid4())
        self.variables = {}
        self.memory = {}
        self.execution_log = []
        self.start_time = datetime.now()
    
    def log_execution(self, node_id: str, node_type: str, inputs: Any, outputs: Any, success: bool = True, error: str = None):
        """Log node execution."""
        self.execution_log.append({
            "node_id": node_id,
            "node_type": node_type,
            "inputs": inputs,
            "outputs": outputs,
            "success": success,
            "error": error,
            "timestamp": datetime.now().isoformat()
        })

class NodeExecutor:
    """Handles individual node execution."""
    
    @staticmethod
    def load_node_class(node_type: str):
        """Dynamically load node class with smart base class detection."""
        try:
            # First check if it's a base node type (defined in nodes/__init__.py)
            from nodes import BaseNode, ProcessorNode, ProviderNode, TerminatorNode
            
            base_node_map = {
                'processornode': ProcessorNode,
                'providernode': ProviderNode,
                'terminatornode': TerminatorNode,
                'processor': ProcessorNode,
                'provider': ProviderNode,
                'terminator': TerminatorNode,
                'basenode': BaseNode,
                'base': BaseNode
            }
            
            # Check if it matches a base node type
            normalized_type = node_type.lower()
            if normalized_type in base_node_map:
                logger.info(f"Using base class: {node_type} -> {base_node_map[normalized_type].__name__}")
                return base_node_map[normalized_type]
            
            # Try to import from specific node module
            try:
                module_name = f"nodes.{node_type.lower()}_node"
                module = importlib.import_module(module_name)
                
                # Find the node class in the module
                for attr_name in dir(module):
                    attr = getattr(module, attr_name)
                    if (isinstance(attr, type) and
                        hasattr(attr, 'execute') and
                        attr_name.lower().find(node_type.lower()) != -1):
                        logger.info(f"Loaded specific class: {node_type} -> {attr.__name__}")
                        return attr
                
                logger.warning(f"No specific class found in {module_name} for {node_type}")
                
            except ImportError:
                logger.warning(f"Could not import module for {node_type}")
            
            # Final fallback based on node type pattern
            if 'processor' in normalized_type:
                logger.info(f"Fallback to ProcessorNode for {node_type}")
                return ProcessorNode
            elif 'provider' in normalized_type:
                logger.info(f"Fallback to ProviderNode for {node_type}")
                return ProviderNode
            elif 'terminator' in normalized_type or 'end' in normalized_type:
                logger.info(f"Fallback to TerminatorNode for {node_type}")
                return TerminatorNode
            else:
                logger.info(f"Fallback to BaseNode for {node_type}")
                return BaseNode
                
        except Exception as e:
            logger.error(f"Error loading node class {node_type}: {e}")
            # Ultimate fallback
            from nodes import BaseNode
            return BaseNode
    
    @staticmethod
    def execute_node(node_data: Dict[str, Any], inputs: Any, context: WorkflowExecutionContext) -> Dict[str, Any]:
        """Execute a single node."""
        node_id = node_data.get('id', 'unknown')
        node_type = node_data.get('type', 'BaseNode')
        user_data = node_data.get('data', {})
        
        try:
            # Load and instantiate node
            node_class = NodeExecutor.load_node_class(node_type)
            node_instance = node_class()
            
            # Set user configuration
            if hasattr(node_instance, 'user_data'):
                node_instance.user_data = user_data
            
            # Create execution input
            execution_input = {
                'input': inputs,
                'session_id': context.session_id,
                'variables': context.variables,
                'memory': context.memory,
                'user_data': user_data
            }
            
            # Execute node
            runnable = node_instance.execute()
            result = runnable.invoke(execution_input)
            
            # Update context with results
            if isinstance(result, dict):
                if 'variables' in result:
                    context.variables.update(result['variables'])
                if 'memory' in result:
                    context.memory.update(result['memory'])
            
            # Log successful execution
            context.log_execution(node_id, node_type, inputs, result, success=True)
            
            return result
            
        except Exception as e:
            error_msg = f"Node {node_id} ({node_type}) execution failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            
            # Log failed execution
            context.log_execution(node_id, node_type, inputs, None, success=False, error=error_msg)
            
            return {
                "success": False,
                "error": error_msg,
                "node_id": node_id,
                "node_type": node_type
            }

class WorkflowGraph:
    """Represents workflow as a directed graph."""
    
    def __init__(self, workflow_def: Dict[str, Any]):
        self.nodes = {node['id']: node for node in workflow_def.get('nodes', [])}
        self.edges = workflow_def.get('edges', [])
        self.adjacency_list = defaultdict(list)
        self.reverse_adjacency_list = defaultdict(list)
        self.build_graph()
    
    def build_graph(self):
        """Build adjacency lists for graph traversal."""
        for edge in self.edges:
            source = edge.get('source')
            target = edge.get('target')
            
            if source and target:
                self.adjacency_list[source].append(target)
                self.reverse_adjacency_list[target].append(source)
    
    def find_start_nodes(self) -> List[str]:
        """Find nodes with no incoming edges."""
        start_nodes = []
        for node_id in self.nodes:
            if node_id not in self.reverse_adjacency_list or not self.reverse_adjacency_list[node_id]:
                start_nodes.append(node_id)
        return start_nodes
    
    def find_end_nodes(self) -> List[str]:
        """Find nodes with no outgoing edges."""
        end_nodes = []
        for node_id in self.nodes:
            if node_id not in self.adjacency_list or not self.adjacency_list[node_id]:
                end_nodes.append(node_id)
        return end_nodes
    
    def topological_sort(self) -> List[str]:
        """Get topological ordering of nodes."""
        in_degree = defaultdict(int)
        
        # Calculate in-degrees
        for node_id in self.nodes:
            in_degree[node_id] = len(self.reverse_adjacency_list[node_id])
        
        # Queue for nodes with no incoming edges
        queue = deque([node_id for node_id in self.nodes if in_degree[node_id] == 0])
        result = []
        
        while queue:
            current = queue.popleft()
            result.append(current)
            
            # Reduce in-degree of neighbors
            for neighbor in self.adjacency_list[current]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        if len(result) != len(self.nodes):
            logger.warning("Workflow contains cycles - using partial ordering")
        
        return result

class DynamicWorkflowEngine:
    """Advanced workflow execution engine with full graph processing."""
    
    def __init__(self, workflow_def: Dict[str, Any]):
        self.workflow_def = workflow_def
        self.graph = WorkflowGraph(workflow_def)
        self.node_executor = NodeExecutor()
        logger.info(f"Workflow engine initialized with {len(self.graph.nodes)} nodes and {len(self.graph.edges)} edges")
    
    def execute_workflow(self, user_input: str, session_id: str = None) -> Dict[str, Any]:
        """Execute the complete workflow."""
        context = WorkflowExecutionContext(session_id)
        
        try:
            logger.info(f"Starting workflow execution with input: {user_input[:100]}...")
            
            # Find execution order
            execution_order = self.graph.topological_sort()
            if not execution_order:
                start_nodes = self.graph.find_start_nodes()
                execution_order = start_nodes
                logger.warning(f"Using start nodes as execution order: {start_nodes}")
            
            logger.info(f"Execution order: {execution_order}")
            
            # Track node outputs
            node_outputs = {}
            current_data = user_input
            
            # Execute nodes in order
            for node_id in execution_order:
                if node_id not in self.graph.nodes:
                    logger.warning(f"Node {node_id} not found in graph")
                    continue
                
                node_data = self.graph.nodes[node_id]
                
                # Determine input for this node
                node_input = self.determine_node_input(node_id, node_outputs, current_data, context)
                
                # Execute node
                logger.info(f"Executing node {node_id} ({node_data.get('type', 'unknown')})")
                result = self.node_executor.execute_node(node_data, node_input, context)
                
                # Store result
                node_outputs[node_id] = result
                
                # Update current data for next node
                if isinstance(result, dict) and 'data' in result:
                    current_data = result['data']
                elif isinstance(result, dict) and result.get('success', True):
                    current_data = result
                else:
                    # Handle error case
                    if not result.get('success', True):
                        logger.error(f"Node {node_id} failed: {result.get('error')}")
                        return self.create_error_response(result.get('error'), context, node_outputs)
            
            # Create success response
            end_nodes = self.graph.find_end_nodes()
            final_output = current_data
            
            if end_nodes:
                final_output = node_outputs.get(end_nodes[-1], current_data)
            
            return self.create_success_response(final_output, context, node_outputs)
            
        except Exception as e:
            error_msg = f"Workflow execution failed: {str(e)}"
            logger.error(error_msg)
            logger.error(traceback.format_exc())
            return self.create_error_response(error_msg, context, {})
    
    def determine_node_input(self, node_id: str, node_outputs: Dict[str, Any], current_data: Any, context: WorkflowExecutionContext) -> Any:
        """Determine input for a node based on its predecessors."""
        predecessors = self.graph.reverse_adjacency_list.get(node_id, [])
        
        if not predecessors:
            # Start node - use current data
            return current_data
        elif len(predecessors) == 1:
            # Single predecessor - use its output
            pred_output = node_outputs.get(predecessors[0], current_data)
            if isinstance(pred_output, dict) and 'data' in pred_output:
                return pred_output['data']
            return pred_output
        else:
            # Multiple predecessors - combine outputs
            combined_inputs = {}
            for pred_id in predecessors:
                pred_output = node_outputs.get(pred_id, {})
                if isinstance(pred_output, dict):
                    combined_inputs[f"input_{pred_id}"] = pred_output.get('data', pred_output)
                else:
                    combined_inputs[f"input_{pred_id}"] = pred_output
            return combined_inputs
    
    def create_success_response(self, final_output: Any, context: WorkflowExecutionContext, node_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create success response."""
        execution_time = (datetime.now() - context.start_time).total_seconds()
        
        # Extract meaningful response
        response_text = ""
        if isinstance(final_output, dict):
            response_text = (final_output.get('output') or
                           final_output.get('result') or
                           final_output.get('final_result') or
                           str(final_output))
        else:
            response_text = str(final_output)
        
        return {
            "response": response_text,
            "type": "success",
            "engine": "advanced_modular",
            "execution_id": context.execution_id,
            "session_id": context.session_id,
            "execution_time": execution_time,
            "nodes_executed": len([log for log in context.execution_log if log['success']]),
            "execution_log": context.execution_log[-10:],  # Last 10 entries
            "final_output": final_output,
            "metadata": {
                "workflow_nodes": len(self.graph.nodes),
                "workflow_edges": len(self.graph.edges),
                "variables": context.variables,
                "memory_keys": list(context.memory.keys())
            }
        }
    
    def create_error_response(self, error_msg: str, context: WorkflowExecutionContext, node_outputs: Dict[str, Any]) -> Dict[str, Any]:
        """Create error response."""
        execution_time = (datetime.now() - context.start_time).total_seconds()
        
        return {
            "response": f"Workflow execution failed: {error_msg}",
            "type": "error",
            "engine": "advanced_modular",
            "execution_id": context.execution_id,
            "session_id": context.session_id,
            "execution_time": execution_time,
            "error": error_msg,
            "execution_log": context.execution_log,
            "partial_results": node_outputs,
            "metadata": {
                "workflow_nodes": len(self.graph.nodes),
                "workflow_edges": len(self.graph.edges)
            }
        }
    
    def get_workflow_info(self) -> Dict[str, Any]:
        """Get workflow information."""
        return {
            "nodes": len(self.graph.nodes),
            "edges": len(self.graph.edges),
            "start_nodes": self.graph.find_start_nodes(),
            "end_nodes": self.graph.find_end_nodes(),
            "node_types": list(set(node.get('type', 'unknown') for node in self.graph.nodes.values()))
        }

# Global workflow engine instance
workflow_engine = None

def initialize_workflow_engine(workflow_definition: Dict[str, Any]) -> DynamicWorkflowEngine:
    """Initialize the global workflow engine."""
    global workflow_engine
    workflow_engine = DynamicWorkflowEngine(workflow_definition)
    return workflow_engine
'''

def create_main_py() -> str:
    """Create enhanced main.py with full workflow capabilities."""
    return '''# -*- coding: utf-8 -*-
"""KAI-Fusion Advanced Workflow Runtime - Production Ready"""

import os
import sys
import logging
import json
import uuid
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from workflow_engine import DynamicWorkflowEngine, initialize_workflow_engine

# Enhanced logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('workflow_runtime.log', encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

# Global workflow engine
workflow_engine = None
WORKFLOW_DEF = {}

def load_workflow_definition():
    """Load and validate workflow definition."""
    global workflow_engine, WORKFLOW_DEF
    
    try:
        # Try multiple locations for workflow definition
        workflow_paths = ['workflow-definition.json', './workflow-definition.json', '/app/workflow-definition.json']
        
        for path in workflow_paths:
            if os.path.exists(path):
                logger.info(f"Loading workflow definition from: {path}")
                with open(path, 'r', encoding='utf-8') as f:
                    WORKFLOW_DEF = json.load(f)
                break
        else:
            raise FileNotFoundError("workflow-definition.json not found in any expected location")
        
        # Validate workflow structure
        if not isinstance(WORKFLOW_DEF, dict):
            raise ValueError("Workflow definition must be a JSON object")
        
        nodes = WORKFLOW_DEF.get('nodes', [])
        edges = WORKFLOW_DEF.get('edges', [])
        
        if not nodes:
            logger.warning("No nodes found in workflow definition")
        
        logger.info(f"Workflow loaded: {len(nodes)} nodes, {len(edges)} edges")
        
        # Initialize workflow engine
        workflow_engine = initialize_workflow_engine(WORKFLOW_DEF)
        workflow_info = workflow_engine.get_workflow_info()
        
        logger.info(f"Workflow engine initialized successfully")
        logger.info(f"   - Nodes: {workflow_info['nodes']}")
        logger.info(f"   - Edges: {workflow_info['edges']}")
        logger.info(f"   - Start nodes: {workflow_info['start_nodes']}")
        logger.info(f"   - End nodes: {workflow_info['end_nodes']}")
        logger.info(f"   - Node types: {workflow_info['node_types']}")
        
        return True
        
    except Exception as e:
        logger.error(f"Failed to load workflow: {e}")
        import traceback
        logger.error(traceback.format_exc())
        
        # Create minimal fallback workflow
        WORKFLOW_DEF = {
            "nodes": [
                {
                    "id": "fallback_node",
                    "type": "ProcessorNode",
                    "data": {"name": "Fallback Node"}
                }
            ],
            "edges": []
        }
        
        try:
            workflow_engine = initialize_workflow_engine(WORKFLOW_DEF)
            logger.info("Fallback workflow engine initialized")
            return True
        except Exception as fallback_error:
            logger.error(f"Even fallback workflow failed: {fallback_error}")
            return False

# Initialize workflow on startup
workflow_loaded = load_workflow_definition()

# Initialize FastAPI with enhanced configuration
app = FastAPI(
    title="KAI-Fusion Advanced Workflow Runtime",
    description="Production-ready workflow execution engine with full graph processing",
    version="2.0.0",
    docs_url="/docs" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None,
    redoc_url="/redoc" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else None
)

# Enhanced CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

# Pydantic models
class WorkflowRequest(BaseModel):
    input: str = Field(..., description="Input data for workflow execution", min_length=1)
    session_id: Optional[str] = Field(None, description="Optional session ID for tracking")
    variables: Optional[Dict[str, Any]] = Field(default_factory=dict, description="Initial variables")
    
    class Config:
        json_schema_extra = {
            "example": {
                "input": "Process this data",
                "session_id": "user_session_123",
                "variables": {"user_id": "123", "context": "production"}
            }
        }

class WorkflowResponse(BaseModel):
    execution_id: str
    session_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
    timestamp: str
    execution_time: Optional[float] = None
    nodes_executed: Optional[int] = None
    metadata: Optional[Dict[str, Any]] = None

class WorkflowInfo(BaseModel):
    nodes: int
    edges: int
    start_nodes: List[str]
    end_nodes: List[str]
    node_types: List[str]

class HealthResponse(BaseModel):
    status: str
    timestamp: str
    workflow_loaded: bool
    workflow_info: Optional[WorkflowInfo] = None
    version: str = "2.0.0"

# In-memory execution tracking
EXECUTIONS = {}
MAX_EXECUTION_HISTORY = 1000

def cleanup_old_executions():
    """Cleanup old execution records."""
    if len(EXECUTIONS) > MAX_EXECUTION_HISTORY:
        # Keep only the most recent executions
        sorted_executions = sorted(EXECUTIONS.items(),
                                 key=lambda x: x[1].get('timestamp', ''),
                                 reverse=True)
        EXECUTIONS.clear()
        EXECUTIONS.update(dict(sorted_executions[:MAX_EXECUTION_HISTORY//2]))
        logger.info(f"Cleaned up old executions, kept {len(EXECUTIONS)} recent ones")

# API Endpoints

@app.get("/", response_model=Dict[str, str])
async def root():
    """Root endpoint with service information."""
    return {
        "service": "KAI-Fusion Advanced Workflow Runtime",
        "version": "2.0.0",
        "status": "running",
        "workflow_loaded": str(workflow_loaded),
        "docs": "/docs" if os.getenv("ENABLE_DOCS", "true").lower() == "true" else "disabled"
    }

@app.get("/health", response_model=HealthResponse)
async def health():
    """Enhanced health check with workflow status."""
    workflow_info = None
    if workflow_engine:
        try:
            info = workflow_engine.get_workflow_info()
            workflow_info = WorkflowInfo(**info)
        except Exception as e:
            logger.error(f"Error getting workflow info: {e}")
    
    return HealthResponse(
        status="healthy" if workflow_loaded else "degraded",
        timestamp=datetime.now().isoformat(),
        workflow_loaded=workflow_loaded,
        workflow_info=workflow_info
    )

@app.get("/workflow/info", response_model=WorkflowInfo)
async def get_workflow_info():
    """Get detailed workflow information."""
    if not workflow_engine:
        raise HTTPException(status_code=503, detail="Workflow engine not initialized")
    
    try:
        info = workflow_engine.get_workflow_info()
        return WorkflowInfo(**info)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error getting workflow info: {str(e)}")

@app.post("/api/workflow/execute", response_model=WorkflowResponse)
async def execute_workflow(request: WorkflowRequest, background_tasks: BackgroundTasks):
    """Execute workflow with enhanced error handling and tracking."""
    execution_id = str(uuid.uuid4())
    session_id = request.session_id or str(uuid.uuid4())
    start_time = datetime.now()
    
    # Store execution start
    EXECUTIONS[execution_id] = {
        "status": "running",
        "start_time": start_time.isoformat(),
        "session_id": session_id,
        "input": request.input[:100] + "..." if len(request.input) > 100 else request.input
    }
    
    try:
        # Validate input
        if not request.input or not request.input.strip():
            raise ValueError("Input cannot be empty")
        
        if not workflow_engine:
            raise RuntimeError("Workflow engine not initialized")
        
        logger.info(f"Executing workflow - ID: {execution_id}, Session: {session_id}")
        
        # Execute workflow with session ID
        result = workflow_engine.execute_workflow(request.input, session_id)
        
        execution_time = (datetime.now() - start_time).total_seconds()
        
        # Update execution tracking
        EXECUTIONS[execution_id].update({
            "status": "completed",
            "end_time": datetime.now().isoformat(),
            "execution_time": execution_time,
            "result_type": result.get("type", "unknown")
        })
        
        # Schedule cleanup
        background_tasks.add_task(cleanup_old_executions)
        
        # Create response
        return WorkflowResponse(
            execution_id=execution_id,
            session_id=session_id,
            status="completed" if result.get("type") != "error" else "failed",
            result=result,
            error=result.get("error") if result.get("type") == "error" else None,
            timestamp=datetime.now().isoformat(),
            execution_time=execution_time,
            nodes_executed=result.get("nodes_executed"),
            metadata=result.get("metadata")
        )
        
    except Exception as e:
        execution_time = (datetime.now() - start_time).total_seconds()
        error_msg = str(e)
        
        # Update execution tracking
        EXECUTIONS[execution_id].update({
            "status": "failed",
            "end_time": datetime.now().isoformat(),
            "execution_time": execution_time,
            "error": error_msg
        })
        
        logger.error(f"Workflow execution failed (ID: {execution_id}): {error_msg}")
        import traceback
        logger.error(traceback.format_exc())
        
        return WorkflowResponse(
            execution_id=execution_id,
            session_id=session_id,
            status="failed",
            result=None,
            error=error_msg,
            timestamp=datetime.now().isoformat(),
            execution_time=execution_time
        )

@app.get("/api/workflow/executions/{execution_id}")
async def get_execution_status(execution_id: str):
    """Get execution status by ID."""
    if execution_id not in EXECUTIONS:
        raise HTTPException(status_code=404, detail="Execution not found")
    
    return EXECUTIONS[execution_id]

@app.get("/api/workflow/executions")
async def list_recent_executions(limit: int = 50):
    """List recent workflow executions."""
    recent_executions = dict(list(EXECUTIONS.items())[-limit:])
    return {
        "executions": recent_executions,
        "total": len(EXECUTIONS),
        "limit": limit
    }

# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error(f"Unhandled exception: {str(exc)}")
    import traceback
    logger.error(traceback.format_exc())
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc),
            "timestamp": datetime.now().isoformat()
        }
    )

# Startup event
@app.on_event("startup")
async def startup_event():
    """Application startup event."""
    logger.info(" KAI-Fusion Advanced Workflow Runtime starting up")
    logger.info(f"   - Workflow loaded: {workflow_loaded}")
    logger.info(f"   - Environment: {os.getenv('ENVIRONMENT', 'development')}")
    logger.info(f"   - Port: {os.getenv('API_PORT', '8000')}")
    
    if workflow_engine:
        workflow_info = workflow_engine.get_workflow_info()
        logger.info(f"   - Workflow nodes: {workflow_info['nodes']}")
        logger.info(f"   - Node types: {', '.join(workflow_info['node_types'])}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown event."""
    logger.info("🛑 KAI-Fusion Advanced Workflow Runtime shutting down")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("API_PORT", "8000"))
    host = os.getenv("API_HOST", "0.0.0.0")
    
    logger.info(f"Starting server on {host}:{port}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
        access_log=True
    )
'''

def create_dockerfile() -> str:
    """Create optimized Dockerfile."""
    return '''FROM python:3.11-slim

WORKDIR /app

ENV PYTHONIOENCODING=utf-8
ENV LANG=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

RUN mkdir -p /app/logs /app/memory

HEALTHCHECK --interval=30s --timeout=10s --retries=3 CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
'''