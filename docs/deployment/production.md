# Production Deployment

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `docs/nutrition_post_cutover_runbook.md`, `app/api/v2/system.py`

## Tong quan

Huong dan deploy he thong len production, bao gom cau hinh, monitoring, va quy trinh cutover Qdrant.

---

## Checklist Truoc Deploy

- [ ] Doi `SECRET_KEY` va `ADMIN_SECRET_KEY` thanh gia tri manh, random
- [ ] Cau hinh `LLM_BACKEND` phu hop (gemini cho production neu khong co GPU)
- [ ] Set `GOOGLE_API_KEY` neu dung Gemini
- [ ] Cau hinh `COLLECTION_NAME_ACTIVE` (alias mode)
- [ ] Gioi han CORS `allow_origins` (bo `*`)
- [ ] Tat `UVICORN_RELOAD`
- [ ] Cau hinh reverse proxy (Nginx/Caddy) voi HTTPS
- [ ] Setup backup PostgreSQL
- [ ] Setup monitoring

---

## Cau hinh Production

```env
# Security
SECRET_KEY="<random-64-chars>"
ADMIN_SECRET_KEY="<random-32-chars>"

# LLM (Gemini khuyen nghi cho production khong GPU)
LLM_BACKEND="gemini"
GOOGLE_API_KEY="<production-key>"
GEMINI_MODEL="gemini-2.5-flash"

# Qdrant (alias mode)
COLLECTION_NAME="gym_food_hybrid_v1"
COLLECTION_NAME_ACTIVE="gym_food_hybrid_active"
COLLECTION_NAME_NEXT=""

# Performance
RETRIEVAL_ENABLE_NATIVE_RERANK=true
RETRIEVAL_OVERFETCH_MULTIPLIER=4
RETRIEVAL_RERANK_CANDIDATES=24

# Server
UVICORN_RELOAD=false
```

---

## Chay Server Production

```powershell
# Khong reload, nhieu workers
uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4

# Hoac voi gunicorn (Linux)
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
```

---

## Monitoring

### Health Check

```bash
# Basic health
curl http://localhost:8000/

# System health (kiem tra tat ca services)
curl http://localhost:8000/api/v2/system/health
```

### Log Streaming

WebSocket endpoint de xem log real-time:
```
ws://localhost:8000/api/v2/system/logs/ws
```

### Workflow Tracking

```bash
# Xem trang thai mot request
curl http://localhost:8000/api/v3/nutrition/workflows/{request_id} \
  -H "Authorization: Bearer <token>"
```

---

## Quy trinh Cutover Qdrant

Khi can cap nhat du lieu dinh duong (blue-green deployment):

### 1. Chuan bi

```env
# .env
COLLECTION_NAME_NEXT="gym_food_hybrid_v2_20260406"
```

### 2. Reindex

```powershell
python -m scripts.reindex_qdrant
```

### 3. Test

```powershell
python -m scripts.test_nutrition_cases \
  --username admin --password admin \
  --recommendation-timeout 900
```

### 4. Quyet dinh

```powershell
python -m scripts.judge_cutover \
  --max-response-time-seconds 240 \
  --max-discouraged-items 1
```

### 5. Cutover (neu pass)

```powershell
python -m scripts.cutover_qdrant_alias
```

### 6. Xoa next (sau cutover)

```env
# .env
COLLECTION_NAME_NEXT=""
```

> Chi tiet day du: [Ops Runbook](../nutrition_post_cutover_runbook.md)

---

## Backup & Recovery

### PostgreSQL

```bash
# Backup
docker exec gym_postgres pg_dump -U admin gym_food_db > backup_$(date +%Y%m%d).sql

# Restore
docker exec -i gym_postgres psql -U admin gym_food_db < backup_20260406.sql
```

### Qdrant

- Du lieu trong `./storage/qdrant/` — backup folder nay
- Hoac dung Qdrant Snapshot API: `POST /collections/{name}/snapshots`

### Redis

- Du lieu trong `./storage/redis/` — backup folder nay
- Redis Stack tu dong luu RDB snapshots

---

## Reverse Proxy (Nginx)

```nginx
server {
    listen 443 ssl;
    server_name api.gymfood.com;

    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    # WebSocket support
    location /api/v2/system/logs/ws {
        proxy_pass http://127.0.0.1:8000;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

---

## Lien ket

- [Docker Compose](docker.md)
- [Cau hinh](../getting-started/configuration.md)
- [Ops Runbook](../nutrition_post_cutover_runbook.md)
