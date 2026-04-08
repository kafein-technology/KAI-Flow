
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, status, Depends
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from confluent_kafka import Consumer, KafkaError, KafkaException

from app.core.database import get_db_session
from app.auth.dependencies import get_current_user
from app.models.user import User
from sqlalchemy.ext.asyncio import AsyncSession

from app.nodes.base import BaseNode, NodeType, NodeMetadata, NodeProperty, NodeInput, NodeOutput, NodePropertyType
from app.core.kafka_utils import get_kafka_config
from app.core.constants import API_START, API_VERSION

logger = logging.getLogger(__name__)

# Kafka reconciliation loop execution interval (seconds)
KAFKA_RECONCILIATION_INTERVAL_SECONDS = 60


# ══════════════════════════════════════════════════════════════════
# DB Lookup — Find workflow containing a KafkaConsumer trigger node
# ══════════════════════════════════════════════════════════════════

async def find_kafka_workflow(db, listener_id: str):
    """
    Verilen listener_id (node ID) ile eşleşen KafkaConsumer node'u içeren
    workflow'u JSONB sorgusuyla bulur.
    
    webhook_trigger.py'deki find_workflow() kalıbını takip eder.
    """
    from sqlalchemy import select, text
    from sqlalchemy.sql import bindparam
    from app.models.workflow import Workflow

    try:
        logger.info(f"Kafka workflow araniyor: listener_id={listener_id}")

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
                logger.warning(f"Birden fazla workflow bulundu listener_id={listener_id}, ilki kullanılıyor")
            workflow = workflows[0]
            logger.info(f"Kafka workflow bulundu: {workflow.id} ({workflow.name})")
            return workflow

        logger.warning(f"Kafka workflow bulunamadı: listener_id={listener_id}")
        return None

    except Exception as e:
        logger.error(f"Kafka workflow aranırken hata: {e}", exc_info=True)
        return None


# ══════════════════════════════════════════════════════════════════
# KafkaListenerService — Arka plan Kafka tüketici yöneticisi
# ══════════════════════════════════════════════════════════════════

