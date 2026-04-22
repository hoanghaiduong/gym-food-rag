# PostgreSQL Schema

> Cap nhat lan cuoi: 2026-04-06  
> Source code: `app/db/tables/users.py`, `app/db/tables/rbac.py`, `app/db/tables/chat.py`, `app/db/migrations.py`, `app/db/seeds.py`

## Tong quan

He thong su dung **PostgreSQL 15** voi **SQLAlchemy Core** (Table-level, khong dung ORM models). Migration su dung he thong custom (`check_and_add_columns`) thay vi Alembic.

---

## Entity Relationship Diagram

```
+------------------+
|      users       |
+------------------+
| id (PK)          |
| username (UQ)    |
| email (UQ)       |
| password_hash    |
| full_name        |
| is_active        |
| age              |
| gender           |
| weight           |
| height           |
| activity_level   |
| dietary_preference|
| allergies        |
| target_goal      |
| refresh_token    |
| refresh_token_   |
|   expires_at     |
| created_at       |
+--------+---------+
         |
    +----+----+                +------------------+
    |         |                |   permissions    |
    v         v                +------------------+
+----------+ +-------------+  | id (PK)          |
|user_roles| |chat_sessions|  | slug (UQ)        |
+----------+ +-------------+  | name             |
|user_id(FK)| |id (PK,UUID) |  | description      |
|role_id(FK)| |user_id (FK) |  +--------+---------+
+----+------+ |title        |           |
     |        |created_at   |      +----+-----+
     v        |updated_at   |      |          |
+----------+  +------+------+   +--+--+  +---+---+
|  roles   |         |          |role_|  | ... |
+----------+         v          |perms|
|id (PK)   |  +-------------+  +-----+
|name (UQ) |  |chat_history  |  |role_id(FK)
|description|  +-------------+  |permission_id(FK)
+----------+  |id (PK)       |
              |user_id (FK)  |
              |session_id(FK)|
              |question      |
              |answer        |
              |sources       |
              |created_at    |
              +--------------+
```

---

## Chi tiet Cac Table

### Table: `users`

| Column | Type | Constraints | Mo ta |
|--------|------|-------------|-------|
| `id` | Integer | PK, auto-increment | ID nguoi dung |
| `username` | String(50) | UNIQUE, NOT NULL | Ten dang nhap |
| `email` | String(100) | UNIQUE, NOT NULL | Dia chi email |
| `password_hash` | String(255) | NOT NULL | Mat khau da hash (bcrypt) |
| `full_name` | String(100) | nullable | Ho va ten |
| `is_active` | Boolean | default=True | Trang thai tai khoan |
| `age` | Integer | nullable | Tuoi |
| `gender` | String(10) | nullable | Gioi tinh (`male`/`female`) |
| `weight` | Float | nullable | Can nang (kg) |
| `height` | Float | nullable | Chieu cao (cm) |
| `activity_level` | String(20) | nullable | Muc van dong |
| `dietary_preference` | String(50) | nullable | Che do an (omnivore/vegetarian...) |
| `allergies` | String(255) | nullable | Di ung (comma-separated) |
| `target_goal` | String(50) | nullable | Muc tieu (lose_weight/gain_muscle...) |
| `refresh_token` | String(500) | nullable | JWT refresh token |
| `refresh_token_expires_at` | DateTime | nullable | Het han refresh token |
| `created_at` | DateTime | server_default=now() | Ngay tao |

### Table: `permissions`

| Column | Type | Constraints | Mo ta |
|--------|------|-------------|-------|
| `id` | Integer | PK | ID permission |
| `slug` | String(100) | UNIQUE, NOT NULL | Ma quyen (VD: `chat.use`) |
| `name` | String(255) | — | Ten hien thi |
| `description` | Text | — | Mo ta quyen |

### Table: `roles`

| Column | Type | Constraints | Mo ta |
|--------|------|-------------|-------|
| `id` | Integer | PK | ID role |
| `name` | String(50) | UNIQUE, NOT NULL | Ten role (Admin/Editor/user) |
| `description` | Text | — | Mo ta role |

### Table: `role_permissions` (N:M)

| Column | Type | Constraints |
|--------|------|-------------|
| `role_id` | Integer | PK, FK -> roles.id (CASCADE) |
| `permission_id` | Integer | PK, FK -> permissions.id (CASCADE) |

### Table: `user_roles` (N:M)

| Column | Type | Constraints |
|--------|------|-------------|
| `user_id` | Integer | PK, FK -> users.id (CASCADE) |
| `role_id` | Integer | PK, FK -> roles.id (CASCADE) |

### Table: `chat_sessions`

| Column | Type | Constraints | Mo ta |
|--------|------|-------------|-------|
| `id` | String(36) | PK | UUID cua session |
| `user_id` | Integer | FK -> users.id, NOT NULL | Owner |
| `title` | String(255) | — | Tieu de hoi thoai |
| `created_at` | DateTime | server_default=now() | — |
| `updated_at` | DateTime | onupdate=now() | — |

### Table: `chat_history`

| Column | Type | Constraints | Mo ta |
|--------|------|-------------|-------|
| `id` | Integer | PK | — |
| `user_id` | Integer | FK -> users.id, NOT NULL | Owner |
| `session_id` | String(36) | FK -> chat_sessions.id, NOT NULL | Thuoc session nao |
| `question` | Text | NOT NULL | Cau hoi cua user |
| `answer` | Text | NOT NULL | Cau tra loi cua AI |
| `sources` | Text | nullable | JSON nguon tham khao |
| `created_at` | DateTime | server_default=now() | — |

---

## Migration System

He thong su dung **custom migration** thay vi Alembic:

```python
# app/db/migrations.py
def check_and_add_columns(engine):
    # Doc metadata hien tai tu database
    # So sanh voi SQLAlchemy table definitions
    # Them cot moi bang ALTER TABLE
```

Migration duoc chay tu dong khi goi `/api/v2/setup/init`.

---

## Seed Data

File `app/db/seeds.py` tao du lieu khoi tao:

1. **10 Permissions:** user.view, user.edit, food.create, food.delete, chat.use, system.config, product.view, order.create, order.view, user.profile
2. **3 Roles:** Admin (8 perms), Editor (3 perms), user (5 perms)
3. **1 Admin user:** username=admin, password=admin, role=Admin

---

## Lien ket

- [Authentication & RBAC](../api/authentication.md)
- [Qdrant Collections](qdrant-collections.md)
- [Redis Keys](redis-keys.md)
