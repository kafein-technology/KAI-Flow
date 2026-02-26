
def get_kafka_config(credential_data: dict) -> dict:
    """
    Maps KAI-Fusion credential data to confluent-kafka configuration.
    """
    config = {
        "bootstrap.servers": (
            credential_data.get("bootstrap_servers") 
            or credential_data.get("bootstrap.servers")
            or credential_data.get("brokers")
        ),
        "security.protocol": credential_data.get("security_protocol", "PLAINTEXT"),
        "client.id": credential_data.get("client_id", "kai-fusion-node"),
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