class KafkaListenerService:
    """
    İş akışı bazında Kafka consumer arka plan görevlerini yönetir.
    
    Her listener_id (canvas üzerindeki node ID) için ayrı bir asyncio task
    oluşturur. Task, confluent_kafka.Consumer ile mesaj poll'lar ve her mesajda
    WorkflowExecutor aracılığıyla iş akışını tetikler.
    """

    _listeners: Dict[str, Dict[str, Any]] = {}

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
        """Belirtilen yapılandırma ile Kafka consumer başlatır."""

        if listener_id in cls._listeners:
            existing = cls._listeners[listener_id]
            if existing.get("status") == "running":
                return {
                    "status": "already_running",
                    "listener_id": listener_id,
                    "message": "Bu listener zaten çalışıyor.",
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

        # Listener kaydını oluştur
        cls._listeners[listener_id] = {
            "config": config,
            "status": "starting",
            "started_at": datetime.now(timezone.utc).isoformat(),
            "stats": {
                "messages_received": 0,
                "workflows_triggered": 0,
                "errors": 0,
                "last_message_at": None,
                "last_error": None,
            },
            "task": None,
        }

        # Arka plan görevini başlat
        task = asyncio.create_task(cls._consumer_loop(listener_id))
        cls._listeners[listener_id]["task"] = task
        cls._listeners[listener_id]["status"] = "running"

        logger.info(f"Kafka listener başlatıldı: {listener_id} topic={topic} group={group_id}")

        return {
            "status": "started",
            "listener_id": listener_id,
            "topic": topic,
            "group_id": group_id,
        }

    @classmethod
    async def stop_listener(cls, listener_id: str) -> dict:
        """Çalışan bir Kafka consumer'ı durdurur ve kayıt temizler."""

        if listener_id not in cls._listeners:
            return {"status": "not_found", "listener_id": listener_id}

        entry = cls._listeners[listener_id]
        entry["status"] = "stopping"

        task = entry.get("task")
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(asyncio.shield(task), timeout=10)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        # Memory leak fix: stopped listener'ı dict'ten sil
        del cls._listeners[listener_id]

        logger.info(f"Kafka listener durduruldu ve temizlendi: {listener_id}")

        return {"status": "stopped", "listener_id": listener_id}

    @classmethod
    def get_listener_status(cls, listener_id: str) -> Optional[dict]:
        """Belirli bir listener'ın durumunu döner."""
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
        """Tüm listener'ların durumunu döner."""
        return [
            cls.get_listener_status(lid)
            for lid in cls._listeners
        ]

    @classmethod
    async def stop_listeners_by_credential(cls, credential_id: str):
        """Belirli bir credential kullanan tüm listener'ları durdurur."""
        listeners_to_stop = []
        for lid, entry in cls._listeners.items():
            config = entry.get("config", {})
            cred_data = config.get("credential_data", {})
            # credential_id string olarak karşılaştır
            if str(cred_data.get("credential_id", "")) == credential_id:
                listeners_to_stop.append(lid)

        results = []
        for lid in listeners_to_stop:
            result = await cls.stop_listener(lid)
            results.append(result)
            logger.info(f"Credential {credential_id} için listener durduruldu: {lid}")

        return results

    # ──────────────────────────────────────────────
    # Arka plan tüketici döngüsü
    # ──────────────────────────────────────────────

    @classmethod
    async def _consumer_loop(cls, listener_id: str):
        """
        confluent_kafka.Consumer ile mesaj dinler.
        poll() bloklayıcı olduğu için asyncio.to_thread() ile sarmalanır.
        """
        entry = cls._listeners[listener_id]
        config = entry["config"]
        stats = entry["stats"]
        opts = config["options"]

        # confluent-kafka yapılandırması
        kafka_conf = get_kafka_config(config["credential_data"])
        kafka_conf["group.id"] = config["group_id"]
        kafka_conf["session.timeout.ms"] = opts.get("session_timeout_ms", 45000)
        kafka_conf["heartbeat.interval.ms"] = opts.get("heartbeat_interval_ms", 3000)
        kafka_conf["fetch.min.bytes"] = opts.get("fetch_min_bytes", 1)
        kafka_conf["fetch.max.bytes"] = opts.get("fetch_max_bytes", 52428800)

        # allow_auto_create_topics: Broker'da topic yoksa otomatik oluşturulsun mu
        kafka_conf["allow.auto.create.topics"] = opts.get("allow_auto_create_topics", True)

        # batch_size: Partition başına max fetch boyutu (bytes)
        kafka_conf["max.partition.fetch.bytes"] = opts.get("batch_size", 1048576)

        # rebalance_timeout_ms: Consumer group rebalance zaman aşımı
        kafka_conf["max.poll.interval.ms"] = opts.get("rebalance_timeout_ms", 300000)

        # auto_commit_threshold: N mesaj sonra manuel commit
        # threshold <= 1 → otomatik commit (varsayılan davranış)
        # threshold > 1  → otomatik commit kapatılır, N mesajda bir commit yapılır
        commit_threshold = opts.get("auto_commit_threshold", 1)
        if commit_threshold and commit_threshold > 1:
            kafka_conf["enable.auto.commit"] = False
            logger.info(f"Manuel commit aktif: her {commit_threshold} mesajda (listener={listener_id})")
        else:
            kafka_conf["enable.auto.commit"] = True
            kafka_conf["auto.commit.interval.ms"] = opts.get("auto_commit_interval_ms", 5000)
            commit_threshold = 0  # Manuel commit devre dışı

        # max_poll_records: Döngü başına işlenecek max mesaj sayısı
        max_poll_records = opts.get("max_poll_records", 500)

        # Baştan oku ayarı
        if opts.get("read_messages_from_beginning", False):
            kafka_conf["auto.offset.reset"] = "earliest"
        else:
            kafka_conf["auto.offset.reset"] = "latest"

        logger.info(f"Kafka consumer config: servers={kafka_conf.get('bootstrap.servers')}, group={kafka_conf.get('group.id')}, topic={config['topic']}")
        logger.debug(f"Kafka consumer full config: {kafka_conf}")

        consumer = None
        retry_delay = opts.get("retry_delay_on_error", 1000) / 1000.0  # ms → s

        try:
            # Consumer() ve subscribe() bloklayıcı C kütüphanesi çağrılarıdır.
            # Kafka broker ulaşılamaz olduğunda event loop'u 45sn boyunca dondurur.
            # Bu yüzden asyncio.to_thread() ile izole ediyoruz.
            consumer = await asyncio.to_thread(Consumer, kafka_conf)
            await asyncio.to_thread(consumer.subscribe, [config["topic"]])
            logger.info(f"Kafka consumer topic'e abone oldu: {config['topic']} (listener={listener_id})")

            # Manuel commit sayacı
            _commit_counter = 0

            while entry["status"] == "running":
                try:
                    # Bloklayıcı poll'u thread pool'da çalıştır
                    msg = await asyncio.to_thread(consumer.poll, 1.0)

                    if msg is None:
                        continue

                    if msg.error():
                        error_code = msg.error().code()
                        if error_code == KafkaError._PARTITION_EOF:
                            logger.debug(f"Partition sonu: {msg.topic()}[{msg.partition()}]")
                            continue
                        else:
                            error_str = str(msg.error())
                            logger.error(f"Kafka hata: {error_str}")
                            stats["errors"] += 1
                            stats["last_error"] = error_str
                            await asyncio.sleep(retry_delay)
                            continue

                    # ── Mesaj başarıyla alındı ──
                    stats["messages_received"] += 1
                    stats["last_message_at"] = datetime.now(timezone.utc).isoformat()

                    # Mesaj verisini hazırla
                    message_data = cls._parse_message(msg, opts)

                    logger.info(
                        f"Kafka mesaj alındı: topic={msg.topic()} "
                        f"partition={msg.partition()} offset={msg.offset()} "
                        f"(listener={listener_id})"
                    )

                    # İş akışını tetikle
                    try:
                        await cls._trigger_workflow(listener_id, message_data)
                        stats["workflows_triggered"] += 1
                    except Exception as e:
                        logger.error(f"Error while triggering workflow: {e}", exc_info=True)
                        stats["errors"] += 1
                        stats["last_error"] = str(e)
                        stats["last_error_at"] = datetime.now(timezone.utc).isoformat()

                    # auto_commit_threshold: N mesajda bir manuel commit
                    if commit_threshold > 1:
                        _commit_counter += 1
                        if _commit_counter >= commit_threshold:
                            try:
                                await asyncio.to_thread(consumer.commit, asynchronous=False)
                                logger.debug(f"Manuel commit yapıldı: {_commit_counter} mesaj (listener={listener_id})")
                            except Exception as ce:
                                logger.warning(f"Manuel commit hatası: {ce}")
                            _commit_counter = 0

                    # max_poll_records: Döngü başına mesaj limiti
                    if stats["messages_received"] % max_poll_records == 0:
                        await asyncio.sleep(0)  # Event loop'a kontrol ver

                except asyncio.CancelledError:
                    logger.info(f"Kafka consumer iptal edildi: {listener_id}")
                    break
                except Exception as e:
                    logger.error(f"Consumer loop hatası: {e}", exc_info=True)
                    stats["errors"] += 1
                    stats["last_error"] = str(e)
                    await asyncio.sleep(retry_delay)

        except asyncio.CancelledError:
            logger.info(f"Kafka consumer görevi iptal edildi: {listener_id}")
        except KafkaException as e:
            logger.error(f"Kafka bağlantı hatası: {e}", exc_info=True)
            stats["errors"] += 1
            stats["last_error"] = str(e)
            entry["status"] = "error"
        except Exception as e:
            logger.error(f"Beklenmeyen consumer hatası: {e}", exc_info=True)
            stats["errors"] += 1
            stats["last_error"] = str(e)
            entry["status"] = "error"
        finally:
            if consumer:
                try:
                    await asyncio.to_thread(consumer.close)
                    logger.info(f"Kafka consumer kapatıldı: {listener_id}")
                except Exception as e:
                    logger.warning(f"Consumer kapatılırken hata: {e}")

            if entry["status"] == "running":
                entry["status"] = "stopped"

    @staticmethod
    def _parse_message(msg, opts: dict) -> dict:
        """Kafka mesajını dict'e dönüştürür."""
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

        # only_message seçeneği: sadece value döndür
        if opts.get("only_message", False):
            return {"value": value}

        return data

    @classmethod
    async def _trigger_workflow(cls, listener_id: str, message_data: dict):
        """
        Kafka mesajı geldiğinde ilgili iş akışını çalıştırır.
        Kafka trigger bağımsız bir node'dur — webhook değildir.
        Workflow sahibinin User objesi doğrudan yüklenir.
        """
        from app.core.database import get_db_session_context
        from app.services.workflow_executor import WorkflowExecutor
        from app.models.workflow import Workflow
        from app.models.user import User
        from sqlalchemy import select

        entry = cls._listeners.get(listener_id)
        if not entry:
            logger.error(f"Listener bulunamadı: {listener_id}")
            return

        config = entry["config"]
        workflow_id = config.get("workflow_id")

        if not workflow_id:
            logger.error(f"Listener config'de workflow_id bulunamadı: {listener_id}")
            return

        logger.info(f"Kafka trigger: workflow yükleniyor workflow_id={workflow_id}, listener={listener_id}")

        async with get_db_session_context() as db:
            # Workflow'u doğrudan ID ile yükle
            stmt = select(Workflow).where(Workflow.id == workflow_id)
            result = await db.execute(stmt)
            workflow = result.scalar_one_or_none()

            if not workflow:
                logger.error(f"Workflow bulunamadı: workflow_id={workflow_id}, listener={listener_id}")
                return

            # Workflow sahibini yükle (credential erişimi için)
            user_stmt = select(User).where(User.id == workflow.user_id)
            user_result = await db.execute(user_stmt)
            owner = user_result.scalar_one_or_none()

            if not owner:
                logger.error(f"Workflow sahibi bulunamadı: user_id={workflow.user_id}, workflow={workflow_id}")
                return

            logger.info(f"Kafka trigger: workflow bulundu {workflow.name} (id={workflow.id}, owner={owner.email})")

            # Kafka mesaj verisini hazırla
            kafka_input = ""
            if message_data:
                value = message_data.get("value", "")
                if isinstance(value, (dict, list)):
                    kafka_input = json.dumps(value, ensure_ascii=False)
                else:
                    kafka_input = str(value)

            if not kafka_input:
                kafka_input = f"Kafka triggered: {listener_id}"

            # Execution girdilerini hazırla
            execution_inputs = {
                "input": kafka_input,                    # Start node uyumluluğu
                "input_text": kafka_input,               # Geriye uyumluluk
                "kafka_trigger": True,
                "kafka_data": message_data,              # Tam mesaj verisi
                "listener_id": listener_id,
                "triggered_at": datetime.now(timezone.utc).isoformat(),
            }

            logger.info(f"Kafka trigger: workflow çalıştırılıyor inputs={list(execution_inputs.keys())}")

            # WorkflowExecutor ile çalıştır — workflow sahibi doğrudan geçiriliyor
            executor = WorkflowExecutor()

            ctx = await executor.prepare_execution_context(
                db=db,
                workflow=workflow,
                execution_inputs=execution_inputs,
                user=owner,            # Workflow sahibi doğrudan
                is_webhook=False,      # Kafka trigger webhook değil
            )

            result = await executor.execute_workflow(
                ctx=ctx,
                db=db,
                stream=False,
            )

            # Check execution result for errors
            if isinstance(result, dict):
                # Check explicit success flag
                if result.get("success") is False:
                    error_msg = result.get("error", "Unknown workflow error")
                    logger.error(
                        f"Kafka-triggered workflow completed with ERROR: "
                        f"workflow={workflow.id} listener={listener_id} "
                        f"execution={ctx.execution_id} error={error_msg}"
                    )
                    raise RuntimeError(f"Workflow execution failed: {error_msg}")
                
                # Check state-level errors
                state_data = result.get("state", {})
                if isinstance(state_data, dict):
                    state_errors = state_data.get("errors", [])
                    if state_errors:
                        error_msg = "; ".join(str(e) for e in state_errors)
                        logger.error(
                            f"Kafka-triggered workflow state errors: "
                            f"workflow={workflow.id} listener={listener_id} "
                            f"execution={ctx.execution_id} errors={error_msg}"
                        )
                        raise RuntimeError(f"Workflow completed with errors: {error_msg}")
                
                # Check node_outputs for errors
                node_outputs = (
                    state_data.get("node_outputs", {})
                    if isinstance(state_data, dict)
                    else result.get("node_outputs", {})
                )
                if isinstance(node_outputs, dict):
                    for nid, nout in node_outputs.items():
                        if isinstance(nout, dict) and nout.get("error"):
                            error_msg = f"Node {nid} failed: {nout['error']}"
                            logger.error(
                                f"Kafka-triggered workflow node error: "
                                f"workflow={workflow.id} listener={listener_id} error={error_msg}"
                            )
                            raise RuntimeError(error_msg)

            logger.info(
                f"Kafka-triggered workflow completed: "
                f"workflow={workflow.id} listener={listener_id} "
                f"execution={ctx.execution_id}"
            )

            return result


# ══════════════════════════════════════════════════════════════════
# Reconciliation Loop — Periyodik Kafka listener senkronizasyonu
# ══════════════════════════════════════════════════════════════════

import hashlib


def _compute_config_hash(topic: str, credential_id: str, group_id: str) -> str:
    """
    Topic, credential_id ve group_id'den hash üretir.
    Config değişikliği tespiti için kullanılır.
    """
    raw = f"{topic}|{credential_id}|{group_id}"
    return hashlib.md5(raw.encode()).hexdigest()


async def _build_desired_state(db) -> Dict[str, Dict[str, Any]]:
    """
    DB'den public + KafkaConsumer/KafkaTrigger node'lu workflow'ları çeker.
    Her Kafka node için istenen config'i döner.
    
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

            # Config çıkar: doğrudan node.data'dan
            credential_id = node_data.get("credential")
            topic = node_data.get("topic")
            group_id = node_data.get("group_id")

            # Fallback: metadata.properties'den
            if not topic or not credential_id:
                metadata_props = node_data.get("metadata", {}).get("properties", [])
                if isinstance(metadata_props, list):
                    for prop in metadata_props:
                        if isinstance(prop, dict) and "name" in prop:
                            prop_name = prop["name"]
                            prop_value = prop.get("value", prop.get("default"))
                            if prop_name == "topic" and not topic and prop_value:
                                topic = prop_value
                            elif prop_name == "credential" and not credential_id and prop_value:
                                credential_id = prop_value
                            elif prop_name == "group_id" and not group_id and prop_value:
                                group_id = prop_value

            if not topic or not credential_id:
                continue

            if not group_id:
                group_id = f"kai-fusion-{workflow.id}"

            # Opsiyonel ayarları topla
            options = {}
            optional_keys = [
                "auto_commit_interval_ms", "session_timeout_ms", "heartbeat_interval_ms",
                "fetch_min_bytes", "fetch_max_bytes", "read_messages_from_beginning",
                "retry_delay_on_error", "json_parse_message", "only_message",
                "return_headers", "keep_message_as_binary_data",
                # Yeni eklenen parametreler
                "allow_auto_create_topics", "auto_commit_threshold", "batch_size",
                "max_poll_records", "rebalance_timeout_ms",
            ]
            for key in optional_keys:
                if key in node_data:
                    options[key] = node_data[key]

            config_hash = _compute_config_hash(topic, str(credential_id), group_id)

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
    KafkaListenerService._listeners dict'inden çalışan listener'ların
    durumunu ve config hash'ini döner.
    """
    actual: Dict[str, Dict[str, Any]] = {}

    for lid, entry in KafkaListenerService._listeners.items():
        config = entry.get("config", {})
        status = entry.get("status", "unknown")

        # Mevcut config'den hash hesapla
        config_hash = _compute_config_hash(
            config.get("topic", ""),
            str(config.get("credential_data", {}).get("credential_id", "")),
            config.get("group_id", ""),
        )

        actual[lid] = {
            "status": status,
            "hash": config_hash,
            "config": config,
        }

    return actual


async def _start_from_desired(node_id: str, desired_entry: Dict[str, Any]):
    """
    Desired state'ten tek bir listener başlatır.
    Credential çözümlemesini burada yapar.
    """
    from app.core.credential_provider import credential_provider

    cred_id = desired_entry["credential_id"]
    user_id = desired_entry["user_id"]
    topic = desired_entry["topic"]
    group_id = desired_entry["group_id"]
    workflow_id = desired_entry["workflow_id"]
    options = desired_entry.get("options", {})

    # Credential çöz
    try:
        cred_uuid = uuid.UUID(str(cred_id))
        user_uuid = uuid.UUID(str(user_id))

        raw_credential = await credential_provider.get_credential(
            credential_id=cred_uuid,
            user_id=user_uuid,
        )

        if not raw_credential:
            logger.warning(
                f"Reconciliation: node {node_id} credential {cred_uuid} bulunamadı, atlanıyor."
            )
            return

        # Secret alanını çöz
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

        # credential_id'yi credential_data'ya ekle (stop_by_credential için)
        if isinstance(credential_data, dict):
            credential_data["credential_id"] = str(cred_id)

    except Exception as e:
        logger.error(f"Reconciliation: node {node_id} credential hatası: {e}")
        return

    # Listener başlat
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
        f"Reconciliation: listener başlatıldı: node={node_id} topic={topic} → {result.get('status')}"
    )


