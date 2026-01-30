"""
KAI-Fusion Enhanced Performance Monitoring System
================================================

Advanced performance monitoring with metrics collection, analysis, and alerting.
"""

from typing import Dict, Any, List, Optional, Callable, NamedTuple
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
import threading
import time
import logging
import statistics
import psutil
import os
from enum import Enum

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types of performance metrics."""
    EXECUTION_TIME = "execution_time"
    MEMORY_USAGE = "memory_usage"
    CONNECTION_RESOLUTION = "connection_resolution"
    ERROR_RATE = "error_rate"
    THROUGHPUT = "throughput"
    LATENCY = "latency"


@dataclass
class PerformanceMetric:
    """Individual performance metric."""
    metric_type: MetricType
    name: str
    value: float
    unit: str
    timestamp: datetime
    session_id: Optional[str] = None
    node_id: Optional[str] = None
    workflow_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecutionMetrics:
    """Comprehensive node execution metrics."""
    node_id: str
    node_type: str
    execution_count: int = 0
    total_execution_time: float = 0.0
    min_execution_time: float = float('inf')
    max_execution_time: float = 0.0
    avg_execution_time: float = 0.0
    error_count: int = 0
    success_count: int = 0
    last_execution: Optional[datetime] = None
    memory_usage_mb: float = 0.0
    recent_executions: deque = field(default_factory=lambda: deque(maxlen=100))


@dataclass
class WorkflowMetrics:
    """Comprehensive workflow metrics."""
    workflow_id: str
    session_id: str
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration: float = 0.0
    node_count: int = 0
    connection_count: int = 0
    success: bool = False
    error_message: Optional[str] = None
    node_metrics: Dict[str, NodeExecutionMetrics] = field(default_factory=dict)
    memory_peak_mb: float = 0.0
    connection_resolution_time: float = 0.0


class PerformanceMonitor:
    """
    Enterprise-grade performance monitoring system.
    
    Features:
    - Real-time performance metrics collection
    - Node execution time tracking
    - Memory usage monitoring
    - Connection resolution performance
    - Error rate tracking and alerting
    - Workflow performance analytics
    - System resource monitoring
    """
    
    def __init__(self, max_metrics_history: int = 10000):
        self.max_metrics_history = max_metrics_history
        self._metrics_history: deque = deque(maxlen=max_metrics_history)
        self._node_metrics: Dict[str, NodeExecutionMetrics] = {}
        self._workflow_metrics: Dict[str, WorkflowMetrics] = {}
        self._active_executions: Dict[str, Dict[str, Any]] = {}
        self._alert_callbacks: List[Callable[[str, Dict[str, Any]], None]] = []
        self._lock = threading.RLock()
        
        # Performance thresholds
        self.thresholds = {
            "node_execution_time_warning": 5.0,  # 5 seconds
            "node_execution_time_critical": 30.0,  # 30 seconds
            "memory_usage_warning": 500.0,  # 500MB
            "memory_usage_critical": 1000.0,  # 1GB
            "error_rate_warning": 0.1,  # 10%
            "error_rate_critical": 0.25,  # 25%
        }

        logger.info("PerformanceMonitor initialized")

    def start_workflow_monitoring(
        self, 
        workflow_id: str, 
        session_id: str, 
        node_count: int = 0,
        connection_count: int = 0
    ) -> str:
        """Start monitoring a workflow execution."""
        with self._lock:
            workflow_metrics = WorkflowMetrics(
                workflow_id=workflow_id,
                session_id=session_id,
                start_time=datetime.now(),
                node_count=node_count,
                connection_count=connection_count
            )
            
            self._workflow_metrics[session_id] = workflow_metrics
            
            logger.info(f"Started workflow monitoring: {workflow_id} (session: {session_id})")
            return session_id
    
    def end_workflow_monitoring(
        self, 
        session_id: str, 
        success: bool = True, 
        error_message: Optional[str] = None
    ):
        """End workflow monitoring and calculate final metrics."""
        with self._lock:
            if session_id not in self._workflow_metrics:
                logger.warning(f"Workflow metrics not found for session: {session_id}")
                return
            
            workflow_metrics = self._workflow_metrics[session_id]
            workflow_metrics.end_time = datetime.now()
            workflow_metrics.total_duration = (
                workflow_metrics.end_time - workflow_metrics.start_time
            ).total_seconds()
            workflow_metrics.success = success
            workflow_metrics.error_message = error_message
            
            # Record workflow completion metric
            self._record_metric(
                MetricType.EXECUTION_TIME,
                "workflow_duration",
                workflow_metrics.total_duration,
                "seconds",
                session_id=session_id,
                workflow_id=workflow_metrics.workflow_id,
                metadata={
                    "success": success,
                    "node_count": workflow_metrics.node_count,
                    "connection_count": workflow_metrics.connection_count
                }
            )
            
            logger.info(f"Workflow completed: {workflow_metrics.workflow_id} "
                       f"({workflow_metrics.total_duration:.3f}s, success: {success})")
    
    def start_node_execution(
        self, 
        node_id: str, 
        node_type: str, 
        session_id: Optional[str] = None
    ) -> str:
        """Start monitoring node execution."""
        execution_id = f"{node_id}_{int(time.time() * 1000)}"
        
        with self._lock:
            # Initialize node metrics if not exists
            if node_id not in self._node_metrics:
                self._node_metrics[node_id] = NodeExecutionMetrics(
                    node_id=node_id,
                    node_type=node_type
                )
            
            # Record execution start
            self._active_executions[execution_id] = {
                "node_id": node_id,
                "node_type": node_type,
                "session_id": session_id,
                "start_time": time.time(),
                "start_memory": self._get_memory_usage()
            }

            logger.debug(f"Started node execution: {node_id}")
            return execution_id
    
    def end_node_execution(
        self, 
        execution_id: str, 
        success: bool = True, 
        error_message: Optional[str] = None,
        output_size: Optional[int] = None
    ):
        """End node execution monitoring and record metrics."""
        with self._lock:
            if execution_id not in self._active_executions:
                logger.warning(f"Execution not found: {execution_id}")
                return
            
            execution_info = self._active_executions[execution_id]
            end_time = time.time()
            execution_time = end_time - execution_info["start_time"]
            end_memory = self._get_memory_usage()
            memory_delta = end_memory - execution_info["start_memory"]
            
            node_id = execution_info["node_id"]
            node_type = execution_info["node_type"]
            session_id = execution_info["session_id"]
            
            # Update node metrics
            node_metrics = self._node_metrics[node_id]
            node_metrics.execution_count += 1
            node_metrics.total_execution_time += execution_time
            node_metrics.min_execution_time = min(node_metrics.min_execution_time, execution_time)
            node_metrics.max_execution_time = max(node_metrics.max_execution_time, execution_time)
            node_metrics.avg_execution_time = (
                node_metrics.total_execution_time / node_metrics.execution_count
            )
            node_metrics.last_execution = datetime.now()
            node_metrics.memory_usage_mb = max(node_metrics.memory_usage_mb, end_memory)
            
            if success:
                node_metrics.success_count += 1
            else:
                node_metrics.error_count += 1
            
            # Add to recent executions
            node_metrics.recent_executions.append({
                "timestamp": datetime.now(),
                "execution_time": execution_time,
                "success": success,
                "memory_delta": memory_delta,
                "output_size": output_size
            })
            
            # Record metrics
            self._record_metric(
                MetricType.EXECUTION_TIME,
                f"node_execution_{node_type}",
                execution_time,
                "seconds",
                session_id=session_id,
                node_id=node_id,
                metadata={
                    "success": success,
                    "error_message": error_message,
                    "memory_delta_mb": memory_delta,
                    "output_size": output_size
                }
            )
            
            # Check for performance alerts
            self._check_performance_alerts(node_id, execution_time, success)
            
            # Clean up
            del self._active_executions[execution_id]
            
            logger.debug(f"Node execution completed: {node_id} "
                        f"({execution_time:.3f}s, success: {success})")
    
    def record_connection_resolution_time(
        self, 
        node_count: int, 
        connection_count: int, 
        resolution_time: float,
        session_id: Optional[str] = None
    ):
        """Record connection resolution performance."""
        self._record_metric(
            MetricType.CONNECTION_RESOLUTION,
            "connection_resolution",
            resolution_time,
            "seconds",
            session_id=session_id,
            metadata={
                "node_count": node_count,
                "connection_count": connection_count,
                "connections_per_second": connection_count / resolution_time if resolution_time > 0 else 0
            }
        )
        
        # Update workflow metrics if available
        if session_id and session_id in self._workflow_metrics:
            self._workflow_metrics[session_id].connection_resolution_time = resolution_time
        
        logger.info(f"📊 Connection resolution: {connection_count} connections "
                   f"in {resolution_time:.3f}s ({connection_count/resolution_time:.1f}/s)")
    
    def record_memory_usage(
        self, 
        usage_mb: float, 
        session_id: Optional[str] = None,
        component: str = "system"
    ):
        """Record memory usage metric."""
        self._record_metric(
            MetricType.MEMORY_USAGE,
            f"memory_usage_{component}",
            usage_mb,
            "MB",
            session_id=session_id,
            metadata={"component": component}
        )
        
        # Update workflow peak memory if available
        if session_id and session_id in self._workflow_metrics:
            workflow_metrics = self._workflow_metrics[session_id]
            workflow_metrics.memory_peak_mb = max(workflow_metrics.memory_peak_mb, usage_mb)
        
        # Check memory alerts
        if usage_mb > self.thresholds["memory_usage_critical"]:
            self._trigger_alert("memory_critical", {
                "usage_mb": usage_mb,
                "session_id": session_id,
                "component": component
            })
        elif usage_mb > self.thresholds["memory_usage_warning"]:
            self._trigger_alert("memory_warning", {
                "usage_mb": usage_mb,
                "session_id": session_id,
                "component": component
            })
    
    def _record_metric(
        self,
        metric_type: MetricType,
        name: str,
        value: float,
        unit: str,
        session_id: Optional[str] = None,
        node_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        """Record a performance metric."""
        metric = PerformanceMetric(
            metric_type=metric_type,
            name=name,
            value=value,
            unit=unit,
            timestamp=datetime.now(),
            session_id=session_id,
            node_id=node_id,
            workflow_id=workflow_id,
            metadata=metadata or {}
        )
        
        self._metrics_history.append(metric)
    
    def _get_memory_usage(self) -> float:
        """Get current memory usage in MB."""
        try:
            process = psutil.Process(os.getpid())
            return process.memory_info().rss / (1024 * 1024)  # Convert to MB
        except Exception:
            return 0.0
    
    def _check_performance_alerts(self, node_id: str, execution_time: float, success: bool):
        """Check for performance alerts and trigger if necessary."""
        # Execution time alerts
        if execution_time > self.thresholds["node_execution_time_critical"]:
            self._trigger_alert("execution_time_critical", {
                "node_id": node_id,
                "execution_time": execution_time,
                "threshold": self.thresholds["node_execution_time_critical"]
            })
        elif execution_time > self.thresholds["node_execution_time_warning"]:
            self._trigger_alert("execution_time_warning", {
                "node_id": node_id,
                "execution_time": execution_time,
                "threshold": self.thresholds["node_execution_time_warning"]
            })
        
        # Error rate alerts
        if node_id in self._node_metrics:
            node_metrics = self._node_metrics[node_id]
            if node_metrics.execution_count >= 10:  # Only check after sufficient executions
                error_rate = node_metrics.error_count / node_metrics.execution_count
                
                if error_rate > self.thresholds["error_rate_critical"]:
                    self._trigger_alert("error_rate_critical", {
                        "node_id": node_id,
                        "error_rate": error_rate,
                        "error_count": node_metrics.error_count,
                        "total_executions": node_metrics.execution_count
                    })
                elif error_rate > self.thresholds["error_rate_warning"]:
                    self._trigger_alert("error_rate_warning", {
                        "node_id": node_id,
                        "error_rate": error_rate,
                        "error_count": node_metrics.error_count,
                        "total_executions": node_metrics.execution_count
                    })
    
    def _trigger_alert(self, alert_type: str, data: Dict[str, Any]):
        """Trigger performance alert."""
        logger.warning(f"🚨 Performance Alert [{alert_type}]: {data}")
        
        for callback in self._alert_callbacks:
            try:
                callback(alert_type, data)
            except Exception as e:
                logger.error(f"Alert callback failed: {e}")
    
    def register_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]):
        """Register callback for performance alerts."""
        self._alert_callbacks.append(callback)
    
    def get_node_statistics(self, node_id: Optional[str] = None) -> Dict[str, Any]:
        """Get node performance statistics."""
        with self._lock:
            if node_id:
                if node_id not in self._node_metrics:
                    return {}
                
                metrics = self._node_metrics[node_id]
                return {
                    "node_id": metrics.node_id,
                    "node_type": metrics.node_type,
                    "execution_count": metrics.execution_count,
                    "success_rate": metrics.success_count / metrics.execution_count if metrics.execution_count > 0 else 0,
                    "error_rate": metrics.error_count / metrics.execution_count if metrics.execution_count > 0 else 0,
                    "avg_execution_time": metrics.avg_execution_time,
                    "min_execution_time": metrics.min_execution_time if metrics.min_execution_time != float('inf') else 0,
                    "max_execution_time": metrics.max_execution_time,
                    "total_execution_time": metrics.total_execution_time,
                    "memory_usage_mb": metrics.memory_usage_mb,
                    "last_execution": metrics.last_execution.isoformat() if metrics.last_execution else None
                }
            else:
                # Return summary for all nodes
                return {
                    "total_nodes": len(self._node_metrics),
                    "total_executions": sum(m.execution_count for m in self._node_metrics.values()),
                    "total_errors": sum(m.error_count for m in self._node_metrics.values()),
                    "nodes": {
                        node_id: self.get_node_statistics(node_id) 
                        for node_id in self._node_metrics.keys()
                    }
                }
    
    def get_workflow_statistics(self, session_id: Optional[str] = None) -> Dict[str, Any]:
        """Get workflow performance statistics."""
        with self._lock:
            if session_id:
                if session_id not in self._workflow_metrics:
                    return {}
                
                metrics = self._workflow_metrics[session_id]
                return {
                    "workflow_id": metrics.workflow_id,
                    "session_id": metrics.session_id,
                    "start_time": metrics.start_time.isoformat(),
                    "end_time": metrics.end_time.isoformat() if metrics.end_time else None,
                    "total_duration": metrics.total_duration,
                    "node_count": metrics.node_count,
                    "connection_count": metrics.connection_count,
                    "success": metrics.success,
                    "error_message": metrics.error_message,
                    "memory_peak_mb": metrics.memory_peak_mb,
                    "connection_resolution_time": metrics.connection_resolution_time
                }
            else:
                # Return summary for all workflows
                completed_workflows = [m for m in self._workflow_metrics.values() if m.end_time]
                
                if completed_workflows:
                    avg_duration = statistics.mean(m.total_duration for m in completed_workflows)
                    success_rate = sum(1 for m in completed_workflows if m.success) / len(completed_workflows)
                else:
                    avg_duration = 0
                    success_rate = 0
                
                return {
                    "total_workflows": len(self._workflow_metrics),
                    "completed_workflows": len(completed_workflows),
                    "active_workflows": len(self._workflow_metrics) - len(completed_workflows),
                    "average_duration": avg_duration,
                    "success_rate": success_rate,
                    "workflows": {
                        session_id: self.get_workflow_statistics(session_id)
                        for session_id in self._workflow_metrics.keys()
                    }
                }
    
    def get_system_metrics(self) -> Dict[str, Any]:
        """Get current system performance metrics."""
        try:
            # CPU usage
            cpu_percent = psutil.cpu_percent(interval=1)
            
            # Memory usage
            memory = psutil.virtual_memory()
            
            # Process-specific metrics
            process = psutil.Process(os.getpid())
            process_memory = process.memory_info()
            
            return {
                "system": {
                    "cpu_percent": cpu_percent,
                    "memory_total_gb": memory.total / (1024**3),
                    "memory_available_gb": memory.available / (1024**3),
                    "memory_percent": memory.percent,
                    "memory_used_gb": memory.used / (1024**3)
                },
                "process": {
                    "memory_rss_mb": process_memory.rss / (1024**2),
                    "memory_vms_mb": process_memory.vms / (1024**2),
                    "cpu_percent": process.cpu_percent(),
                    "num_threads": process.num_threads(),
                    "create_time": datetime.fromtimestamp(process.create_time()).isoformat()
                }
            }
        except Exception as e:
            logger.error(f"Failed to get system metrics: {e}")
            return {}
    
    def export_metrics(self, format: str = "json") -> Dict[str, Any]:
        """Export all performance metrics."""
        with self._lock:
            return {
                "export_time": datetime.now().isoformat(),
                "metrics_count": len(self._metrics_history),
                "node_statistics": self.get_node_statistics(),
                "workflow_statistics": self.get_workflow_statistics(),
                "system_metrics": self.get_system_metrics(),
                "thresholds": self.thresholds
            }


# Global performance monitor instance
_performance_monitor: Optional[PerformanceMonitor] = None


def get_performance_monitor() -> PerformanceMonitor:
    """Get the global performance monitor instance."""
    global _performance_monitor
    if _performance_monitor is None:
        _performance_monitor = PerformanceMonitor()
    return _performance_monitor