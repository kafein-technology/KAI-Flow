#  KAI-Fusion Webhook & HTTP Node Integration Guide

##  Overview

This comprehensive guide explains how to configure external services to trigger KAI-Fusion workflows via webhooks and retrieve data using HTTP nodes. You'll learn how to set up webhook triggers, configure HTTP request nodes, and integrate external systems with your AI workflows.

##  Architecture Overview

```
External Service → Webhook Trigger → Start Node → HTTP Request → End Node → Response
      ↓                 ↓               ↓            ↓            ↓         ↓
   Postman/API    →  webhook_id   →  Workflow  →  External  →   Data   →  Return
```

---

##  Part 1: Webhook Trigger Configuration

### 1.1 Webhook Node Setup in KAI-Fusion UI

When creating a webhook trigger node in your workflow:

```json
{
  "node_type": "WebhookTrigger",
  "webhook_id": "wh_your_unique_id_123",
  "config": {
    "authentication_required": true,
    "secret_token": "webhook_token_secure_123",
    "max_payload_size": 1024,
    "rate_limit_per_minute": 60,
    "webhook_timeout": 30,
    "enable_cors": true
  }
}
```

**Key Configuration Fields:**
- `webhook_id`: Unique identifier for your webhook (must start with `wh_`)
- `secret_token`: Bearer token for authentication
- `max_payload_size`: Maximum payload size in KB
- `rate_limit_per_minute`: Request rate limiting
- `webhook_timeout`: Timeout in seconds

### 1.2 Webhook URL Format

Your webhook URL will be:
```
POST http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/{webhook_id}
```

**Example:**
```
POST http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123
```

---

## 🌐 Part 2: External Service Integration

### 2.1 Postman Configuration

**Request Setup:**
- **Method**: `POST`
- **URL**: `http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123`

**Headers:**
```
Content-Type: application/json
Authorization: Bearer webhook_token_secure_123
User-Agent: External-Service/1.0
X-Source-System: your-system-name
```

**Body (JSON):**
```json
{
  "event_type": "data.scraping.request",
  "data": {
    "target_url": "https://example.com/api/data",
    "scraping_config": {
      "selector": ".content",
      "extract_type": "text"
    },
    "webhook_source": "postman_test",
    "timestamp": "2025-08-10T22:42:00Z",
    "correlation_id": "req_12345"
  },
  "metadata": {
    "user_id": "external_user_123",
    "priority": "high",
    "retry_count": 0
  }
}
```

### 2.2 cURL Command Example

```bash
curl -X POST "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer webhook_token_secure_123" \
  -H "User-Agent: External-Service/1.0" \
  -d '{
    "event_type": "data.processing.request",
    "data": {
      "target_url": "https://jsonplaceholder.typicode.com/posts/1",
      "processing_type": "json_extract",
      "fields_to_extract": ["title", "body", "userId"],
      "webhook_source": "curl_test"
    },
    "metadata": {
      "correlation_id": "curl_req_001",
      "timestamp": "'$(date -Iseconds)'"
    }
  }'
```

### 2.3 Python Integration Example

```python
import requests
import json
from datetime import datetime

class KAIFusionWebhookClient:
    def __init__(self, base_url="http://localhost:8000", webhook_token="webhook_token_secure_123"):
        self.base_url = base_url
        self.webhook_token = webhook_token
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {webhook_token}",
            "User-Agent": "KAI-Fusion-Client/1.0"
        }
    
    def trigger_workflow(self, webhook_id, data, event_type="workflow.trigger"):
        """Trigger a KAI-Fusion workflow via webhook"""
        url = f"{self.base_url}/{API_START}/{API_VERSION_ONLY}/webhooks/{webhook_id}"
        
        payload = {
            "event_type": event_type,
            "data": data,
            "metadata": {
                "timestamp": datetime.utcnow().isoformat() + "Z",
                "source": "python_client"
            }
        }
        
        response = requests.post(url, headers=self.headers, json=payload, timeout=30)
        return response.json()

# Usage Example
client = KAIFusionWebhookClient()

result = client.trigger_workflow(
    webhook_id="wh_your_unique_id_123",
    data={
        "target_url": "https://api.github.com/repos/microsoft/vscode",
        "action": "fetch_repo_data",
        "extract_fields": ["name", "description", "stars"]
    },
    event_type="github.data.fetch"
)

logger(f"Workflow triggered: {result}")
```

