# HTTP Client Node - Kapsamlı Kullanım Kılavuzu

Bu kılavuz, KAI-Fusion platformunda HTTP Client Node'un tüm özelliklerini ve kullanım senaryolarını detaylı şekilde açıklar.

##  HTTP Client Node Nedir?

HTTP Client Node, KAI-Fusion platformunun dış servislere HTTP istekleri gönderen güçlü bileşenidir. RESTful API'lere bağlanma, veri çekme/gönderme ve dış sistemlerle entegrasyon için kullanılır.

## ⚙️ Temel Özellikler

### 🌐 HTTP Metodları
- **GET** - Veri çekme
- **POST** - Veri gönderme/oluşturma
- **PUT** - Veri güncelleme/değiştirme
- **PATCH** - Kısmi güncelleme
- **DELETE** - Veri silme
- **HEAD** - Sadece header bilgileri
- **OPTIONS** - Desteklenen metodları öğrenme

### 🔐 Kimlik Doğrulama Türleri
- **Bearer Token** - JWT ve OAuth tokenları
- **Basic Auth** - Kullanıcı adı/şifre
- **API Key** - Header veya query parameter olarak
- **Custom Headers** - Özel authentication header'ları
- **No Auth** - Açık API'ler için

### 📄 Content Type Desteği
- **application/json** - JSON verileri (varsayılan)
- **application/x-www-form-urlencoded** - Form verileri
- **multipart/form-data** - Dosya yüklemeleri
- **text/plain** - Metin verileri
- **application/xml** - XML verileri
- **Custom** - Özel content type'lar

##  Konfigürasyon Parametreleri

###  Temel Ayarlar
```json
{
  "url": "https://api.example.com/users",
  "method": "GET",
  "timeout": 30,
  "follow_redirects": true,
  "verify_ssl": true
}
```

### 🔑 Authentication Ayarları
```json
{
  "auth_type": "bearer",
  "auth_token": "your-jwt-token-here",
  "auth_username": "user@example.com",
  "auth_password": "secure-password",
  "api_key_header": "X-API-Key",
  "api_key_value": "api-key-value"
}
```

### 📝 Request Body ve Headers
```json
{
  "headers": {
    "Content-Type": "application/json",
    "User-Agent": "KAI-Fusion/2.1.0",
    "Accept": "application/json"
  },
  "body": {
    "name": "John Doe",
    "email": "john@example.com"
  }
}
```

##  Kullanım Senaryoları

### 1. **RESTful API Entegrasyonu**
```json
{
  "url": "https://jsonplaceholder.typicode.com/posts",
  "method": "POST",
  "content_type": "application/json",
  "body": {
    "title": "{{title}}",
    "body": "{{content}}", 
    "userId": 1
  },
  "headers": {
    "Authorization": "Bearer {{token}}"
  }
}
```

### 2. **Webhook Çağırma**
```json
{
  "url": "https://hooks.slack.com/services/xxx/yyy/zzz",
  "method": "POST",
  "content_type": "application/json",
  "body": {
    "text": "KAI-Fusion notification: {{message}}",
    "channel": "#alerts"
  }
}
```

### 3. **Database API Sorguları**
```json
{
  "url": "https://api.airtable.com/v0/{{base_id}}/{{table_name}}",
  "method": "GET",
  "auth_type": "bearer",
  "auth_token": "{{airtable_token}}",
  "headers": {
    "Accept": "application/json"
  }
}
```

### 4. **Dosya Yükleme**
```json
{
  "url": "https://api.cloudinary.com/v1_1/{{cloud_name}}/image/upload",
  "method": "POST",
  "content_type": "multipart/form-data",
  "body": {
    "file": "{{file_data}}",
    "upload_preset": "ml_default"
  }
}
```

## 🎨 Template Engine (Jinja2)

### Dinamik URL'ler
```json
{
  "url": "https://api.github.com/repos/{{owner}}/{{repo}}/issues",
  "method": "GET"
}
```

### Koşullu İçerik
```json
{
  "body": {
    "status": "{% if priority == 'high' %}urgent{% else %}normal{% endif %}",
    "priority": "{{priority}}",
    "message": "{{message | title}}"
  }
}
```

### Döngüler ve Listeler
```json
{
  "body": {
    "items": [
      "{% for item in items %}",
      {
        "id": "{{item.id}}",
        "name": "{{item.name}}"
      },
      "{% if not loop.last %},{% endif %}",
      "{% endfor %}"
    ]
  }
}
```

##  Retry ve Error Handling

### Retry Konfigürasyonu
```json
{
  "max_retries": 3,
  "retry_delay": 1,
  "retry_exponential_backoff": true,
  "retry_on_status_codes": [502, 503, 504],
  "circuit_breaker_enabled": true
}
```

### Error Responses
```json
{
  "status_code": 404,
  "error": "Not Found",
  "response": {
    "message": "Resource not found",
    "error_code": "RESOURCE_NOT_FOUND"
  },
  "request_time": "2024-08-06T09:30:00Z"
}
```

##  Response İşleme

### Başarılı Response
```json
{
  "status_code": 200,
  "headers": {
    "Content-Type": "application/json",
    "X-RateLimit-Remaining": "99"
  },
  "data": {
    "id": 1,
    "name": "John Doe",
    "email": "john@example.com"
  },
  "response_time": 0.45,
  "request_url": "https://api.example.com/users/1"
}
```

### Response Filtreleme
```json
{
  "response_filter": "$.data.users[*].{id: id, name: name}",
  "extract_field": "data.access_token",
  "save_to_variable": "user_token"
}
```

## 🛡️ Güvenlik Özellikleri

