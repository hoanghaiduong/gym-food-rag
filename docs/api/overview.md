# Tong quan API

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/api/router.py`, `app/core/response.py`, `app/core/exceptions.py`

## API Versioning

He thong su dung **URL-based versioning**: `/api/v2/...` va `/api/v3/...`

### Cac Router Dang Active

| Prefix | Tags | Router | Mo ta |
|--------|------|--------|-------|
| `/api/v2/setup` | Setup Wizard | `app.api.v2.setup` | Khoi tao database, seed data |
| `/api/v2/system` | System Control | `app.api.v2.system` | Health check, log streaming |
| `/api/v3/auth` | Authentication V3 | `app.api.v3.auth` | Dang ky, dang nhap, JWT |
| `/api/v3/rbac` | V3 Access Control | `app.api.v3.rbac` | Quan ly roles & permissions |
| `/api/v3/users` | V3 User Management | `app.modules.users.router` | CRUD users |
| `/api/v3/nutrition` | Nutrition Decision Support | `app.api.v3.nutrition` | Goi y dinh duong (core) |

### Router Legacy (Da bo khoi router chinh)

| Prefix | Mo ta | Ly do loai bo |
|--------|-------|---------------|
| `/api/v1/chat` | Chat co ban voi Gemini | Thay bang V3 agent |
| `/api/v2/chat` | Chat voi Ollama | Thay bang V3 nutrition |
| `/api/v2/auth` | Auth V2 | Thay bang V3 auth |
| `/api/v2/admin` | Admin endpoints | Thay bang V3 RBAC |

---

## Response Format

Tat ca endpoint deu tra ve dinh dang **BaseResponse** thong nhat:

### Success Response

```json
{
  "status": "success",
  "code": 200,
  "message": "Success",
  "data": { ... },
  "meta": null
}
```

### Error Response

```json
{
  "status": "error",
  "code": 400,
  "message": "Mo ta loi",
  "detail": { ... }
}
```

### Paginated Response

```json
{
  "status": "success",
  "code": 200,
  "message": "Success",
  "data": [ ... ],
  "meta": {
    "page": 1,
    "limit": 10,
    "total": 100,
    "total_pages": 10
  }
}
```

### Response Helpers (app/core/response.py)

| Function | Code | Muc dich |
|----------|------|----------|
| `success_response()` | 200 | Thanh cong chung |
| `created_response()` | 201 | Tao moi thanh cong |
| `paginated_response()` | 200 | Tra ve co phan trang |
| `error_response()` | 400+ | Tra ve loi |

---

## Error Handling

He thong su dung **Global Exception Handlers** (`app/core/exceptions.py`):

| Exception | HTTP Code | Message |
|-----------|-----------|---------|
| `HTTPException` | Tuy loi | Detail tu endpoint |
| `RequestValidationError` | 422 | "Validation Error" + chi tiet |
| `OperationalError` (DB) | 503 | "Database connection failed" |
| `SQLAlchemyError` | 500 | "Database query error" |
| `Exception` (catchall) | 500 | "Internal Server Error" |

---

## Authentication Flow

Tat ca endpoint V3 yeu cau **JWT Bearer Token** (tru `/auth/register` va `/auth/login`):

```
Authorization: Bearer <access_token>
```

### Permission System

Su dung `PermissionChecker` class:

```python
# Su dung trong endpoint
@router.get("/profile")
async def get_profile(
    current_user = Depends(PermissionChecker("user.profile"))
):
    ...
```

Logic:
1. Verify JWT token
2. Lay user tu database
3. Kiem tra `is_active`
4. Lay permissions tu `user_roles -> role_permissions -> permissions`
5. Kiem tra permission can thiet
6. Admin (`system.config`) luon bypass

> Chi tiet: [Authentication & RBAC](authentication.md)

---

## CORS

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # Tat ca origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

> **Luu y:** Production nen gioi han `allow_origins`.

---

## Static Files

```python
app.mount("/assets", StaticFiles(directory=STORAGE_DIR), name="assets")
```

Phuc vu hinh anh thuc pham tai: `http://localhost:8000/assets/nutrition_images/...`

---

## Swagger UI

Truy cap: **http://localhost:8000/docs**  
ReDoc: **http://localhost:8000/redoc**

---

## Lien ket

- [Authentication chi tiet](authentication.md)
- [Nutrition V3 Endpoints](v3-nutrition.md)
- [Chat V3 Endpoints](v3-chat.md)
- [Kien truc tong quan](../architecture/overview.md)