async def kafka_reconciliation_loop(interval: int = KAFKA_RECONCILIATION_INTERVAL_SECONDS):
    """
    Periyodik Kafka listener reconciliation döngüsü.
    
    Her 'interval' saniyede:
    1. DB'den istenen durumu çeker (public + Kafka node'lu workflow'lar)
    2. Çalışan listener'ların gerçek durumunu kontrol eder
    3. Farkı hesaplar: eksik → başlat, fazla → durdur, config değişen → restart
    4. Crash/error olan listener'ları otomatik iyileştirir
    
    Bu döngü main.py lifespan'da asyncio.create_task ile başlatılır.
    Tüm event-driven Kafka yönetimini (save, visibility, credential) değiştirir.
    """
    from app.core.database import get_db_session_context

    logger.info(f"Kafka reconciliation loop başlatıldı (interval={interval}s)")

    first_run = True

    while True:
        if not first_run:
            await asyncio.sleep(interval)
        first_run = False

        try:
            # 1. İstenen durum: public + KafkaConsumer node'lu workflow'lar
            async with get_db_session_context() as db:
                desired = await _build_desired_state(db)
            # DB session HEMEN kapanıyor — pool baskısı yok

            # 2. Gerçek durum
            actual = _build_actual_state()

            # 3. Fark hesapla
            desired_ids = set(desired.keys())
            actual_ids = set(actual.keys())

            to_start = desired_ids - actual_ids       # Olması gerekip olmayan
            to_stop = actual_ids - desired_ids         # Olmaması gerekip olan
            common = desired_ids & actual_ids          # Her ikisinde de olan

            # Config değişenler → restart
            to_restart = {
                lid for lid in common
                if desired[lid]["hash"] != actual[lid].get("hash")
            }

            # Crash/error/stopped olanlar → yeniden başlat
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

            # 4. SIRALI uygula — race condition yok
            for lid in to_stop:
                logger.info(f"Reconciliation: listener durduruluyor: {lid}")
                await KafkaListenerService.stop_listener(lid)

            for lid in to_restart:
                logger.info(f"Reconciliation: listener yeniden başlatılıyor (config değişti): {lid}")
                await KafkaListenerService.stop_listener(lid)
                await _start_from_desired(lid, desired[lid])

            for lid in to_heal:
                logger.info(f"Reconciliation: listener iyileştiriliyor (crash/error): {lid}")
                await _start_from_desired(lid, desired[lid])

            for lid in to_start:
                await _start_from_desired(lid, desired[lid])

            if changes == 0:
                logger.debug(
                    f"Reconciliation: değişiklik yok "
                    f"(desired={len(desired_ids)}, actual={len(actual_ids)})"
                )

        except asyncio.CancelledError:
            logger.info("Kafka reconciliation loop iptal edildi (shutdown)")
            break
        except Exception as e:
            logger.error(f"Reconciliation döngüsü hatası: {e}", exc_info=True)

    logger.info("Kafka reconciliation loop sonlandı")

