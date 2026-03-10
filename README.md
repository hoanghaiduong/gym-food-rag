# Gym Food RAG

Backend FastAPI cho bài toán RAG dinh dưỡng. Repo đã được dọn lại để source code, dữ liệu, log và storage runtime tách nhau rõ ràng hơn.

## Cấu trúc chính

```text
app/                 # API, core, db, modules
scripts/             # script thu thập dữ liệu, ingest, debug, export
data/
  raw/               # dữ liệu gốc
  processed/         # dữ liệu đã chuẩn hóa / build lại
  cache/             # file tạm cho ingest
logs/                # log runtime
storage/             # bind-mount cho postgres/qdrant/redis/ollama
docs/                # tài liệu và export API
```

## Chạy local

1. Tạo file `.env` từ `.env.example`.
2. Khởi động hạ tầng:

```powershell
docker-compose up -d
```

3. Chạy API:

```powershell
python start.py
```

Hoặc dùng:

```powershell
.\run_server.ps1
```

## Các script hữu ích

```powershell
python scripts\data_collector.py
python scripts\data_collector_v2.py
python scripts\verify_schema.py
python scripts\run_and_verify.py
python scripts\export_openapi.py
python scripts\debug_import.py
```

## Response contract

Các route đang được bật trong `app/main.py` đã được chuẩn hóa theo format:

```json
{
  "status": "success",
  "code": 200,
  "message": "Success",
  "data": {},
  "meta": null
}
```

Khi lỗi, app trả về:

```json
{
  "status": "error",
  "code": 400,
  "message": "...",
  "detail": {}
}
```

## Ghi chú

- `data/processed/` và `data/cache/` là output sinh ra, đã được ignore khỏi git.
- `storage/` chứa dữ liệu runtime của Docker services, cũng đã được ignore khỏi git.
- Module `users` hiện dùng pattern rõ ràng hơn: `router.py`, `service.py`, `repository.py`, `schemas.py`.
