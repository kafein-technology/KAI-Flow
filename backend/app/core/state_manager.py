"""
KAI-Flow Enhanced State Management System
==========================================

Advanced state management with cleanup, monitoring, and lifecycle management.
"""

from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
import logging
import weakref
import gc
from collections import defaultdict
import psutil
import os

from .state import FlowState

logger = logging.getLogger(__name__)


@dataclass
class StateMetrics:
    """State usage metrics."""
    session_id: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    memory_size_bytes: int = 0
    node_count: int = 0
    variable_count: int = 0
    message_count: int = 0
    cleanup_count: int = 0


@dataclass
class CleanupPolicy:
    """State cleanup policy configuration."""
    max_session_age_minutes: int = 60  # 1 hour
    max_inactive_minutes: int = 30     # 30 minutes
    max_memory_mb: int = 100           # 100MB per session
    max_total_sessions: int = 1000     # Maximum concurrent sessions
    cleanup_interval_seconds: int = 300  # 5 minutes
    force_cleanup_threshold: float = 0.8  # 80% memory usage


class StateManager:
    """
    Enterprise-grade state management with automatic cleanup.
    
    Features:
    - Automatic state cleanup based on policies
    - Memory usage monitoring and optimization
    - Session lifecycle management
    - Garbage collection optimization
    - Performance metrics and analytics
    """
    
    def __init__(self, cleanup_policy: Optional[CleanupPolicy] = None):
        self.cleanup_policy = cleanup_policy or CleanupPolicy()
        self._states: Dict[str, FlowState] = {}
        self._state_metrics: Dict[str, StateMetrics] = {}
        self._cleanup_callbacks: List[Callable[[str], None]] = []
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._total_cleanups = 0
        self._memory_warnings = 0
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
        logger.info(f"StateManager initialized with policy: {self.cleanup_policy}")
    
    def create_state(
        self, 
        session_id: str, 
        user_id: Optional[str] = None,
        workflow_id: Optional[str] = None,
        **kwargs
    ) -> FlowState:
        """Create a new managed state."""
        with self._lock:
            # Check if state already exists
            if session_id in self._states:
                logger.warning(f"State {session_id} already exists, returning existing")
                self._update_access_metrics(session_id)
                return self._states[session_id]
            
            # Check session limits
            if len(self._states) >= self.cleanup_policy.max_total_sessions:
                logger.warning(f"Session limit reached, forcing cleanup")
                self._force_cleanup()
            
            # Create new state
            state = FlowState(
                session_id=session_id,
                user_id=user_id,
                workflow_id=workflow_id,
                started_at=datetime.now(),
                **kwargs
            )
            
            # Store state and metrics
            self._states[session_id] = state
            self._state_metrics[session_id] = StateMetrics(
                session_id=session_id,
                created_at=datetime.now(),
                last_accessed=datetime.now()
            )
            
            logger.info(f"Created managed state: {session_id}")
            return state
    
    def get_state(self, session_id: str) -> Optional[FlowState]:
        """Get existing state with access tracking."""
        with self._lock:
            if session_id not in self._states:
                return None
            
            self._update_access_metrics(session_id)
            return self._states[session_id]
    
    def update_state(self, session_id: str, **updates) -> bool:
        """Update state with monitoring."""
        with self._lock:
            if session_id not in self._states:
                return False
            
            state = self._states[session_id]
            
            # Apply updates
            for key, value in updates.items():
                if hasattr(state, key):
                    setattr(state, key, value)
            
            # Update metrics
            self._update_state_metrics(session_id)
            self._update_access_metrics(session_id)
            
            return True
    
    def cleanup_state(self, session_id: str, reason: str = "manual") -> bool:
        """Clean up a specific state."""
        with self._lock:
            if session_id not in self._states:
                return False
            
            # Get state for cleanup callbacks
            state = self._states[session_id]
            
            # Call cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback(session_id)
                except Exception as e:
                    logger.error(f"Cleanup callback failed for {session_id}: {e}")
            
            # Remove state and metrics
            del self._states[session_id]
            if session_id in self._state_metrics:
                del self._state_metrics[session_id]
            
            self._total_cleanups += 1
            logger.info(f"Cleaned up state {session_id} (reason: {reason})")
            
            return True
    
    def register_cleanup_callback(self, callback: Callable[[str], None]):
        """Register callback to be called before state cleanup."""
        self._cleanup_callbacks.append(callback)
    
    def _update_access_metrics(self, session_id: str):
        """Update access metrics for a session."""
        if session_id in self._state_metrics:
            metrics = self._state_metrics[session_id]
            metrics.last_accessed = datetime.now()
            metrics.access_count += 1
    
    def _update_state_metrics(self, session_id: str):
        """Update comprehensive state metrics."""
        if session_id not in self._states or session_id not in self._state_metrics:
            return
        
        state = self._states[session_id]
        metrics = self._state_metrics[session_id]
        
        # Calculate memory size (approximate)
        try:
            import sys
            memory_size = sys.getsizeof(state)
            memory_size += sum(sys.getsizeof(v) for v in state.variables.values())
            memory_size += sum(sys.getsizeof(v) for v in state.node_outputs.values())
            memory_size += sum(sys.getsizeof(msg) for msg in state.chat_history)
            
            metrics.memory_size_bytes = memory_size
        except Exception as e:
            logger.warning(f"Failed to calculate memory size for {session_id}: {e}")
        
        # Update counts
        metrics.node_count = len(state.executed_nodes)
        metrics.variable_count = len(state.variables)
        metrics.message_count = len(state.chat_history)
    
    def _start_cleanup_thread(self):
        """Start the background cleanup thread."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            name="StateManager-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()
        logger.info("Cleanup thread started")
    
    def _cleanup_worker(self):
        """Background cleanup worker."""
        while not self._shutdown_event.is_set():
            try:
                self._perform_cleanup()
                
                # Wait for next cleanup cycle
                self._shutdown_event.wait(self.cleanup_policy.cleanup_interval_seconds)
                
            except Exception as e:
                logger.error(f"Cleanup worker error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def _perform_cleanup(self):
        """Perform automatic cleanup based on policies."""
        with self._lock:
            if not self._states:
                return
            
            now = datetime.now()
            cleanup_candidates = []
            
            # Check each session against cleanup policies
            for session_id, metrics in self._state_metrics.items():
                reasons = []
                
                # Age-based cleanup
                age_minutes = (now - metrics.created_at).total_seconds() / 60
                if age_minutes > self.cleanup_policy.max_session_age_minutes:
                    reasons.append(f"age ({age_minutes:.1f}m)")
                
                # Inactivity-based cleanup
                inactive_minutes = (now - metrics.last_accessed).total_seconds() / 60
                if inactive_minutes > self.cleanup_policy.max_inactive_minutes:
                    reasons.append(f"inactive ({inactive_minutes:.1f}m)")
                
                # Memory-based cleanup
                memory_mb = metrics.memory_size_bytes / (1024 * 1024)
                if memory_mb > self.cleanup_policy.max_memory_mb:
                    reasons.append(f"memory ({memory_mb:.1f}MB)")
                
                if reasons:
                    cleanup_candidates.append((session_id, reasons))
            
            # Perform cleanups
            cleaned_count = 0
            for session_id, reasons in cleanup_candidates:
                reason_str = ", ".join(reasons)
                if self.cleanup_state(session_id, f"policy: {reason_str}"):
                    cleaned_count += 1
            
            if cleaned_count > 0:
                logger.info(f"Automatic cleanup: {cleaned_count} sessions")
            
            # Check system memory pressure
            self._check_memory_pressure()
    
    def _force_cleanup(self):
        """Force cleanup of oldest sessions."""
        with self._lock:
            if not self._state_metrics:
                return
            
            # Sort by last accessed time (oldest first)
            sorted_sessions = sorted(
                self._state_metrics.items(),
                key=lambda x: x[1].last_accessed
            )
            
            # Clean up oldest 25% of sessions
            cleanup_count = max(1, len(sorted_sessions) // 4)
            
            for session_id, _ in sorted_sessions[:cleanup_count]:
                self.cleanup_state(session_id, "force cleanup")
            
            logger.warning(f"Force cleanup: {cleanup_count} sessions")
    
    def _check_memory_pressure(self):
        """Check system memory pressure and take action."""
        try:
            # Get system memory info
            memory = psutil.virtual_memory()
            memory_percent = memory.percent / 100.0
            
            if memory_percent > self.cleanup_policy.force_cleanup_threshold:
                self._memory_warnings += 1
                logger.warning(f"High memory usage: {memory_percent:.1%}")

                # Force cleanup if memory pressure is high
                if memory_percent > 0.9:  # 90% memory usage
                    logger.error(f"Critical memory usage: {memory_percent:.1%}, forcing cleanup")
                    self._force_cleanup()
                    
                    # Force garbage collection
                    gc.collect()
                    
        except Exception as e:
            logger.error(f"Memory pressure check failed: {e}")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive state management statistics."""
        with self._lock:
            total_memory = sum(
                metrics.memory_size_bytes 
                for metrics in self._state_metrics.values()
            )
            
            total_nodes = sum(
                metrics.node_count 
                for metrics in self._state_metrics.values()
            )
            
            total_variables = sum(
                metrics.variable_count 
                for metrics in self._state_metrics.values()
            )
            
            # Calculate average session age
            now = datetime.now()
            ages = [
                (now - metrics.created_at).total_seconds() / 60
                for metrics in self._state_metrics.values()
            ]
            avg_age = sum(ages) / len(ages) if ages else 0
            
            return {
                "active_sessions": len(self._states),
                "total_memory_mb": total_memory / (1024 * 1024),
                "total_nodes": total_nodes,
                "total_variables": total_variables,
                "average_session_age_minutes": avg_age,
                "total_cleanups": self._total_cleanups,
                "memory_warnings": self._memory_warnings,
                "cleanup_policy": {
                    "max_session_age_minutes": self.cleanup_policy.max_session_age_minutes,
                    "max_inactive_minutes": self.cleanup_policy.max_inactive_minutes,
                    "max_memory_mb": self.cleanup_policy.max_memory_mb,
                    "max_total_sessions": self.cleanup_policy.max_total_sessions
                }
            }
    
    def optimize_memory(self):
        """Perform memory optimization."""
        with self._lock:
            logger.info("Starting memory optimization")
            
            # Update all state metrics
            for session_id in self._states.keys():
                self._update_state_metrics(session_id)
            
            # Force garbage collection
            collected = gc.collect()
            logger.info(f"Garbage collection: {collected} objects collected")
            
            # Log memory statistics
            stats = self.get_statistics()
            logger.info(f"Memory optimization complete: {stats['total_memory_mb']:.1f}MB across {stats['active_sessions']} sessions")
    
    def shutdown(self):
        """Shutdown the state manager."""
        logger.info("Shutting down StateManager")

        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for cleanup thread
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # Clean up all states
        with self._lock:
            session_ids = list(self._states.keys())
            for session_id in session_ids:
                self.cleanup_state(session_id, "shutdown")
        
        logger.info("StateManager shutdown complete")


# Global state manager instance
_state_manager: Optional[StateManager] = None


def get_state_manager() -> StateManager:
    """Get the global state manager instance."""
    global _state_manager
    if _state_manager is None:
        _state_manager = StateManager()
    return _state_manager


def create_managed_state(
    session_id: str,
    user_id: Optional[str] = None,
    workflow_id: Optional[str] = None,
    **kwargs
) -> FlowState:
    """Create a managed state using the global state manager."""
    return get_state_manager().create_state(session_id, user_id, workflow_id, **kwargs)


def get_managed_state(session_id: str) -> Optional[FlowState]:
    """Get a managed state using the global state manager."""
    return get_state_manager().get_state(session_id)


def cleanup_managed_state(session_id: str) -> bool:
    """Clean up a managed state using the global state manager."""
    return get_state_manager().cleanup_state(session_id)