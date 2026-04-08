"""
KAI-Flow Enhanced Memory Management System
===========================================

Advanced memory management for conversation nodes with cleanup and monitoring.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
import threading
import time
import logging
import weakref
from collections import defaultdict
import sys

from langchain.memory import ConversationBufferMemory
from langchain_core.runnables import Runnable

logger = logging.getLogger(__name__)


@dataclass
class MemoryMetrics:
    """Memory usage metrics for a session."""
    session_id: str
    created_at: datetime
    last_accessed: datetime
    access_count: int = 0
    message_count: int = 0
    memory_size_bytes: int = 0
    node_type: str = "BufferMemory"


@dataclass
class MemoryCleanupPolicy:
    """Memory cleanup policy configuration."""
    max_session_age_hours: int = 24      # 24 hours
    max_inactive_hours: int = 6          # 6 hours
    max_messages_per_session: int = 1000 # 1000 messages
    max_memory_mb_per_session: int = 50  # 50MB per session
    cleanup_interval_minutes: int = 15   # 15 minutes
    max_total_sessions: int = 500        # Maximum concurrent sessions


class EnhancedMemoryManager:
    """
    Enterprise-grade memory management for conversation nodes.
    
    Features:
    - Automatic memory cleanup based on policies
    - Memory usage monitoring and optimization
    - Session lifecycle management
    - Thread-safe operations
    - Performance metrics and analytics
    """
    
    def __init__(self, cleanup_policy: Optional[MemoryCleanupPolicy] = None):
        self.cleanup_policy = cleanup_policy or MemoryCleanupPolicy()
        self._session_memories: Dict[str, ConversationBufferMemory] = {}
        self._memory_metrics: Dict[str, MemoryMetrics] = {}
        self._cleanup_callbacks: List[Callable[[str], None]] = []
        self._lock = threading.RLock()
        self._cleanup_thread: Optional[threading.Thread] = None
        self._shutdown_event = threading.Event()
        self._total_cleanups = 0
        self._memory_warnings = 0
        
        # Start cleanup thread
        self._start_cleanup_thread()
        
        logger.info(f"EnhancedMemoryManager initialized with policy: {self.cleanup_policy}")
    
    def get_or_create_memory(
        self,
        session_id: str,
        memory_key: str = "memory",
        return_messages: bool = True,
        input_key: str = "input",
        output_key: str = "output",
        node_type: str = "BufferMemory"
    ) -> ConversationBufferMemory:
        """Get existing memory or create new one with tracking."""
        with self._lock:
            # Check session limits
            if (session_id not in self._session_memories and 
                len(self._session_memories) >= self.cleanup_policy.max_total_sessions):
                logger.warning(f"Memory session limit reached, forcing cleanup")
                self._force_cleanup()
            
            # Get or create memory
            if session_id not in self._session_memories:
                # Create new memory
                memory = ConversationBufferMemory(
                    memory_key=memory_key,
                    return_messages=return_messages,
                    input_key=input_key,
                    output_key=output_key
                )
                
                self._session_memories[session_id] = memory
                self._memory_metrics[session_id] = MemoryMetrics(
                    session_id=session_id,
                    created_at=datetime.now(),
                    last_accessed=datetime.now(),
                    node_type=node_type
                )
                
                logger.info(f"Created new memory session: {session_id}")
            else:
                memory = self._session_memories[session_id]
                logger.info(f"Reusing existing memory session: {session_id}")

            # Update access metrics
            self._update_access_metrics(session_id)
            
            return memory
    
    def cleanup_memory(self, session_id: str, reason: str = "manual") -> bool:
        """Clean up memory for a specific session."""
        with self._lock:
            if session_id not in self._session_memories:
                return False
            
            # Call cleanup callbacks
            for callback in self._cleanup_callbacks:
                try:
                    callback(session_id)
                except Exception as e:
                    logger.error(f"Memory cleanup callback failed for {session_id}: {e}")
            
            # Remove memory and metrics
            del self._session_memories[session_id]
            if session_id in self._memory_metrics:
                del self._memory_metrics[session_id]
            
            self._total_cleanups += 1
            logger.info(f"Cleaned up memory session {session_id} (reason: {reason})")
            
            return True
    
    def register_cleanup_callback(self, callback: Callable[[str], None]):
        """Register callback to be called before memory cleanup."""
        self._cleanup_callbacks.append(callback)
    
    def _update_access_metrics(self, session_id: str):
        """Update access metrics for a session."""
        if session_id in self._memory_metrics:
            metrics = self._memory_metrics[session_id]
            metrics.last_accessed = datetime.now()
            metrics.access_count += 1
            
            # Update memory-specific metrics
            if session_id in self._session_memories:
                memory = self._session_memories[session_id]
                
                # Count messages
                if hasattr(memory, 'chat_memory') and hasattr(memory.chat_memory, 'messages'):
                    metrics.message_count = len(memory.chat_memory.messages)
                
                # Estimate memory size
                try:
                    memory_size = sys.getsizeof(memory)
                    if hasattr(memory, 'chat_memory') and hasattr(memory.chat_memory, 'messages'):
                        memory_size += sum(sys.getsizeof(msg) for msg in memory.chat_memory.messages)
                    metrics.memory_size_bytes = memory_size
                except Exception as e:
                    logger.warning(f"Failed to calculate memory size for {session_id}: {e}")
    
    def _start_cleanup_thread(self):
        """Start the background cleanup thread."""
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            return
        
        self._cleanup_thread = threading.Thread(
            target=self._cleanup_worker,
            name="MemoryManager-Cleanup",
            daemon=True
        )
        self._cleanup_thread.start()
        logger.info("Memory cleanup thread started")
    
    def _cleanup_worker(self):
        """Background cleanup worker."""
        while not self._shutdown_event.is_set():
            try:
                self._perform_cleanup()
                
                # Wait for next cleanup cycle
                wait_seconds = self.cleanup_policy.cleanup_interval_minutes * 60
                self._shutdown_event.wait(wait_seconds)
                
            except Exception as e:
                logger.error(f"Memory cleanup worker error: {e}")
                time.sleep(60)  # Wait 1 minute on error
    
    def _perform_cleanup(self):
        """Perform automatic cleanup based on policies."""
        with self._lock:
            if not self._session_memories:
                return
            
            now = datetime.now()
            cleanup_candidates = []
            
            # Check each session against cleanup policies
            for session_id, metrics in self._memory_metrics.items():
                reasons = []
                
                # Age-based cleanup
                age_hours = (now - metrics.created_at).total_seconds() / 3600
                if age_hours > self.cleanup_policy.max_session_age_hours:
                    reasons.append(f"age ({age_hours:.1f}h)")
                
                # Inactivity-based cleanup
                inactive_hours = (now - metrics.last_accessed).total_seconds() / 3600
                if inactive_hours > self.cleanup_policy.max_inactive_hours:
                    reasons.append(f"inactive ({inactive_hours:.1f}h)")
                
                # Message count-based cleanup
                if metrics.message_count > self.cleanup_policy.max_messages_per_session:
                    reasons.append(f"messages ({metrics.message_count})")
                
                # Memory size-based cleanup
                memory_mb = metrics.memory_size_bytes / (1024 * 1024)
                if memory_mb > self.cleanup_policy.max_memory_mb_per_session:
                    reasons.append(f"memory ({memory_mb:.1f}MB)")
                if reasons:
                    cleanup_candidates.append((session_id, reasons))
            # Perform cleanups
            cleaned_count = 0
            for session_id, reasons in cleanup_candidates:
                reason_str = ", ".join(reasons)
                if self.cleanup_memory(session_id, f"policy: {reason_str}"):
                    cleaned_count += 1
            if cleaned_count > 0:
                logger.info(f"Automatic memory cleanup: {cleaned_count} sessions")
    
    def _force_cleanup(self):
        """Force cleanup of oldest memory sessions."""
        with self._lock:
            if not self._memory_metrics:
                return
            
            # Sort by last accessed time (oldest first)
            sorted_sessions = sorted(
                self._memory_metrics.items(),
                key=lambda x: x[1].last_accessed
            )
            
            # Clean up oldest 25% of sessions
            cleanup_count = max(1, len(sorted_sessions) // 4)
            
            for session_id, _ in sorted_sessions[:cleanup_count]:
                self.cleanup_memory(session_id, "force cleanup")
            
            logger.warning(f"Force memory cleanup: {cleanup_count} sessions")
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get comprehensive memory management statistics."""
        with self._lock:
            total_memory = sum(
                metrics.memory_size_bytes 
                for metrics in self._memory_metrics.values()
            )
            
            total_messages = sum(
                metrics.message_count 
                for metrics in self._memory_metrics.values()
            )
            
            # Calculate average session age
            now = datetime.now()
            ages = [
                (now - metrics.created_at).total_seconds() / 3600
                for metrics in self._memory_metrics.values()
            ]
            avg_age = sum(ages) / len(ages) if ages else 0
            
            # Calculate average messages per session
            avg_messages = total_messages / len(self._memory_metrics) if self._memory_metrics else 0
            
            return {
                "active_memory_sessions": len(self._session_memories),
                "total_memory_mb": total_memory / (1024 * 1024),
                "total_messages": total_messages,
                "average_messages_per_session": avg_messages,
                "average_session_age_hours": avg_age,
                "total_cleanups": self._total_cleanups,
                "memory_warnings": self._memory_warnings,
                "cleanup_policy": {
                    "max_session_age_hours": self.cleanup_policy.max_session_age_hours,
                    "max_inactive_hours": self.cleanup_policy.max_inactive_hours,
                    "max_messages_per_session": self.cleanup_policy.max_messages_per_session,
                    "max_memory_mb_per_session": self.cleanup_policy.max_memory_mb_per_session
                }
            }
    
    def optimize_memory(self):
        """Perform memory optimization."""
        with self._lock:
            logger.info("Starting memory optimization")
            
            # Update all memory metrics
            for session_id in self._session_memories.keys():
                self._update_access_metrics(session_id)
            
            # Log memory statistics
            stats = self.get_statistics()
            logger.info(f"Memory optimization complete: {stats['total_memory_mb']:.1f}MB across {stats['active_memory_sessions']} sessions")
    
    def get_session_info(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a specific session."""
        with self._lock:
            if session_id not in self._memory_metrics:
                return None
            
            metrics = self._memory_metrics[session_id]
            memory = self._session_memories.get(session_id)
            
            info = {
                "session_id": session_id,
                "created_at": metrics.created_at.isoformat(),
                "last_accessed": metrics.last_accessed.isoformat(),
                "access_count": metrics.access_count,
                "message_count": metrics.message_count,
                "memory_size_mb": metrics.memory_size_bytes / (1024 * 1024),
                "node_type": metrics.node_type,
                "age_hours": (datetime.now() - metrics.created_at).total_seconds() / 3600,
                "inactive_hours": (datetime.now() - metrics.last_accessed).total_seconds() / 3600
            }
            
            # Add memory-specific info
            if memory and hasattr(memory, 'chat_memory'):
                info["memory_key"] = getattr(memory, 'memory_key', 'memory')
                info["return_messages"] = getattr(memory, 'return_messages', True)
                info["input_key"] = getattr(memory, 'input_key', 'input')
                info["output_key"] = getattr(memory, 'output_key', 'output')
            
            return info
    
    def shutdown(self):
        """Shutdown the memory manager."""
        logger.info("Shutting down EnhancedMemoryManager")

        # Signal shutdown
        self._shutdown_event.set()
        
        # Wait for cleanup thread
        if self._cleanup_thread and self._cleanup_thread.is_alive():
            self._cleanup_thread.join(timeout=5)
        
        # Clean up all memories
        with self._lock:
            session_ids = list(self._session_memories.keys())
            for session_id in session_ids:
                self.cleanup_memory(session_id, "shutdown")
        
        logger.info("EnhancedMemoryManager shutdown complete")


# Global memory manager instance
_memory_manager: Optional[EnhancedMemoryManager] = None


def get_memory_manager() -> EnhancedMemoryManager:
    """Get the global memory manager instance."""
    global _memory_manager
    if _memory_manager is None:
        _memory_manager = EnhancedMemoryManager()
    return _memory_manager


def get_managed_memory(
    session_id: str,
    memory_key: str = "memory",
    return_messages: bool = True,
    input_key: str = "input",
    output_key: str = "output",
    node_type: str = "BufferMemory"
) -> ConversationBufferMemory:
    """Get managed memory using the global memory manager."""
    return get_memory_manager().get_or_create_memory(
        session_id, memory_key, return_messages, input_key, output_key, node_type
    )


def cleanup_managed_memory(session_id: str) -> bool:
    """Clean up managed memory using the global memory manager."""
    return get_memory_manager().cleanup_memory(session_id)