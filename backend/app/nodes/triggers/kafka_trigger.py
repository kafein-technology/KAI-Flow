
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from confluent_kafka import Consumer, KafkaError, KafkaException, Producer, TopicPartition

from app.core.database import get_db_session
from app.auth.dependencies import get_current_user
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from app.nodes.base import BaseNode, NodeType, NodeMetadata, NodeProperty, NodeInput, NodeOutput, NodePropertyType
from app.core.kafka_utils import get_kafka_config, get_kafka_node_value
from app.core.constants import API_START, API_VERSION

logger = logging.getLogger(__name__)

# Kafka reconciliation loop execution interval (seconds)
KAFKA_RECONCILIATION_INTERVAL_SECONDS = 60
KAFKA_STREAM_MAX_QUEUE_LENGTH = 100
kafka_execution_subscribers: Dict[str, List[asyncio.Queue]] = {}


async def broadcast_kafka_execution_event(listener_id: str, event: Dict[str, Any]) -> None:
    """Broadcast Kafka-triggered workflow execution events to canvas subscribers."""
    subscribers = kafka_execution_subscribers.get(listener_id, [])
    if not subscribers:
        return

    stale_subscribers: List[asyncio.Queue] = []
    for queue in subscribers.copy():
        try:
            if queue.qsize() >= KAFKA_STREAM_MAX_QUEUE_LENGTH:
                stale_subscribers.append(queue)
                continue
            queue.put_nowait(event)
        except asyncio.QueueFull:
            stale_subscribers.append(queue)
        except Exception:
            stale_subscribers.append(queue)

    for queue in stale_subscribers:
        if queue in subscribers:
            subscribers.remove(queue)


# ══════════════════════════════════════════════════════════════════
# DB Lookup — Find workflow containing a KafkaConsumer trigger node
# ══════════════════════════════════════════════════════════════════

