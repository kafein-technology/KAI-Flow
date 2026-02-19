# KAI Fusion - Frontend Docker Compose Deployment

Bu proje Docker Compose kullanılarak sadece frontend deploy edilebilir.

## Servisler

- **client**: React frontend uygulaması (Port: 3000)

## Kurulum ve Çalıştırma

### 1. Development Ortamı

```bash
# Frontend servisini başlat
docker-compose up

# Arka planda çalıştır
docker-compose up -d

# Sadece client servisini başlat
docker-compose up client
```

### 2. Production Ortamı

```bash
# Production build ile çalıştır
docker-compose -f docker-compose.yml up --build

# Arka planda çalıştır
docker-compose -f docker-compose.yml up -d --build
```

### 3. Servisleri Durdurma

```bash
# Tüm servisleri durdur
docker-compose down

# Volumeleri de sil
docker-compose down -v
```

## Environment Değişkenleri

### Frontend (Client)
- `VITE_API_BASE_URL`: API base URL (default: http://localhost:8000)
- `VITE_API_VERSION`: API versiyonu (default: /api/kai/api/v1)
- `VITE_NODE_ENV`: Node environment (default: development)
- `VITE_ENABLE_LOGGING`: Logging aktif/pasif (default: true)

## Erişim URL'leri

- **Frontend**: http://localhost:3000

## Geliştirme İpuçları

### Hot Reload
Development ortamında kod değişiklikleri otomatik olarak yansır.

### Logları İzleme
```bash
# Client servisinin loglarını izle
docker-compose logs -f client
```

### Container'a Bağlanma
```bash
# Client container'ına bağlan
docker-compose exec client sh
```

## Troubleshooting

### Port Çakışması
Eğer port 3000 kullanımdaysa, `docker-compose.yml` dosyasındaki port mapping'i değiştirin.

### Volume Sorunları
```bash
# Volumeleri temizle
docker-compose down -v
docker volume prune
```

### Build Sorunları
```bash
# Cache'i temizle ve yeniden build et
docker-compose build --no-cache
```

## Not

Bu yapılandırma sadece frontend'i deploy eder. Backend API'niz ayrı bir serviste çalışıyorsa, `VITE_API_BASE_URL` environment değişkenini backend'inizin URL'sine göre güncelleyin. 