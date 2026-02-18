# API Routing Debugger — Project Memory

## Project: KAI-Fusion
- **Stack:** FastAPI (Python) backend + React/Vite (TypeScript) frontend
- **Base path:** `window.VITE_BASE_PATH = "/kai"` → BrowserRouter `basename="/kai"`
- **Runtime config:** `client/public/config.js` → `window.VITE_*` değişkenler (NOT build-time env)
- **API pattern:** `/{API_START}/{API_VERSION}/...` → şu an `api/v1`, `kai` olması isteniyor
- **Backend constants:** `backend/app/core/constants.py` — `API_START="api"`, `API_VERSION="v1"`

## Confirmed Patterns
- `window.VITE_API_BASE_URL` = host only (e.g. `//localhost:23056`) — path içermez
- `window.VITE_API_VERSION` = `/${API_START}/${API_VERSION_ONLY}` (e.g. `/api/v1`)
- `api-client.ts` baseURL = `${window.VITE_API_BASE_URL}${window.VITE_API_VERSION}`
- `config.API_BASE_URL` (config.ts) = `window.VITE_API_BASE_URL` değerini okur

## Known Bugs (in progress)
- [FIXED] Bug 1: `NodeReadonlyText.tsx:18` — `config.API_BASE_URL` yerine `window.location.origin` kullanılmalı
- [FIXED] Bug 2: `FlowCanvas.tsx:1950` — `import.meta.env.VITE_API_BASE_URL` → `window.location.origin`
- [FIXED] Bug 3: `api-client.ts:134,144` — pushState `/signin` → `${window.VITE_BASE_PATH}/signin`
- [FIXED] Bug 4: `constants.py:127` + `config.js:7` — `v1` → `kai`
- [FIXED] Bug 5: `webhooks.py:624` — `localhost:8000` → `localhost:{PORT}`
- [FIXED] Bug 6: `register.tsx:79` — `from !== "/home"` → `from !== "/"`

## Critical Rule — URL Construction
- Webhook display URL'leri için ASLA `config.API_BASE_URL` kullanma
- Production'da nginx proxy path'ini içerdiğinden çift prefix oluşur
- Her zaman `window.location.origin` (sadece domain) + path segmentleri birleştir

## Details
→ See `patterns.md` for more