async def find_kafka_workflow(db, listener_id: str):
    """
    Find the workflow containing the KafkaConsumer node that matches the
    given listener_id (node ID) using a JSONB query.
    
    Follows the find_workflow() pattern in webhook_trigger.py.
    """
    from sqlalchemy import select, text
    from sqlalchemy.sql import bindparam
    from app.models.workflow import Workflow

    try:
        logger.info(f"Searching for Kafka workflow: listener_id={listener_id}")

        search_stmt = select(Workflow).where(
            text("""
                EXISTS (
                    SELECT 1
                    FROM jsonb_array_elements(workflows.flow_data->'nodes') AS node
                    WHERE
                        (node->>'id') = :listener_id
                        AND (node->>'type') IN ('KafkaConsumer', 'KafkaTrigger')
                )
            """).bindparams(bindparam("listener_id", listener_id))
        )

        result = await db.execute(search_stmt)
        workflows = result.scalars().all()

        if workflows:
            if len(workflows) > 1:
                logger.warning(f"Multiple workflows found for listener_id={listener_id}; using the first one")
            workflow = workflows[0]
            logger.info(f"Kafka workflow found: {workflow.id} ({workflow.name})")
            return workflow

        logger.warning(f"Kafka workflow not found: listener_id={listener_id}")
        return None

    except Exception as e:
        logger.error(f"Error while searching for Kafka workflow: {e}", exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════
# KafkaListenerService — Background Kafka consumer manager
# ══════════════════════════════════════════════════════════════════

class KafkaListenerService:
    """
    Manage background Kafka consumer tasks per workflow.
    
    Creates a separate asyncio task for each listener_id (the node ID on the
    canvas). The task polls messages through confluent_kafka.Consumer and
    triggers the workflow through WorkflowExecutor for every message.
    """

    _listeners: Dict[str, Dict[str, Any]] = {}
    _workflow_slots = asyncio.Semaphore(max(1, min(64, int(os.getenv("KAFKA_MAX_ACTIVE_WORKFLOWS", "4")))))

    @staticmethod
    def _source_id(listener_id: str, group_id: str, msg) -> uuid.UUID:
        source = f"{listener_id}:{group_id}:{msg.topic()}:{msg.partition()}:{msg.offset()}"
        return uuid.uuid5(uuid.NAMESPACE_URL, f"kai-flow:kafka:{source}")

    @staticmethod
    def _publish_dead_letter(config: dict, msg, error: Exception, attempts: int) -> None:
        topic = config["options"].get("dead_letter_topic") or f"{config['topic']}.dlq"
        producer_config = get_kafka_config(config["credential_data"])
        producer_config.update({"enable.idempotence": True, "acks": "all", "message.timeout.ms": 30000})
        producer = Producer(producer_config)
        delivery = {}

        def on_delivery(err, _message):
            delivery["error" if err else "ok"] = str(err) if err else True

        headers = list(msg.headers() or [])
        headers.extend([
            ("kai-source-topic", msg.topic().encode()),
            ("kai-source-partition", str(msg.partition()).encode()),
            ("kai-source-offset", str(msg.offset()).encode()),
            ("kai-attempts", str(attempts).encode()),
            ("kai-error", str(error)[:500].encode("utf-8", errors="replace")),
        ])
        producer.produce(topic, key=msg.key(), value=msg.value(), headers=headers, callback=on_delivery)
        remaining = producer.flush(30)
        if remaining or not delivery.get("ok"):
            raise RuntimeError(f"Dead-letter delivery failed: {delivery.get('error', 'timeout')}")

    @classmethod
    async def _run_message(cls, listener_id: str, config: dict, msg) -> None:
        opts = config["options"]
        attempts = max(1, min(10, int(opts.get("max_workflow_attempts") or 3)))
        retry_delay = max(0.0, min(60.0, float(opts.get("retry_delay_on_error", 1000)) / 1000.0))
        source_id = cls._source_id(listener_id, config["group_id"], msg)
        for attempt in range(1, attempts + 1):
            try:
                message_data = cls._parse_message(msg, opts)
                async with cls._workflow_slots:
                    await cls._trigger_workflow(listener_id, message_data, source_id=source_id)
                return True
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.warning(
                    "Kafka workflow failed: listener=%s topic=%s partition=%s offset=%s attempt=%s/%s: %s",
                    listener_id, msg.topic(), msg.partition(), msg.offset(), attempt, attempts, exc,
                )
                if attempt < attempts:
                    await asyncio.sleep(min(60.0, retry_delay * (2 ** (attempt - 1))))
                    continue
                await asyncio.to_thread(cls._publish_dead_letter, config, msg, exc, attempts)
                cls._listeners[listener_id]["stats"]["dead_lettered"] += 1
                cls._listeners[listener_id]["stats"]["last_error"] = str(exc)[:500]
                logger.error("Kafka message moved to dead-letter topic: listener=%s offset=%s", listener_id, msg.offset())
                return False

    @classmethod
    async def start_listener(
        cls,
        listener_id: str,
        workflow_id: str,
        user_id: str,
        credential_data: dict,
        topic: str,
        group_id: str,
        options: Optional[Dict[str, Any]] = None,
    ) -> dict:
        """Start a Kafka consumer with the specified configuration."""

        if listener_id in cls._listeners:
            existing = cls._listeners[listener_id]
            if existing.get("status") in ("starting", "running"):
                return {
                    "status": "already_running",
                    "listener_id": listener_id,
                    "message": "This listener is already running.",
                }

        opts = options or {}

        config = {
            "listener_id": listener_id,
            "workflow_id": workflow_id,
            "user_id": user_id,
            "credential_data": credential_data,
            "topic": topic,
            "group_id": group_id,
            "options": opts,
        }

        # Create the listener record
        cls._listeners[listener_id] = {
            "config": config,
            "status": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "messages_received": 0,
                "workflows_triggered": 0,
                "dead_lettered": 0,
                "consecutive_failures": 0,
                "active_workflows": 0,
                "errors": 0,
                "last_message_at": None,
                "last_error": None,
            },
            "task": None,
        }

        # Start the background task
        task = asyncio.create_task(cls._consumer_loop(listener_id))
        cls._listeners[listener_id]["task"] = task

        logger.info(f"Kafka listener starting: {listener_id} topic={topic} group={group_id}")

        return {
            "status": "started",
            "listener_id": listener_id,
            "topic": topic,
            "group_id": group_id,
        }

    @classmethod
    async def stop_listener(cls, listener_id: str) -> dict:
        """Stop a running Kafka consumer and remove its listener record."""

        if listener_id not in cls._listeners:
            return {"status": "not_found", "listener_id": listener_id}

        entry = cls._listeners[listener_id]
        entry["status"] = "stopping"

        task = entry.get("task")
        if task and not task.done():
            try:
                grace_seconds = max(1, min(300, int(os.getenv("KAFKA_SHUTDOWN_GRACE_SECONDS", "120"))))
                await asyncio.wait_for(task, timeout=grace_seconds)
            except asyncio.TimeoutError:
                logger.warning(f"Consumer {listener_id} It wasn't shut down on time; it's being forcibly cancelled.")
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

        # Memory leak fix: remove the stopped listener from the dictionary
        del cls._listeners[listener_id]

        logger.info(f"Kafka listener has been stopped and cleaned: {listener_id}")

        return {"status": "stopped", "listener_id": listener_id}

    @classmethod
    def get_listener_status(cls, listener_id: str) -> Optional[dict]:
        """Return the status of a specific listener."""
        if listener_id not in cls._listeners:
            return None

        entry = cls._listeners[listener_id]
        return {
            "listener_id": listener_id,
            "status": entry["status"],
            "started_at": entry.get("started_at"),
            "stopped_at": entry.get("stopped_at"),
            "config": {
                "topic": entry["config"]["topic"],
                "group_id": entry["config"]["group_id"],
                "workflow_id": entry["config"]["workflow_id"],
            },
            "stats": entry["stats"],
        }

    @classmethod
    def get_all_listeners(cls) -> List[dict]:
        """Return the status of all listeners."""
        return [
            cls.get_listener_status(lid)
            for lid in cls._listeners
        ]

    @classmethod
    async def stop_listeners_by_credential(cls, credential_id: str):
        """Stop all listeners that use a specific credential."""
        listeners_to_stop = []
        for lid, entry in cls._listeners.items():
            config = entry.get("config", {})
            cred_data = config.get("credential_data", {})
            # Compare credential_id as a string
            if str(cred_data.get("credential_id", "")) == credential_id:
                listeners_to_stop.append(lid)

        results = []
        for lid in listeners_to_stop:
            result = await cls.stop_listener(lid)
            results.append(result)
            logger.info(f"Stopped listener {lid} for credential {credential_id}")

        return results

    # ──────────────────────────────────────────────
    # Background consumer loop
    # ──────────────────────────────────────────────

    @classmethod
    async def _consumer_loop(cls, listener_id: str):
        """
        Listen for messages with confluent_kafka.Consumer.
        Wrap poll() with asyncio.to_thread() because it is blocking.
        """
        entry = cls._listeners[listener_id]
        config = entry["config"]
        stats = entry["stats"]
        opts = config["options"]

        # confluent-kafka configuration
        kafka_conf = get_kafka_config(config["credential_data"])
        kafka_conf["group.id"] = config["group_id"]
        kafka_conf["session.timeout.ms"] = opts.get("session_timeout_ms", 45000)
        kafka_conf["heartbeat.interval.ms"] = opts.get("heartbeat_interval_ms", 3000)
        kafka_conf["fetch.min.bytes"] = opts.get("fetch_min_bytes", 1)
        kafka_conf["fetch.max.bytes"] = opts.get("fetch_max_bytes", 52428800)

        # allow_auto_create_topics: whether the broker may create a missing topic automatically
        kafka_conf["allow.auto.create.topics"] = opts.get("allow_auto_create_topics", True)

        # batch_size: maximum fetch size per partition (bytes)
        kafka_conf["max.partition.fetch.bytes"] = opts.get("batch_size", 1048576)

        # rebalance_timeout_ms: consumer group rebalance timeout
        kafka_conf["max.poll.interval.ms"] = opts.get("rebalance_timeout_ms", 300000)

        # Each partition is committed only after its workflow or dead-letter delivery succeeds.
        kafka_conf["enable.auto.commit"] = False

        # Read-from-beginning setting
        if opts.get("read_messages_from_beginning", False):
            kafka_conf["auto.offset.reset"] = "earliest"
        else:
            kafka_conf["auto.offset.reset"] = "latest"

        logger.info(f"Kafka consumer config: servers={kafka_conf.get('bootstrap.servers')}, group={kafka_conf.get('group.id')}, topic={config['topic']}")
        logger.debug("Kafka consumer config keys: %s", sorted(kafka_conf.keys()))

        consumer = None
        retry_delay = max(0.0, min(60.0, float(opts.get("retry_delay_on_error", 1000)) / 1000.0))

        try:
            # Consumer() and subscribe() are blocking C library calls.
            # An unreachable Kafka broker can block the event loop for 45 seconds,
            # so isolate these calls with asyncio.to_thread().
            consumer = await asyncio.to_thread(Consumer, kafka_conf)
            await asyncio.to_thread(consumer.subscribe, [config["topic"]])
            logger.info(f"Kafka consumer subscribed to topic: {config['topic']} (listener={listener_id})")

            max_concurrent = max(1, min(16, int(opts.get("max_concurrent_workflows") or 4)))
            inflight: Dict[tuple, tuple] = {}
            deferred_offsets: Dict[tuple, int] = {}
            paused_keys = set()

            async def sync_pauses():
                nonlocal paused_keys
                assigned = await asyncio.to_thread(consumer.assignment)
                assigned_by_key = {(part.topic, part.partition): part for part in assigned}
                should_pause = set(assigned_by_key) if len(inflight) >= max_concurrent or entry["status"] != "running" else set(inflight)
                should_pause &= set(assigned_by_key)
                new_pauses = should_pause - paused_keys
                new_resumes = (paused_keys - should_pause) & set(assigned_by_key)
                if new_pauses:
                    await asyncio.to_thread(consumer.pause, [assigned_by_key[key] for key in new_pauses])
                if new_resumes:
                    await asyncio.to_thread(consumer.resume, [assigned_by_key[key] for key in new_resumes])
                paused_keys = should_pause

            while entry["status"] in ("starting", "running") or inflight:
                try:
                    # Poll even while all workers are occupied to service group rebalances.
                    msg = await asyncio.to_thread(consumer.poll, 0.25)
                    if entry["status"] == "starting":
                        assignment = await asyncio.to_thread(consumer.assignment)
                        if assignment:
                            entry["status"] = "running"
                            logger.info("Kafka listener ready: listener=%s partitions=%s", listener_id, len(assignment))

                    if msg is not None and msg.error():
                        error_code = msg.error().code()
                        if error_code == KafkaError._PARTITION_EOF:
                            logger.debug(f"Partition EOF: {msg.topic()}[{msg.partition()}]")
                        else:
                            error_str = str(msg.error())
                            logger.error(f"Kafka error: {error_str}")
                            stats["errors"] += 1
                            stats["last_error"] = error_str
                            await asyncio.sleep(retry_delay)
                        msg = None

                    if msg is not None:
                        key = (msg.topic(), msg.partition())
                        if key in inflight or len(inflight) >= max_concurrent or entry["status"] != "running":
                            deferred_offsets[key] = min(deferred_offsets.get(key, msg.offset()), msg.offset())
                        else:
                            stats["messages_received"] += 1
                            stats["last_message_at"] = datetime.now(timezone.utc).isoformat()
                            inflight[key] = (msg, asyncio.create_task(cls._run_message(listener_id, config, msg)))
                            stats["active_workflows"] = len(inflight)
                            await sync_pauses()

                    for key, (processed_msg, task) in list(inflight.items()):
                        if not task.done():
                            continue
                        try:
                            workflow_succeeded = await task
                            assigned = await asyncio.to_thread(consumer.assignment)
                            assigned_keys = {(part.topic, part.partition) for part in assigned}
                            if key in assigned_keys:
                                await asyncio.to_thread(
                                    consumer.commit,
                                    offsets=[TopicPartition(key[0], key[1], processed_msg.offset() + 1)],
                                    asynchronous=False,
                                )
                                if workflow_succeeded:
                                    stats["workflows_triggered"] += 1
                                    stats["consecutive_failures"] = 0
                                else:
                                    stats["consecutive_failures"] += 1
                                    failure_limit = max(1, min(100, int(opts.get("max_consecutive_failures") or 5)))
                                    if stats["consecutive_failures"] >= failure_limit:
                                        logger.error("Kafka listener blocked after %s consecutive dead-lettered messages: %s", failure_limit, listener_id)
                                        entry["status"] = "blocked"
                                if key in deferred_offsets:
                                    await asyncio.to_thread(consumer.seek, TopicPartition(key[0], key[1], deferred_offsets.pop(key)))
                        except Exception as e:
                            logger.error("Kafka message could not be acknowledged: listener=%s offset=%s: %s", listener_id, processed_msg.offset(), e, exc_info=True)
                            stats["errors"] += 1
                            stats["last_error"] = str(e)
                            entry["status"] = "blocked"
                        finally:
                            del inflight[key]
                            stats["active_workflows"] = len(inflight)
                            if entry["status"] == "running":
                                assigned = await asyncio.to_thread(consumer.assignment)
                                assigned_keys = {(part.topic, part.partition) for part in assigned}
                                for deferred_key, offset in list(deferred_offsets.items()):
                                    if deferred_key not in inflight and deferred_key in assigned_keys:
                                        await asyncio.to_thread(consumer.seek, TopicPartition(*deferred_key, offset))
                                        del deferred_offsets[deferred_key]
                                await sync_pauses()

                    if msg is None and not inflight and entry["status"] not in ("starting", "running"):
                        break

                except asyncio.CancelledError:
                    logger.info(f"Kafka consumer cancelled: {listener_id}")
                    for _msg, task in inflight.values():
                        task.cancel()
                    await asyncio.gather(*(task for _msg, task in inflight.values()), return_exceptions=True)
                    break
                except Exception as e:
                    logger.error(f"Consumer loop error: {e}", exc_info=True)
                    stats["errors"] += 1
                    stats["last_error"] = str(e)
                    entry["status"] = "error"
                    break

        except asyncio.CancelledError:
            logger.info(f"Kafka consumer task cancelled: {listener_id}")
        except KafkaException as e:
            logger.error(f"Kafka connection error: {e}", exc_info=True)
            stats["errors"] += 1
            stats["last_error"] = str(e)
            entry["status"] = "error"
        except Exception as e:
            logger.error(f"Unexpected consumer error: {e}", exc_info=True)
            stats["errors"] += 1
            stats["last_error"] = str(e)
            entry["status"] = "error"
        finally:
            if "inflight" in locals() and inflight:
                for _msg, task in inflight.values():
                    task.cancel()
                await asyncio.gather(*(task for _msg, task in inflight.values()), return_exceptions=True)
            if consumer:
                try:
                    await asyncio.to_thread(consumer.close)
                    logger.info(f"Kafka consumer closed: {listener_id}")
                except Exception as e:
                    logger.warning(f"Error while closing consumer: {e}")

            if entry["status"] in ("starting", "running"):
                entry["status"] = "stopped"

    @staticmethod
    def _parse_message(msg, opts: dict) -> dict:
        """Convert a Kafka message to a dictionary."""
        # Value
        raw_value = msg.value()
        value = None
        if raw_value is not None:
            if opts.get("keep_message_as_binary_data", False):
                import base64
                value = base64.b64encode(raw_value).decode("utf-8")
            else:
                try:
                    decoded = raw_value.decode("utf-8")
                    if opts.get("json_parse_message", True):
                        try:
                            value = json.loads(decoded)
                        except (json.JSONDecodeError, ValueError):
                            value = decoded
                    else:
                        value = decoded
                except UnicodeDecodeError:
                    import base64
                    value = base64.b64encode(raw_value).decode("utf-8")

        # Key
        raw_key = msg.key()
        key = None
        if raw_key is not None:
            try:
                key = raw_key.decode("utf-8")
            except (UnicodeDecodeError, AttributeError):
                key = str(raw_key)

        # Headers
        headers = None
        if opts.get("return_headers", True) and msg.headers():
            headers = {}
            for h_key, h_val in msg.headers():
                try:
                    headers[h_key] = h_val.decode("utf-8") if h_val else None
                except (UnicodeDecodeError, AttributeError):
                    headers[h_key] = str(h_val)

        data = {
            "value": value,
            "key": key,
            "topic": msg.topic(),
            "partition": msg.partition(),
            "offset": msg.offset(),
            "timestamp": msg.timestamp()[1] if msg.timestamp() else None,
            "headers": headers,
        }

        # only_message option: return only the value
        if opts.get("only_message", False):
            return {"value": value}

        return data

    @classmethod
    async def _trigger_workflow(cls, listener_id: str, message_data: dict, source_id: Optional[uuid.UUID] = None):
        """
        Run the related workflow when a Kafka message arrives.
        The Kafka trigger is an independent node, not a webhook.
        Load the workflow owner's User object directly.
        """
        from app.core.database import get_db_session_context
        from app.services.workflow_executor import WorkflowExecutor
        from app.models.workflow import Workflow
        from app.models.user import User
        from app.models.execution import WorkflowExecution
        from sqlalchemy import select

        entry = cls._listeners.get(listener_id)
        if not entry:
            raise RuntimeError(f"Listener not found: {listener_id}")

        config = entry["config"]
        workflow_id = config.get("workflow_id")

        if not workflow_id:
            raise RuntimeError(f"workflow_id is missing from listener config: {listener_id}")

        logger.info(f"Kafka trigger: loading workflow workflow_id={workflow_id}, listener={listener_id}")

        async with get_db_session_context() as db:
            # Load the workflow directly by ID
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await db.execute(stmt)
            workflow = result.scalar_one_or_none()

            if not workflow:
                raise RuntimeError(f"Workflow not found: workflow_id={workflow_id}, listener={listener_id}")

            # Load the workflow owner for credential access
            user_stmt = select(User).where(User.id == workflow.user_id)
            user_result = await db.execute(user_stmt)
            owner = user_result.scalar_one_or_none()

            if not owner:
                raise RuntimeError(f"Workflow owner not found: user_id={workflow.user_id}, workflow={workflow_id}")

            logger.info(f"Kafka trigger: workflow found {workflow.name} (id={workflow.id}, owner={owner.email})")

            # Prepare Kafka message data
            kafka_input = ""
            if message_data:
                value = message_data.get("value", "")
                if isinstance(value, (dict, list)):
                    kafka_input = json.dumps(value, ensure_ascii=False)
                else:
                    kafka_input = str(value)

            if not kafka_input:
                kafka_input = f"Kafka triggered: {listener_id}"

            # Prepare execution inputs
            execution_inputs = {
                "input": kafka_input,                    # Start node compatibility
                "input_text": kafka_input,               # Backward compatibility
                "kafka_trigger": True,
                "kafka_data": message_data,              # Complete message data
                "listener_id": listener_id,
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }
            if source_id:
                execution_inputs["kafka_source_id"] = str(source_id)
                existing_execution = await db.get(WorkflowExecution, source_id)
                if existing_execution and existing_execution.status == "completed":
                    logger.info("Skipping completed Kafka execution: source_id=%s", source_id)
                    return {"success": True, "deduplicated": True}
                if not existing_execution:
                    db.add(WorkflowExecution(
                        id=source_id,
                        workflow_id=workflow.id,
                        user_id=workflow.user_id,
                        status="pending",
                        inputs=execution_inputs,
                    ))
                    await db.commit()
                else:
                    existing_execution.status = "pending"
                    existing_execution.outputs = None
                    existing_execution.error_message = None
                    await db.commit()

            logger.info(f"Kafka trigger: executing workflow inputs={list(execution_inputs.keys())}")

            # Execute through WorkflowExecutor and pass the workflow owner directly
            executor = WorkflowExecutor()

            ctx = await executor.prepare_execution_context(
                db=db,
                workflow=workflow,
                execution_inputs=execution_inputs,
                user=owner,            # Workflow owner
                is_webhook=False,      # Kafka trigger is not a webhook
            )
            ctx.user_context["preserve_active_executions"] = True
            if source_id:
                ctx.execution_id = source_id

            result_stream = await executor.execute_workflow(
                ctx=ctx,
                db=db,
                stream=True,
            )

            result = None
            stream_error = None
            payload_sent = False
            saw_complete = False
            if hasattr(result_stream, "__aiter__"):
                async for event_chunk in result_stream:
                    if isinstance(event_chunk, dict):
                        if event_chunk.get("type") in ("error", "workflow_error"):
                            stream_error = event_chunk.get("error") or "Workflow execution failed"
                        if event_chunk.get("type") in ("complete", "workflow_complete"):
                            saw_complete = True
                            result = event_chunk

                        ui_event = {
                            "type": "kafka_execution_event",
                            "listener_id": listener_id,
                            "workflow_id": str(workflow.id),
                            "execution_id": str(ctx.execution_id) if ctx.execution_id else None,
                            "event": event_chunk,
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        }
                        if not payload_sent or event_chunk.get("type") in ("complete", "workflow_complete", "error", "workflow_error"):
                            ui_event["kafka_payload"] = message_data
                            payload_sent = True
                        await broadcast_kafka_execution_event(listener_id, ui_event)
            else:
                result = result_stream

            # Check execution result for errors
            if hasattr(result_stream, "__aiter__") and not saw_complete and not stream_error:
                raise RuntimeError("Kafka-triggered workflow stream ended without a completion event")
            if stream_error or (isinstance(result, dict) and result.get("success") is False):
                error_msg = stream_error or result.get("error", "Unknown workflow error")
                logger.error(
                    f"Kafka-triggered workflow completed with an error: "
                    f"workflow={workflow.id} listener={listener_id} "
                    f"execution={ctx.execution_id} error={error_msg}"
                )
                raise RuntimeError(f"Workflow execution failed: {error_msg}")

            logger.info(
                f"Kafka-triggered workflow completed: "
                f"workflow={workflow.id} listener={listener_id} "
                f"execution={ctx.execution_id}"
            )

            return result


