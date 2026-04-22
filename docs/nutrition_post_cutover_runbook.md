# Nutrition Post-Cutover Runbook

## Trạng thái ổn định sau cutover

Giữ cấu hình như sau trong `.env`:

```env
COLLECTION_NAME="gym_food_hybrid_v1"
COLLECTION_NAME_ACTIVE="gym_food_hybrid_active"
COLLECTION_NAME_NEXT=""
```

Ý nghĩa:

- `COLLECTION_NAME_ACTIVE`: alias ổn định để app luôn query qua một tên cố định
- `COLLECTION_NAME_NEXT`: để trống khi không có migration đang chờ
- `COLLECTION_NAME`: fallback mặc định cho môi trường cũ hoặc local dev

## Kiểm tra alias hiện tại

```powershell
@'
from qdrant_client import QdrantClient
client = QdrantClient(host="localhost", port=6333, timeout=10, check_compatibility=False)
for item in client.get_aliases().aliases:
    if item.alias_name == "gym_food_hybrid_active":
        print({"alias": item.alias_name, "collection": item.collection_name})
'@ | .\myenv\Scripts\python -
```

## Chuẩn bị migration lần tiếp theo

1. Đặt collection đích mới:

```env
COLLECTION_NAME_NEXT="gym_food_hybrid_v4_YYYYMMDD"
```

2. Reindex:

```powershell
python scripts\reindex_qdrant.py
```

3. Test backend bằng collection mới trước cutover:

```powershell
$env:COLLECTION_NAME_ACTIVE="gym_food_hybrid_v4_YYYYMMDD"
python start.py
```

4. Chạy test và judge:

```powershell
python scripts\test_nutrition_cases.py --username "admin" --password "admin" --recommendation-timeout 900 --heartbeat-seconds 10
python scripts\judge_cutover.py --max-response-time-seconds 240 --max-discouraged-items 1
```

5. Nếu đạt, cutover alias:

```powershell
python scripts\cutover_qdrant_alias.py
```

6. Sau khi cutover xong, dọn lại `.env`:

```env
COLLECTION_NAME_NEXT=""
```

## Rollback nhanh

Nếu cần rollback sang collection cũ, tạm set:

```env
COLLECTION_NAME_NEXT="gym_food_hybrid_v2_20260329"
```

Rồi chạy:

```powershell
python scripts\cutover_qdrant_alias.py
```

Sau rollback, tiếp tục để `COLLECTION_NAME_NEXT=""`.
