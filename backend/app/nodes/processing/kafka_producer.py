
import json
import logging
from typing import Any, Dict, Optional
from confluent_kafka import Producer
from app.nodes.base import BaseNode, NodeType, NodeMetadata, NodeProperty, NodeInput, NodeOutput, NodePropertyType
from app.core.kafka_utils import get_kafka_config

logger = logging.getLogger(__name__)

class KafkaProducerNode(BaseNode):
    __doc__ = """
    Sends messages to a Kafka topic.
    """
    
    name = "KafkaProducer"
    description = "Sends a message to a Kafka topic using confluent-kafka."
    node_type = NodeType.PROCESSOR
    category = "Processing"
    icon = {"name": "kafka", "path": "icons/kafka.svg", "alt": "Kafka"} # Frontend expects this in public/icons
    
    metadata = NodeMetadata(
        name="KafkaProducer",
        display_name="Kafka Producer",
        description="Sends a message to a Kafka topic using confluent-kafka.",
        node_type=NodeType.PROCESSOR,
        category="Processing",
        icon={"name": "kafka", "path": "icons/kafka.svg", "alt": "Kafka"},
        colors=["orange-500", "rose-600"],
        inputs=[
            NodeInput(
                name="input", 
                type="any", 
                description="Message content (priority over property)", 
                required=False,
                is_connection=True
            ),
        ],
        outputs=[
            NodeOutput(
                name="output", 
                type="json", 
                description="Message delivery metadata (topic, partition, offset)",
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
                description="Target Kafka topic",
                required=True
            ),
            NodeProperty(
                name="message",
                displayName="Message",
                type=NodePropertyType.TEXT_AREA,
                description="Default message content if input socket is empty",
                required=True
            ),
            NodeProperty(
                name="key",
                displayName="Key",
                type=NodePropertyType.TEXT,
                description="Message key",
                required=False
            ),
            # ── Headers ──
            NodeProperty(
                name="header_key",
                displayName="Header Key",
                type=NodePropertyType.TEXT,
                description="Header key",
                required=False
            ),
            NodeProperty(
                name="header_value",
                displayName="Header Value",
                type=NodePropertyType.TEXT,
                description="Header value",
                required=False
            ),
            # ── Optional ──
            NodeProperty(
                name="acks", 
                displayName="Acks",
                type=NodePropertyType.CHECKBOX, 
                description="Enable acknowledgment assurance", 
                default=False,
                required=False
            ),
            NodeProperty(
                name="compression_type", 
                displayName="Compression",
                type=NodePropertyType.CHECKBOX, 
                description="Enable message compression", 
                default=False,
                required=False
            ),
            NodeProperty(
                name="json_encode",
                displayName="JSON Encode",
                type=NodePropertyType.CHECKBOX,
                description="Automatically wrap non-dict/list values in JSON (string -> 'string')",
                default=False,
                required=True
            ),
            NodeProperty(
                name="request_timeout_ms", 
                displayName="Timeout (ms)",
                type=NodePropertyType.NUMBER, 
                description="Request timeout", 
                default=30000,
                required=False
            ),
        ]
    )

    def execute(self, inputs: Dict[str, Any], connected_nodes: Dict[str, Any] = None, **kwargs) -> Dict[str, Any]:
        """
        Executes the Kafka Producer logic.
        """
        try:
            # 1. Configuration
            credential_id = inputs.get("credential")
            if not credential_id:
                raise ValueError("Kafka Credential is not selected. Please edit node settings and select a valid credential.")

            credential_data = self.get_credential(credential_id)
            if not credential_data:
                logger.error(f"Kafka Producer: Credential not found for ID {credential_id}")
                raise ValueError(f"Kafka credentials not found for ID {credential_id}. Please check your credentials.")

            # Extract actual secret if it's wrapped in the standard credential dict
            if isinstance(credential_data, dict) and "secret" in credential_data:
                credential_data = credential_data["secret"]

            producer_config = get_kafka_config(credential_data)
            
            if not producer_config.get("bootstrap.servers"):
                logger.error(f"Kafka Producer: No bootstrap.servers found in credential data.")
                raise ValueError("Kafka configuration error: Selected credential does not contain bootstrap.servers.")

            # Optional settings
            acks = inputs.get("acks")
            if acks:
                producer_config["acks"] = "all" if acks is True else str(acks)
            
            compression = inputs.get("compression_type")
            if compression is True:
                producer_config["compression.type"] = "gzip" 
            elif compression and compression != "none":
                producer_config["compression.type"] = compression
            
            producer_config["message.timeout.ms"] = int(inputs.get("request_timeout_ms", 30000))
            
            # 2. Initialize Producer
            producer = Producer(producer_config)

            # 3. Prepare Message
            topic = inputs.get("topic")
            if not topic:
                 raise ValueError("Kafka Topic is required. Please enter a topic in node settings.")
                 
            # Message priority: Input Socket > Property
            message = inputs.get("message")
            if message is None or (isinstance(message, str) and not message.strip()):
                # If message is empty/None, use property if available
                # Wait, 'inputs.get("message")' already covers both if names match.
                # However, if both are empty, we should probably warn.
                logger.warning("Kafka Producer: Message is empty.")

            key = inputs.get("key")
            json_encode = inputs.get("json_encode", False)
            
            # Headers
            headers = {}
            if inputs.get("header_key"):
                headers[str(inputs.get("header_key"))] = str(inputs.get("header_value", ""))

            # 4. Prepare values (Encoding logic)
            value_bytes = None
            if message is not None:
                if isinstance(message, (dict, list)):
                    value_bytes = json.dumps(message).encode('utf-8')
                elif json_encode:
                    # Force JSON encoding (e.g. string "Hello" -> b'"Hello"')
                    value_bytes = json.dumps(message).encode('utf-8')
                elif isinstance(message, str):
                    value_bytes = message.encode('utf-8')
                else:
                    value_bytes = str(message).encode('utf-8')
                
            key_bytes = key.encode('utf-8') if key else None
            
            if value_bytes is None:
                logger.warning("Kafka Producer: Sending empty (None) message value.")
            
            # 4. Define Callback
            delivery_report = {}
            error_container = {}

            def acked(err, msg):
                if err is not None:
                    error_container["error"] = str(err)
                else:
                    delivery_report.update({
                        "topic": msg.topic(),
                        "partition": msg.partition(),
                        "offset": msg.offset()
                    })

            # 5. Send Message
            producer.produce(
                topic, 
                value=value_bytes, 
                key=key_bytes, 
                headers=headers if isinstance(headers, dict) else None,
                callback=acked
            )
            
            # 6. Flush (Blocking wait for delivery)
            # This makes the node synchronous (Processor behavior)
            producer.flush(timeout=producer_config["message.timeout.ms"] / 1000)
            
            if "error" in error_container:
                raise Exception(f"Kafka Error: {error_container['error']}")
            
            logger.info(f"Kafka message sent to {topic} [{delivery_report.get('partition')}] @ {delivery_report.get('offset')}")

            return {
                "metadata": delivery_report,
                "message": message,
                "key": key,
                "topic": topic,
                "headers": headers,
                "inputs": inputs
            }

        except Exception as e:
            logger.error(f"Kafka Producer Error: {e}")
            raise e