# ══════════════════════════════════════════════════════════════════
# Reconciliation Loop — Periodic Kafka listener synchronization
# ══════════════════════════════════════════════════════════════════

import hashlib


def _compute_config_hash(topic: str, credential_id: str, group_id: str, options: Optional[Dict[str, Any]] = None) -> str:
    """
    Generate a hash from topic, credential_id, and group_id.
    Used to detect configuration changes.
    """
    raw = json.dumps([topic, credential_id, group_id, options or {}], sort_keys=True, default=str)
    return hashlib.md5(raw.encode()).hexdigest()


async def _build_desired_state(db) -> Dict[str, Dict[str, Any]]:
    """
    Fetch public workflows containing KafkaConsumer/KafkaTrigger nodes from the database.
    Return the desired configuration for each Kafka node.
    
    Returns:
        {node_id: {workflow_id, user_id, topic, group_id, credential_id, 
                    node_data, hash, ...}}
    """
    from sqlalchemy import select, text
    from app.models.workflow import Workflow

    desired: Dict[str, Dict[str, Any]] = {}

    kafka_stmt = select(Workflow).where(
        Workflow.is_public == True,
        text("""
            EXISTS (
                SELECT 1
                FROM jsonb_array_elements(workflows.flow_data->'nodes') AS node
                WHERE (node->>'type') IN ('KafkaConsumer', 'KafkaTrigger')
            )
        """)
    )
    result = await db.execute(kafka_stmt)
    kafka_workflows = result.scalars().all()

    for workflow in kafka_workflows:
        flow_data = workflow.flow_data
        if not flow_data or "nodes" not in flow_data:
            continue

        for node in flow_data.get("nodes", []):
            node_type = node.get("type", "")
            if node_type not in ("KafkaConsumer", "KafkaTrigger"):
                continue

            node_id = node.get("id")
            if not node_id:
                continue

            node_data = node.get("data", {})

            # Read configuration directly from node.data
            credential_id = get_kafka_node_value(node_data, "credential")
            topic = get_kafka_node_value(node_data, "topic")
            group_id = get_kafka_node_value(node_data, "group_id")

            if not topic or not credential_id:
                continue

            if not group_id:
                # Keep the legacy group prefix so existing deployments preserve
                # committed offsets during the product-name transition.
                group_id = f"kai-flow-{workflow.id}"

            # Collect optional settings
            options = {}
            optional_keys = [
                "auto_commit_interval_ms", "session_timeout_ms", "heartbeat_interval_ms",
                "fetch_min_bytes", "fetch_max_bytes", "read_messages_from_beginning",
                "retry_delay_on_error", "json_parse_message", "only_message",
                "return_headers", "keep_message_as_binary_data",
                # Additional parameters
                "allow_auto_create_topics", "auto_commit_threshold", "batch_size",
                "max_poll_records", "rebalance_timeout_ms",
                "max_concurrent_workflows", "max_workflow_attempts", "dead_letter_topic",
                "max_consecutive_failures",
            ]
            for key in optional_keys:
                value = get_kafka_node_value(node_data, key)
                if value is not None:
                    options[key] = value

            config_hash = _compute_config_hash(topic, str(credential_id), group_id, options)

            desired[node_id] = {
                "workflow_id": str(workflow.id),
                "user_id": str(workflow.user_id),
                "credential_id": credential_id,
                "topic": topic,
                "group_id": group_id,
                "options": options,
                "hash": config_hash,
            }

    return desired


