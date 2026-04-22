# Authentication & RBAC

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/api/v3/auth.py`, `app/core/security.py`, `app/api/deps.py`, `app/db/tables/rbac.py`

## Tong quan

He thong su dung **JWT (JSON Web Token)** cho authentication va **RBAC (Role-Based Access Control)** cho authorization.

```
Client                  API                     Database
  |--- Login ---------> |                          |
  |                      |--- Verify password ----> |
  |                      |<--- User record -------- |
  |<-- Access + Refresh  |                          |
  |                      |--- Store refresh ------> |
  |                      |                          |
  |--- Request -------> |                          |
  |  (Bearer token)      |--- Decode JWT           |
  |                      |--- Get user -----------> |
  |                      |--- Get permissions ----> |
  |                      |--- Check permission     |
  |<-- Response -------- |                          |
```

---

## Token System

### Access Token (JWT)

| Thuoc tinh | Gia tri |
|-----------|---------|
| Algorithm | HS256 |
| TTL | 30 phut (mac dinh) |
| Payload | `{"sub": username, "id": user_id, "type": "access", "exp": ...}` |
| Key | `SECRET_KEY` tu `.env` |

### Refresh Token (Opaque)

| Thuoc tinh | Gia tri |
|-----------|---------|
| Loai | Random string (secrets.token_urlsafe, 64 chars) |
| TTL | 7 ngay (mac dinh) |
| Luu tru | PostgreSQL `users.refresh_token` |
| Rotation | Moi lan refresh -> tao token moi (chong replay attack) |

### Reset Token

| Thuoc tinh | Gia tri |
|-----------|---------|
| Algorithm | HS256 |
| TTL | 15 phut |
| Payload | `{"sub": email, "type": "reset", "exp": ...}` |

---

## API Endpoints

### POST /api/v3/auth/register

Dang ky tai khoan moi. Tu dong gan role `user`.

```bash
curl -X POST http://localhost:8000/api/v3/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "username": "johndoe",
    "email": "john@example.com",
    "password": "securepass",
    "full_name": "John Doe"
  }'
```

### POST /api/v3/auth/login

Dang nhap bang username hoac email. Tra ve access + refresh token.

```bash
curl -X POST http://localhost:8000/api/v3/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username": "admin", "password": "admin"}'
```

Response:
```json
{
  "status": "success",
  "data": {
    "access_token": "eyJhbGciOi...",
    "refresh_token": "abc123...",
    "token_type": "bearer",
    "permissions": ["chat.use", "user.profile", "product.view"]
  }
}
```

### GET /api/v3/auth/me

Lay thong tin user hien tai + permissions. Yeu cau Bearer token.

### POST /api/v3/auth/refresh

Lam moi access token bang refresh token. Su dung **token rotation** — refresh token cu bi vo hieu.

### POST /api/v3/auth/logout

Dang xuat: xoa refresh token trong database.

---

## RBAC (Role-Based Access Control)

### Database Schema

```
users ──(N:M)──> user_roles ──(N:M)──> roles
                                           |
                                      (N:M) role_permissions
                                           |
                                       permissions
```

### Roles Mac dinh (Seed Data)

| Role | Permissions |
|------|-------------|
| **Admin** | `user.view`, `user.edit`, `food.create`, `food.delete`, `chat.use`, `system.config`, `product.view`, `order.view` |
| **Editor** | `food.create`, `chat.use`, `product.view` |
| **user** | `chat.use`, `product.view`, `order.create`, `order.view`, `user.profile` |

### Permissions Co ban

| Slug | Mo ta |
|------|-------|
| `user.view` | Xem danh sach user |
| `user.edit` | Chinh sua thong tin user |
| `user.profile` | Quan ly ho so ca nhan |
| `food.create` | Them mon an moi |
| `food.delete` | Xoa mon an |
| `chat.use` | Su dung chatbot / nutrition recommendation |
| `system.config` | Cau hinh he thong (Admin bypass) |
| `product.view` | Xem san pham |
| `order.create` | Tao don hang |
| `order.view` | Xem lich su don |

### Permission Check Logic

```python
class PermissionChecker:
    def __init__(self, required_permission: str):
        self.required_permission = required_permission

    async def __call__(self, current_user, db):
        perms = get_user_permissions(current_user["id"], db)
        
        # Admin bypass: system.config co the truy cap moi thu
        if self.required_permission not in perms:
            if "system.config" in perms:
                return current_user  # Bypass
            raise HTTPException(403, f"Thieu quyen: '{self.required_permission}'")
        
        return current_user
```

### Setup Wizard (Admin Key)

Endpoint `/api/v2/setup/init` su dung **Admin Key** (khong phai JWT):

```bash
curl -X POST http://localhost:8000/api/v2/setup/init \
  -H "X-Admin-Key: your-admin-secret-key"
```

Admin key duoc kiem tra qua `verify_admin()` dependency.

---

## Security Best Practices

| Thuc hanh | Trang thai | Ghi chu |
|-----------|-----------|---------|
| Password hashing (bcrypt) | Co | `passlib.context.CryptContext` |
| JWT token expiry | Co | 30 phut access, 7 ngay refresh |
| Refresh token rotation | Co | Chong replay attack |
| Token type validation | Co | Khong dung refresh lam access |
| Account deactivation | Co | Check `is_active` flag |
| Rate limiting | Chua | Nen them cho production |
| HTTPS enforcement | Chua | Can reverse proxy |

---

## Lien ket

- [Tong quan API](overview.md)
- [Auth & Users V3](v3-auth-users.md)
- [PostgreSQL Schema](../database/schema.md)