---

##  Part 3: HTTP Request Node Configuration

### 3.1 HTTP Node Setup in Workflow

When configuring the HTTP Request node that follows your webhook trigger:

```json
{
  "node_type": "HttpRequest",
  "node_id": "http_request_001",
  "config": {
    "method": "POST",
    "url": "https://external-api.example.com/process",
    "headers": {
      "Content-Type": "application/json",
      "Authorization": "Bearer your-api-key-here",
      "X-Source": "kai-fusion-workflow",
      "Accept": "application/json"
    },
    "body_type": "json",
    "timeout": 30,
    "retry_attempts": 3,
    "retry_delay": 2
  }
}
```

### 3.2 Dynamic Data Forwarding

The HTTP node can forward data received from the webhook trigger:

```json
{
  "url": "https://external-service.com/api/process",
  "method": "POST",
  "headers": {
    "Authorization": "Bearer api-key-123",
    "Content-Type": "application/json"
  },
  "body": {
    "original_webhook_data": "{{webhook.data}}",
    "processed_timestamp": "{{current_time}}",
    "workflow_id": "{{workflow.id}}",
    "extracted_content": "{{scraper.content}}"
  }
}
```

### 3.3 Response Handling Configuration

```json
{
  "response_handling": {
    "success_status_codes": [200, 201, 202],
    "parse_response": true,
    "response_format": "json",
    "extract_fields": ["result", "data", "status"],
    "error_handling": {
      "on_error": "log_and_continue",
      "retry_on_status": [500, 502, 503]
    }
  }
}
```

---

##  Part 4: Complete Workflow Examples

### 4.1 Web Scraping → HTTP Forward Workflow

**Workflow Structure:**
```
WebhookTrigger → StartNode → WebScraper → HttpRequest → EndNode
```

**Webhook Payload:**
```json
{
  "event_type": "scrape.and.forward",
  "data": {
    "scrape_url": "https://news.ycombinator.com",
    "scrape_selector": ".titleline a",
    "forward_endpoint": "https://your-service.com/api/news",
    "forward_auth": "Bearer your-token"
  }
}
```

**HTTP Node Configuration:**
```json
{
  "method": "POST",
  "url": "{{data.forward_endpoint}}",
  "headers": {
    "Authorization": "{{data.forward_auth}}",
    "Content-Type": "application/json"
  },
  "body": {
    "scraped_data": "{{webscraper.content}}",
    "source_url": "{{data.scrape_url}}",
    "scraped_at": "{{current_timestamp}}",
    "workflow_id": "{{workflow.id}}"
  }
}
```

### 4.2 API Data Processing Workflow

**Webhook Payload:**
```json
{
  "event_type": "api.data.process",
  "data": {
    "source_api": "https://jsonplaceholder.typicode.com/posts",
    "processing_rules": {
      "filter_by": "userId",
      "filter_value": 1,
      "extract_fields": ["title", "body"]
    },
    "destination": {
      "endpoint": "https://webhook.site/your-unique-url",
      "method": "POST"
    }
  }
}
```

---

##  Part 5: External Service Setup

### 5.1 Webhook Receiver Service (Node.js Example)

```javascript
const express = require('express');
const axios = require('axios');
const app = express();

app.use(express.json());

// Endpoint to receive processed data from KAI-Fusion
app.post('/api/receive-processed-data', (req, res) => {
    console.log('Received processed data:', req.body);
    
    const { scraped_data, source_url, workflow_id, scraped_at } = req.body;
    
    // Process the received data
    console.log(`Workflow ${workflow_id} scraped ${scraped_data.length} items from ${source_url}`);
    
    res.json({ 
        success: true, 
        message: 'Data received successfully',
        processed_items: scraped_data?.length || 0
    });
});

// Endpoint to trigger KAI-Fusion workflows
app.post('/trigger-kai-fusion', async (req, res) => {
    try {
        const response = await axios.post(
            'http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123',
            {
                event_type: 'external.trigger',
                data: req.body
            },
            {
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer webhook_token_secure_123'
                }
            }
        );
        
        res.json(response.data);
    } catch (error) {
        res.status(500).json({ error: error.message });
    }
});

app.listen(3000, () => {
    console.log('External service running on port 3000');
});
```