def _build_actual_state() -> Dict[str, Dict[str, Any]]:
    """
    Return the status and configuration hash of active listeners from
    KafkaListenerService._listeners.
    """
    actual: Dict[str, Dict[str, Any]] = {}

    for lid, entry in KafkaListenerService._listeners.items():
        config = entry.get("config", {})
        status = entry.get("status", "unknown")

        # Calculate the hash from the current configuration
        config_hash = _compute_config_hash(
            config.get("topic", ""),
            str(config.get("credential_data", {}).get("credential_id", "")),
            config.get("group_id", ""),
            config.get("options", {}),
        )

        actual[lid] = {
            "status": status,
            "hash": config_hash,
            "config": config,
        }

    return actual


async def _start_from_desired(node_id: str, desired_entry: Dict[str, Any]):
    """
    Start a single listener from the desired state.
    Resolve its credential here.
    """
    from app.core.credential_provider import credential_provider

    cred_id = desired_entry["credential_id"]
    user_id = desired_entry["user_id"]
    topic = desired_entry["topic"]
    group_id = desired_entry["group_id"]
    workflow_id = desired_entry["workflow_id"]
    options = desired_entry.get("options", {})

    # Resolve the credential
    try:
        cred_uuid = uuid.UUID(str(cred_id))
        user_uuid = uuid.UUID(str(user_id))

        raw_credential = await credential_provider.get_credential(
            credential_id=cred_uuid,
            user_id=user_uuid,
        )

        if not raw_credential:
            logger.warning(
                f"Reconciliation: credential {cred_uuid} not found for node {node_id}; skipping"
            )
            return

        # Resolve the secret field
        if isinstance(raw_credential, dict):
            secret = raw_credential.get("secret", raw_credential)
            if isinstance(secret, str):
                try:
                    secret = json.loads(secret)
                except (json.JSONDecodeError, ValueError):
                    pass
            credential_data = secret if isinstance(secret, dict) else raw_credential
        elif hasattr(raw_credential, "secret"):
            credential_data = raw_credential.secret
            if isinstance(credential_data, str):
                try:
                    credential_data = json.loads(credential_data)
                except (json.JSONDecodeError, ValueError):
                    pass
        else:
            credential_data = raw_credential

        # Add credential_id to credential_data for stop_by_credential
        if isinstance(credential_data, dict):
            credential_data["credential_id"] = str(cred_id)

    except Exception as e:
        logger.error(f"Reconciliation: credential error for node {node_id}: {e}")
        return

    # Start the listener
    result = await KafkaListenerService.start_listener(
        listener_id=node_id,
        workflow_id=workflow_id,
        user_id=str(user_id),
        credential_data=credential_data,
        topic=topic,
        group_id=group_id,
        options=options,
    )

    logger.info(
        f"Reconciliation: listener started: node={node_id} topic={topic} status={result.get('status')}"
    )


