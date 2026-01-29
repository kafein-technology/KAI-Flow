"""Timer Start Node - Scheduled trigger that initiates workflows."""

import asyncio
import logging
import uuid
from typing import Dict, Any, Optional, AsyncGenerator
from datetime import datetime, timedelta, timezone
from croniter import croniter
from pydantic import BaseModel, Field

from app.nodes.base import TerminatorNode, NodeInput, NodeOutput, NodeType, NodeProperty, NodePosition, NodePropertyType
from app.core.state import FlowState
from app.core.execution_queue import execution_queue
from app.core.engine import get_engine

logger = logging.getLogger(__name__)


# Global timer registry for active timers
active_timers: Dict[str, Dict[str, Any]] = {}
timer_tasks: Dict[str, asyncio.Task] = {}

class TimerTriggerData(BaseModel):
    """Timer trigger data model."""
    timer_id: str
    triggered_at: str
    schedule_type: str
    trigger_data: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    execution_count: int = 0
    next_run_at: Optional[str] = None

class TimerStartNode(TerminatorNode):
    """
    Enhanced timer start node with automatic workflow triggering infrastructure.
    
    This node provides sophisticated scheduling capabilities similar to webhook triggers:
    - Automatic workflow execution when timer expires
    - Support for interval, cron, once, and manual scheduling
    - Automatic timer restart for recurring schedules
    - Integration with workflow execution system
    - Timer status tracking and monitoring
    - Error handling and recovery
    """

    def __init__(self):
        super().__init__()
        self.timer_id = f"timer_{uuid.uuid4().hex[:8]}"
        self.workflow_id: Optional[str] = None
        self.user_id: Optional[str] = None
        self._timer_task: Optional[asyncio.Task] = None
        self._is_active = False
        
        self._metadata = {
            "name": "TimerStart",
            "display_name": "Timer Start",
            "description": "Start workflow on schedule, timer events, or manual trigger",
            "node_type": NodeType.TERMINATOR,
            "category": "Triggers",
            "colors": ["green-500", "emerald-600"],
            "icon": {"name": "clock", "path": None, "alt": None},
            "inputs": [
                NodeInput(
                    name="schedule_type",
                    type="select",
                    description="Type of schedule",
                    default="interval",
                    required=False,
                ),
                NodeInput(
                    name="interval_seconds",
                    type="int",
                    description="Interval in seconds (for interval type)",
                    default=3600,  # 1 hour
                    required=False,
                ),
                NodeInput(
                    name="cron_expression",
                    type="string",
                    description="Cron expression (for cron type)",
                    default="0 */1 * * *",  # Every hour
                    required=False
                ),
                NodeInput(
                    name="scheduled_time",
                    type="string",
                    description="Specific time to run (ISO format for once type)",
                    default="",
                    required=False
                ),
                NodeInput(
                    name="timezone",
                    type="string",
                    description="Timezone for scheduling",
                    default="UTC",
                    required=False
                ),
                NodeInput(
                    name="enabled",
                    type="bool",
                    description="Enable/disable the timer",
                    default=True,
                    required=False
                ),
                NodeInput(
                    name="trigger_data",
                    type="object",
                    description="Data to pass when timer triggers",
                    default={},
                    required=False
                ),
                NodeInput(
                    name="auto_trigger_workflow",
                    type="bool",
                    description="Automatically trigger workflow execution when timer expires",
                    default=True,
                    required=False
                ),
                NodeInput(
                    name="max_executions",
                    type="int",
                    description="Maximum number of executions (0 = unlimited)",
                    default=0,
                    required=False,
                ),
                NodeInput(
                    name="timeout_seconds",
                    type="int",
                    description="Workflow execution timeout in seconds",
                    default=300,
                    required=False,
                ),
                NodeInput(
                    name="retry_on_failure",
                    type="bool",
                    description="Retry workflow execution on failure",
                    default=False,
                    required=False
                ),
                NodeInput(
                    name="retry_count",
                    type="int",
                    description="Number of retries on failure",
                    default=3,
                    required=False,
                )
            ],
            "outputs": [
                NodeOutput(
                    name="timer_data",
                    displayName="Timer Data",
                    type="object",
                    description="Timer trigger information",
                    is_connection=True
                ),
                NodeOutput(
                    name="schedule_info",
                    type="object",
                    description="Schedule configuration and next run time"
                ),
                NodeOutput(
                    name="timer_stats",
                    type="object",
                    description="Timer execution statistics and monitoring data"
                ),
                NodeOutput(
                    name="timer_control",
                    type="object",
                    description="Timer control interface for start/stop/status operations"
                )
            ],
            "properties": [
                # Basic Tab
                NodeProperty(
                    name="schedule_type",
                    displayName="Schedule Type",
                    type=NodePropertyType.SELECT,
                    default="interval",
                    options=[
                        {"label": "Interval ", "value": "interval", "hint": "Run at regular intervals"},
                        {"label": "Cron Expression", "value": "cron", "hint": "Use cron expression for complex scheduling"},
                        {"label": "One Time", "value": "once", "hint": "Run once at a specific time"},
                        {"label": "Manual Trigger", "value": "manual", "hint": "Trigger manually only"},
                    ],
                    tabName="basic",
                    required=True,
                ),
                NodeProperty(
                    name="interval_seconds",
                    displayName="Interval (seconds)",
                    type=NodePropertyType.RANGE,
                    default=3600,
                    min=60,
                    max=86400,
                    minLabel="1 minute",
                    maxLabel="24 hours",
                    step=60,
                    description="Run at regular intervals",
                    displayOptions={
                        "show": {
                            "schedule_type": "interval"
                        }
                    },
                    tabName="basic",
                    required=True,
                ),
                NodeProperty(
                    name="cron_expression",
                    displayName="Cron Expression",
                    type=NodePropertyType.TEXT,
                    default="0 */1 * * *",
                    placeholder="0 */1 * * *",
                    hint="Format: minute hour day month weekday",
                    displayOptions={
                        "show": {
                            "schedule_type": "cron"
                        }
                    },
                    tabName="basic",
                    required=True,
                ),
                NodeProperty(
                    name="scheduled_time",
                    displayName="Scheduled Time",
                    type=NodePropertyType.DATETIME,
                    hint="Run once at a specific time (ISO format)",
                    displayOptions={
                        "show": {
                            "schedule_type": "once"
                        }
                    },
                    tabName="basic",
                    required=False,
                ),
                NodeProperty(
                    name="timezone",
                    displayName="Timezone",
                    type=NodePropertyType.SELECT,
                    default="UTC",
                    options=[
                        {"label": "UTC ", "value": "UTC"},
                        {"label": "Eastern Time", "value": "America/New_York"},
                        {"label": "Central Time", "value": "America/Chicago"},
                        {"label": "Mountain Time", "value": "America/Denver"},
                        {"label": "Pacific Time", "value": "America/Los_Angeles"},
                        {"label": "London", "value": "Europe/London"},
                        {"label": "Paris", "value": "Europe/Paris"},
                        {"label": "Tokyo", "value": "Asia/Tokyo"},
                        {"label": "Shanghai", "value": "Asia/Shanghai"},
                        {"label": "Sydney", "value": "Australia/Sydney"},
                    ],
                    hint="Timezone for scheduling",
                    tabName="basic",
                    required=True,
                ),

                # Advanced Tab
                NodeProperty(
                    name="enabled",
                    displayName="Enable Timer",
                    type=NodePropertyType.CHECKBOX,
                    default=True,
                    hint="Enable or disable the timer trigger",
                    tabName="advanced",
                ),

                # Data Tab
                NodeProperty(
                    name="trigger_data",
                    displayName="Trigger Data",
                    type=NodePropertyType.JSON_EDITOR,
                    default="{}",
                    hint="Data to pass when timer triggers (JSON format)",
                    tabName="data",
                ),
            ],
        }
        
        # Register timer in global registry
        active_timers[self.timer_id] = {
            "node_instance": self,
            "status": "initialized",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "execution_count": 0,
            "last_execution": None,
            "next_execution": None
        }
        
        logger.info(f"Timer trigger created: {self.timer_id}")

    def _execute(self, state: FlowState) -> Dict[str, Any]:
        """
        Execute the timer start node with enhanced workflow triggering.
        
        Args:
            state: Current workflow state
            
        Returns:
            Dict containing comprehensive timer data and control interface
        """
        # Get timer configuration
        schedule_type = self.user_data.get("schedule_type", "interval")
        interval_seconds = self.user_data.get("interval_seconds", 3600)
        trigger_data = self.user_data.get("trigger_data", {})
        enabled = self.user_data.get("enabled", True)
        auto_trigger = self.user_data.get("auto_trigger_workflow", True)
        max_executions = self.user_data.get("max_executions", 0)
        
        # Store workflow context for automatic triggering
        if state and hasattr(state, 'workflow_id'):
            self.workflow_id = state.workflow_id
        if state and hasattr(state, 'user_id'):
            self.user_id = state.user_id
        
        # Calculate next run time with enhanced scheduling
        next_run = self._calculate_next_run_time()
        
        # Create enhanced timer data
        timer_data = TimerTriggerData(
            timer_id=self.timer_id,
            triggered_at=datetime.now(timezone.utc).isoformat(),
            schedule_type=schedule_type,
            trigger_data=trigger_data,
            enabled=enabled,
            execution_count=active_timers[self.timer_id]["execution_count"],
            next_run_at=next_run.isoformat() if next_run else None
        )
        
        # Set initial input from trigger data or default message
        if trigger_data:
            initial_input = trigger_data.get("message", "Timer triggered")
        else:
            initial_input = f"Timer workflow initialized ({schedule_type})"
        
        # Update state if provided
        if state:
            state.last_output = str(initial_input)
            
            # Add this node to executed nodes list
            if self.node_id and self.node_id not in state.executed_nodes:
                state.executed_nodes.append(self.node_id)
        
        # Start automatic timer if enabled and auto_trigger is on
        if enabled and auto_trigger and schedule_type != "manual":
            self._start_automatic_timer()
        
        logger.info(f"[TimerStartNode] Timer {self.timer_id} initialized: {initial_input}")
        
        return {
            "timer_data": timer_data.dict(),
            "schedule_info": self._get_schedule_info(),
            "timer_stats": self._get_timer_stats(),
            "timer_control": {
                "timer_id": self.timer_id,
                "status": "active" if self._is_active else "inactive",
                "actions": {
                    "start": self.start_timer,
                    "stop": self.stop_timer,
                    "trigger_now": self.trigger_now,
                    "get_status": self.get_timer_status
                }
            },
            "output": initial_input,
            "status": "timer_initialized"
        }

    def _calculate_next_run_time(self) -> Optional[datetime]:
        """Calculate the next run time with enhanced scheduling logic."""
        schedule_type = self.user_data.get("schedule_type", "interval")
        
        if schedule_type == "manual" or not self.user_data.get("enabled", True):
            return None
        
        now = datetime.now(timezone.utc)
        
        if schedule_type == "interval":
            interval_seconds = self.user_data.get("interval_seconds", 3600)
            # For first run, schedule immediately or with small delay
            last_run = active_timers[self.timer_id].get("last_execution")
            if not last_run:
                return now + timedelta(seconds=min(30, interval_seconds))
            else:
                last_run_dt = datetime.fromisoformat(last_run)
                return last_run_dt + timedelta(seconds=interval_seconds)
                
        elif schedule_type == "cron":
            cron_expression = self.user_data.get("cron_expression", "0 */1 * * *")
            try:
                cron = croniter(cron_expression, now)
                return cron.get_next(datetime)
            except Exception as e:
                logger.error(f"Invalid cron expression '{cron_expression}': {e}")
                return now + timedelta(hours=1)  # Fallback
                
        elif schedule_type == "once":
            scheduled_time = self.user_data.get("scheduled_time", "")
            if scheduled_time:
                try:
                    target_time = datetime.fromisoformat(scheduled_time)
                    # If scheduled time is in the past, execute immediately
                    if target_time <= now:
                        return now + timedelta(seconds=5)
                    return target_time
                except Exception as e:
                    logger.error(f"Invalid scheduled time '{scheduled_time}': {e}")
                    return now + timedelta(minutes=5)  # Fallback
        
        return None
    
    def _get_schedule_info(self) -> Dict[str, Any]:
        """Get comprehensive schedule information."""
        schedule_type = self.user_data.get("schedule_type", "interval")
        next_run = self._calculate_next_run_time()
        
        return {
            "schedule_type": schedule_type,
            "next_run": next_run.isoformat() if next_run else None,
            "interval_seconds": self.user_data.get("interval_seconds") if schedule_type == "interval" else None,
            "cron_expression": self.user_data.get("cron_expression") if schedule_type == "cron" else None,
            "scheduled_time": self.user_data.get("scheduled_time") if schedule_type == "once" else None,
            "timezone": self.user_data.get("timezone", "UTC"),
            "enabled": self.user_data.get("enabled", True),
            "auto_trigger_workflow": self.user_data.get("auto_trigger_workflow", True),
            "max_executions": self.user_data.get("max_executions", 0),
            "timeout_seconds": self.user_data.get("timeout_seconds", 300)
        }
    
    def _get_timer_stats(self) -> Dict[str, Any]:
        """Get timer execution statistics."""
        timer_info = active_timers.get(self.timer_id, {})
        
        return {
            "timer_id": self.timer_id,
            "status": timer_info.get("status", "unknown"),
            "created_at": timer_info.get("created_at"),
            "execution_count": timer_info.get("execution_count", 0),
            "last_execution": timer_info.get("last_execution"),
            "next_execution": timer_info.get("next_execution"),
            "is_active": self._is_active,
            "workflow_id": self.workflow_id,
            "user_id": self.user_id
        }
    
    def _start_automatic_timer(self) -> None:
        """Start the automatic timer with workflow triggering."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        self._timer_task = asyncio.create_task(self._timer_loop())
        self._is_active = True
        
        # Update global registry
        active_timers[self.timer_id].update({
            "status": "running",
            "next_execution": self._calculate_next_run_time().isoformat() if self._calculate_next_run_time() else None
        })
        
        timer_tasks[self.timer_id] = self._timer_task
        logger.info(f"Started automatic timer: {self.timer_id}")
    
    async def _timer_loop(self) -> None:
        """Main timer loop for automatic workflow triggering."""
        max_executions = self.user_data.get("max_executions", 0)
        schedule_type = self.user_data.get("schedule_type", "interval")
        
        try:
            while self.user_data.get("enabled", True) and self._is_active:
                next_run = self._calculate_next_run_time()
                if not next_run:
                    break
                
                # Check max executions limit
                if max_executions > 0 and active_timers[self.timer_id]["execution_count"] >= max_executions:
                    logger.info(f"Timer {self.timer_id} reached max executions limit: {max_executions}")
                    break
                
                # Calculate sleep time
                now = datetime.now(timezone.utc)
                sleep_seconds = (next_run - now).total_seconds()
                
                if sleep_seconds > 0:
                    logger.debug(f"Timer {self.timer_id} sleeping for {sleep_seconds:.1f} seconds")
                    await asyncio.sleep(sleep_seconds)
                
                # Check if still enabled after sleep
                if not self.user_data.get("enabled", True) or not self._is_active:
                    break
                
                # Trigger workflow execution
                await self._trigger_workflow_execution()
                
                # For "once" type timers, stop after execution
                if schedule_type == "once":
                    break
                    
        except asyncio.CancelledError:
            logger.info(f"Timer {self.timer_id} loop cancelled")
        except Exception as e:
            logger.error(f"Timer {self.timer_id} loop error: {e}")
            active_timers[self.timer_id]["status"] = "error"
        finally:
            self._is_active = False
            active_timers[self.timer_id]["status"] = "stopped"
    
    async def _trigger_workflow_execution(self) -> None:
        """Trigger automatic workflow execution."""
        try:
            execution_id = str(uuid.uuid4())
            
            # Update execution stats
            active_timers[self.timer_id]["execution_count"] += 1
            active_timers[self.timer_id]["last_execution"] = datetime.now(timezone.utc).isoformat()
            
            logger.info(f"Timer {self.timer_id} triggering workflow execution: {execution_id}")
            
            # If we have workflow context, trigger actual workflow
            if self.workflow_id and self.user_id:
                success = await self._execute_workflow_via_engine(execution_id)
                if not success and self.user_data.get("retry_on_failure", False):
                    await self._retry_workflow_execution(execution_id)
            else:
                logger.warning(f"Timer {self.timer_id} missing workflow context, skipping execution")
            
        except Exception as e:
            logger.error(f"Timer {self.timer_id} workflow execution failed: {e}")
            active_timers[self.timer_id]["status"] = "error"
    
    async def _execute_workflow_via_engine(self, execution_id: str) -> bool:
        """Execute workflow using the workflow engine."""
        try:
            # Get workflow execution slot
            slot_acquired = await execution_queue.acquire_execution_slot(
                self.workflow_id, self.user_id, execution_id
            )
            
            if not slot_acquired:
                logger.warning(f"Could not acquire execution slot for timer {self.timer_id}")
                return False
            
            try:
                # Get workflow engine
                engine = get_engine()
                
                # Prepare execution inputs with timer data
                execution_inputs = {
                    "timer_trigger": True,
                    "timer_id": self.timer_id,
                    "execution_id": execution_id,
                    "triggered_at": datetime.now(timezone.utc).isoformat(),
                    **self.user_data.get("trigger_data", {})
                }
                
                # Execute workflow with timeout
                timeout = self.user_data.get("timeout_seconds", 300)
                result = await asyncio.wait_for(
                    engine.execute(
                        inputs=execution_inputs,
                        user_context={
                            "user_id": self.user_id,
                            "workflow_id": self.workflow_id,
                            "execution_id": execution_id,
                            "trigger_type": "timer",
                            "timer_id": self.timer_id
                        }
                    ),
                    timeout=timeout
                )
                
                logger.info(f"Timer {self.timer_id} workflow execution completed: {execution_id}")
                return True
                
            finally:
                # Always release execution slot
                await execution_queue.release_execution_slot(self.workflow_id, self.user_id)
                
        except asyncio.TimeoutError:
            logger.error(f"Timer {self.timer_id} workflow execution timed out: {execution_id}")
            return False
        except Exception as e:
            logger.error(f"Timer {self.timer_id} workflow execution error: {e}")
            return False
    
    async def _retry_workflow_execution(self, original_execution_id: str) -> None:
        """Retry workflow execution on failure."""
        retry_count = self.user_data.get("retry_count", 3)
        
        for retry in range(retry_count):
            try:
                # Wait before retry
                await asyncio.sleep(min(2 ** retry, 60))  # Exponential backoff
                
                retry_execution_id = f"{original_execution_id}_retry_{retry + 1}"
                success = await self._execute_workflow_via_engine(retry_execution_id)
                
                if success:
                    logger.info(f"Timer {self.timer_id} workflow execution succeeded on retry {retry + 1}")
                    return
                    
            except Exception as e:
                logger.error(f"Timer {self.timer_id} retry {retry + 1} failed: {e}")
        
        logger.error(f"Timer {self.timer_id} workflow execution failed after {retry_count} retries")
    
    def start_timer(self) -> Dict[str, Any]:
        """Manually start the timer."""
        if not self._is_active:
            self._start_automatic_timer()
            return {"success": True, "message": f"Timer {self.timer_id} started"}
        else:
            return {"success": False, "message": f"Timer {self.timer_id} is already active"}
    
    def stop_timer(self) -> Dict[str, Any]:
        """Manually stop the timer."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        self._is_active = False
        active_timers[self.timer_id]["status"] = "stopped"
        
        if self.timer_id in timer_tasks:
            del timer_tasks[self.timer_id]
        
        logger.info(f"Timer {self.timer_id} stopped")
        return {"success": True, "message": f"Timer {self.timer_id} stopped"}
    
    async def trigger_now(self) -> Dict[str, Any]:
        """Manually trigger workflow execution immediately."""
        try:
            execution_id = str(uuid.uuid4())
            await self._trigger_workflow_execution()
            return {"success": True, "message": f"Timer {self.timer_id} triggered manually", "execution_id": execution_id}
        except Exception as e:
            return {"success": False, "message": f"Failed to trigger timer {self.timer_id}: {e}"}
    
    def get_timer_status(self) -> Dict[str, Any]:
        """Get current timer status."""
        return {
            "timer_id": self.timer_id,
            "is_active": self._is_active,
            "timer_stats": self._get_timer_stats(),
            "schedule_info": self._get_schedule_info()
        }
    
    def cleanup(self) -> None:
        """Cleanup timer resources."""
        if self._timer_task and not self._timer_task.done():
            self._timer_task.cancel()
        
        self._is_active = False
        
        if self.timer_id in active_timers:
            del active_timers[self.timer_id]
        
        if self.timer_id in timer_tasks:
            del timer_tasks[self.timer_id]
        
        logger.info(f"Timer {self.timer_id} cleaned up")


# Utility functions for timer management
def get_active_timers() -> Dict[str, Dict[str, Any]]:
    """Get all active timers."""
    return active_timers.copy()

def stop_all_timers() -> None:
    """Stop all active timers."""
    for timer_id, task in timer_tasks.items():
        if not task.done():
            task.cancel()
    
    timer_tasks.clear()
    
    for timer_id in active_timers:
        active_timers[timer_id]["status"] = "stopped"
    
    logger.info("All timers stopped")

def cleanup_completed_timers() -> int:
    """Clean up completed timer tasks."""
    completed_count = 0
    completed_timer_ids = []
    
    for timer_id, task in timer_tasks.items():
        if task.done():
            completed_timer_ids.append(timer_id)
            completed_count += 1
    
    for timer_id in completed_timer_ids:
        del timer_tasks[timer_id]
        if timer_id in active_timers:
            active_timers[timer_id]["status"] = "completed"
    
    logger.info(f"Cleaned up {completed_count} completed timers")
    return completed_count