### 5.2 Python Flask Receiver Service

```python
from flask import Flask, request, jsonify
import requests
from datetime import datetime

app = Flask(__name__)

KAI_FUSION_WEBHOOK_URL = "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123"
WEBHOOK_TOKEN = "webhook_token_secure_123"

@app.route('/api/receive-data', methods=['POST'])
def receive_processed_data():
    """Receive processed data from KAI-Fusion HTTP node"""
    data = request.get_json()
    
    logger(f"Received processed data at {datetime.now()}")
    logger(f"Workflow ID: {data.get('workflow_id')}")
    logger(f"Scraped content length: {len(data.get('scraped_data', []))}")
    
    # Process the received data here
    processed_result = {
        'received_at': datetime.utcnow().isoformat(),
        'items_count': len(data.get('scraped_data', [])),
        'status': 'processed_successfully'
    }
    
    return jsonify({
        'success': True,
        'result': processed_result
    })

@app.route('/trigger-workflow', methods=['POST'])
def trigger_kai_fusion_workflow():
    """Trigger KAI-Fusion workflow from external system"""
    payload = {
        'event_type': 'external.system.trigger',
        'data': request.get_json(),
        'metadata': {
            'triggered_at': datetime.utcnow().isoformat(),
            'source': 'flask_service'
        }
    }
    
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {WEBHOOK_TOKEN}'
    }
    
    try:
        response = requests.post(
            KAI_FUSION_WEBHOOK_URL, 
            json=payload, 
            headers=headers,
            timeout=30
        )
        return jsonify(response.json())
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
```

---

## 🧪 Part 6: Testing Scenarios

### 6.1 End-to-End Test

```bash
#!/bin/bash
echo " Testing KAI-Fusion Webhook → HTTP Integration"

# Test 1: Simple webhook trigger
echo "Test 1: Basic webhook trigger"
curl -X POST "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer webhook_token_secure_123" \
  -d '{
    "event_type": "test.basic",
    "data": {
      "message": "Basic webhook test",
      "test_id": "basic_001"
    }
  }'

echo -e "\n"

# Test 2: Scraping workflow
echo "Test 2: Web scraping workflow"
curl -X POST "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer webhook_token_secure_123" \
  -d '{
    "event_type": "scrape.test",
    "data": {
      "target_url": "https://httpbin.org/json",
      "extract_fields": ["slideshow"],
      "forward_to": "https://webhook.site/your-test-url"
    }
  }'

echo -e "\n"

# Test 3: Concurrent execution
echo "Test 3: Concurrent webhook execution"
for i in {1..3}; do
  curl -X POST "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123" \
    -H "Content-Type: application/json" \
    -H "Authorization: Bearer webhook_token_secure_123" \
    -d "{
      \"event_type\": \"concurrent.test\",
      \"data\": {
        \"test_id\": $i,
        \"message\": \"Concurrent test $i\"
      }
    }" &
done

wait
echo " All tests completed!"
```

### 6.2 Monitoring and Debugging

**Check webhook status:**
```bash
curl -X GET "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123/info" \
  -H "Content-Type: application/json"
```

**Get webhook statistics:**
```bash
curl -X GET "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123/stats" \
  -H "Authorization: Bearer your-auth-token"
```

**Health check:**
```bash
curl -X GET "http://localhost:8000/{API_START}/{API_VERSION_ONLY}/webhooks/wh_your_unique_id_123/health"
```

---

## ⚙️ Part 7: Configuration Best Practices

### 7.1 Security Configuration