kafka_reconciliation_wakeup = asyncio.Event()

async def kafka_reconciliation_loop(interval: int = KAFKA_RECONCILIATION_INTERVAL_SECONDS):
    """
    Periodic Kafka listener reconciliation loop.
    
    Every 'interval' seconds:
    1. Fetch the desired state from the database (public workflows with Kafka nodes).
    2. Inspect the actual state of active listeners.
    3. Calculate the difference: start missing listeners, stop extra listeners,
       and restart listeners whose configuration changed.
    4. Automatically recover listeners in a crash/error state.
    
    The main.py lifespan starts this loop with asyncio.create_task.
    It handles event-driven Kafka changes for save, visibility, and credentials.
    """
    from app.core.database import get_db_session_context

    logger.info(f"Kafka reconciliation loop started (interval={interval}s)")

    first_run = True

    while True:
        if not first_run:
            try:
                await asyncio.wait_for(kafka_reconciliation_wakeup.wait(), timeout=interval)
                kafka_reconciliation_wakeup.clear()
            except asyncio.TimeoutError:
                pass
        first_run = False

        try:
            # 1. Desired state: public workflows containing KafkaConsumer nodes
            async with get_db_session_context() as db:
                desired = await _build_desired_state(db)
            # Close the database session immediately to avoid pool pressure

            # 2. Actual state
            actual = _build_actual_state()

            # 3. Calculate differences
            desired_ids = set(desired.keys())
            actual_ids = set(actual.keys())

            to_start = desired_ids - actual_ids       # Desired but not active
            to_stop = actual_ids - desired_ids        # Active but no longer desired
            common = desired_ids & actual_ids         # Present in both states

            # Restart listeners whose configuration changed
            to_restart = {
                lid for lid in common
                if desired[lid]["hash"] != actual[lid].get("hash")
            }

            # Restart listeners in a crash/error/stopped state
            to_heal = {
                lid for lid in (common - to_restart)
                if actual[lid]["status"] in ("error", "stopped")
            }

            changes = len(to_start) + len(to_stop) + len(to_restart) + len(to_heal)

            if changes > 0:
                logger.info(
                    f"Reconciliation: start={len(to_start)} stop={len(to_stop)} "
                    f"restart={len(to_restart)} heal={len(to_heal)}"
                )

            # 4. Apply sequentially to avoid race conditions
            for lid in to_stop:
                logger.info(f"Reconciliation: stopping listener: {lid}")
                await KafkaListenerService.stop_listener(lid)

            for lid in to_restart:
                logger.info(f"Reconciliation: restarting listener after configuration change: {lid}")
                await KafkaListenerService.stop_listener(lid)
                await _start_from_desired(lid, desired[lid])

            for lid in to_heal:
                logger.info(f"Reconciliation: recovering listener from crash/error state: {lid}")
                await _start_from_desired(lid, desired[lid])

            for lid in to_start:
                await _start_from_desired(lid, desired[lid])

            if changes == 0:
                logger.debug(
                    f"Reconciliation: no changes "
                    f"(desired={len(desired_ids)}, actual={len(actual_ids)})"
                )

        except asyncio.CancelledError:
            logger.info("Kafka reconciliation loop cancelled during shutdown")
            break
        except Exception as e:
            logger.error(f"Reconciliation loop error: {e}", exc_info=True)

    logger.info("Kafka reconciliation loop ended")