# ══════════════════════════════════════════════════════════════════
# FastAPI Router — Kafka listener yönetim endpointleri
# ══════════════════════════════════════════════════════════════════

kafka_router = APIRouter(prefix=f"/{API_START}/{API_VERSION}/kafka")


@kafka_router.post("/listeners/{listener_id}/stop")
async def stop_kafka_listener(listener_id: str):
    """Çalışan Kafka consumer listener'ı durdurur."""
    try:
        result = await KafkaListenerService.stop_listener(listener_id)
        return result
    except Exception as e:
        logger.error(f"Listener durdurulamadı: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Listener durdurulamadı: {str(e)}",
        )


@kafka_router.post("/debug/{node_id}")
async def debug_kafka_single_message(
    node_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """
    Debug modu: Kafka'dan TEK mesaj çeker ve workflow'u bir kez çalıştırır.
    Start node'un kullandığı aynı WorkflowExecutor pipeline'ını kullanır.
    """
    from app.core.credential_provider import credential_provider
    from app.services.workflow_executor import WorkflowExecutor, get_workflow_executor
    from app.models.workflow import Workflow
    from sqlalchemy import select as sa_select
    from app.core.json_utils import make_json_serializable

    # 1. Workflow'u bul (node_id ile JSONB sorgusu)
    workflow = await find_kafka_workflow(db, node_id)
    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Kafka node {node_id} içeren workflow bulunamadı",
        )

    # Yetki kontrolü
    if workflow.user_id != current_user.id and not workflow.is_public:
        raise HTTPException(status_code=403, detail="Access denied")

    # 2. Node config'ini çıkar
    node_config = None
    for node in workflow.flow_data.get("nodes", []):
        if node.get("id") == node_id:
            node_config = node.get("data", {})
            break

    if not node_config:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {node_id} config bulunamadı",
        )

    topic = node_config.get("topic")
    credential_id = node_config.get("credential")
    group_id = node_config.get("group_id", f"kai-debug-{uuid.uuid4().hex[:8]}")

    if not topic or not credential_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Topic veya credential eksik",
        )

    # 3. Credential'ı çöz
    try:
        raw_credential = await credential_provider.get_credential(
            credential_id=uuid.UUID(credential_id) if isinstance(credential_id, str) else credential_id,
            user_id=current_user.id,
        )
        if not raw_credential:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Credential {credential_id} bulunamadı",
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
            detail=f"Credential çözümlenirken hata: {str(e)}",
        )

    # 4. Geçici consumer oluştur ve 1 mesaj poll et
    kafka_conf = get_kafka_config(credential_data)
    # Debug için benzersiz group_id — mevcut consumer group'u etkilememek için
    kafka_conf["group.id"] = f"kai-debug-{uuid.uuid4().hex[:8]}"
    kafka_conf["enable.auto.commit"] = False
    kafka_conf["auto.offset.reset"] = "latest"

    consumer = None
    message_data = None
    try:
        # Consumer() ve subscribe() bloklayıcı C calls — asyncio.to_thread ile izole et
        consumer = await asyncio.to_thread(Consumer, kafka_conf)
        await asyncio.to_thread(consumer.subscribe, [topic])
        logger.info(f"[KAFKA DEBUG] Tek mesaj bekleniyor: topic={topic}, node={node_id}")

        # 10 saniye timeout ile tek mesaj bekle
        msg = await asyncio.to_thread(consumer.poll, 10.0)

        if msg is None:
            raise HTTPException(
                status_code=status.HTTP_408_REQUEST_TIMEOUT,
                detail=f"10 saniye içinde topic '{topic}' üzerinden mesaj gelmedi",
            )

        if msg.error():
            error_code = msg.error().code()
            if error_code == KafkaError._PARTITION_EOF:
                raise HTTPException(
                    status_code=status.HTTP_408_REQUEST_TIMEOUT,
                    detail=f"Topic '{topic}' partition sonuna ulaşıldı, yeni mesaj yok",
                )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Kafka hatası: {msg.error()}",
            )

        # Mesajı parse et
        opts = {k: node_config.get(k) for k in ["json_parse_message", "only_message", "return_headers", "keep_message_as_binary_data"] if k in node_config}
        opts.setdefault("json_parse_message", True)
        opts.setdefault("return_headers", True)
        message_data = KafkaListenerService._parse_message(msg, opts)

        logger.info(f"[KAFKA DEBUG] Mesaj alındı: topic={msg.topic()} partition={msg.partition()} offset={msg.offset()}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[KAFKA DEBUG] Consumer hatası: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Kafka consumer hatası: {str(e)}",
        )
    finally:
        if consumer:
            try:
                await asyncio.to_thread(consumer.close)
            except Exception:
                pass

    # 5. Mevcut WorkflowExecutor ile workflow'u çalıştır (Start node ile aynı pipeline)
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
            detail=f"Workflow çalıştırılamadı: {str(e)}",
        )


# ══════════════════════════════════════════════════════════════════
# KafkaTriggerNode — Node tanımı
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
        ]
    )

    def execute(self, inputs: Dict[str, Any], previous_node: Any = None, **kwargs) -> Dict[str, Any]:
        """
        Trigger node execute metodu.
        KafkaListenerService tarafından tetiklendiğinde, inputs içinde
        kafka_data mesaj verisi bulunur.
        """
        kafka_data = inputs.get("kafka_data", {})

        # Eğer doğrudan mesaj alanları gönderildiyse (geriye uyumluluk)
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
