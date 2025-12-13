from sqlalchemy import text as sql_text
from sqlalchemy import insert, select
from app.db.tables import users, roles, permissions, role_permissions, user_roles
from app.core.security import get_password_hash

async def seed_initial_data(engine, log_func=None):
    async def log(msg):
        if log_func: await log_func(msg)

    with engine.begin() as conn:
        # 1. Tạo Permissions (Danh sách quyền hệ thống)
        all_perms = [
            {"slug": "user.view", "name": "Xem người dùng"},
            {"slug": "user.edit", "name": "Sửa người dùng"},
            {"slug": "food.create", "name": "Thêm món ăn"},
            {"slug": "food.delete", "name": "Xóa món ăn"},
            {"slug": "chat.use", "name": "Sử dụng Chatbot"},
            {"slug": "system.config", "name": "Cấu hình hệ thống"},
        ]
        
        for perm in all_perms:
            # Insert nếu chưa có (Postgres Upsert syntax hoặc check exist)
            check = conn.execute(select(permissions).where(permissions.c.slug == perm["slug"])).fetchone()
            if not check:
                conn.execute(insert(permissions).values(**perm))
        
        await log("✅ Permissions seeded.")

        # 2. Tạo Roles (Admin, Editor, User)
        role_map = {
            "Admin": ["user.view", "user.edit", "food.create", "food.delete", "chat.use", "system.config"],
            "Editor": ["food.create", "chat.use"],
            "User": ["chat.use"]
        }

        for role_name, perm_slugs in role_map.items():
            # Tạo Role
            role_id = conn.execute(select(roles.c.id).where(roles.c.name == role_name)).scalar()
            if not role_id:
                role_id = conn.execute(insert(roles).values(name=role_name).returning(roles.c.id)).scalar()
            
            # Gán Permission cho Role
            for slug in perm_slugs:
                perm_id = conn.execute(select(permissions.c.id).where(permissions.c.slug == slug)).scalar()
                # Check exist in link table
                link_check = conn.execute(select(role_permissions).where(
                    (role_permissions.c.role_id == role_id) & 
                    (role_permissions.c.permission_id == perm_id)
                )).fetchone()
                if not link_check:
                    conn.execute(insert(role_permissions).values(role_id=role_id, permission_id=perm_id))

        await log("✅ Roles & Permissions linked.")

        # 3. Tạo Super Admin User
        admin_id = conn.execute(select(users.c.id).where(users.c.username == 'admin')).scalar()
        if not admin_id:
             # ... (Logic tạo user admin cũ của bạn) ...
             # Giả sử tạo xong lấy được admin_id
             pass
        
        # Gán User Admin vào Role "Admin"
        admin_role_id = conn.execute(select(roles.c.id).where(roles.c.name == 'Admin')).scalar()
        if admin_id and admin_role_id:
            check_ur = conn.execute(select(user_roles).where(
                (user_roles.c.user_id == admin_id) & (user_roles.c.role_id == admin_role_id)
            )).fetchone()
            if not check_ur:
                conn.execute(insert(user_roles).values(user_id=admin_id, role_id=admin_role_id))
                
        await log("✅ Admin user assigned to Admin role.")