# ══════════════════════════════════════════════════════════════════
# FastAPI Router — Kafka listener management endpoints
# ══════════════════════════════════════════════════════════════════

kafka_router = APIRouter(prefix=f"/{API_START}/{API_VERSION}/kafka")


@kafka_router.get("/listeners/{listener_id}/stream")
async def stream_kafka_listener_execution(listener_id: str):
    """Stream Kafka-triggered workflow execution events for the canvas UI."""

    async def event_stream():
        queue: asyncio.Queue = asyncio.Queue(maxsize=KAFKA_STREAM_MAX_QUEUE_LENGTH)
        kafka_execution_subscribers.setdefault(listener_id, []).append(queue)

        try:
            yield f"data: {json.dumps({'type': 'connected', 'listener_id': listener_id, 'timestamp': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"

            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
                except asyncio.TimeoutError:
                    yield f"data: {json.dumps({'type': 'ping', 'timestamp': datetime.now(timezone.utc).isoformat()}, ensure_ascii=False)}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            subscribers = kafka_execution_subscribers.get(listener_id, [])
            if queue in subscribers:
                subscribers.remove(queue)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "*",
        },
    )


@kafka_router.post("/listeners/{listener_id}/stop")
async def stop_kafka_listener(listener_id: str):
    """Stop a running Kafka consumer listener."""
    try:
        result = await KafkaListenerService.stop_listener(listener_id)
        return result
    except Exception as e:
        logger.error(f"Failed to stop listener: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop listener: {str(e)}",
        )