### SSL/TLS Doğrulama
```json
{
  "verify_ssl": true,
  "ssl_cert_path": "/path/to/cert.pem",
  "ssl_key_path": "/path/to/key.pem",
  "ssl_ca_bundle": "/path/to/ca-bundle.crt"
}
```

### Proxy Desteği
```json
{
  "proxy_url": "http://proxy.company.com:8080",
  "proxy_username": "proxy_user",
  "proxy_password": "proxy_pass"
}
```

##  Workflow Entegrasyonu

### 1. **API Chain Workflow**
```json
{
  "nodes": [
    {
      "id": "auth_request",
      "type": "HttpClient",
      "data": {
        "url": "https://api.service.com/auth",
        "method": "POST",
        "body": {"username": "{{user}}", "password": "{{pass}}"}
      }
    },
    {
      "id": "data_request", 
      "type": "HttpClient",
      "data": {
        "url": "https://api.service.com/data",
        "method": "GET",
        "auth_type": "bearer",
        "auth_token": "{{auth_request.response.access_token}}"
      }
    }
  ]
}
```

### 2. **Conditional API Calls**
```json
{
  "condition": "{{previous_response.status_code}} == 200",
  "if_true": {
    "url": "https://api.success-handler.com/webhook",
    "method": "POST",
    "body": {"status": "success", "data": "{{data}}"}
  },
  "if_false": {
    "url": "https://api.error-handler.com/webhook", 
    "method": "POST",
    "body": {"status": "error", "error": "{{error}}"}
  }
}
```

## 📈 Performance & Monitoring

### Request Metrics
```json
{
  "request_metrics": {
    "response_time": 0.245,
    "dns_lookup_time": 0.012,
    "connection_time": 0.089,
    "ssl_handshake_time": 0.156,
    "transfer_time": 0.088,
    "total_time": 0.245
  }
}
```

### Rate Limiting
```json
{
  "rate_limit_enabled": true,
  "requests_per_second": 10,
  "burst_size": 50,
  "rate_limit_headers": {
    "X-RateLimit-Limit": "100",
    "X-RateLimit-Remaining": "85",
    "X-RateLimit-Reset": "1641234567"
  }
}
```

## 🧪 Testing & Debugging

### Test Konfigürasyonu
```json
{
  "test_mode": true,
  "mock_response": {
    "status_code": 200,
    "body": {"id": 1, "name": "Test User"},
    "headers": {"Content-Type": "application/json"}
  },
  "debug_logging": true,
  "save_request_response": true
}
```

### Debug Output
```json
{
  "debug_info": {
    "request_headers": {"Authorization": "[REDACTED]"},
    "request_body": {"name": "John"},
    "response_headers": {"Content-Type": "application/json"},
    "curl_command": "curl -X POST 'https://api.example.com/users' -H 'Content-Type: application/json' -d '{\"name\":\"John\"}'"
  }
}
```

##  Best Practices

### 1. **Error Handling**
```json
{
  "error_handling": {
    "on_4xx": "log_and_continue",
    "on_5xx": "retry_with_backoff", 
    "on_timeout": "retry_once",
    "on_network_error": "fail_fast"
  }
}
```

### 2. **Security**
```json
{
  "security_practices": {
    "never_log_auth_headers": true,
    "use_environment_variables": true,
    "validate_ssl_certificates": true,
    "sanitize_sensitive_data": true
  }
}
```

### 3. **Performance**
```json
{
  "performance_tips": {
    "connection_pooling": true,
    "keep_alive": true,
    "compression": "gzip",
    "timeout_optimization": true
  }
}
```

##  Common Use Cases

### 1. **CRM Integration**
- Müşteri verilerini senkronize etme
- Lead'leri otomatik oluşturma
- Satış pipeline güncellemeleri

### 2. **Notification Systems**
- Slack/Teams bildirimleri
- Email servisleri
- SMS gateway entegrasyonu

### 3. **Data Collection**
- API'den veri çekme
- Scheduled data sync
- Real-time data streaming

### 4. **Authentication Flows**
- OAuth token alma
- JWT refresh işlemleri
- Multi-step authentication

## 🛠️ Troubleshooting

### Yaygın Hatalar
```json
{
  "connection_timeout": {
    "error": "Connection timed out",
    "solution": "Timeout değerini artırın veya network bağlantısını kontrol edin"
  },
  "ssl_error": {
    "error": "SSL certificate verification failed", 
    "solution": "verify_ssl: false yapın veya doğru sertifikaları kullanın"
  },
  "404_not_found": {
    "error": "Resource not found",
    "solution": "URL ve endpoint'i kontrol edin"
  }
}
```

## 📚 Örnekler

### GitHub API Integration
```json
{
  "url": "https://api.github.com/user/repos",
  "method": "GET",
  "auth_type": "bearer",
  "auth_token": "{{github_token}}",
  "headers": {
    "Accept": "application/vnd.github.v3+json",
    "User-Agent": "KAI-Fusion-Bot"
  }
}
```

### Stripe Payment Processing
```json
{
  "url": "https://api.stripe.com/v1/charges",
  "method": "POST", 
  "auth_type": "basic",
  "auth_username": "{{stripe_secret_key}}",
  "auth_password": "",
  "content_type": "application/x-www-form-urlencoded",
  "body": {
    "amount": "{{amount}}",
    "currency": "usd",
    "source": "{{token}}"
  }
}
```

HTTP Client Node, KAI-Fusion platformunda dış sistemlerle entegrasyon kurmak için güçlü ve esnek bir araçtır. Bu kılavuzdaki örnekleri kullanarak kendi API entegrasyonlarınızı kolayca oluşturabilirsiniz.