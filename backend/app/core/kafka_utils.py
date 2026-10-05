
def get_kafka_node_value(node_data: dict, name: str):
    """Read a saved Kafka setting from the supported workflow node layouts."""
    required_reference = name in {"credential", "topic", "group_id"}
    if name in node_data and node_data[name] is not None and (not required_reference or node_data[name]):
        return node_data[name]

    nested_inputs = node_data.get("inputs")
    if isinstance(nested_inputs, dict) and name in nested_inputs and nested_inputs[name] is not None and (not required_reference or nested_inputs[name]):
        return nested_inputs[name]

    properties = (node_data.get("metadata") or {}).get("properties") or []
    for prop in properties:
        if isinstance(prop, dict) and prop.get("name") == name:
            value = prop.get("value", prop.get("default"))
            return value or prop.get("default") if required_reference else value
    return None


def get_kafka_config(credential_data: dict) -> dict:
    """
    Maps KAI Flow credential data to confluent-kafka configuration.
    """
    servers = (
        credential_data.get("bootstrap_servers")
        or credential_data.get("bootstrap.servers")
        or credential_data.get("brokers")
    )
    if isinstance(servers, (list, tuple)):
        servers = ",".join(str(server).strip() for server in servers if str(server).strip())
    config = {
        "bootstrap.servers": servers,
        "security.protocol": credential_data.get("security_protocol", "PLAINTEXT"),
        "client.id": credential_data.get("client_id", "kai-flow-node"),
    }
    
    # SASL Settings
    if config["security.protocol"].startswith("SASL"):
        config["sasl.mechanism"] = credential_data.get("sasl_mechanism", "PLAIN")
        config["sasl.username"] = credential_data.get("sasl_username") or credential_data.get("sasl_plain_username")
        config["sasl.password"] = credential_data.get("sasl_password") or credential_data.get("sasl_plain_password")
    
    # SSL Settings
    if credential_data.get("ssl_cafile"):
        config["ssl.ca.location"] = credential_data.get("ssl_cafile")
        
    return config