@kafka_router.post("/debug/{node_id}")
async def debug_kafka_single_message(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Debug mode: consume one message from Kafka and run the workflow once.
    Uses the same WorkflowExecutor pipeline as the Start node.
    """
    from app.core.credential_provider import credential_provider
    from app.services.workflow_executor import WorkflowExecutor, get_workflow_executor
    from app.models.workflow import Workflow
    from sqlalchemy import select as sa_select
    from app.core.json_utils import make_json_serializable

    # 1. Find the workflow with a JSONB query using node_id
    workflow = await find_kafka_workflow(db, node_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow containing Kafka node {node_id} was not found",
        )

    # Authorization check
    if workflow.user_id != current_user.id and not workflow.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Extract node configuration
    node_config = None
    for node in workflow.flow_data.get("nodes", []):
        if node.get("id") == node_id:
            node_config = node.get("data", {})
            break

    if not node_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Configuration for node {node_id} was not found",
        )

    topic = get_kafka_node_value(node_config, "topic")
    credential_id = get_kafka_node_value(node_config, "credential")
    if not topic or not credential_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic or credential is missing",
        )

    # 3. Resolve the credential
    try:
        raw_credential = await credential_provider.get_credential(
            credential_id=uuid.UUID(credential_id) if isinstance(credential_id, str) else credential_id,
            user_id=current_user.id,
        )
        if not raw_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential {credential_id} was not found",
            )

        if isinstance(raw_credential, dict):
            secret = raw_credential.get("secret", raw_credential)
            if isinstance(secret, str):
                try:
                    secret = json.loads(secret)
                except (json.JSONDecodeError, ValueError):
                    pass
            credential_data = secret if isinstance(secret, dict) else raw_credential
        elif hasattr(raw_credential, "secret"):
            credential_data = raw_credential.secret
            if isinstance(credential_data, str):
                try:
                    credential_data = json.loads(credential_data)
                except (json.JSONDecodeError, ValueError):
                    pass
        else:
            credential_data = raw_credential
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error while resolving credential: {str(e)}",
        )

    # 4. Create a temporary consumer and poll one message
    kafka_conf = get_kafka_config(credential_data)
    # Use a unique group_id in debug mode to avoid affecting the existing consumer group
    kafka_conf["group.id"] = f"kai-debug-{uuid.uuid4().hex[:8]}"
    kafka_conf["enable.auto.commit"] = False
    kafka_conf["auto.offset.reset"] = "latest"

    consumer = None
    message_data = None
    try:
        # Isolate blocking Consumer() and subscribe() C calls with asyncio.to_thread
        consumer = await asyncio.to_thread(Consumer, kafka_conf)
        await asyncio.to_thread(consumer.subscribe, [topic])
        logger.debug(f"Kafka: waiting for one message: topic={topic}, node={node_id}")

        # Wait up to 10 seconds for one message
        msg = await asyncio.to_thread(consumer.poll, 10.0)

        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"No message was received from topic '{topic}' within 10 seconds",
            )

        if msg.error():
            error_code = msg.error().code()
            if error_code == KafkaError._PARTITION_EOF:
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"Topic '{topic}' reached partition EOF; no new message is available",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Kafka error: {msg.error()}",
            )

        # Parse the message
        opts = {k: node_config.get(k) for k in ["json_parse_message", "only_message", "return_headers", "keep_message_as_binary_data"] if k in node_config}
        opts.setdefault("json_parse_message", True)
        opts.setdefault("return_headers", True)
        message_data = KafkaListenerService._parse_message(msg, opts)

        logger.debug(f"Kafka: message received: topic={msg.topic()} partition={msg.partition()} offset={msg.offset()}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[KAFKA DEBUG] Consumer error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kafka consumer error: {str(e)}",
        )
    finally:
        if consumer:
            try:
                await asyncio.to_thread(consumer.close)
            except Exception:
                pass

    # 5. Run the workflow with the existing WorkflowExecutor (same pipeline as Start node)
    kafka_input = ""
    if message_data:
        value = message_data.get("value", "")
        if isinstance(value, (dict, list)):
            kafka_input = json.dumps(value, ensure_ascii=False)
        else:
            kafka_input = str(value)

    execution_inputs = {
        "input": kafka_input,
        "input_text": kafka_input,
        "kafka_trigger": True,
        "kafka_data": message_data,
        "kafka_debug": True,
        "listener_id": node_id,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        executor = get_workflow_executor()

        ctx = await executor.prepare_execution_context(
            db=db,
            workflow=workflow,
            execution_inputs=execution_inputs,
            user=current_user,
            is_webhook=False,
            owner_id=workflow.user_id,
        )

        result_stream = await executor.execute_workflow(
            ctx=ctx,
            db=db,
            stream=True,
        )

        async def event_generator():
            try:
                if hasattr(result_stream, "__aiter__"):
                    async for chunk in result_stream:
                        try:
                            serialized = make_json_serializable(chunk)
                            yield f"data: {json.dumps(serialized, ensure_ascii=False)}\n\n"
                        except (TypeError, ValueError) as e:
                            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
                else:
                    # Non-streaming result
                    serialized = make_json_serializable(result_stream)
                    yield f"data: {json.dumps(serialized, ensure_ascii=False)}\n\n"
            except Exception as e:
                logger.error(f"[KAFKA DEBUG] Streaming error: {e}", exc_info=True)
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"

        return StreamingResponse(event_generator(), media_type="text/event-stream")

    except Exception as e:
        logger.error(f"[KAFKA DEBUG] Workflow execution failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Workflow execution failed: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════
# KafkaTriggerNode — Node definition
# ══════════════════════════════════════════════════════════════════

class KafkaTriggerNode(BaseNode):
    __doc__ = """
    Consumes messages from a Kafka topic and triggers the workflow.
    """
    
    name = "KafkaConsumer"
    description = "Triggers the workflow when a message is received from a Kafka topic."
    category = "Triggers"
    icon = {"name": "kafka", "path": "icons/kafka.svg", "alt": "Kafka"}
    
    metadata = NodeMetadata(
        name="KafkaConsumer",
        display_name="Kafka Consumer Trigger",
        description="Consumes messages from a Kafka topic and triggers the workflow.",
        node_type=NodeType.TERMINATOR,
        category="Triggers",
        icon={"name": "kafka", "path": "icons/kafka.svg", "alt": "Kafka"},
        colors=["green-500", "emerald-600"],
        inputs=[],
        outputs=[
            NodeOutput(
                name="kafka_data", 
                displayName="Kafka Data", 
                type="json", 
                description="The received Kafka message (value, key, topic, etc.)",
                is_connection=True
            ),
        ],
        properties=[
            # ── Required ──
            NodeProperty(
                name="credential", 
                displayName="Credential",
                type=NodePropertyType.CREDENTIAL_SELECT, 
                description="Client ID and Brokers configuration", 
                required=True,
                options=["Kafka"],
                serviceType="kafka"
            ),
            NodeProperty(
                name="topic", 
                displayName="Topic",
                type=NodePropertyType.TEXT, 
                description="Topic to listen to", 
                required=True
            ),
            NodeProperty(
                name="group_id", 
                displayName="Group ID",
                type=NodePropertyType.TEXT, 
                description="Consumer Group ID", 
                required=True
            ),
            # ── Optional ──
            NodeProperty(
                name="allow_auto_create_topics",
                displayName="Allow Topic Creation",
                type=NodePropertyType.CHECKBOX,
                description="Allow automatic topic creation on the broker",
                default=True,
                required=False
            ),
            NodeProperty(
                name="auto_commit_threshold",
                displayName="Auto Commit Threshold",
                type=NodePropertyType.NUMBER,
                description="Commit after N messages",
                default=1,
                required=False
            ),
            NodeProperty(
                name="auto_commit_interval_ms",
                displayName="Auto Commit Interval (ms)",
                type=NodePropertyType.NUMBER,
                description="Frequency of offset commits",
                default=5000,
                required=False
            ),
            NodeProperty(
                name="batch_size",
                displayName="Batch Size",
                type=NodePropertyType.NUMBER,
                description="Maximum number of bytes per batch",
                default=1048576,
                required=False
            ),
            NodeProperty(
                name="fetch_max_bytes",
                displayName="Fetch Max Bytes",
                type=NodePropertyType.NUMBER,
                description="Maximum bytes to fetch per request",
                default=52428800,
                required=False
            ),
            NodeProperty(
                name="fetch_min_bytes",
                displayName="Fetch Min Bytes",
                type=NodePropertyType.NUMBER,
                description="Minimum bytes to fetch per request",
                default=1,
                required=False
            ),
            NodeProperty(
                name="heartbeat_interval_ms", 
                displayName="Heartbeat Interval (ms)",
                type=NodePropertyType.NUMBER, 
                description="Heartbeat interval", 
                default=3000,
                required=False
            ),
            NodeProperty(
                name="max_poll_records",
                displayName="Max Number of Requests",
                type=NodePropertyType.NUMBER,
                description="Max number of records per poll",
                default=500,
                required=False
            ),
            NodeProperty(
                name="read_messages_from_beginning",
                displayName="Read Messages From Beginning",
                type=NodePropertyType.CHECKBOX,
                description="Read messages from the beginning of the topic",
                default=False,
                required=False
            ),

            NodeProperty(
                name="only_message",
                displayName="Only Message",
                type=NodePropertyType.CHECKBOX,
                description="Output only the message value",
                default=False,
                required=False
            ),
            NodeProperty(
                name="return_headers",
                displayName="Return Headers",
                type=NodePropertyType.CHECKBOX,
                description="Include headers in output",
                default=True,
                required=False
            ),
            NodeProperty(
                name="rebalance_timeout_ms",
                displayName="Rebalance Timeout (ms)",
                type=NodePropertyType.NUMBER,
                description="Timeout for rebalancing",
                default=60000,
                required=False
            ),
            NodeProperty(
                name="session_timeout_ms", 
                displayName="Session Timeout (ms)",
                type=NodePropertyType.NUMBER, 
                description="Session timeout", 
                default=45000,
                required=False
            ),

            NodeProperty(
                name="json_parse_message",
                displayName="JSON Parse Message",
                type=NodePropertyType.CHECKBOX,
                description="Attempt to parse message value as JSON",
                default=True,
                required=False
            ),
            NodeProperty(
                name="keep_message_as_binary_data",
                displayName="Keep Message as Binary Data",
                type=NodePropertyType.CHECKBOX,
                description="Keep original message as binary",
                default=False,
                required=False
            ),
            NodeProperty(
                name="retry_delay_on_error",
                displayName="Retry Delay on Error (ms)",
                type=NodePropertyType.NUMBER,
                description="Delay before retrying after error",
                default=1000,
                required=False
            ),
            NodeProperty(
                name="max_concurrent_workflows",
                displayName="Parallel Partitions",
                type=NodePropertyType.NUMBER,
                description="Maximum concurrent workflows across Kafka partitions (1-16); ordering within each partition is preserved",
                default=4,
                required=False
            ),
            NodeProperty(
                name="max_workflow_attempts",
                displayName="Workflow Attempts",
                type=NodePropertyType.NUMBER,
                description="Total attempts before sending a failed message to the dead-letter topic (1-10)",
                default=3,
                required=False
            ),
            NodeProperty(
                name="dead_letter_topic",
                displayName="Dead-Letter Topic",
                type=NodePropertyType.TEXT,
                description="Failed-message topic; defaults to the input topic plus .dlq. It must exist or broker auto-creation must be enabled.",
                required=False
            ),
            NodeProperty(
                name="max_consecutive_failures",
                displayName="Failure Circuit Limit",
                type=NodePropertyType.NUMBER,
                description="Stop this listener after N consecutive dead-lettered messages (1-100); default 5",
                default=5,
                required=False
            ),
        ]
    )

    def execute(self, inputs: Dict[str, Any], previous_node: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Execute the trigger node.
        When KafkaListenerService invokes it, inputs contains kafka_data.
        """
        kafka_data = inputs.get("kafka_data", {})

        # Support directly supplied message fields for backward compatibility
        if not kafka_data and inputs.get("value") is not None:
            kafka_data = {
                "value": inputs.get("value"),
                "key": inputs.get("key"),
                "topic": inputs.get("topic"),
                "partition": inputs.get("partition"),
                "offset": inputs.get("offset"),
                "headers": inputs.get("headers"),
                "timestamp": inputs.get("timestamp"),
            }

        return {
            "kafka_data": kafka_data,
            "output": kafka_data.get("value", inputs.get("initial_input", "Kafka trigger")),
        }
