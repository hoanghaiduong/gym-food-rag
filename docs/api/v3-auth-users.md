# Auth & Users V3 Endpoints

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/api/v3/auth.py`, `app/modules/users/router.py`

## Authentication Endpoints

### POST /api/v3/auth/register

Dang ky tai khoan moi.

**Auth:** Khong can

**Request:**
```json
{
  "username": "johndoe",
  "email": "john@example.com",
  "password": "securepass123",
  "full_name": "John Doe"
}
```

**Validation:**
- `username`: unique, khong duoc trung
- `email`: unique, format email hop le
- `password`: bat buoc

**Logic:**
1. Kiem tra trung username/email
2. Hash password (bcrypt)
3. Insert user vao database
4. Tim role `user` va gan vao `user_roles`
5. Tao access + refresh token
6. Lay danh sach permissions
7. Tra ve tokens + permissions

---

### POST /api/v3/auth/login

Dang nhap bang username hoac email.

**Auth:** Khong can

**Request:**
```json
{"username": "admin", "password": "admin"}
```

**Logic:**
1. Tim user bang username HOAC email
2. Verify password (bcrypt)
3. Kiem tra `is_active`
4. Tao access token (JWT 30 phut)
5. Tao refresh token (random 64 chars, 7 ngay)
6. Luu refresh token vao database
7. Lay permissions cua user
8. Tra ve tokens + permissions

---

### GET /api/v3/auth/me

Lay thong tin user hien tai.

**Auth:** Bearer token

**Response:**
```json
{
  "status": "success",
  "data": {
    "id": 1,
    "username": "admin",
    "email": "admin@gmail.com",
    "full_name": "Super Administrator",
    "phone": "0900000000",
    "target_goal": "lose_weight",
    "goal_normalized_internal": "lose_weight",
    "planning_strategy": "deficit_high_satiety",
    "age": 25,
    "gender": "male",
    "height": 170,
    "weight": 65,
    "activity_level": "active",
    "is_profile_completed": true,
    "permissions": ["user.view", "system.config", "chat.use"]
  }
}
```

---

### POST /api/v3/auth/refresh

Lam moi access token.

**Auth:** Khong can (dung refresh token)

**Request:**
```json
{"refresh_token": "abc123..."}
```

**Logic (Token Rotation):**
1. Tim user co `refresh_token` match
2. Kiem tra `refresh_token_expires_at` chua het han
3. Tao **access token MOI** + **refresh token MOI**
4. Cap nhat refresh token trong database (vo hieu token cu)
5. Tra ve tokens moi

---

### POST /api/v3/auth/logout

Dang xuat (xoa refresh token).

**Auth:** Bearer token

**Logic:** Dat `refresh_token = null` va `refresh_token_expires_at = null` trong database.

---

## User Management Endpoints

### GET /api/v3/users

Lay danh sach users (co phan trang).

**Auth:** `user.view`

**Query params:** `page`, `limit`, `search`

---

### GET /api/v3/users/{user_id}

Lay chi tiet 1 user.

**Auth:** `user.view`

---

### PUT /api/v3/users/{user_id}

Cap nhat thong tin user.

**Auth:** `user.edit`

---

### DELETE /api/v3/users/{user_id}

Deactivate user (set `is_active = false`).

**Auth:** `user.edit`

---

## RBAC Endpoints

### GET /api/v3/rbac/roles

Lay danh sach roles + permissions.

**Auth:** `system.config`

### POST /api/v3/rbac/roles

Tao role moi.

### PUT /api/v3/rbac/roles/{role_id}

Cap nhat role (gan/go permissions).

### POST /api/v3/rbac/users/{user_id}/roles

Gan role cho user.

---

## Lien ket

- [Authentication & RBAC chi tiet](authentication.md)
- [Tong quan API](overview.md)
- [PostgreSQL Schema](../database/schema.md)
