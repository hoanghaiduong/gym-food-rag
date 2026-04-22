# V2 Legacy Endpoints

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/api/v2/`

## Trang thai

Cac endpoint V2 da duoc thay the boi V3. Chi con 2 router duoc mount:

| Prefix | Module | Trang thai |
|--------|--------|-----------|
| `/api/v2/setup` | `setup.py` | **Active** — Khoi tao he thong |
| `/api/v2/system` | `system.py` | **Active** — Health check, log streaming |
| `/api/v2/chat` | `chat_v2.py` | **Removed** — Thay bang V3 |
| `/api/v2/auth` | `auth_v2.py` | **Removed** — Thay bang V3 auth |
| `/api/v2/admin` | `admin.py` | **Removed** — Thay bang V3 RBAC |
| `/api/v2/users` | `users_v2.py` | **Removed** — Thay bang V3 users |
| `/api/v2/history` | `history_v2.py` | **Removed** — Chua co thay the |

---

## Setup Wizard (Con active)

### POST /api/v2/setup/init

Khoi tao database tu scratch: tao tables, chay migrations, seed data.

**Auth:** `X-Admin-Key` header

```bash
curl -X POST http://localhost:8000/api/v2/setup/init \
  -H "X-Admin-Key: your-admin-secret-key"
```

**Logic:**
1. Tao tat ca tables tu SQLAlchemy metadata (`metadata.create_all`)
2. Chay `check_and_add_columns()` — them cot moi neu thieu
3. Chay `seed_initial_data()` — tao permissions, roles, admin user
4. Tra ve ket qua setup qua WebSocket stream

### GET /api/v2/setup/ws

WebSocket endpoint de nhan tien trinh setup real-time.

---

## System Control (Con active)

### GET /api/v2/system/health

Kiem tra ket noi toi tat ca services.

### GET /api/v2/system/logs/ws

WebSocket stream log file real-time (dung `watch_log_file()` trong lifespan).

---

## Lien ket

- [Tong quan API](overview.md)
- [Installation (Setup)](../getting-started/installation.md)