```json
{
  "webhook_security": {
    "token_rotation": "weekly",
    "ip_whitelist": ["192.168.1.0/24", "10.0.0.0/8"],
    "rate_limiting": {
      "requests_per_minute": 60,
      "burst_limit": 10
    },
    "payload_validation": true,
    "ssl_verification": true
  }
}
```

### 7.2 Error Handling

```json
{
  "error_handling": {
    "webhook_timeout": 30,
    "max_retries": 3,
    "retry_delay": "exponential",
    "failed_webhook_queue": true,
    "dead_letter_queue": true
  }
}
```

### 7.3 Monitoring Configuration

```json
{
  "monitoring": {
    "enable_logging": true,
    "log_level": "INFO",
    "metrics_collection": true,
    "alert_on_failures": true,
    "performance_tracking": true
  }
}
```

---

##  Part 8: Response Formats

### 8.1 Successful Webhook Response

```json
{
  "success": true,
  "message": "Webhook received and workflow started",
  "webhook_id": "wh_your_unique_id_123",
  "received_at": "2025-08-10T22:42:02.965832+00:00",
  "correlation_id": "uuid-generated-correlation-id",
  "workflow_status": "initiated",
  "estimated_completion": "2025-08-10T22:42:32Z"
}
```

### 8.2 HTTP Node Response

```json
{
  "node_type": "HttpRequest",
  "execution_status": "completed",
  "response": {
    "status_code": 200,
    "headers": {
      "content-type": "application/json"
    },
    "body": {
      "processed_data": [...],
      "status": "success",
      "processing_time": "2.3s"
    }
  },
  "execution_time_ms": 2300,
  "next_node": "end_node"
}
```

### 8.3 Error Response

```json
{
  "success": false,
  "error": "webhook_not_found",
  "message": "Webhook endpoint wh_invalid_id not found",
  "error_code": 404,
  "correlation_id": "error-uuid",
  "timestamp": "2025-08-10T22:42:02Z",
  "retry_after": 300
}
```

---

##  Part 9: Advanced Use Cases

### 9.1 Multi-Step Data Pipeline

```json
{
  "event_type": "pipeline.data.process",
  "data": {
    "pipeline": [
      {
        "step": 1,
        "action": "scrape",
        "target": "https://api.github.com/repos/trending"
      },
      {
        "step": 2,
        "action": "filter",
        "criteria": "language:javascript"
      },
      {
        "step": 3,
        "action": "enrich",
        "api_endpoint": "https://api.github.com/repos/{owner}/{repo}"
      },
      {
        "step": 4,
        "action": "forward",
        "destination": "https://your-analytics-service.com/api/trends"
      }
    ]
  }
}
```

### 9.2 Conditional Workflow Execution

```json
{
  "event_type": "conditional.workflow",
  "data": {
    "conditions": {
      "if_data_count_gt": 10,
      "then_action": "full_processing",
      "else_action": "light_processing"
    },
    "full_processing": {
      "http_endpoint": "https://heavy-processor.com/api/process",
      "timeout": 120
    },
    "light_processing": {
      "http_endpoint": "https://quick-processor.com/api/process",
      "timeout": 30
    }
  }
}
```

---

##  Quick Start Checklist

- [ ] Create webhook trigger node in KAI-Fusion UI
- [ ] Note down your `webhook_id` and `secret_token`
- [ ] Configure external service with webhook URL
- [ ] Set up HTTP request node for data forwarding  
- [ ] Configure external endpoint to receive processed data
- [ ] Test webhook trigger with Postman/cURL
- [ ] Verify data flow end-to-end
- [ ] Set up monitoring and error handling
- [ ] Scale to production with proper security

---

## 📞 Support & Resources

- **Documentation**: Check KAI-Fusion docs for latest updates
- **API Reference**: `/api/docs` for interactive API documentation  
- **Health Checks**: Use `/health` endpoints for monitoring
- **Logs**: Check application logs for debugging
- **Community**: Join KAI-Fusion community for support

---

**Last Updated**: August 10, 2025
**Version**: 2.1.0
**Compatibility**: KAI-Fusion Platform v2.x+