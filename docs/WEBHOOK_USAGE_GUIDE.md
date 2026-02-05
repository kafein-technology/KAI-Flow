# 🌐 KAI-Flow Webhook Trigger Kullanım Kılavuzu

## 📋 İçindekiler
- [Genel Bakış](#genel-bakış)
- [Webhook Oluşturma](#webhook-oluşturma)
- [Workflow Bağlantısı](#workflow-bağlantısı)
- [External Integration](#external-integration)
- [Kullanım Örnekleri](#kullanım-örnekleri)
- [Güvenlik](#güvenlik)
- [Troubleshooting](#troubleshooting)

---

## 🎯 Genel Bakış

KAI-Flow Webhook Trigger Node, external sistemlerin HTTP POST istekleri ile workflow'ları tetiklemesini sağlar. Webhook sanki manuel start butonuna tıklanmış gibi workflow'u başlatır ve complete processing chain'i execute eder.

### ✨ Temel Özellikler
- 🔗 **External HTTP Integration**: Dışarıdan API çağrıları kabul eder
- ⚡ **Automatic Workflow Triggering**: Start node'a bağlanarak workflow'u başlatır
- 📤 **Output Return**: Workflow sonuçlarını external sistem'e döndürür
- 🔒 **Security**: Authentication, rate limiting, CORS support
- 📊 **Monitoring**: Event tracking, statistics, correlation ID

---

## 🛠️ Webhook Oluşturma

### 1. Node Ekleme
Workflow editörde **Webhook Trigger** node'unu ekleyin:

```
Workflow: [Webhook Trigger] → [Start Node] → [Processing...] → [End Node]
Position: Start node'undan ÖNCE
```

### 2. Konfigürasyon

#### Temel Ayarlar
```json
{
  "authentication_required": false,        // Bearer token gerekli mi?
  "allowed_event_types": "user.action,api.request",  // İzin verilen event türleri
  "max_payload_size": 2048,              // Max payload boyutu (KB)
  "rate_limit_per_minute": 100,          // Dakika başına max istek
  "enable_cors": true,                   // Cross-origin support
  "webhook_timeout": 30                  // İşlem timeout (saniye)
}
```

#### Güvenlik Ayarları
```json
{
  "authentication_required": true,       // Production için önerilen
  "allowed_event_types": "user.created,order.completed",
  "max_payload_size": 1024,
  "rate_limit_per_minute": 60
}
```

### 3. Output Alımı
Node konfigüre edildiğinde aşağıdaki bilgileri alırsınız:

```json
{
  "webhook_endpoint": "http://localhost:8000/{API_START}/webhooks/wh_abc123",
  "webhook_token": "wht_secrettoken123",  // authentication_required=true ise
  "webhook_config": {
    "webhook_id": "wh_abc123",
    "authentication_required": true,
    "created_at": "2025-08-04T23:00:00Z"
  }
}
```

---

## 🔗 Workflow Bağlantısı

### Connection Pattern
```
[Webhook Trigger] ---> [Start Node] ---> [Processing Nodes] ---> [End Node]
       ↑                    ↑                    ↑                   ↑
   External HTTP        Workflow Entry      Processing Chain     Output Ready
```

### Bağlantı Kurma
1. **Webhook Trigger** node'unun output'unu seçin
2. **Start Node**'un input'una bağlayın
3. Normal workflow chain'i oluşturun

### Data Flow
```javascript
// External Request
{
  "event_type": "user.action",
  "data": {
    "user_id": 12345,
    "action": "process_data"
  }
}

// ↓ Webhook processes

// Start Node receives
{
  "message": "Workflow started by webhook",
  "webhook_data": {
    "event_type": "user.action",
    "payload": { "user_id": 12345, "action": "process_data" },
    "correlation_id": "req_abc123"
  }
}
```

---

## 🌐 External Integration

### 1. Basic HTTP Request

#### Without Authentication
```bash
curl -X POST "http://localhost:8000/{API_START}/webhooks/wh_abc123" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.action",
    "data": {
      "user_id": 12345,
      "action": "process_user_data"
    },
    "source": "user_dashboard"
  }'
```

#### With Authentication
```bash
curl -X POST "http://localhost:8000/{API_START}/webhooks/wh_abc123" \
  -H "Authorization: Bearer wht_secrettoken123" \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "user.action",
    "data": {
      "user_id": 12345,
      "action": "process_user_data"
    },
    "source": "user_dashboard"
  }'
```

### 2. Programming Language Examples

#### Python
```python
import requests

url = "http://localhost:8000/{API_START}/webhooks/wh_abc123"
headers = {
    "Content-Type": "application/json",
    "Authorization": "Bearer wht_secrettoken123"  # if auth required
}
payload = {
    "event_type": "api.request",
    "data": {
        "user_id": 12345,
        "action": "fetch_profile",
        "target_api": "https://api.example.com/users/12345"
    },
    "source": "python_client",
    "correlation_id": "req_001"
}

response = requests.post(url, json=payload, headers=headers)
print(f"Status: {response.status_code}")
print(f"Response: {response.json()}")
```

#### JavaScript/Node.js
```javascript
const axios = require('axios');

const url = 'http://localhost:8000/{API_START}/webhooks/wh_abc123';
const headers = {
    'Content-Type': 'application/json',
    'Authorization': 'Bearer wht_secrettoken123'
};
const payload = {
    event_type: 'user.action',
    data: {
        user_id: 12345,
        action: 'process_order',
        order_id: 'ORD-789'
    },
    source: 'ecommerce_frontend'
};

axios.post(url, payload, { headers })
    .then(response => {
        console.log('Status:', response.status);
        console.log('Response:', response.data);
    })
    .catch(error => {
        console.error('Error:', error.response?.data || error.message);
    });
```

#### PHP
```php
<?php
$url = 'http://localhost:8000/{API_START}/webhooks/wh_abc123';
$headers = [
    'Content-Type: application/json',
    'Authorization: Bearer wht_secrettoken123'
];
$payload = [
    'event_type' => 'user.action',
    'data' => [
        'user_id' => 12345,
        'action' => 'update_profile'
    ],
    'source' => 'php_application'
];

$ch = curl_init();
curl_setopt($ch, CURLOPT_URL, $url);
curl_setopt($ch, CURLOPT_POST, true);
curl_setopt($ch, CURLOPT_POSTFIELDS, json_encode($payload));
curl_setopt($ch, CURLOPT_HTTPHEADER, $headers);
curl_setopt($ch, CURLOPT_RETURNTRANSFER, true);

$response = curl_exec($ch);
$httpCode = curl_getinfo($ch, CURLINFO_HTTP_CODE);
curl_close($ch);

echo "Status: $httpCode\n";
echo "Response: $response\n";
?>
```

---

## 📚 Kullanım Örnekleri

### 1. E-commerce Order Processing

#### Workflow Setup
```
[Webhook Trigger] → [Start] → [HTTP Client] → [Email Notification] → [End]
```

#### Configuration
```json
{
  "authentication_required": true,
  "allowed_event_types": "order.created,order.completed,order.cancelled",
  "max_payload_size": 5120,
  "rate_limit_per_minute": 200
}
```

#### External Request
```javascript
// Order completion trigger
{
  "event_type": "order.completed",
  "data": {
    "order_id": "ORD-98765",
    "customer_id": 67890,
    "total_amount": 299.99,
    "items": [
      {"sku": "PROD-001", "quantity": 2, "price": 149.99}
    ],
    "payment_status": "paid",
    "shipping_address": {
      "street": "123 Main St",
      "city": "Anytown",
      "zip": "12345"
    }
  },
  "source": "payment_gateway",
  "correlation_id": "payment_12345"
}
```

### 2. User Registration Workflow

#### Workflow Setup
```
[Webhook Trigger] → [Start] → [User Validation] → [Email Verification] → [Database Update] → [End]
```

#### External Request
```javascript
// User registration trigger
{
  "event_type": "user.registered",
  "data": {
    "user_id": 12345,
    "email": "user@example.com",
    "name": "John Doe",
    "registration_source": "web_app",
    "verification_required": true,
    "welcome_email": true
  },
  "source": "user_service",
  "correlation_id": "reg_67890"
}
```

### 3. API Gateway Pattern

#### Workflow Setup
```
[Webhook Trigger] → [Start] → [API Orchestrator] → [Response Aggregator] → [End]
```

#### External Request
```javascript
// API orchestration trigger
{
  "event_type": "api.orchestrate",
  "data": {
    "request_id": "api_req_001",
    "endpoints": [
      {
        "name": "user_profile",
        "url": "https://api.users.com/profile/12345",
        "method": "GET"
      },
      {
        "name": "user_orders",
        "url": "https://api.orders.com/user/12345/orders",
        "method": "GET"
      }
    ],
    "aggregation_rules": {
      "merge_on": "user_id",
      "include_metadata": true
    }
  },
  "source": "api_gateway",
  "correlation_id": "gateway_001"
}
```

### 4. System Monitoring & Alerts

#### Workflow Setup
```
[Webhook Trigger] → [Start] → [Alert Processor] → [Notification Service] → [End]
```

#### External Request
```javascript
// System alert trigger
{
  "event_type": "system.alert",
  "data": {
    "alert_type": "service_down",
    "service_name": "payment_processor",
    "severity": "critical",
    "affected_users": 1500,
    "auto_recovery": false,
    "details": {
      "error_message": "Connection timeout to payment gateway",
      "last_successful": "2025-08-04T22:30:00Z",
      "retry_attempts": 3
    }
  },
  "source": "monitoring_system",
  "correlation_id": "alert_001"
}
```

### 5. Data Pipeline Trigger

#### Workflow Setup
```
[Webhook Trigger] → [Start] → [Data Fetcher] → [Processor] → [Vector Store] → [End]
```

#### External Request
```javascript
// Data processing trigger
{
  "event_type": "data.process",
  "data": {
    "pipeline_id": "data_pipeline_001",
    "source_urls": [
      "https://api.news.com/articles/latest",
      "https://api.blog.com/posts/tech"
    ],
    "processing_options": {
      "extract_text": true,
      "generate_embeddings": true,
      "store_vectors": true,
      "chunk_size": 1000
    },
    "output_collection": "tech_articles_2025"
  },
  "source": "data_ingestion_service",
  "correlation_id": "pipeline_001"
}
```

---

## 🔒 Güvenlik

### 1. Authentication Setup

#### Bearer Token Authentication
```json
{
  "authentication_required": true,
  "webhook_token": "wht_abc123def456"
}
```

#### Request Header
```
Authorization: Bearer wht_abc123def456
```

### 2. Event Type Filtering
```json
{
  "allowed_event_types": "user.created,user.updated,user.deleted"
}
```

Sadece belirtilen event türleri kabul edilir.

### 3. Rate Limiting
```json
{
  "rate_limit_per_minute": 60
}
```

Dakika başına maksimum 60 istek.

### 4. Payload Size Limits
```json
{
  "max_payload_size": 1024  // KB
}
```

### 5. CORS Configuration
```json
{
  "enable_cors": true
}
```

Web uygulamaları için cross-origin support.

### 6. Production Security Checklist
- ✅ `authentication_required: true`
- ✅ Strong webhook token
- ✅ Appropriate rate limits
- ✅ Event type whitelist
- ✅ HTTPS endpoint (production)
- ✅ Payload size limits
- ✅ Request logging enabled

---

## 🔧 Troubleshooting

### Common Issues

#### 1. 404 Not Found
```
Error: {"error": true, "message": "Not Found"}
```

**Çözüm:**
- FastAPI server çalışıyor mu kontrol edin
- Webhook endpoint URL'ini doğrulayın
- Server restart gerekebilir

#### 2. 401 Authentication Failed
```
Error: {"error": true, "message": "Invalid or missing authentication token"}
```

**Çözüm:**
- Authorization header ekleyin: `Bearer <token>`
- Token'ın doğru olduğunu kontrol edin
- `authentication_required` ayarını kontrol edin

#### 3. 400 Event Type Not Allowed
```
Error: {"error": true, "message": "Event type 'test.event' not allowed"}
```

**Çözüm:**
- `allowed_event_types` listesine event type'ı ekleyin
- Boş liste tüm event türlerine izin verir

#### 4. 413 Payload Too Large
```
Error: {"error": true, "message": "Payload size 2048KB exceeds limit 1024KB"}
```

**Çözüm:**
- `max_payload_size` değerini artırın
- Payload boyutunu küçültün

#### 5. 429 Rate Limit Exceeded
```
Error: {"error": true, "message": "Rate limit exceeded"}
```

**Çözüm:**
- `rate_limit_per_minute` değerini artırın
- Request frequency'i azaltın
- Exponential backoff uygulayın

### Debug Commands

#### Test Webhook Health
```bash
curl -X GET "http://localhost:8000/{API_START}/webhooks/"
```

#### Test Specific Webhook
```bash
curl -X POST "http://your-endpoint" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "test", "data": {"test": true}}'
```

#### Check Server Status
```bash
curl -X GET "http://localhost:8000/health"
```

---

## 📊 Monitoring & Analytics

### Webhook Statistics
```python
# Get webhook statistics
webhook_stats = webhook_node.get_webhook_stats()
print(f"Total events: {webhook_stats['total_events']}")
print(f"Event types: {webhook_stats['event_types']}")
print(f"Sources: {webhook_stats['sources']}")
print(f"Last event: {webhook_stats['last_event_at']}")
```

### Available Metrics
- `total_events`: Toplam alınan event sayısı
- `event_types`: Event türü dağılımı
- `sources`: Source sistem dağılımı
- `recent_events`: Son 10 event
- `last_event_at`: Son event zamanı

---

## 🚀 Production Deployment

### Environment Variables
```bash
# Production webhook base URL
export WEBHOOK_BASE_URL="https://your-domain.com"

# Enable LangChain tracing
export LANGCHAIN_TRACING_V2="true"
```

### Production Configuration
```json
{
  "authentication_required": true,
  "allowed_event_types": "user.action,order.created,system.alert",
  "max_payload_size": 2048,
  "rate_limit_per_minute": 100,
  "enable_cors": false,
  "webhook_timeout": 60
}
```

### Load Testing
```bash
# Apache Bench example
ab -n 100 -c 10 -p payload.json -T application/json \
  http://your-domain.com/{API_START}/webhooks/wh_your_id
```

---

## 📞 Support

### Documentation
- [API Reference](./api-reference.md)
- [Workflow Guide](./workflow-guide.md)
- [Security Best Practices](./security-guide.md)

### Contact
- GitHub Issues: [KAI-Flow Issues](https://github.com/KAI-Flow/issues)
- Email: support@KAI-Flow.com
- Discord: KAI-Flow Community

---

## 📈 Version History

- **v2.1.0**: Current version with full external integration
- **v2.0.0**: Enterprise architecture rewrite
- **v1.x**: Legacy implementation (deprecated)

**Last Updated:** 2025-08-04  
**Status:** ✅ Production Ready