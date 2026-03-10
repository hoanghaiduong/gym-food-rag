from sqlalchemy import insert, select
from app.db.tables import users, roles, permissions, role_permissions, user_roles
from app.core.security import get_password_hash

async def seed_initial_data(engine, log_func=None):
    """
    Hàm khởi tạo dữ liệu mẫu: Permissions, Roles, Admin User
    """
    async def log(msg):
        if log_func: await log_func(msg)
        else: print(msg)

    # Lưu ý: Nếu engine là AsyncEngine, bạn cần dùng 'async with' và 'await conn.execute'
    # Nếu engine là Sync (thường dùng trong script init), code dưới đây chạy chuẩn.
    # Dưới đây viết theo style Sync bên trong begin() để đảm bảo atomic.
    
    with engine.begin() as conn:
        # ==========================================
        # 1. TẠO PERMISSIONS (QUYỀN HẠN)
        # ==========================================
        all_perms = [
            {"slug": "user.view", "name": "Xem người dùng", "description": "Quyền xem danh sách user"},
            {"slug": "user.edit", "name": "Sửa người dùng", "description": "Quyền chỉnh sửa thông tin user"},
            {"slug": "food.create", "name": "Thêm món ăn", "description": "Quyền tạo món ăn mới"},
            {"slug": "food.delete", "name": "Xóa món ăn", "description": "Quyền xóa món ăn"},
            {"slug": "chat.use", "name": "Sử dụng Chatbot", "description": "Quyền chat với AI"},
            {"slug": "system.config", "name": "Cấu hình hệ thống", "description": "Quyền quản trị system"},
            # Thêm các quyền cần thiết cho luồng order/product nếu thiếu
            {"slug": "product.view", "name": "Xem sản phẩm", "description": "Xem sản phẩm"},
            {"slug": "order.create", "name": "Tạo đơn hàng", "description": "Mua hàng"},
            {"slug": "order.view", "name": "Xem đơn hàng", "description": "Xem lịch sử đơn"},
            {"slug": "user.profile", "name": "Quản lý hồ sơ", "description": "Sửa hồ sơ cá nhân"},
        ]
        
        for perm in all_perms:
            # Kiểm tra tồn tại
            check = conn.execute(select(permissions).where(permissions.c.slug == perm["slug"])).fetchone()
            if not check:
                conn.execute(insert(permissions).values(
                    slug=perm["slug"],
                    name=perm["name"],
                    description=perm.get("description", "")
                ))
        
        await log("✅ Permissions seeded.")

        # ==========================================
        # 2. TẠO ROLES (VAI TRÒ)
        # ==========================================
        # Định nghĩa Role và các quyền đi kèm
        role_map = {
            "Admin": [
                "user.view", "user.edit", "food.create", "food.delete", 
                "chat.use", "system.config", "product.view", "order.view"
            ],
            "Editor": ["food.create", "chat.use", "product.view"],
            # Role 'user' (viết thường để khớp với logic đăng ký ở auth.py)
            "user": ["chat.use", "product.view", "order.create", "order.view", "user.profile"] 
        }

        for role_name, perm_slugs in role_map.items():
            # 2.1 Tạo Role nếu chưa có
            role_id = conn.execute(select(roles.c.id).where(roles.c.name == role_name)).scalar()
            if not role_id:
                role_id = conn.execute(
                    insert(roles).values(name=role_name, description=f"Vai trò {role_name}")
                    .returning(roles.c.id)
                ).scalar()
            
            # 2.2 Gán Permission cho Role
            for slug in perm_slugs:
                # Lấy ID của quyền
                perm_id = conn.execute(select(permissions.c.id).where(permissions.c.slug == slug)).scalar()
                
                if perm_id:
                    # Check xem đã link chưa
                    link_check = conn.execute(select(role_permissions).where(
                        (role_permissions.c.role_id == role_id) & 
                        (role_permissions.c.permission_id == perm_id)
                    )).fetchone()
                    
                    if not link_check:
                        conn.execute(insert(role_permissions).values(role_id=role_id, permission_id=perm_id))

        await log("✅ Roles & Permissions linked.")

        # ==========================================
        # 3. TẠO SUPER ADMIN USER (FULL LOGIC)
        # ==========================================
        admin_username = "admin"
        admin_email = "admin@gmail.com"
        admin_raw_pass = "admin"  # Mật khẩu mặc định

        # Kiểm tra xem user admin đã tồn tại chưa
        admin_id = conn.execute(select(users.c.id).where(users.c.username == admin_username)).scalar()
        
        if not admin_id:
            # Hash mật khẩu
            hashed_pwd = get_password_hash(admin_raw_pass)
            
            # Thực hiện Insert đầy đủ các trường
            stmt = insert(users).values(
                username=admin_username,
                email=admin_email,
                password_hash=hashed_pwd,
                full_name="Super Administrator",
                is_active=True,
                # Không insert cột 'role' vì đã bỏ, dùng bảng user_roles
            ).returning(users.c.id)
            
            admin_id = conn.execute(stmt).scalar()
            await log(f"✅ Admin user created (User: {admin_username} / Pass: {admin_raw_pass})")
        else:
            await log("ℹ️ Admin user already exists.")

        # ==========================================
        # 4. GÁN USER ADMIN VÀO ROLE "Admin"
        # ==========================================
        if admin_id:
            # Lấy ID của role Admin
            admin_role_id = conn.execute(select(roles.c.id).where(roles.c.name == 'Admin')).scalar()
            
            if admin_role_id:
                # Kiểm tra xem đã gán chưa
                check_ur = conn.execute(select(user_roles).where(
                    (user_roles.c.user_id == admin_id) & (user_roles.c.role_id == admin_role_id)
                )).fetchone()
                
                if not check_ur:
                    conn.execute(insert(user_roles).values(user_id=admin_id, role_id=admin_role_id))
                    await log("✅ Admin user assigned to 'Admin' role.")